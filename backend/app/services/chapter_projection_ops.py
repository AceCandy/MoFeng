# AIMETA P=章节投影运维命令_试运行与重放|R=权限后范围校验_幂等_审计_限流|NR=不绕过durable_job执行投影|E=ChapterProjectionOpsService|X=internal|A=service|D=sqlalchemy,job_service|S=db|RD=./README.ai
"""Privileged, audited operations for replayable chapter projections."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_projection import (
    ChapterOutboxEvent,
    ChapterProjectionReplayAudit,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
)
from ..models.novel import Chapter, NovelProject
from ..models.user import User
from ..schemas.chapter_projection import (
    ChapterProjectionOperationRequest,
    ChapterProjectionOperationResponse,
)
from ..schemas.job import ChapterProjectionJobPayload
from .chapter_projection_contract import (
    FINALIZE_EVENT_TYPE,
    validate_finalize_outbox_event,
)
from .chapter_projection_runtime import PROJECTION_JOB_TYPES
from .event_bus import publish_background_task
from .job_service import JobService


class ChapterProjectionOperationError(RuntimeError):
    """不向客户端暴露内部数据的运维命令错误。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ChapterProjectionNotFoundError(ChapterProjectionOperationError):
    pass


class ChapterProjectionConflictError(ChapterProjectionOperationError):
    pass


class ChapterProjectionRateLimitError(ChapterProjectionOperationError):
    pass


