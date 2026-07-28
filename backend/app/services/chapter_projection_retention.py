# AIMETA P=章节投影制品留存治理|R=安全预览_精确代际清理_不可变审计|NR=不清理canonical快照或执行任务|E=ChapterProjectionRetentionService|X=internal|A=事务服务|D=sqlalchemy|S=db|RD=./README.ai
"""受控清理已 supersede/tombstone 的章节投影派生制品。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_projection import (
    ChapterProjectionRetentionAudit,
    ChapterProjectionRun,
    ChapterRevision,
)
from ..models.foreshadowing import Foreshadowing
from ..models.novel import Chapter
from ..models.rag import RagChunk, RagSummary
from ..models.user import User
from ..schemas.chapter_projection import (
    ChapterProjectionRetentionRequest,
    ChapterProjectionRetentionResponse,
)


RetentionMode = Literal["preview", "purge"]


class ChapterProjectionRetentionError(RuntimeError):
    """可安全暴露错误码的 retention 领域异常。"""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ChapterProjectionRetentionNotFoundError(ChapterProjectionRetentionError):
    pass


class ChapterProjectionRetentionConflictError(ChapterProjectionRetentionError):
    pass


class ChapterProjectionRetentionRateLimitError(ChapterProjectionRetentionError):
    pass


class ChapterProjectionRetentionService:
    """仅清理可精确定位且已失活的 RAG/非手工伏笔 generation。"""

    RATE_LIMIT_PER_MINUTE = 10
    RETIRABLE_LIFECYCLES = frozenset({"superseded", "tombstoned"})
    IN_PROGRESS_STATUSES = frozenset({"queued", "running", "retry_wait"})

    def __init__(self, session: AsyncSession):
        self.session = session

    async def execute(
        self,
        *,
        request: ChapterProjectionRetentionRequest,
        operator_user_id: int,
        mode: RetentionMode,
    ) -> ChapterProjectionRetentionResponse:
        if mode not in {"preview", "purge"}:
            raise ValueError("不支持的章节投影 retention 模式")

        operator = (
            await self.session.execute(
                select(User).where(User.id == operator_user_id).with_for_update()
            )
        ).scalars().first()
        if operator is None:
            raise ChapterProjectionRetentionNotFoundError("operator_not_found")
        if not operator.is_admin or not operator.is_active:
            raise ChapterProjectionRetentionNotFoundError("operator_not_authorized")

        scope = request.model_dump(mode="json")
        existing = await self._find_idempotent(operator_user_id, request.idempotency_key)
        if existing is not None:
            response = self._existing_response(
                existing,
                mode=mode,
                reason=request.reason,
                scope=scope,
            )
            self._raise_purge_rejection(response)
            return response

        chapter = (
            await self.session.execute(
                select(Chapter)
                .where(
                    Chapter.project_id == request.project_id,
                    Chapter.chapter_number == request.chapter_number,
                )
                .with_for_update()
            )
        ).scalars().first()
        revision = (
            await self.session.execute(
                select(ChapterRevision)
                .where(
                    ChapterRevision.project_id == request.project_id,
                    ChapterRevision.chapter_number == request.chapter_number,
                    ChapterRevision.revision == request.revision,
                )
                .with_for_update()
            )
        ).scalars().first()
        if revision is None:
            await self.session.rollback()
            raise ChapterProjectionRetentionNotFoundError("revision_not_found")

        projection_name = "rag" if request.artifact_kind == "rag" else "foreshadowing"
        runs = (
            await self.session.execute(
                select(ChapterProjectionRun)
                .where(
                    ChapterProjectionRun.chapter_revision_id == revision.id,
                    ChapterProjectionRun.project_id == request.project_id,
                    ChapterProjectionRun.revision == request.revision,
                    ChapterProjectionRun.projection_name == projection_name,
                    ChapterProjectionRun.artifact_generation
                    == request.artifact_generation,
                )
                .order_by(ChapterProjectionRun.id)
                .with_for_update()
            )
        ).scalars().all()
        candidate_ids, active_count = await self._load_artifacts(request)
        candidate_rows = {name: len(ids) for name, ids in candidate_ids.items()}
        candidate_total = sum(candidate_rows.values())
        completed_target = await self._find_completed_target(request)

        now = datetime.now(timezone.utc)
        recent_count = int(
            await self.session.scalar(
                select(func.count(ChapterProjectionRetentionAudit.id)).where(
                    ChapterProjectionRetentionAudit.operator_user_id == operator_user_id,
                    ChapterProjectionRetentionAudit.created_at >= now - timedelta(minutes=1),
                )
            )
            or 0
        )
        reason_code: str | None = None
        response_status: Literal["eligible", "completed", "rejected"]
        deleted_rows: dict[str, int] = {}

        if recent_count >= self.RATE_LIMIT_PER_MINUTE:
            reason_code = "rate_limit_exceeded"
        elif request.artifact_generation == "legacy":
            reason_code = "legacy_generation_protected"
        elif revision.lifecycle not in self.RETIRABLE_LIFECYCLES:
            reason_code = "revision_not_retirable"
        elif (
            chapter is not None
            and chapter.current_revision == request.revision
            and chapter.projection_generation == request.artifact_generation
        ):
            reason_code = "current_generation_protected"
        elif any(run.is_active for run in runs):
            reason_code = "active_projection_run"
        elif any(run.status in self.IN_PROGRESS_STATUSES for run in runs):
            reason_code = "projection_in_progress"
        elif active_count > 0:
            reason_code = "active_artifacts"
        elif candidate_total > request.max_rows:
            reason_code = "retention_batch_too_large"

        if reason_code is not None:
            response_status = "rejected"
        elif mode == "purge" and completed_target is not None:
            response_status = "rejected"
            reason_code = "artifact_generation_already_purged"
        elif candidate_total == 0:
            response_status = "rejected"
            reason_code = "no_inactive_artifacts"
        elif mode == "preview":
            response_status = "eligible"
        else:
            deleted_rows = await self._delete_artifacts(request, candidate_ids)
            response_status = "completed"

        audit_id = str(uuid4())
        response = ChapterProjectionRetentionResponse(
            mode=mode,
            status=response_status,
            idempotency_key=request.idempotency_key,
            audit_id=audit_id,
            project_id=request.project_id,
            chapter_id=revision.chapter_id,
            chapter_number=request.chapter_number,
            revision=request.revision,
            artifact_generation=request.artifact_generation,
            artifact_kind=request.artifact_kind,
            reason_code=reason_code,
            candidate_rows=candidate_rows,
            deleted_rows=deleted_rows,
        )
        self.session.add(
            ChapterProjectionRetentionAudit(
                id=audit_id,
                operator_user_id=operator_user_id,
                project_id=request.project_id,
                chapter_id=revision.chapter_id,
                chapter_number=request.chapter_number,
                revision=request.revision,
                artifact_generation=request.artifact_generation,
                artifact_kind=request.artifact_kind,
                projection_run_id=runs[0].id if len(runs) == 1 else None,
                mode=mode,
                status="rejected" if response_status == "rejected" else "completed",
                idempotency_key=request.idempotency_key,
                reason=request.reason,
                request_scope=scope,
                result=response.model_dump(mode="json"),
                created_at=now,
                completed_at=now,
            )
        )
        await self.session.commit()
        self._raise_purge_rejection(response)
        return response

    async def _load_artifacts(
        self,
        request: ChapterProjectionRetentionRequest,
    ) -> tuple[dict[str, list[Any]], int]:
        common = {
            "project_id": request.project_id,
            "chapter_number": request.chapter_number,
            "artifact_generation": request.artifact_generation,
        }
        if request.artifact_kind == "foreshadowing":
            base_filters = (
                Foreshadowing.project_id == common["project_id"],
                Foreshadowing.chapter_number == common["chapter_number"],
                Foreshadowing.chapter_revision == request.revision,
                Foreshadowing.artifact_generation == common["artifact_generation"],
                Foreshadowing.is_manual.is_(False),
            )
            ids = (
                await self.session.execute(
                    select(Foreshadowing.id)
                    .where(*base_filters, Foreshadowing.is_active.is_(False))
                    .order_by(Foreshadowing.id)
                    .limit(request.max_rows + 1)
                    .with_for_update()
                )
            ).scalars().all()
            active_count = int(
                await self.session.scalar(
                    select(func.count(Foreshadowing.id)).where(
                        *base_filters,
                        Foreshadowing.is_active.is_(True),
                    )
                )
                or 0
            )
            return {"foreshadowings": list(ids)}, active_count

        artifact_ids: dict[str, list[Any]] = {}
        active_count = 0
        for name, model in (("rag_chunks", RagChunk), ("rag_summaries", RagSummary)):
            base_filters = (
                model.project_id == common["project_id"],
                model.chapter_number == common["chapter_number"],
                model.source_revision == request.revision,
                model.artifact_generation == common["artifact_generation"],
            )
            ids = (
                await self.session.execute(
                    select(model.id)
                    .where(*base_filters, model.is_active.is_(False))
                    .order_by(model.id)
                    .limit(request.max_rows + 1)
                    .with_for_update()
                )
            ).scalars().all()
            active_count += int(
                await self.session.scalar(
                    select(func.count(model.id)).where(
                        *base_filters,
                        model.is_active.is_(True),
                    )
                )
                or 0
            )
            artifact_ids[name] = list(ids)
        return artifact_ids, active_count

    async def _delete_artifacts(
        self,
        request: ChapterProjectionRetentionRequest,
        candidate_ids: dict[str, list[Any]],
    ) -> dict[str, int]:
        deleted_rows: dict[str, int] = {}
        for name, ids in candidate_ids.items():
            if not ids:
                deleted_rows[name] = 0
                continue
            if name == "rag_chunks":
                statement = delete(RagChunk).where(
                    RagChunk.id.in_(ids),
                    RagChunk.project_id == request.project_id,
                    RagChunk.chapter_number == request.chapter_number,
                    RagChunk.source_revision == request.revision,
                    RagChunk.artifact_generation == request.artifact_generation,
                    RagChunk.is_active.is_(False),
                )
            elif name == "rag_summaries":
                statement = delete(RagSummary).where(
                    RagSummary.id.in_(ids),
                    RagSummary.project_id == request.project_id,
                    RagSummary.chapter_number == request.chapter_number,
                    RagSummary.source_revision == request.revision,
                    RagSummary.artifact_generation == request.artifact_generation,
                    RagSummary.is_active.is_(False),
                )
            else:
                statement = delete(Foreshadowing).where(
                    Foreshadowing.id.in_(ids),
                    Foreshadowing.project_id == request.project_id,
                    Foreshadowing.chapter_number == request.chapter_number,
                    Foreshadowing.chapter_revision == request.revision,
                    Foreshadowing.artifact_generation == request.artifact_generation,
                    Foreshadowing.is_manual.is_(False),
                    Foreshadowing.is_active.is_(False),
                )
            result = await self.session.execute(statement)
            if result.rowcount != len(ids):
                await self.session.rollback()
                raise ChapterProjectionRetentionConflictError("artifact_state_changed")
            deleted_rows[name] = len(ids)
        return deleted_rows

    async def _find_idempotent(
        self,
        operator_user_id: int,
        idempotency_key: str,
    ) -> ChapterProjectionRetentionAudit | None:
        return (
            await self.session.execute(
                select(ChapterProjectionRetentionAudit).where(
                    ChapterProjectionRetentionAudit.operator_user_id == operator_user_id,
                    ChapterProjectionRetentionAudit.idempotency_key == idempotency_key,
                )
            )
        ).scalars().first()

    async def _find_completed_target(
        self,
        request: ChapterProjectionRetentionRequest,
    ) -> ChapterProjectionRetentionAudit | None:
        return (
            await self.session.execute(
                select(ChapterProjectionRetentionAudit).where(
                    ChapterProjectionRetentionAudit.project_id == request.project_id,
                    ChapterProjectionRetentionAudit.chapter_number
                    == request.chapter_number,
                    ChapterProjectionRetentionAudit.revision == request.revision,
                    ChapterProjectionRetentionAudit.artifact_generation
                    == request.artifact_generation,
                    ChapterProjectionRetentionAudit.artifact_kind
                    == request.artifact_kind,
                    ChapterProjectionRetentionAudit.mode == "purge",
                    ChapterProjectionRetentionAudit.status == "completed",
                )
            )
        ).scalars().first()

    @staticmethod
    def _existing_response(
        audit: ChapterProjectionRetentionAudit,
        *,
        mode: RetentionMode,
        reason: str,
        scope: dict[str, Any],
    ) -> ChapterProjectionRetentionResponse:
        if audit.mode != mode or audit.reason != reason or audit.request_scope != scope:
            raise ChapterProjectionRetentionConflictError("idempotency_key_conflict")
        return ChapterProjectionRetentionResponse.model_validate(audit.result)

    @staticmethod
    def _raise_purge_rejection(response: ChapterProjectionRetentionResponse) -> None:
        if response.mode != "purge" or response.status != "rejected":
            return
        if response.reason_code == "rate_limit_exceeded":
            raise ChapterProjectionRetentionRateLimitError(response.reason_code)
        raise ChapterProjectionRetentionConflictError(
            response.reason_code or "retention_rejected"
        )


__all__ = [
    "ChapterProjectionRetentionConflictError",
    "ChapterProjectionRetentionError",
    "ChapterProjectionRetentionNotFoundError",
    "ChapterProjectionRetentionRateLimitError",
    "ChapterProjectionRetentionService",
]
