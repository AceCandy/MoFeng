# AIMETA P=章节投影运行时_当前修订与fencing守卫|R=payload校验_run状态提交_DAG子任务创建|NR=不拥有job_claim或外部副作用|E=load_current_projection_mark_projection_succeeded|X=worker|A=runtime|D=sqlalchemy,job_service|S=db|RD=./README.ai
"""Shared transactional guards for typed chapter projection JobRuns."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_projection import (
    ChapterOutboxEvent,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
)
from ..models.novel import Chapter, NovelProject
from ..schemas.job import ChapterProjectionJobPayload, ChapterTombstoneJobPayload
from .chapter_projection_contract import (
    OUTBOX_EVENT_VERSION,
    payload_fingerprint,
    validate_finalize_outbox_event,
)
from .job_service import JobService


PROJECTION_JOB_TYPES = {
    "memory": "chapter_projection_memory",
    "rag": "chapter_projection_rag",
    "foreshadowing": "chapter_projection_foreshadowing",
    "trace": "chapter_projection_trace",
    "reconcile": "chapter_projection_reconcile",
}


def _derived_projection_id(
    *,
    chapter_revision_id: str,
    dependency_run_id: str,
    projection_name: str,
    identity: str,
) -> str:
    return str(
        uuid5(
            NAMESPACE_URL,
            "mofeng:chapter-projection:"
            f"{chapter_revision_id}:{dependency_run_id}:{projection_name}:{identity}",
        )
    )


@dataclass(frozen=True)
class CurrentProjection:
    """Rows locked for a fenced projection outcome commit."""

    chapter: Chapter
    revision: ChapterRevision
    run: ChapterProjectionRun
    rollout: ChapterProjectionRollout
    dependency: Optional[ChapterProjectionRun]


@dataclass(frozen=True)
class CurrentTombstone:
    """Immutable tombstone command rows locked for cleanup outcome commit."""

    revision: ChapterRevision
    run: ChapterProjectionRun
    outbox_event: ChapterOutboxEvent
    target_revision: Optional[ChapterRevision]


async def load_current_projection(
    session: AsyncSession,
    *,
    payload: ChapterProjectionJobPayload,
    user_id: int,
    job_id: str,
    expected_projection: str,
    for_update: bool,
) -> Optional[CurrentProjection]:
    """Load the canonical revision and reject stale, fenced, or cross-owner input."""

    expected_state = "shadow" if payload.execution_mode == "shadow" else "projection"
    expected_active = payload.execution_mode == "active"
    chapter_stmt = (
        select(Chapter)
        .join(NovelProject, NovelProject.id == Chapter.project_id)
        .where(
            Chapter.id == payload.chapter_id,
            Chapter.project_id == payload.project_id,
            Chapter.chapter_number == payload.chapter_number,
            NovelProject.user_id == user_id,
        )
    )
    if for_update:
        chapter_stmt = chapter_stmt.with_for_update(of=Chapter)
    chapter = (await session.execute(chapter_stmt)).scalars().first()
    if chapter is None:
        return None

    outbox_stmt = (
        select(ChapterOutboxEvent)
        .join(NovelProject, NovelProject.id == ChapterOutboxEvent.project_id)
        .where(
            ChapterOutboxEvent.id == payload.outbox_event_id,
            ChapterOutboxEvent.project_id == chapter.project_id,
            NovelProject.user_id == user_id,
        )
    )
    if for_update:
        outbox_stmt = outbox_stmt.with_for_update(of=ChapterOutboxEvent)
    outbox_event = (await session.execute(outbox_stmt)).scalars().first()
    if outbox_event is None:
        return None
    finalize_payload, validation_error = validate_finalize_outbox_event(outbox_event)
    if validation_error is not None or finalize_payload is None:
        return None
    if (
        finalize_payload.project_id != payload.project_id
        or finalize_payload.chapter_id != payload.chapter_id
        or finalize_payload.chapter_number != payload.chapter_number
        or finalize_payload.chapter_revision_id != payload.chapter_revision_id
        or finalize_payload.revision != payload.revision
        or finalize_payload.source_hash != payload.source_hash
        or finalize_payload.source_generation != payload.source_generation
        or finalize_payload.workflow_stream_id != payload.workflow_stream_id
        or finalize_payload.outbox_event_id != payload.outbox_event_id
        or finalize_payload.rollout_owner != payload.rollout_owner
        or finalize_payload.rollout_generation != payload.rollout_generation
        or finalize_payload.rollout_fencing_token
        != payload.rollout_fencing_token
        or finalize_payload.execution_mode != payload.execution_mode
        or finalize_payload.skip_vector_update != payload.skip_vector_update
        or (
            expected_projection == "summary"
            and (
                finalize_payload.selected_version_id != payload.selected_version_id
                or finalize_payload.content_hash != payload.content_hash
            )
        )
    ):
        return None

    revision_stmt = select(ChapterRevision).where(
        ChapterRevision.id == payload.chapter_revision_id,
        ChapterRevision.chapter_id == chapter.id,
        ChapterRevision.project_id == chapter.project_id,
        ChapterRevision.chapter_number == chapter.chapter_number,
        ChapterRevision.revision == payload.revision,
        ChapterRevision.source_hash == payload.source_hash,
        ChapterRevision.source_generation == payload.source_generation,
    )
    if for_update:
        revision_stmt = revision_stmt.with_for_update()
    revision = (await session.execute(revision_stmt)).scalars().first()

    rollout_stmt = select(ChapterProjectionRollout).where(
        ChapterProjectionRollout.chapter_id == chapter.id,
        ChapterProjectionRollout.project_id == chapter.project_id,
        ChapterProjectionRollout.owner == payload.rollout_owner,
        ChapterProjectionRollout.state == expected_state,
        ChapterProjectionRollout.generation == payload.rollout_generation,
        ChapterProjectionRollout.fencing_token == payload.rollout_fencing_token,
    )
    if for_update:
        rollout_stmt = rollout_stmt.with_for_update()
    rollout = (await session.execute(rollout_stmt)).scalars().first()

    run_stmt = select(ChapterProjectionRun).where(
        ChapterProjectionRun.id == payload.projection_run_id,
        ChapterProjectionRun.chapter_revision_id == payload.chapter_revision_id,
        ChapterProjectionRun.chapter_id == chapter.id,
        ChapterProjectionRun.project_id == chapter.project_id,
        ChapterProjectionRun.revision == payload.revision,
        ChapterProjectionRun.projection_name == expected_projection,
        ChapterProjectionRun.source_hash == payload.source_hash,
        ChapterProjectionRun.artifact_generation == payload.artifact_generation,
    )
    if for_update:
        run_stmt = run_stmt.with_for_update()
    run = (await session.execute(run_stmt)).scalars().first()
    if revision is None or rollout is None or run is None:
        return None
    if (
        run.job_id not in (None, job_id)
        or chapter.current_revision != payload.revision
        or chapter.source_hash != payload.source_hash
        or chapter.projection_generation != payload.source_generation
        or chapter.tombstone_revision >= payload.revision
        or revision.lifecycle not in ("finalizing", "successful")
        or revision.tombstoned_at is not None
    ):
        return None

    dependency: Optional[ChapterProjectionRun] = None
    if payload.dependency_run_id is not None:
        dependency_stmt = select(ChapterProjectionRun).where(
            ChapterProjectionRun.id == payload.dependency_run_id
        )
        if for_update:
            dependency_stmt = dependency_stmt.with_for_update()
        dependency = (await session.execute(dependency_stmt)).scalars().first()
        if (
            dependency is None
            or dependency.chapter_revision_id != revision.id
            or dependency.chapter_id != chapter.id
            or dependency.project_id != chapter.project_id
            or dependency.revision != payload.revision
            or dependency.projection_name != "summary"
            or dependency.source_hash != payload.source_hash
            or dependency.status != "succeeded"
            or dependency.is_active != expected_active
            or not dependency.artifact_generation
        ):
            return None
    return CurrentProjection(chapter, revision, run, rollout, dependency)


async def load_current_tombstone(
    session: AsyncSession,
    *,
    payload: ChapterTombstoneJobPayload,
    user_id: int,
    job_id: str,
    for_update: bool,
) -> Optional[CurrentTombstone]:
    """Validate one immutable tombstone fact without requiring a live Chapter row."""

    outbox_stmt = (
        select(ChapterOutboxEvent)
        .join(NovelProject, NovelProject.id == ChapterOutboxEvent.project_id)
        .where(
            NovelProject.user_id == user_id,
            ChapterOutboxEvent.id == payload.outbox_event_id,
            ChapterOutboxEvent.aggregate_type == "chapter",
            ChapterOutboxEvent.aggregate_id == str(payload.chapter_id),
            ChapterOutboxEvent.project_id == payload.project_id,
            ChapterOutboxEvent.revision == payload.tombstone_revision,
            ChapterOutboxEvent.event_type == payload.event_type,
            ChapterOutboxEvent.event_version == OUTBOX_EVENT_VERSION,
            ChapterOutboxEvent.workflow_stream_type == "workflow",
            ChapterOutboxEvent.workflow_stream_id == payload.workflow_stream_id,
        )
    )
    if for_update:
        outbox_stmt = outbox_stmt.with_for_update(of=ChapterOutboxEvent)
    outbox_event = (await session.execute(outbox_stmt)).scalars().first()
    if outbox_event is None:
        return None

    event_payload = outbox_event.payload if isinstance(outbox_event.payload, dict) else {}
    expected_event_payload = {
        "job_type": "chapter_projection_tombstone",
        "payload_version": 1,
        "project_id": payload.project_id,
        "chapter_id": payload.chapter_id,
        "chapter_number": payload.chapter_number,
        "chapter_revision_id": payload.chapter_revision_id,
        "tombstone_revision": payload.tombstone_revision,
        "source_hash": payload.source_hash,
        "source_generation": payload.source_generation,
        "projection_run_id": payload.projection_run_id,
        "artifact_generation": payload.artifact_generation,
        "target_revision": payload.target_revision,
        "target_generation": payload.target_generation,
        "target_artifact_generations": payload.target_artifact_generations,
        "event_type": payload.event_type,
        "reason": payload.reason,
        "workflow_stream_type": "workflow",
        "workflow_stream_id": payload.workflow_stream_id,
    }
    if (
        outbox_event.chapter_id not in (None, payload.chapter_id)
        or event_payload != expected_event_payload
        or payload_fingerprint(event_payload) != outbox_event.payload_fingerprint
    ):
        return None

    revision_stmt = select(ChapterRevision).where(
        ChapterRevision.id == payload.chapter_revision_id,
        ChapterRevision.project_id == payload.project_id,
        ChapterRevision.chapter_number == payload.chapter_number,
        ChapterRevision.revision == payload.tombstone_revision,
        ChapterRevision.source_hash == payload.source_hash,
        ChapterRevision.source_generation == payload.source_generation,
        ChapterRevision.lifecycle == "tombstone",
    )
    if for_update:
        revision_stmt = revision_stmt.with_for_update()
    revision = (await session.execute(revision_stmt)).scalars().first()
    if revision is None or revision.chapter_id not in (None, payload.chapter_id):
        return None

    target_revision: Optional[ChapterRevision] = None
    if payload.target_revision > 0:
        target_stmt = select(ChapterRevision).where(
            ChapterRevision.project_id == payload.project_id,
            ChapterRevision.chapter_number == payload.chapter_number,
            ChapterRevision.revision == payload.target_revision,
        )
        if for_update:
            target_stmt = target_stmt.with_for_update()
        target_revision = (await session.execute(target_stmt)).scalars().first()
        if (
            target_revision is None
            or target_revision.lifecycle
            not in ("tombstoned", "superseded")
            or target_revision.superseded_by_revision != payload.tombstone_revision
        ):
            return None
    run_stmt = select(ChapterProjectionRun).where(
        ChapterProjectionRun.id == payload.projection_run_id,
        ChapterProjectionRun.chapter_revision_id == revision.id,
        ChapterProjectionRun.project_id == payload.project_id,
        ChapterProjectionRun.revision == payload.tombstone_revision,
        ChapterProjectionRun.projection_name == "tombstone",
        ChapterProjectionRun.source_hash == payload.source_hash,
        ChapterProjectionRun.artifact_generation == payload.artifact_generation,
    )
    if for_update:
        run_stmt = run_stmt.with_for_update()
    run = (await session.execute(run_stmt)).scalars().first()
    if (
        run is None
        or run.chapter_id not in (None, payload.chapter_id)
        or run.job_id not in (None, job_id)
    ):
        return None
    return CurrentTombstone(revision, run, outbox_event, target_revision)


async def mark_tombstone_running(
    session: AsyncSession,
    *,
    payload: ChapterTombstoneJobPayload,
    user_id: int,
    job_id: str,
    attempt: int,
    fencing_token: int,
    executor_generation: int,
) -> bool:
    """Mirror a fenced tombstone JobRun into its typed domain run."""

    current = await load_current_tombstone(
        session,
        payload=payload,
        user_id=user_id,
        job_id=job_id,
        for_update=True,
    )
    if current is None:
        await mark_projection_stale(
            session,
            run_id=payload.projection_run_id,
            job_id=job_id,
            reason="tombstone_fact_stale",
        )
        return False
    current.run.job_id = job_id
    current.run.status = "running"
    current.run.checkpoint = {
        **(current.run.checkpoint or {}),
        "attempt": attempt,
        "fencing_token": fencing_token,
        "executor_generation": executor_generation,
    }
    return True


async def mark_projection_running(
    session: AsyncSession,
    *,
    payload: ChapterProjectionJobPayload,
    user_id: int,
    job_id: str,
    expected_projection: str,
    attempt: int,
    fencing_token: int,
    executor_generation: int,
) -> bool:
    """Mirror JobRun execution state without introducing a second claim loop."""

    current = await load_current_projection(
        session,
        payload=payload,
        user_id=user_id,
        job_id=job_id,
        expected_projection=expected_projection,
        for_update=True,
    )
    if current is None:
        run = await session.get(ChapterProjectionRun, payload.projection_run_id)
        if run is not None and run.job_id in (None, job_id):
            run.job_id = job_id
            run.status = "stale"
            run.is_active = False
        return False
    current.run.job_id = job_id
    current.run.status = "running"
    current.run.checkpoint = {
        **(current.run.checkpoint or {}),
        "attempt": attempt,
        "fencing_token": fencing_token,
        "executor_generation": executor_generation,
    }
    return True


async def mark_projection_stale(
    session: AsyncSession,
    *,
    run_id: str,
    job_id: str,
    reason: str,
) -> None:
    run = await session.get(ChapterProjectionRun, run_id)
    if run is None or run.job_id not in (None, job_id):
        return
    run.job_id = job_id
    run.status = "stale"
    run.is_active = False
    run.error_category = reason


async def complete_projection(
    session: AsyncSession,
    *,
    current: CurrentProjection,
    result: dict[str, Any],
    activate: bool,
) -> None:
    """提交 typed result；只有 active owner 可以切换可见 generation。"""

    if activate:
        await session.execute(
            update(ChapterProjectionRun)
            .where(
                ChapterProjectionRun.chapter_id == current.chapter.id,
                ChapterProjectionRun.revision == current.revision.revision,
                ChapterProjectionRun.projection_name == current.run.projection_name,
                ChapterProjectionRun.id != current.run.id,
                ChapterProjectionRun.is_active.is_(True),
            )
            .values(is_active=False)
        )
    current.run.status = "succeeded"
    current.run.result = result
    current.run.error_category = None
    current.run.is_active = activate


async def enqueue_downstream_projections(
    session: AsyncSession,
    *,
    payload: ChapterProjectionJobPayload,
    current: CurrentProjection,
    user_id: int,
) -> list[ChapterProjectionRun]:
    """Create summary-dependent typed child JobRuns in the summary outcome transaction."""

    created: list[ChapterProjectionRun] = []
    required = set(current.revision.required_projections or [])
    names = ["memory", "foreshadowing", "trace"]
    if "rag" in required:
        names.append("rag")

    for projection_name in names:
        run_id = _derived_projection_id(
            chapter_revision_id=current.revision.id,
            dependency_run_id=current.run.id,
            projection_name=projection_name,
            identity="run",
        )
        artifact_generation = _derived_projection_id(
            chapter_revision_id=current.revision.id,
            dependency_run_id=current.run.id,
            projection_name=projection_name,
            identity="artifact",
        )
        existing = await session.get(ChapterProjectionRun, run_id)
        if existing is not None:
            created.append(existing)
            continue

        run = ChapterProjectionRun(
            id=run_id,
            chapter_revision_id=current.revision.id,
            chapter_id=current.chapter.id,
            project_id=current.chapter.project_id,
            revision=current.revision.revision,
            projection_name=projection_name,
            source_hash=current.revision.source_hash,
            dependency_run_id=current.run.id,
            artifact_generation=artifact_generation,
            status="queued",
            required=projection_name in required,
            is_active=False,
            checkpoint={
                "outbox_event_id": payload.outbox_event_id,
                "execution_mode": payload.execution_mode,
                "rollout_generation": payload.rollout_generation,
                "rollout_fencing_token": payload.rollout_fencing_token,
            },
        )
        session.add(run)
        child_payload = payload.model_copy(
            update={
                "projection_run_id": run_id,
                "artifact_generation": artifact_generation,
                "dependency_run_id": current.run.id,
                "selected_version_id": None,
                "content_hash": None,
            }
        ).model_dump()
        job = await JobService(session).enqueue_job_in_transaction(
            user_id=user_id,
            project_id=current.chapter.project_id,
            job_type=PROJECTION_JOB_TYPES[projection_name],
            title=f"第 {current.chapter.chapter_number} 章 {projection_name} 投影",
            payload=child_payload,
            payload_version=1,
            idempotency_key=(
                f"chapter:{current.chapter.id}:revision:{current.revision.revision}:"
                f"projection:{projection_name}:dependency:{current.run.id}"
            ),
            stream_type="workflow",
            stream_id=payload.workflow_stream_id,
        )
        run.job_id = job.id
        created.append(run)

    if "rag" not in required:
        skipped = (
            await session.execute(
                select(ChapterProjectionRun).where(
                    ChapterProjectionRun.chapter_revision_id == current.revision.id,
                    ChapterProjectionRun.projection_name == "rag",
                    ChapterProjectionRun.dependency_run_id == current.run.id,
                )
            )
        ).scalars().first()
        if skipped is None:
            skipped = ChapterProjectionRun(
                id=_derived_projection_id(
                    chapter_revision_id=current.revision.id,
                    dependency_run_id=current.run.id,
                    projection_name="rag",
                    identity="run",
                ),
                chapter_revision_id=current.revision.id,
                chapter_id=current.chapter.id,
                project_id=current.chapter.project_id,
                revision=current.revision.revision,
                projection_name="rag",
                source_hash=current.revision.source_hash,
                dependency_run_id=current.run.id,
                artifact_generation=_derived_projection_id(
                    chapter_revision_id=current.revision.id,
                    dependency_run_id=current.run.id,
                    projection_name="rag",
                    identity="artifact",
                ),
                status="skipped",
                required=False,
                is_active=payload.execution_mode == "active",
                checkpoint={"authorized_by": "canonical_finalize"},
                result={"reason": "vector_projection_disabled"},
            )
            session.add(skipped)
        created.append(skipped)
    return created


async def maybe_enqueue_reconciler(
    session: AsyncSession,
    *,
    payload: ChapterProjectionJobPayload,
    current: CurrentProjection,
    user_id: int,
) -> Optional[ChapterProjectionRun]:
    """Queue the sole successful-state owner once every required result is active."""

    await session.flush()
    required = set(current.revision.required_projections or [])
    expected_active = payload.execution_mode == "active"
    satisfied = set(
        (
            await session.scalars(
                select(ChapterProjectionRun.projection_name).where(
                    ChapterProjectionRun.chapter_revision_id == current.revision.id,
                    ChapterProjectionRun.projection_name.in_(required),
                    ChapterProjectionRun.status == "succeeded",
                    ChapterProjectionRun.is_active == expected_active,
                )
            )
        ).all()
    )
    if satisfied != required:
        return None

    run_id = _derived_projection_id(
        chapter_revision_id=current.revision.id,
        dependency_run_id=current.revision.id,
        projection_name="reconcile",
        identity="run",
    )
    existing = await session.get(ChapterProjectionRun, run_id)
    if existing is not None:
        return existing

    artifact_generation = _derived_projection_id(
        chapter_revision_id=current.revision.id,
        dependency_run_id=current.revision.id,
        projection_name="reconcile",
        identity="artifact",
    )
    run = ChapterProjectionRun(
        id=run_id,
        chapter_revision_id=current.revision.id,
        chapter_id=current.chapter.id,
        project_id=current.chapter.project_id,
        revision=current.revision.revision,
        projection_name="reconcile",
        source_hash=current.revision.source_hash,
        artifact_generation=artifact_generation,
        status="queued",
        required=False,
        is_active=False,
        checkpoint={
            "required": sorted(required),
            "execution_mode": payload.execution_mode,
            "rollout_generation": payload.rollout_generation,
            "rollout_fencing_token": payload.rollout_fencing_token,
        },
    )
    session.add(run)
    reconcile_payload = payload.model_copy(
        update={
            "projection_run_id": run_id,
            "artifact_generation": artifact_generation,
            "dependency_run_id": None,
            "selected_version_id": None,
            "content_hash": None,
        }
    ).model_dump()
    job = await JobService(session).enqueue_job_in_transaction(
        user_id=user_id,
        project_id=current.chapter.project_id,
        job_type=PROJECTION_JOB_TYPES["reconcile"],
        title=f"完成第 {current.chapter.chapter_number} 章投影",
        payload=reconcile_payload,
        payload_version=1,
        idempotency_key=(
            f"chapter:{current.chapter.id}:revision:{current.revision.revision}:reconcile"
        ),
        stream_type="workflow",
        stream_id=payload.workflow_stream_id,
    )
    run.job_id = job.id
    return run


__all__ = [
    "CurrentProjection",
    "PROJECTION_JOB_TYPES",
    "complete_projection",
    "enqueue_downstream_projections",
    "load_current_projection",
    "mark_projection_running",
    "mark_projection_stale",
    "maybe_enqueue_reconciler",
]
