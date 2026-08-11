# AIMETA P=章节outbox派发_事实到typed_job映射|R=事件校验_幂等run与job创建_backlog修复|NR=不执行projection或拥有claim重试|E=handle_chapter_outbox_dispatch_repair_chapter_outbox_backlog|X=worker|A=dispatcher|D=sqlalchemy,job_service|S=db|RD=./README.ai
"""Dispatch immutable Chapter outbox facts into the durable job runtime."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from sqlalchemy import exists, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.chapter_projection import (
    ChapterOutboxEvent,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
)
from ..models.novel import Chapter, NovelProject
from ..schemas.job import (
    ChapterFinalizeOutboxPayload,
    ChapterOutboxDispatchJobPayload,
    ChapterProjectionJobPayload,
    ChapterTombstoneJobPayload,
)
from .chapter_projection_contract import (
    FINALIZE_EVENT_TYPE,
    OUTBOX_EVENT_VERSION,
    SUPPORTED_EVENT_TYPES,
    payload_fingerprint,
    validate_finalize_outbox_event,
)
from .job_service import JobService
from .job_worker import JobOutcome, PermanentJobError

DISPATCH_JOB_TYPE = "chapter_outbox_dispatch"
DISPATCH_PAYLOAD_VERSION = 1


def _dispatcher_job_payload(event: ChapterOutboxEvent) -> dict[str, Any]:
    return ChapterOutboxDispatchJobPayload(
        project_id=event.project_id,
        outbox_event_id=event.id,
        event_type=event.event_type,
        event_version=event.event_version,
        payload_fingerprint=event.payload_fingerprint,
    ).model_dump()


def _dispatch_key(event: ChapterOutboxEvent) -> str:
    raw_payload = event.payload if isinstance(event.payload, dict) else {}
    value = raw_payload.get("dispatch_idempotency_key")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return f"chapter-outbox:{event.id}"


async def _enqueue_dispatcher(
    session: AsyncSession,
    *,
    event: ChapterOutboxEvent,
    user_id: int,
) -> BackgroundTask:
    return await JobService(session).enqueue_job_in_transaction(
        user_id=user_id,
        project_id=event.project_id,
        job_type=DISPATCH_JOB_TYPE,
        title=f"派发章节事件 {event.event_type}",
        payload=_dispatcher_job_payload(event),
        payload_version=DISPATCH_PAYLOAD_VERSION,
        idempotency_key=_dispatch_key(event),
        stream_type=event.workflow_stream_type,
        stream_id=event.workflow_stream_id,
    )


class ChapterOutboxDispatcher:
    """Validate one outbox fact and materialize its deterministic child jobs."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def dispatch(
        self,
        *,
        command: ChapterOutboxDispatchJobPayload,
        user_id: int,
    ) -> dict[str, Any]:
        candidate = (
            await self.session.execute(
                select(
                    ChapterOutboxEvent.id,
                    ChapterOutboxEvent.event_type,
                    ChapterOutboxEvent.chapter_id,
                    ChapterOutboxEvent.payload,
                )
                .join(NovelProject, NovelProject.id == ChapterOutboxEvent.project_id)
                .where(
                    ChapterOutboxEvent.id == command.outbox_event_id,
                    ChapterOutboxEvent.project_id == command.project_id,
                    ChapterOutboxEvent.event_type == command.event_type,
                    ChapterOutboxEvent.event_version == command.event_version,
                    NovelProject.user_id == user_id,
                )
            )
        ).first()
        if candidate is None:
            raise PermanentJobError(
                "chapter_outbox_event_missing",
                "章节 outbox 事件不存在或归属不匹配",
            )

        chapter = None
        if candidate.event_type == FINALIZE_EVENT_TYPE:
            raw_payload = candidate.payload if isinstance(candidate.payload, dict) else {}
            chapter_id = candidate.chapter_id or raw_payload.get("chapter_id")
            if isinstance(chapter_id, int):
                chapter = (
                    (
                        await self.session.execute(
                            select(Chapter)
                            .where(
                                Chapter.id == chapter_id,
                                Chapter.project_id == command.project_id,
                            )
                            .with_for_update()
                        )
                    )
                    .scalars()
                    .first()
                )

        event = (
            (
                await self.session.execute(
                    select(ChapterOutboxEvent)
                    .join(NovelProject, NovelProject.id == ChapterOutboxEvent.project_id)
                    .where(
                        ChapterOutboxEvent.id == command.outbox_event_id,
                        ChapterOutboxEvent.project_id == command.project_id,
                        ChapterOutboxEvent.event_type == command.event_type,
                        ChapterOutboxEvent.event_version == command.event_version,
                        NovelProject.user_id == user_id,
                    )
                    .with_for_update(of=ChapterOutboxEvent)
                )
            )
            .scalars()
            .first()
        )
        if event is None:
            raise PermanentJobError(
                "chapter_outbox_event_missing",
                "章节 outbox 事件不存在或归属不匹配",
            )
        if event.payload_fingerprint != command.payload_fingerprint:
            raise PermanentJobError(
                "chapter_outbox_payload_mismatch",
                "章节 outbox 事件指纹不匹配",
            )

        if event.event_type == FINALIZE_EVENT_TYPE:
            payload, validation_error = validate_finalize_outbox_event(event)
            if validation_error == "payload_mismatch":
                raise PermanentJobError(
                    "chapter_outbox_payload_mismatch",
                    "章节 outbox 事件指纹不匹配",
                )
            if validation_error == "invalid_payload":
                raise PermanentJobError(
                    "invalid_chapter_finalize_outbox",
                    "章节定稿 outbox 事件无效",
                )
            if validation_error == "event_contract_mismatch":
                raise PermanentJobError(
                    "chapter_finalize_outbox_contract_mismatch",
                    "章节定稿 outbox 事件版本合同不匹配",
                )
            if validation_error is not None or payload is None:
                raise PermanentJobError(
                    "chapter_finalize_outbox_identity_mismatch",
                    "章节定稿 outbox identity 不匹配",
                )
            return await self._dispatch_finalize(
                event,
                payload=payload,
                chapter=chapter,
                user_id=user_id,
            )
        raw_payload = event.payload if isinstance(event.payload, dict) else None
        if raw_payload is None or payload_fingerprint(raw_payload) != event.payload_fingerprint:
            raise PermanentJobError(
                "chapter_outbox_payload_mismatch",
                "章节 outbox 事件指纹不匹配",
            )
        return await self._dispatch_tombstone(event, user_id=user_id)

    async def _dispatch_finalize(
        self,
        event: ChapterOutboxEvent,
        *,
        payload: ChapterFinalizeOutboxPayload,
        chapter: Chapter | None,
        user_id: int,
    ) -> dict[str, Any]:
        if chapter is None or (
            chapter.id != payload.chapter_id
            or chapter.project_id != payload.project_id
            or chapter.chapter_number != payload.chapter_number
            or chapter.current_revision != payload.revision
            or chapter.source_hash != payload.source_hash
            or chapter.projection_generation != payload.source_generation
            or chapter.tombstone_revision >= payload.revision
        ):
            return {
                "status": "stale",
                "event_id": event.id,
                "event_type": event.event_type,
                "root_job_id": None,
                "job_ids": [],
                "run_ids": [],
            }
        revision = (
            (
                await self.session.execute(
                    select(ChapterRevision)
                    .where(
                        ChapterRevision.id == payload.chapter_revision_id,
                        ChapterRevision.chapter_id == chapter.id,
                        ChapterRevision.project_id == chapter.project_id,
                        ChapterRevision.chapter_number == chapter.chapter_number,
                        ChapterRevision.revision == payload.revision,
                        ChapterRevision.source_hash == payload.source_hash,
                        ChapterRevision.source_generation == payload.source_generation,
                        ChapterRevision.lifecycle == "finalizing",
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        rollout = (
            (
                await self.session.execute(
                    select(ChapterProjectionRollout)
                    .where(
                        ChapterProjectionRollout.chapter_id == chapter.id,
                        ChapterProjectionRollout.project_id == chapter.project_id,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if revision is None or rollout is None:
            return {
                "status": "stale",
                "event_id": event.id,
                "event_type": event.event_type,
                "root_job_id": None,
                "job_ids": [],
                "run_ids": [],
            }
        if (
            rollout.owner != payload.rollout_owner
            or rollout.generation != payload.rollout_generation
            or rollout.fencing_token != payload.rollout_fencing_token
        ):
            return {
                "status": "stale",
                "event_id": event.id,
                "event_type": event.event_type,
                "root_job_id": None,
                "job_ids": [],
                "run_ids": [],
            }

        jobs: list[BackgroundTask] = []
        runs: list[ChapterProjectionRun] = []
        legacy_job = None
        if payload.execution_mode in {"legacy", "shadow"}:
            legacy_payload = {
                "project_id": payload.project_id,
                "chapter_number": payload.chapter_number,
                "selected_version_id": payload.selected_version_id,
                "content_hash": payload.content_hash,
                "skip_vector_update": payload.skip_vector_update,
                "chapter_id": payload.chapter_id,
                "chapter_revision_id": payload.chapter_revision_id,
                "revision": payload.revision,
                "source_hash": payload.source_hash,
                "source_generation": payload.source_generation,
                "execution_mode": payload.execution_mode,
                "rollout_generation": payload.rollout_generation,
                "rollout_fencing_token": payload.rollout_fencing_token,
                "workflow_stream_id": payload.workflow_stream_id,
                "outbox_event_id": event.id,
            }
            legacy_job = await JobService(self.session).enqueue_job_in_transaction(
                user_id=user_id,
                project_id=payload.project_id,
                job_type="chapter_finalize",
                title=f"定稿第 {payload.chapter_number} 章",
                payload=legacy_payload,
                payload_version=1,
                idempotency_key=f"chapter-outbox:{event.id}:legacy",
                stream_type="workflow",
                stream_id=payload.workflow_stream_id,
            )
            revision.legacy_job_id = legacy_job.id
            jobs.append(legacy_job)

        projection_job = None
        if payload.execution_mode in {"active", "shadow"}:
            if payload.summary_run_id is None or payload.summary_artifact_generation is None:
                raise PermanentJobError(
                    "chapter_summary_identity_missing",
                    "章节摘要投影 identity 缺失",
                )
            projection_payload = ChapterProjectionJobPayload(
                project_id=payload.project_id,
                chapter_id=payload.chapter_id,
                chapter_number=payload.chapter_number,
                chapter_revision_id=payload.chapter_revision_id,
                revision=payload.revision,
                source_hash=payload.source_hash,
                source_generation=payload.source_generation,
                projection_run_id=payload.summary_run_id,
                artifact_generation=payload.summary_artifact_generation,
                workflow_stream_id=payload.workflow_stream_id,
                outbox_event_id=event.id,
                rollout_owner=payload.rollout_owner,
                rollout_generation=payload.rollout_generation,
                rollout_fencing_token=payload.rollout_fencing_token,
                execution_mode=("shadow" if payload.execution_mode == "shadow" else "active"),
                legacy_job_id=legacy_job.id if legacy_job is not None else None,
                selected_version_id=payload.selected_version_id,
                content_hash=payload.content_hash,
                skip_vector_update=payload.skip_vector_update,
            ).model_dump()
            projection_job = await JobService(self.session).enqueue_job_in_transaction(
                user_id=user_id,
                project_id=payload.project_id,
                job_type="chapter_finalize",
                title=(
                    f"影子投影第 {payload.chapter_number} 章"
                    if payload.execution_mode == "shadow"
                    else f"定稿第 {payload.chapter_number} 章"
                ),
                payload=projection_payload,
                payload_version=2,
                idempotency_key=f"chapter-outbox:{event.id}:summary",
                stream_type="workflow",
                stream_id=payload.workflow_stream_id,
            )
            summary_run = await self.session.get(
                ChapterProjectionRun,
                payload.summary_run_id,
                with_for_update=True,
            )
            if summary_run is None:
                summary_run = ChapterProjectionRun(
                    id=payload.summary_run_id,
                    chapter_revision_id=revision.id,
                    chapter_id=chapter.id,
                    project_id=chapter.project_id,
                    revision=revision.revision,
                    projection_name="summary",
                    source_hash=revision.source_hash,
                    job_id=projection_job.id,
                    artifact_generation=payload.summary_artifact_generation,
                    status="queued",
                    required=True,
                    is_active=False,
                    checkpoint={
                        "outbox_event_id": event.id,
                        "execution_mode": payload.execution_mode,
                        "legacy_job_id": legacy_job.id if legacy_job is not None else None,
                    },
                )
                self.session.add(summary_run)
            elif (
                summary_run.chapter_revision_id != revision.id
                or summary_run.projection_name != "summary"
                or summary_run.artifact_generation != payload.summary_artifact_generation
                or summary_run.job_id not in (None, projection_job.id)
            ):
                raise PermanentJobError(
                    "chapter_summary_identity_conflict",
                    "章节摘要投影 identity 冲突",
                )
            else:
                summary_run.job_id = projection_job.id
            jobs.append(projection_job)
            runs.append(summary_run)

        root_job = legacy_job or projection_job
        if root_job is None:
            raise PermanentJobError(
                "chapter_finalize_owner_missing",
                "章节定稿事件没有可执行 owner",
            )
        return {
            "status": "dispatched",
            "event_id": event.id,
            "event_type": event.event_type,
            "root_job_id": root_job.id,
            "job_ids": [job.id for job in jobs],
            "run_ids": [run.id for run in runs],
        }

    async def _dispatch_tombstone(
        self,
        event: ChapterOutboxEvent,
        *,
        user_id: int,
    ) -> dict[str, Any]:
        try:
            payload = ChapterTombstoneJobPayload.model_validate(
                {**(event.payload or {}), "outbox_event_id": event.id}
            )
        except ValidationError as exc:
            raise PermanentJobError(
                "invalid_chapter_tombstone_outbox",
                "章节 tombstone outbox 事件无效",
            ) from exc
        if (
            event.aggregate_type != "chapter"
            or event.aggregate_id != str(payload.chapter_id)
            or event.chapter_id not in (None, payload.chapter_id)
            or event.project_id != payload.project_id
            or event.revision != payload.tombstone_revision
            or event.event_type != payload.event_type
            or event.workflow_stream_type != "workflow"
            or event.workflow_stream_id != payload.workflow_stream_id
        ):
            raise PermanentJobError(
                "chapter_tombstone_outbox_identity_mismatch",
                "章节 tombstone outbox identity 不匹配",
            )
        revision = await self.session.get(
            ChapterRevision,
            payload.chapter_revision_id,
            with_for_update=True,
        )
        if (
            revision is None
            or revision.chapter_id not in (None, payload.chapter_id)
            or revision.project_id != payload.project_id
            or revision.chapter_number != payload.chapter_number
            or revision.revision != payload.tombstone_revision
            or revision.source_hash != payload.source_hash
            or revision.source_generation != payload.source_generation
            or revision.lifecycle != "tombstone"
        ):
            raise PermanentJobError(
                "chapter_tombstone_revision_mismatch",
                "章节 tombstone revision 不匹配",
            )

        job = await JobService(self.session).enqueue_job_in_transaction(
            user_id=user_id,
            project_id=payload.project_id,
            job_type="chapter_projection_tombstone",
            title=f"清理第 {payload.chapter_number} 章旧投影",
            payload=payload.model_dump(),
            payload_version=1,
            idempotency_key=f"chapter-outbox:{event.id}:tombstone",
            stream_type="workflow",
            stream_id=payload.workflow_stream_id,
        )
        run = await self.session.get(
            ChapterProjectionRun,
            payload.projection_run_id,
            with_for_update=True,
        )
        if run is None:
            run = ChapterProjectionRun(
                id=payload.projection_run_id,
                chapter_revision_id=revision.id,
                chapter_id=revision.chapter_id,
                project_id=revision.project_id,
                revision=revision.revision,
                projection_name="tombstone",
                source_hash=revision.source_hash,
                job_id=job.id,
                artifact_generation=payload.artifact_generation,
                status="queued",
                required=True,
                is_active=False,
                checkpoint={
                    "outbox_event_id": event.id,
                    "target_revision": payload.target_revision,
                    "target_artifact_generations": payload.target_artifact_generations,
                },
            )
            self.session.add(run)
        elif (
            run.chapter_revision_id != revision.id
            or run.projection_name != "tombstone"
            or run.artifact_generation != payload.artifact_generation
            or run.job_id not in (None, job.id)
        ):
            raise PermanentJobError(
                "chapter_tombstone_identity_conflict",
                "章节 tombstone projection identity 冲突",
            )
        else:
            run.job_id = job.id
        return {
            "status": "dispatched",
            "event_id": event.id,
            "event_type": event.event_type,
            "root_job_id": job.id,
            "job_ids": [job.id],
            "run_ids": [run.id],
        }


async def handle_chapter_outbox_dispatch(context) -> JobOutcome:
    """Materialize typed child jobs inside the dispatcher's fenced success commit."""

    try:
        command = ChapterOutboxDispatchJobPayload.model_validate(context.lease.payload)
    except ValidationError as exc:
        raise PermanentJobError(
            "invalid_chapter_outbox_dispatch_payload",
            "章节 outbox dispatcher 参数无效",
        ) from exc
    if context.lease.project_id != command.project_id:
        raise PermanentJobError(
            "chapter_outbox_dispatch_project_mismatch",
            "章节 outbox dispatcher 项目不匹配",
        )

    result: dict[str, Any] = {
        "status": "dispatching",
        "event_id": command.outbox_event_id,
        "event_type": command.event_type,
        "root_job_id": None,
        "job_ids": [],
        "run_ids": [],
    }

    async def write_outcome(session: AsyncSession) -> None:
        dispatched = await ChapterOutboxDispatcher(session).dispatch(
            command=command,
            user_id=context.lease.user_id,
        )
        result.update(dispatched)

    return JobOutcome(result=result, outcome_writer=write_outcome)


async def repair_chapter_outbox_backlog(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> int:
    """Recreate missing dispatcher jobs for v2 events without mutating facts."""

    if limit < 1 or limit > 1000:
        raise ValueError("outbox backlog repair limit 必须为 1 到 1000")
    dispatcher_key = func.coalesce(
        ChapterOutboxEvent.payload["dispatch_idempotency_key"].as_string(),
        literal("chapter-outbox:") + ChapterOutboxEvent.id,
    )
    dispatcher_exists = exists(
        select(BackgroundTask.id).where(
            BackgroundTask.user_id == NovelProject.user_id,
            BackgroundTask.task_type == DISPATCH_JOB_TYPE,
            BackgroundTask.idempotency_key == dispatcher_key,
        )
    )
    rows = (
        await session.execute(
            select(ChapterOutboxEvent, NovelProject.user_id)
            .join(NovelProject, NovelProject.id == ChapterOutboxEvent.project_id)
            .where(
                ChapterOutboxEvent.event_type.in_(SUPPORTED_EVENT_TYPES),
                ChapterOutboxEvent.event_version == OUTBOX_EVENT_VERSION,
                ~dispatcher_exists,
            )
            .order_by(ChapterOutboxEvent.created_at, ChapterOutboxEvent.id)
            .limit(limit)
            .with_for_update(
                of=ChapterOutboxEvent,
                skip_locked=True,
            )
        )
    ).all()
    for event, user_id in rows:
        await _enqueue_dispatcher(session, event=event, user_id=int(user_id))
    return len(rows)


__all__ = [
    "DISPATCH_JOB_TYPE",
    "OUTBOX_EVENT_VERSION",
    "ChapterOutboxDispatcher",
    "handle_chapter_outbox_dispatch",
    "repair_chapter_outbox_backlog",
]