class ChapterProjectionOpsService:
    """Single-revision admin operations with DB-backed idempotency and rate limits."""

    RATE_LIMIT_PER_MINUTE = 10
    ALLOWED_PROJECTIONS = {
        "summary",
        "memory",
        "rag",
        "foreshadowing",
        "trace",
        "reconcile",
    }

    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(
        self,
        *,
        request: ChapterProjectionOperationRequest,
        operator_user_id: int,
        mode: str,
    ) -> ChapterProjectionOperationResponse:
        if mode not in {"dry_run", "replay"}:
            raise ValueError("不支持的章节投影运维模式")
        idempotency_key = request.idempotency_key.strip()
        reason = request.reason.strip()
        scope = {
            "project_id": request.project_id,
            "chapter_id": request.chapter_id,
            "revision": request.revision,
            "projection_name": request.projection_name,
            "outbox_event_id": request.outbox_event_id,
        }

        operator = await self.session.get(User, operator_user_id)
        if operator is None:
            raise ChapterProjectionNotFoundError("operator_not_found")
        if not operator.is_admin or not operator.is_active:
            raise ChapterProjectionNotFoundError("operator_not_authorized")

        project_owner_user_id = await self.session.scalar(
            select(NovelProject.user_id).where(NovelProject.id == request.project_id)
        )
        authority_user_ids = {operator_user_id}
        if project_owner_user_id is not None:
            authority_user_ids.add(int(project_owner_user_id))
        for authority_user_id in sorted(authority_user_ids):
            locked_user = (
                await self.session.execute(
                    select(User)
                    .where(User.id == authority_user_id)
                    .with_for_update()
                )
            ).scalars().first()
            if locked_user is None:
                code = (
                    "operator_not_found"
                    if authority_user_id == operator_user_id
                    else "projection_scope_not_found"
                )
                raise ChapterProjectionNotFoundError(code)
            if authority_user_id == operator_user_id:
                operator = locked_user
        if not operator.is_admin or not operator.is_active:
            raise ChapterProjectionNotFoundError("operator_not_authorized")

        existing = await self._find_audit(operator_user_id, idempotency_key)
        if existing is not None:
            response = self._existing_response(existing, mode=mode, reason=reason, scope=scope)
            self._raise_existing_rejection(response, mode=mode)
            return response

        project, chapter, revision, outbox, rollout, runs = await self._load_scope(
            request,
            for_update=True,
        )
        now = datetime.now(timezone.utc)
        audit = ChapterProjectionReplayAudit(
            id=str(uuid4()),
            operator_user_id=operator_user_id,
            project_id=project.id,
            chapter_id=chapter.id,
            revision=request.revision,
            projection_name=request.projection_name,
            mode=mode,
            idempotency_key=idempotency_key,
            reason=reason,
            status="accepted",
            request_scope=scope,
        )
        self.session.add(audit)
        await self.session.flush()

        recent_count = int(
            await self.session.scalar(
                select(func.count(ChapterProjectionReplayAudit.id)).where(
                    ChapterProjectionReplayAudit.operator_user_id == operator_user_id,
                    ChapterProjectionReplayAudit.created_at >= now - timedelta(minutes=1),
                    ChapterProjectionReplayAudit.id != audit.id,
                )
            )
            or 0
        )

        response, previous, dependency = await self._describe(
            request=request,
            mode=mode,
            idempotency_key=idempotency_key,
            chapter=chapter,
            revision=revision,
            outbox=outbox,
            rollout=rollout,
            runs=runs,
        )
        if recent_count >= self.RATE_LIMIT_PER_MINUTE:
            response.status = "rejected"
            response.reason_code = "rate_limit_exceeded"

        if response.status == "rejected" or mode == "dry_run":
            audit.status = "rejected" if response.status == "rejected" else "completed"
            audit.result = response.model_dump(mode="json")
            audit.completed_at = now
            await self.session.commit()
            if response.reason_code == "rate_limit_exceeded":
                raise ChapterProjectionRateLimitError(response.reason_code)
            if mode == "replay" and response.status == "rejected":
                raise ChapterProjectionConflictError(response.reason_code or "replay_rejected")
            return response

        run_id = str(uuid4())
        artifact_generation = str(uuid4())
        dependency_run_id = dependency.id if dependency is not None else None
        run = ChapterProjectionRun(
            id=run_id,
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=revision.revision,
            projection_name=request.projection_name,
            source_hash=revision.source_hash,
            dependency_run_id=dependency_run_id,
            replay_of_run_id=previous.id if previous is not None else None,
            artifact_generation=artifact_generation,
            status="queued",
            required=request.projection_name in set(revision.required_projections or []),
            is_active=False,
            checkpoint={
                "outbox_event_id": outbox.id,
                "replay_audit_id": audit.id,
            },
        )
        self.session.add(run)

        workflow_stream_id = outbox.workflow_stream_id or str(uuid4())
        payload = ChapterProjectionJobPayload(
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
            chapter_revision_id=revision.id,
            revision=revision.revision,
            source_hash=revision.source_hash,
            source_generation=revision.source_generation,
            projection_run_id=run_id,
            artifact_generation=artifact_generation,
            workflow_stream_id=workflow_stream_id,
            outbox_event_id=outbox.id,
            rollout_owner=rollout.owner,
            rollout_generation=rollout.generation,
            rollout_fencing_token=rollout.fencing_token,
            dependency_run_id=dependency_run_id,
            selected_version_id=(
                revision.selected_version_id if request.projection_name == "summary" else None
            ),
            content_hash=(revision.source_hash if request.projection_name == "summary" else None),
            skip_vector_update="rag" not in set(revision.required_projections or []),
        )
        job_type = (
            "chapter_finalize"
            if request.projection_name == "summary"
            else PROJECTION_JOB_TYPES[request.projection_name]
        )
        job = await JobService(self.session).enqueue_job_in_transaction(
            user_id=project.user_id,
            project_id=chapter.project_id,
            job_type=job_type,
            title=f"重放第 {chapter.chapter_number} 章 {request.projection_name} 投影",
            payload=payload.model_dump(),
            payload_version=2 if request.projection_name == "summary" else 1,
            idempotency_key=f"chapter-replay:{audit.id}",
            stream_type="workflow",
            stream_id=workflow_stream_id,
        )
        run.job_id = job.id
        response.status = "queued"
        response.projection_run_id = run.id
        response.job_id = job.id
        audit.status = "completed"
        audit.result = response.model_dump(mode="json")
        audit.completed_at = now
        await self.session.commit()
        await publish_background_task(project.user_id)
        return response

    async def _find_audit(
        self,
        operator_user_id: int,
        idempotency_key: str,
    ) -> Optional[ChapterProjectionReplayAudit]:
        return (
            await self.session.execute(
                select(ChapterProjectionReplayAudit).where(
                    ChapterProjectionReplayAudit.operator_user_id == operator_user_id,
                    ChapterProjectionReplayAudit.idempotency_key == idempotency_key,
                )
            )
        ).scalars().first()

    @staticmethod
    def _existing_response(
        audit: ChapterProjectionReplayAudit,
        *,
        mode: str,
        reason: str,
        scope: dict[str, object],
    ) -> ChapterProjectionOperationResponse:
        if audit.mode != mode or audit.reason != reason or dict(audit.request_scope or {}) != scope:
            raise ChapterProjectionConflictError("idempotency_key_conflict")
        if not isinstance(audit.result, dict):
            raise ChapterProjectionConflictError("idempotent_operation_incomplete")
        return ChapterProjectionOperationResponse.model_validate(audit.result)

    @staticmethod
    def _raise_existing_rejection(
        response: ChapterProjectionOperationResponse,
        *,
        mode: str,
    ) -> None:
        if mode != "replay" or response.status != "rejected":
            return
        if response.reason_code == "rate_limit_exceeded":
            raise ChapterProjectionRateLimitError(response.reason_code)
        raise ChapterProjectionConflictError(response.reason_code or "replay_rejected")

    async def _load_scope(
        self,
        request: ChapterProjectionOperationRequest,
        *,
        for_update: bool,
    ) -> tuple[
        NovelProject,
        Chapter,
        ChapterRevision,
        ChapterOutboxEvent,
        ChapterProjectionRollout,
        list[ChapterProjectionRun],
    ]:
        project = await self.session.get(NovelProject, request.project_id)
        chapter_stmt = select(Chapter).where(
            Chapter.id == request.chapter_id,
            Chapter.project_id == request.project_id,
        )
        if for_update:
            chapter_stmt = chapter_stmt.with_for_update()
        chapter = (await self.session.execute(chapter_stmt)).scalars().first()
        if project is None or chapter is None:
            raise ChapterProjectionNotFoundError("projection_scope_not_found")
        outbox_stmt = select(ChapterOutboxEvent).where(
            ChapterOutboxEvent.chapter_id == chapter.id,
            ChapterOutboxEvent.revision == request.revision,
            ChapterOutboxEvent.event_type == FINALIZE_EVENT_TYPE,
        )
        if request.outbox_event_id is not None:
            outbox_stmt = outbox_stmt.where(ChapterOutboxEvent.id == request.outbox_event_id)
        if for_update:
            outbox_stmt = outbox_stmt.with_for_update()
        outbox = (await self.session.execute(outbox_stmt)).scalars().first()
        revision_stmt = select(ChapterRevision).where(
            ChapterRevision.chapter_id == chapter.id,
            ChapterRevision.revision == request.revision,
        )
        if for_update:
            revision_stmt = revision_stmt.with_for_update()
        revision = (await self.session.execute(revision_stmt)).scalars().first()
        rollout_stmt = select(ChapterProjectionRollout).where(
            ChapterProjectionRollout.chapter_id == chapter.id,
        )
        if for_update:
            rollout_stmt = rollout_stmt.with_for_update()
        rollout = (await self.session.execute(rollout_stmt)).scalars().first()
        if revision is None or outbox is None or rollout is None:
            raise ChapterProjectionNotFoundError("projection_revision_not_found")
        runs_stmt = (
            select(ChapterProjectionRun)
            .where(ChapterProjectionRun.chapter_revision_id == revision.id)
            .order_by(ChapterProjectionRun.id)
        )
        if for_update:
            runs_stmt = runs_stmt.with_for_update()
        runs = list((await self.session.execute(runs_stmt)).scalars().all())
        return project, chapter, revision, outbox, rollout, runs

    async def _describe(
        self,
        *,
        request: ChapterProjectionOperationRequest,
        mode: str,
        idempotency_key: str,
        chapter: Chapter,
        revision: ChapterRevision,
        outbox: ChapterOutboxEvent,
        rollout: ChapterProjectionRollout,
        runs: list[ChapterProjectionRun],
    ) -> tuple[
        ChapterProjectionOperationResponse,
        Optional[ChapterProjectionRun],
        Optional[ChapterProjectionRun],
    ]:
        status_counts = dict(
            Counter(f"{run.projection_name}.{run.status}" for run in runs)
        )
        active_projections = sorted(
            run.projection_name for run in runs if run.is_active
        )
        previous = max(
            (run for run in runs if run.projection_name == request.projection_name),
            key=lambda run: (run.created_at is not None, run.created_at, run.id),
            default=None,
        )
        dependency = None
        if request.projection_name not in {"summary", "reconcile"}:
            dependency = max(
                (
                    run
                    for run in runs
                    if run.projection_name == "summary"
                    and run.status == "succeeded"
                    and run.is_active
                ),
                key=lambda run: (run.updated_at is not None, run.updated_at, run.id),
                default=None,
            )

        reason_code = self._eligibility_reason(
            request=request,
            chapter=chapter,
            revision=revision,
            outbox=outbox,
            rollout=rollout,
            previous=previous,
            dependency=dependency,
            active_projections=active_projections,
        )
        reason_code = reason_code or self._identity_reason(
            request=request,
            chapter=chapter,
            revision=revision,
            outbox=outbox,
            rollout=rollout,
            runs=runs,
            dependency=dependency,
        )
        response = ChapterProjectionOperationResponse(
            mode=mode,
            status="rejected" if reason_code else "eligible",
            idempotency_key=idempotency_key,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
            revision=revision.revision,
            current_revision=int(chapter.current_revision or 0),
            projection_name=request.projection_name,
            reason_code=reason_code,
            run_status_counts=status_counts,
            active_projections=active_projections,
        )
        return response, previous, dependency

    @staticmethod
    def _identity_reason(
        *,
        request: ChapterProjectionOperationRequest,
        chapter: Chapter,
        revision: ChapterRevision,
        outbox: ChapterOutboxEvent,
        rollout: ChapterProjectionRollout,
        runs: list[ChapterProjectionRun],
        dependency: Optional[ChapterProjectionRun],
    ) -> Optional[str]:
        if (
            revision.chapter_id != chapter.id
            or revision.project_id != chapter.project_id
            or revision.chapter_number != chapter.chapter_number
            or revision.revision != request.revision
        ):
            return "revision_identity_mismatch"
        if revision.tombstoned_at is not None:
            return "revision_tombstoned"
        payload, validation_error = validate_finalize_outbox_event(outbox)
        if validation_error is not None or payload is None:
            return {
                "event_contract_mismatch": "outbox_event_contract_mismatch",
                "payload_mismatch": "outbox_payload_mismatch",
                "invalid_payload": "invalid_chapter_finalize_outbox",
                "identity_mismatch": "outbox_identity_mismatch",
            }.get(validation_error, "invalid_chapter_finalize_outbox")
        if (
            payload.project_id != chapter.project_id
            or payload.chapter_id != chapter.id
            or payload.chapter_number != chapter.chapter_number
            or payload.chapter_revision_id != revision.id
            or payload.revision != revision.revision
            or payload.source_hash != revision.source_hash
            or payload.content_hash != revision.source_hash
            or payload.source_generation != revision.source_generation
            or payload.selected_version_id != revision.selected_version_id
        ):
            return "outbox_identity_mismatch"
        if (
            rollout.chapter_id != chapter.id
            or rollout.project_id != chapter.project_id
            or payload.rollout_owner != rollout.owner
            or payload.rollout_generation != rollout.generation
            or payload.rollout_fencing_token != rollout.fencing_token
        ):
            return "rollout_identity_mismatch"
        if any(
            run.chapter_revision_id != revision.id
            or run.chapter_id != chapter.id
            or run.project_id != chapter.project_id
            or run.revision != revision.revision
            or run.source_hash != revision.source_hash
            or not run.artifact_generation
            for run in runs
        ):
            return "projection_run_identity_mismatch"
        if dependency is not None and (
            dependency.projection_name != "summary"
            or dependency.status != "succeeded"
            or not dependency.is_active
        ):
            return "summary_dependency_identity_mismatch"
        return None

    @staticmethod
    def _eligibility_reason(
        *,
        request: ChapterProjectionOperationRequest,
        chapter: Chapter,
        revision: ChapterRevision,
        outbox: ChapterOutboxEvent,
        rollout: ChapterProjectionRollout,
        previous: Optional[ChapterProjectionRun],
        dependency: Optional[ChapterProjectionRun],
        active_projections: list[str],
    ) -> Optional[str]:
        if request.projection_name not in ChapterProjectionOpsService.ALLOWED_PROJECTIONS:
            return "projection_not_allowed"
        if chapter.current_revision != revision.revision:
            return "stale_revision"
        if chapter.tombstone_revision >= revision.revision:
            return "tombstoned_revision"
        if (
            chapter.source_hash != revision.source_hash
            or chapter.projection_generation != revision.source_generation
        ):
            return "canonical_identity_mismatch"
        if revision.lifecycle not in {"finalizing", "successful"}:
            return "revision_not_replayable"
        if rollout.owner != "projection" or rollout.state != "projection":
            return "rollout_owner_mismatch"
        if outbox.revision != revision.revision:
            return "outbox_revision_mismatch"
        if previous is not None and previous.status in {"queued", "running", "retry_wait"}:
            return "projection_in_progress"
        required = set(revision.required_projections or [])
        if request.projection_name == "rag" and "rag" not in required:
            return "projection_skipped_by_canonical_command"
        if request.projection_name == "summary" and revision.lifecycle == "successful":
            return "summary_replay_requires_new_finalize"
        if request.projection_name not in {"summary", "reconcile"} and dependency is None:
            return "summary_dependency_missing"
        if request.projection_name == "reconcile":
            if revision.lifecycle != "finalizing":
                return "revision_already_finalized"
            if not required.issubset(set(active_projections)):
                return "required_projection_gate_not_satisfied"
        return None


__all__ = [
    "ChapterProjectionConflictError",
    "ChapterProjectionNotFoundError",
    "ChapterProjectionOperationError",
    "ChapterProjectionOpsService",
    "ChapterProjectionRateLimitError",
]
