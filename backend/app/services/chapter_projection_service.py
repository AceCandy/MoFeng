# AIMETA P=章节canonical修订_outbox与投影编排|R=revision分配_事件追加_tombstone_运行指标|NR=不执行worker投影或隐藏提交|E=ChapterProjectionService|X=internal|A=service|D=sqlalchemy,job_service|S=db|RD=./README.ai
"""Canonical chapter revision and projection orchestration primitives."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.background_task import BackgroundTask
from ..models.chapter_projection import (
    ChapterOutboxEvent,
    ChapterProjectionRollout,
    ChapterProjectionRolloutTransition,
    ChapterProjectionRun,
    ChapterProjectionShadowObservation,
    ChapterRevision,
)
from ..models.foreshadowing import Foreshadowing
from ..models.job import AIUsageRecord, JobActivity, JobEvent
from ..models.memory_layer import CharacterState
from ..models.novel import Chapter, ChapterOutline, ChapterVersion
from ..models.project_memory import ChapterSnapshot, ProjectMemory
from ..models.rag import RagChunk, RagSummary
from ..schemas.job import (
    ChapterFinalizeOutboxPayload,
    ChapterOutboxDispatchJobPayload,
)
from .event_bus import publish_background_task
from .chapter_projection_rollout import (
    ChapterProjectionRolloutConflictError,
    ChapterProjectionRolloutService,
)
from .chapter_memory_projection import load_memory_input
from .foreshadowing_sync_service import (
    ForeshadowingSyncService,
    serialize_foreshadowing_context,
)
from .chapter_projection_runtime import _derived_projection_id
from .chapter_projection_contract import (
    FINALIZE_EVENT_TYPE,
    OUTBOX_EVENT_VERSION,
    payload_fingerprint,
)
from .job_service import JobService
from .job_registry import SideEffectClass
from .prompt_service import PromptService


FINALIZE_PAYLOAD_VERSION = 2
PROJECTION_JOB_PAYLOAD_VERSION = 1
_EXTERNAL_SIDE_EFFECT_CLASSES = (
    SideEffectClass.IDEMPOTENT_EXTERNAL.value,
    SideEffectClass.AMBIGUOUS_EXTERNAL.value,
)
_EXTERNAL_ACTIVITY_STATUSES = frozenset(
    {"started", "succeeded", "retryable_failed", "failed", "ambiguous"}
)
_AI_COST_UNKNOWN_REASONS = frozenset(
    {
        "usage_unavailable",
        "usage_invalid",
        "pricing_unconfigured",
        "pricing_incomplete",
        "currency_unconfigured",
        "cost_envelope_invalid",
        "unspecified",
    }
)


@dataclass(frozen=True)
class CanonicalFinalizeResult:
    """Rows created by one canonical finalization transaction."""

    job: BackgroundTask
    revision: ChapterRevision
    outbox_event: ChapterOutboxEvent
    jobs: tuple[BackgroundTask, ...]


class ChapterFinalizeConflictError(ValueError):
    """Canonical finalize command conflicts with an existing durable identity."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ChapterProjectionService:
    """Own canonical revision/outbox writes and immediate visibility cuts."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _lock_revision_state(self, chapter_id: int) -> tuple[int, Optional[str]]:
        """锁定 canonical Chapter，并返回数据库中的 revision/generation。"""

        with self.session.no_autoflush:
            row = (
                await self.session.execute(
                    select(Chapter.current_revision, Chapter.projection_generation)
                    .where(Chapter.id == chapter_id)
                    .with_for_update()
                )
            ).one_or_none()
        if row is None:
            raise ValueError("章节不存在")
        return int(row.current_revision or 0), row.projection_generation

    async def find_existing_finalize_job(
        self,
        *,
        user_id: int,
        project_id: str,
        selected_version_id: int,
        source_hash: str,
        skip_vector_update: bool,
        idempotency_key: Optional[str],
    ) -> Optional[BackgroundTask]:
        """Resolve an already committed command before allocating another revision."""

        if idempotency_key is None:
            return None
        normalized_key = idempotency_key.strip()
        if not normalized_key:
            raise ValueError("idempotency_key 不能为空")
        existing = await JobService(self.session).repo.get_by_idempotency_key(
            user_id=user_id,
            job_type="chapter_outbox_dispatch",
            idempotency_key=normalized_key,
        )
        if existing is not None:
            command_payload = ChapterOutboxDispatchJobPayload.model_validate(
                existing.payload or {}
            )
            outbox = await self.session.get(
                ChapterOutboxEvent,
                command_payload.outbox_event_id,
            )
            if outbox is None or outbox.event_type != FINALIZE_EVENT_TYPE:
                raise ChapterFinalizeConflictError(
                    "finalize_idempotency_conflict",
                    "同一 idempotency_key 已绑定其他章节命令",
                )
            canonical = ChapterFinalizeOutboxPayload.model_validate(outbox.payload)
            if (
                canonical.project_id != project_id
                or canonical.selected_version_id != selected_version_id
                or canonical.content_hash != source_hash
                or canonical.skip_vector_update != skip_vector_update
            ):
                raise ChapterFinalizeConflictError(
                    "finalize_idempotency_conflict",
                    "同一 idempotency_key 不能用于不同的定稿参数",
                )
            return existing

        existing = await JobService(self.session).repo.get_by_idempotency_key(
            user_id=user_id,
            job_type="chapter_finalize",
            idempotency_key=normalized_key,
        )
        if existing is None:
            return None
        payload = existing.payload or {}
        if (
            existing.project_id != project_id
            or payload.get("selected_version_id") != selected_version_id
            or payload.get("content_hash") != source_hash
            or bool(payload.get("skip_vector_update")) != skip_vector_update
        ):
            raise ChapterFinalizeConflictError(
                "finalize_idempotency_conflict",
                "同一 idempotency_key 不能用于不同的定稿参数",
            )
        return existing

    async def create_finalize(
        self,
        *,
        chapter: Chapter,
        selected_version: ChapterVersion,
        source_content: str,
        source_hash: str,
        user_id: int,
        skip_vector_update: bool,
        idempotency_key: Optional[str],
    ) -> CanonicalFinalizeResult:
        """Append a canonical revision, outbox fact, root projection and typed JobRun."""

        if chapter.id is None or selected_version.id is None:
            raise ValueError("章节与选中版本必须已持久化")

        current_revision, _ = await self._lock_revision_state(chapter.id)
        rollout = await ChapterProjectionRolloutService(
            self.session
        ).ensure_projection_rollout(chapter=chapter)
        if rollout.owner == "projection" and rollout.state == "projection":
            execution_mode = "active"
        elif rollout.owner == "legacy" and rollout.state == "legacy":
            execution_mode = "legacy"
        elif rollout.owner == "legacy" and rollout.state == "shadow":
            execution_mode = "shadow"
        else:
            raise ChapterProjectionRolloutConflictError(
                "rollout_finalize_unavailable"
            )

        revision_number = current_revision + 1
        revision_id = str(uuid4())
        source_generation = str(uuid4())
        outbox_event_id = str(uuid4())
        workflow_id = str(uuid4())

        required = [] if execution_mode == "legacy" else ["summary", "memory", "foreshadowing"]
        skipped: list[str] = []
        if execution_mode != "legacy" and settings.vector_store_enabled and not skip_vector_update:
            required.append("rag")
        elif execution_mode != "legacy":
            skipped.append("rag")

        memory_input = await load_memory_input(
            self.session,
            project_id=chapter.project_id,
        )
        foreshadowing_context = await ForeshadowingSyncService(
            self.session
        ).load_compute_context(
            project_id=chapter.project_id,
            chapter_number=chapter.chapter_number,
            content=source_content,
        )
        outline = (
            await self.session.execute(
                select(ChapterOutline).where(
                    ChapterOutline.project_id == chapter.project_id,
                    ChapterOutline.chapter_number == chapter.chapter_number,
                )
            )
        ).scalars().first()
        projection_context = {
            "memory": memory_input,
            "foreshadowing": serialize_foreshadowing_context(foreshadowing_context),
            "summary_prompt": await PromptService(self.session).get_prompt("extraction"),
            "rag_title": (
                outline.title
                if outline is not None and outline.title
                else f"第{chapter.chapter_number}章"
            ),
        }

        await self.session.execute(
            update(ChapterRevision)
            .where(
                ChapterRevision.chapter_id == chapter.id,
                ChapterRevision.lifecycle.in_(
                    (
                        "finalizing",
                        "successful",
                        "shadow_ready",
                        "shadow_mismatch",
                    )
                ),
            )
            .values(
                lifecycle="superseded",
                superseded_by_revision=revision_number,
            )
        )

        chapter.current_revision = revision_number
        chapter.source_hash = source_hash
        chapter.required_projection_snapshot = required
        chapter.projection_generation = source_generation

        revision = ChapterRevision(
            id=revision_id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            chapter_number=chapter.chapter_number,
            revision=revision_number,
            selected_version_id=selected_version.id,
            source_hash=source_hash,
            source_content=source_content,
            projection_context=projection_context,
            lifecycle="finalizing",
            required_projections=required,
            skipped_projections=skipped,
            source_generation=source_generation,
        )
        self.session.add(revision)
        await self.session.flush()

        outbox_key = f"chapter:{chapter.id}:revision:{revision_number}:finalize"
        normalized_key = idempotency_key.strip() if idempotency_key else outbox_key
        summary_run_id: Optional[str] = None
        summary_generation: Optional[str] = None
        if execution_mode in {"active", "shadow"}:
            summary_run_id = _derived_projection_id(
                chapter_revision_id=revision_id,
                dependency_run_id=outbox_event_id,
                projection_name="summary",
                identity="run",
            )
            summary_generation = _derived_projection_id(
                chapter_revision_id=revision_id,
                dependency_run_id=outbox_event_id,
                projection_name="summary",
                identity="artifact",
            )

        outbox_payload = ChapterFinalizeOutboxPayload(
            job_type="chapter_finalize",
            payload_version=FINALIZE_PAYLOAD_VERSION,
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
            chapter_revision_id=revision_id,
            revision=revision_number,
            source_hash=source_hash,
            source_generation=source_generation,
            execution_mode=execution_mode,
            rollout_owner=rollout.owner,
            rollout_generation=rollout.generation,
            rollout_fencing_token=rollout.fencing_token,
            workflow_stream_type="workflow",
            workflow_stream_id=workflow_id,
            outbox_event_id=outbox_event_id,
            selected_version_id=selected_version.id,
            content_hash=source_hash,
            skip_vector_update=skip_vector_update,
            dispatch_idempotency_key=normalized_key,
            summary_run_id=summary_run_id,
            summary_artifact_generation=summary_generation,
        ).model_dump()
        outbox = ChapterOutboxEvent(
            id=outbox_event_id,
            aggregate_type="chapter",
            aggregate_id=str(chapter.id),
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=revision_number,
            event_type=FINALIZE_EVENT_TYPE,
            event_version=OUTBOX_EVENT_VERSION,
            payload=outbox_payload,
            payload_fingerprint=payload_fingerprint(outbox_payload),
            idempotency_key=outbox_key,
            workflow_stream_type="workflow",
            workflow_stream_id=workflow_id,
        )
        self.session.add(outbox)
        dispatcher = await JobService(self.session).enqueue_job_in_transaction(
            user_id=user_id,
            project_id=chapter.project_id,
            job_type="chapter_outbox_dispatch",
            title=f"派发第 {chapter.chapter_number} 章定稿事件",
            payload=ChapterOutboxDispatchJobPayload(
                project_id=chapter.project_id,
                outbox_event_id=outbox_event_id,
                event_type=FINALIZE_EVENT_TYPE,
                event_version=OUTBOX_EVENT_VERSION,
                payload_fingerprint=outbox.payload_fingerprint,
            ).model_dump(),
            payload_version=1,
            idempotency_key=normalized_key,
            stream_type="workflow",
            stream_id=workflow_id,
        )
        await self.session.flush()
        return CanonicalFinalizeResult(
            dispatcher,
            revision,
            outbox,
            (dispatcher,),
        )

    async def commit_finalize(self, result: CanonicalFinalizeResult) -> BackgroundTask:
        """Commit the canonical transaction, then notify connected job consumers."""

        await self.session.commit()
        for job in result.jobs:
            await self.session.refresh(job)
        await publish_background_task(result.job.user_id)
        return result.job

    async def create_tombstone_job(
        self,
        *,
        chapter: Chapter,
        user_id: int,
        reason: str,
        event_type: str = "ChapterTombstoned",
    ) -> BackgroundTask:
        """Append a precise cleanup fact before delete or regenerate commits."""

        if chapter.id is None:
            raise ValueError("章节必须已持久化")
        if event_type not in {"ChapterTombstoned", "ChapterRevisionSuperseded"}:
            raise ValueError("不支持的章节 tombstone 事件类型")
        target_revision, current_generation = await self._lock_revision_state(chapter.id)
        tombstone_revision = target_revision + 1
        target_generation = current_generation or "legacy"
        target_revision_row: Optional[ChapterRevision] = None
        if target_revision > 0:
            target_revision_row = (
                await self.session.execute(
                    select(ChapterRevision)
                    .where(
                        ChapterRevision.chapter_id == chapter.id,
                        ChapterRevision.revision == target_revision,
                    )
                    .with_for_update()
                )
            ).scalars().first()
            if target_revision_row is None:
                raise RuntimeError("章节 current_revision 缺少 immutable revision")
            source_content = target_revision_row.source_content
            source_hash = target_revision_row.source_hash
        else:
            selected_version = (
                await self.session.get(ChapterVersion, chapter.selected_version_id)
                if chapter.selected_version_id is not None
                else None
            )
            source_content = selected_version.content if selected_version is not None else ""
            source_hash = chapter.source_hash or hashlib.sha256(
                source_content.encode("utf-8")
            ).hexdigest()

        command_revision_id = str(uuid4())
        command_generation = str(uuid4())
        workflow_id = str(uuid4())
        event_id = str(uuid4())
        cleanup_run_id = _derived_projection_id(
            chapter_revision_id=command_revision_id,
            dependency_run_id=event_id,
            projection_name="tombstone",
            identity="run",
        )
        cleanup_generation = _derived_projection_id(
            chapter_revision_id=command_revision_id,
            dependency_run_id=event_id,
            projection_name="tombstone",
            identity="artifact",
        )
        active_rows = (
            await self.session.execute(
                select(
                    ChapterProjectionRun.projection_name,
                    ChapterProjectionRun.artifact_generation,
                ).where(
                    ChapterProjectionRun.chapter_id == chapter.id,
                    ChapterProjectionRun.revision == target_revision,
                    ChapterProjectionRun.is_active.is_(True),
                )
            )
        ).all()
        target_artifact_generations = {
            str(projection_name): str(artifact_generation)
            for projection_name, artifact_generation in active_rows
        }
        fallback_artifact_generation = (
            "legacy"
            if not active_rows
            and target_revision_row is not None
            and target_revision_row.legacy_job_id is not None
            else target_generation
        )
        for projection_name in ("memory", "rag", "foreshadowing"):
            target_artifact_generations.setdefault(
                projection_name,
                fallback_artifact_generation,
            )
        rag_generation = target_artifact_generations.get(
            "rag", fallback_artifact_generation
        )
        memory_generation = target_artifact_generations.get(
            "memory", fallback_artifact_generation
        )
        foreshadowing_generation = target_artifact_generations.get(
            "foreshadowing", fallback_artifact_generation
        )
        event_payload = {
            "job_type": "chapter_projection_tombstone",
            "payload_version": 1,
            "project_id": chapter.project_id,
            "chapter_id": chapter.id,
            "chapter_number": chapter.chapter_number,
            "chapter_revision_id": command_revision_id,
            "tombstone_revision": tombstone_revision,
            "source_hash": source_hash,
            "source_generation": command_generation,
            "projection_run_id": cleanup_run_id,
            "artifact_generation": cleanup_generation,
            "target_revision": target_revision,
            "target_generation": target_generation,
            "target_artifact_generations": target_artifact_generations,
            "event_type": event_type,
            "reason": reason,
            "workflow_stream_type": "workflow",
            "workflow_stream_id": workflow_id,
        }
        event_key = f"chapter:{chapter.id}:revision:{tombstone_revision}:{event_type}"
        command_revision = ChapterRevision(
            id=command_revision_id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            chapter_number=chapter.chapter_number,
            revision=tombstone_revision,
            selected_version_id=chapter.selected_version_id,
            source_hash=source_hash,
            source_content=source_content,
            lifecycle="tombstone",
            required_projections=["tombstone"],
            skipped_projections=[],
            source_generation=command_generation,
        )
        outbox = ChapterOutboxEvent(
            id=event_id,
            aggregate_type="chapter",
            aggregate_id=str(chapter.id),
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=tombstone_revision,
            event_type=event_type,
            event_version=OUTBOX_EVENT_VERSION,
            payload=event_payload,
            payload_fingerprint=payload_fingerprint(event_payload),
            idempotency_key=event_key,
            workflow_stream_type="workflow",
            workflow_stream_id=workflow_id,
        )
        self.session.add(command_revision)
        await self.session.flush()
        self.session.add(outbox)
        job = await JobService(self.session).enqueue_job_in_transaction(
            user_id=user_id,
            project_id=chapter.project_id,
            job_type="chapter_outbox_dispatch",
            title=f"派发第 {chapter.chapter_number} 章清理事件",
            payload=ChapterOutboxDispatchJobPayload(
                project_id=chapter.project_id,
                outbox_event_id=event_id,
                event_type=event_type,
                event_version=OUTBOX_EVENT_VERSION,
                payload_fingerprint=outbox.payload_fingerprint,
            ).model_dump(),
            payload_version=1,
            idempotency_key=f"chapter-outbox:{event_id}",
            stream_type="workflow",
            stream_id=workflow_id,
        )

        # Tombstone 与 active visibility cut 同事务，避免提交后仍读到旧代产物。
        await self.session.execute(
            update(ChapterProjectionRun)
            .where(
                ChapterProjectionRun.chapter_id == chapter.id,
                ChapterProjectionRun.revision == target_revision,
                ChapterProjectionRun.is_active.is_(True),
            )
            .values(is_active=False, status="stale", error_category=reason)
        )
        for model in (RagChunk, RagSummary):
            await self.session.execute(
                update(model)
                .where(
                    model.project_id == chapter.project_id,
                    model.chapter_number == chapter.chapter_number,
                    model.source_revision == target_revision,
                    model.artifact_generation == rag_generation,
                    model.is_active.is_(True),
                )
                .values(is_active=False)
            )
        await self.session.execute(
            update(ChapterSnapshot)
            .where(
                ChapterSnapshot.project_id == chapter.project_id,
                ChapterSnapshot.chapter_number == chapter.chapter_number,
                ChapterSnapshot.chapter_revision == target_revision,
                ChapterSnapshot.artifact_generation == memory_generation,
                ChapterSnapshot.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.execute(
            update(CharacterState)
            .where(
                CharacterState.project_id == chapter.project_id,
                CharacterState.chapter_number == chapter.chapter_number,
                CharacterState.chapter_revision == target_revision,
                CharacterState.artifact_generation == memory_generation,
                CharacterState.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.execute(
            update(Foreshadowing)
            .where(
                Foreshadowing.project_id == chapter.project_id,
                Foreshadowing.chapter_number == chapter.chapter_number,
                Foreshadowing.chapter_revision == target_revision,
                Foreshadowing.artifact_generation == foreshadowing_generation,
                Foreshadowing.is_manual.is_(False),
                Foreshadowing.is_active.is_(True),
            )
            .values(is_active=False)
        )
        if event_type == "ChapterTombstoned":
            await self.session.execute(
                update(Foreshadowing)
                .where(
                    Foreshadowing.project_id == chapter.project_id,
                    Foreshadowing.chapter_id == chapter.id,
                )
                .values(chapter_id=None)
            )
        await self._restore_project_memory(
            project_id=chapter.project_id,
            chapter_number=chapter.chapter_number,
            target_revision=target_revision,
            target_generation=memory_generation,
        )

        chapter.current_revision = tombstone_revision
        chapter.tombstone_revision = tombstone_revision
        chapter.source_hash = None
        chapter.required_projection_snapshot = []
        if target_revision_row is not None:
            target_revision_row.lifecycle = (
                "tombstoned" if event_type == "ChapterTombstoned" else "superseded"
            )
            target_revision_row.superseded_by_revision = tombstone_revision
            target_revision_row.tombstoned_at = (
                datetime.now(timezone.utc) if event_type == "ChapterTombstoned" else None
            )
        await self.session.flush()
        return job

    async def _restore_project_memory(
        self,
        *,
        project_id: str,
        chapter_number: int,
        target_revision: int,
        target_generation: str,
    ) -> None:
        """仅当项目记忆仍指向目标代时，回退到前一份 active 快照。"""

        memory = (
            await self.session.execute(
                select(ProjectMemory)
                .where(ProjectMemory.project_id == project_id)
                .with_for_update()
            )
        ).scalars().first()
        if memory is None or memory.last_updated_chapter != chapter_number:
            return
        if target_revision > 0:
            if (
                memory.projection_revision != target_revision
                or memory.projection_generation != target_generation
            ):
                return
        elif (
            memory.projection_revision not in (0, target_revision)
            or memory.projection_generation not in (None, "legacy")
        ):
            return

        previous_snapshot = (
            await self.session.execute(
                select(ChapterSnapshot)
                .where(
                    ChapterSnapshot.project_id == project_id,
                    ChapterSnapshot.chapter_number < chapter_number,
                    ChapterSnapshot.is_active.is_(True),
                )
                .order_by(
                    ChapterSnapshot.chapter_number.desc(),
                    ChapterSnapshot.chapter_revision.desc(),
                    ChapterSnapshot.id.desc(),
                )
            )
        ).scalars().first()
        memory.version = int(memory.version or 0) + 1
        if previous_snapshot is None:
            memory.last_updated_chapter = 0
            memory.global_summary = ""
            memory.plot_arcs = {}
            memory.projection_revision = 0
            memory.projection_generation = None
            return
        memory.last_updated_chapter = previous_snapshot.chapter_number
        memory.global_summary = previous_snapshot.global_summary_snapshot or ""
        memory.plot_arcs = previous_snapshot.plot_arcs_snapshot or {}
        memory.projection_revision = previous_snapshot.chapter_revision
        memory.projection_generation = previous_snapshot.artifact_generation

    async def get_runtime_metrics(
        self,
        *,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Return allowlisted projection/outbox aggregates for operational alerts."""

        checked_at = now or datetime.now(timezone.utc)
        age_seconds = lambda value: (
            max(0.0, (checked_at - value).total_seconds())
            if isinstance(value, datetime)
            else None
        )

        current_run_filter = and_(
            ChapterProjectionRun.revision == Chapter.current_revision,
            Chapter.source_hash.is_not(None),
            ChapterProjectionRun.source_hash == Chapter.source_hash,
        )
        status_rows = (
            await self.session.execute(
                select(ChapterProjectionRun.status, func.count(ChapterProjectionRun.id))
                .select_from(ChapterProjectionRun)
                .join(Chapter, Chapter.id == ChapterProjectionRun.chapter_id)
                .where(current_run_filter)
                .group_by(ChapterProjectionRun.status)
            )
        ).all()
        status_counts = {str(status): int(count) for status, count in status_rows}
        projection_rows = (
            await self.session.execute(
                select(
                    ChapterProjectionRun.projection_name,
                    ChapterProjectionRun.status,
                    func.count(ChapterProjectionRun.id),
                )
                .select_from(ChapterProjectionRun)
                .join(Chapter, Chapter.id == ChapterProjectionRun.chapter_id)
                .where(current_run_filter)
                .group_by(
                    ChapterProjectionRun.projection_name,
                    ChapterProjectionRun.status,
                )
            )
        ).all()
        projection_status_counts = {
            f"{projection}.{status}": int(count)
            for projection, status, count in projection_rows
        }
        history_status_rows = (
            await self.session.execute(
                select(ChapterProjectionRun.status, func.count(ChapterProjectionRun.id))
                .group_by(ChapterProjectionRun.status)
            )
        ).all()
        history_status_counts = {
            str(status): int(count) for status, count in history_status_rows
        }
        history_projection_rows = (
            await self.session.execute(
                select(
                    ChapterProjectionRun.projection_name,
                    ChapterProjectionRun.status,
                    func.count(ChapterProjectionRun.id),
                ).group_by(
                    ChapterProjectionRun.projection_name,
                    ChapterProjectionRun.status,
                )
            )
        ).all()
        history_projection_status_counts = {
            f"{projection}.{status}": int(count)
            for projection, status, count in history_projection_rows
        }

        outbox_total = int(
            await self.session.scalar(select(func.count(ChapterOutboxEvent.id))) or 0
        )
        outbox_execution_mode = ChapterOutboxEvent.payload["execution_mode"].as_string()
        projection_outbox_filter = and_(
            ChapterOutboxEvent.event_type == FINALIZE_EVENT_TYPE,
            or_(
                outbox_execution_mode.is_(None),
                outbox_execution_mode != "legacy",
            ),
        )
        projection_outbox_total = int(
            await self.session.scalar(
                select(func.count(ChapterOutboxEvent.id)).where(
                    projection_outbox_filter
                )
            )
            or 0
        )
        legacy_outbox_total = int(
            await self.session.scalar(
                select(func.count(ChapterOutboxEvent.id)).where(
                    ChapterOutboxEvent.event_type == FINALIZE_EVENT_TYPE,
                    outbox_execution_mode == "legacy",
                )
            )
            or 0
        )
        backlog_count, oldest_backlog_at = (
            await self.session.execute(
                select(
                    func.count(ChapterOutboxEvent.id),
                    func.min(ChapterOutboxEvent.created_at),
                )
                .select_from(ChapterOutboxEvent)
                .join(Chapter, Chapter.id == ChapterOutboxEvent.chapter_id)
                .outerjoin(
                    ChapterProjectionRun,
                    and_(
                        ChapterProjectionRun.chapter_id == ChapterOutboxEvent.chapter_id,
                        ChapterProjectionRun.revision == ChapterOutboxEvent.revision,
                        ChapterProjectionRun.projection_name == "summary",
                        ChapterProjectionRun.source_hash == Chapter.source_hash,
                    ),
                )
                .where(
                    projection_outbox_filter,
                    ChapterOutboxEvent.revision == Chapter.current_revision,
                    ChapterProjectionRun.id.is_(None),
                )
            )
        ).one()
        oldest_backlog_age = age_seconds(oldest_backlog_at)

        generation_mismatch = int(
            await self.session.scalar(
                select(func.count(ChapterProjectionRun.id))
                .select_from(ChapterProjectionRun)
                .join(Chapter, Chapter.id == ChapterProjectionRun.chapter_id)
                .where(
                    ChapterProjectionRun.is_active.is_(True),
                    or_(
                        ChapterProjectionRun.revision != Chapter.current_revision,
                        Chapter.source_hash.is_(None),
                        ChapterProjectionRun.source_hash != Chapter.source_hash,
                    ),
                )
            )
            or 0
        )
        reconcile_count, reconcile_latency = (
            await self.session.execute(
                select(
                    func.count(ChapterProjectionRun.id),
                    func.avg(
                        func.extract(
                            "epoch",
                            ChapterProjectionRun.updated_at - ChapterProjectionRun.created_at,
                        )
                    ),
                ).where(
                    ChapterProjectionRun.projection_name == "reconcile",
                    ChapterProjectionRun.status == "succeeded",
                )
            )
        ).one()

        projection_job = or_(
            BackgroundTask.task_type == "chapter_outbox_dispatch",
            and_(
                BackgroundTask.task_type == "chapter_finalize",
                BackgroundTask.payload_version == FINALIZE_PAYLOAD_VERSION,
                or_(
                    BackgroundTask.payload["execution_mode"].as_string().is_(None),
                    BackgroundTask.payload["execution_mode"].as_string() != "legacy",
                ),
            ),
            BackgroundTask.task_type.like("chapter_projection_%"),
        )
        job_age_anchor = case(
            (BackgroundTask.status == "queued", BackgroundTask.created_at),
            (BackgroundTask.status == "running", BackgroundTask.started_at),
            (BackgroundTask.status == "retry_wait", BackgroundTask.updated_at),
            (
                BackgroundTask.status == "dead_letter",
                BackgroundTask.dead_lettered_at,
            ),
            else_=BackgroundTask.updated_at,
        )
        projection_job_rows = (
            await self.session.execute(
                select(
                    BackgroundTask.status,
                    func.count(BackgroundTask.id),
                    func.min(job_age_anchor),
                )
                .where(projection_job)
                .group_by(BackgroundTask.status)
            )
        ).all()
        projection_job_status_counts = {
            str(status): int(count)
            for status, count, _oldest_at in projection_job_rows
        }
        operational_statuses = {
            "queued",
            "running",
            "retry_wait",
            "needs_attention",
            "dead_letter",
        }
        projection_job_oldest_age_seconds = {
            str(status): age
            for status, _count, oldest_at in projection_job_rows
            if status in operational_statuses
            and (age := age_seconds(oldest_at)) is not None
        }
        expired_lease_count, oldest_expired_lease_at = (
            await self.session.execute(
                select(
                    func.count(BackgroundTask.id),
                    func.min(BackgroundTask.lease_expires_at),
                ).where(
                    projection_job,
                    BackgroundTask.status == "running",
                    BackgroundTask.lease_expires_at.is_not(None),
                    BackgroundTask.lease_expires_at <= checked_at,
                )
            )
        ).one()
        projection_reclaim_event_count = int(
            await self.session.scalar(
                select(func.count(JobEvent.cursor))
                .select_from(JobEvent)
                .join(BackgroundTask, BackgroundTask.id == JobEvent.job_id)
                .where(projection_job, JobEvent.event_type == "job.reclaimed")
            )
            or 0
        )
        external_count, external_latency = (
            await self.session.execute(
                select(
                    func.count(JobActivity.id),
                    func.avg(
                        func.extract(
                            "epoch",
                            JobActivity.completed_at - JobActivity.started_at,
                        )
                    ),
                )
                .select_from(JobActivity)
                .join(BackgroundTask, BackgroundTask.id == JobActivity.job_id)
                .where(
                    projection_job,
                    JobActivity.side_effect_class.in_(_EXTERNAL_SIDE_EFFECT_CLASSES),
                    JobActivity.status == "succeeded",
                )
            )
        ).one()
        ambiguous_external = int(
            await self.session.scalar(
                select(func.count(JobActivity.id))
                .select_from(JobActivity)
                .join(BackgroundTask, BackgroundTask.id == JobActivity.job_id)
                .where(
                    projection_job,
                    JobActivity.side_effect_class.in_(_EXTERNAL_SIDE_EFFECT_CLASSES),
                    JobActivity.status == "ambiguous",
                )
            )
            or 0
        )
        external_status_rows = (
            await self.session.execute(
                select(JobActivity.status, func.count(JobActivity.id))
                .select_from(JobActivity)
                .join(BackgroundTask, BackgroundTask.id == JobActivity.job_id)
                .where(
                    projection_job,
                    JobActivity.side_effect_class.in_(_EXTERNAL_SIDE_EFFECT_CLASSES),
                )
                .group_by(JobActivity.status)
            )
        ).all()
        external_status_counts: dict[str, int] = {}
        for status, count in external_status_rows:
            status_key = str(status)
            if status_key not in _EXTERNAL_ACTIVITY_STATUSES:
                status_key = "unknown"
            external_status_counts[status_key] = (
                external_status_counts.get(status_key, 0) + int(count)
            )
        cost_envelope_known = and_(
            AIUsageRecord.cost_known.is_(True),
            AIUsageRecord.cost_amount.is_not(None),
            AIUsageRecord.cost_currency.is_not(None),
        )
        cost_envelope_unknown = or_(
            AIUsageRecord.cost_known.is_(False),
            AIUsageRecord.cost_amount.is_(None),
            AIUsageRecord.cost_currency.is_(None),
        )
        cost_unknown_reason = case(
            (
                and_(
                    AIUsageRecord.cost_known.is_(True),
                    or_(
                        AIUsageRecord.cost_amount.is_(None),
                        AIUsageRecord.cost_currency.is_(None),
                    ),
                ),
                "cost_envelope_invalid",
            ),
            (AIUsageRecord.cost_unknown_reason.is_(None), "unspecified"),
            else_=AIUsageRecord.cost_unknown_reason,
        )
        (
            ai_usage_record_count,
            ai_usage_incomplete_count,
            input_tokens_total,
            output_tokens_total,
            total_tokens_total,
            cached_input_tokens_total,
            cache_write_input_tokens_total,
            reasoning_tokens_total,
            ai_cost_known_count,
            ai_cost_unknown_count,
        ) = (
            await self.session.execute(
                select(
                    func.count(AIUsageRecord.job_activity_id),
                    func.coalesce(
                        func.sum(
                            case((AIUsageRecord.usage_complete.is_(False), 1), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(func.sum(AIUsageRecord.input_tokens), 0),
                    func.coalesce(func.sum(AIUsageRecord.output_tokens), 0),
                    func.coalesce(func.sum(AIUsageRecord.total_tokens), 0),
                    func.coalesce(func.sum(AIUsageRecord.cached_input_tokens), 0),
                    func.coalesce(
                        func.sum(AIUsageRecord.cache_write_input_tokens),
                        0,
                    ),
                    func.coalesce(func.sum(AIUsageRecord.reasoning_tokens), 0),
                    func.coalesce(
                        func.sum(
                            case((cost_envelope_known, 1), else_=0)
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(
                            case((cost_envelope_unknown, 1), else_=0)
                        ),
                        0,
                    ),
                )
                .select_from(AIUsageRecord)
                .join(BackgroundTask, BackgroundTask.id == AIUsageRecord.job_id)
                .where(projection_job)
            )
        ).one()
        ai_cost_rows = (
            await self.session.execute(
                select(
                    AIUsageRecord.cost_currency,
                    func.sum(AIUsageRecord.cost_amount),
                )
                .select_from(AIUsageRecord)
                .join(BackgroundTask, BackgroundTask.id == AIUsageRecord.job_id)
                .where(
                    projection_job,
                    cost_envelope_known,
                )
                .group_by(AIUsageRecord.cost_currency)
            )
        ).all()
        ai_cost_totals = {
            str(currency): str(amount) for currency, amount in ai_cost_rows
        }
        ai_cost_unknown_rows = (
            await self.session.execute(
                select(
                    cost_unknown_reason,
                    func.count(AIUsageRecord.job_activity_id),
                )
                .select_from(AIUsageRecord)
                .join(BackgroundTask, BackgroundTask.id == AIUsageRecord.job_id)
                .where(
                    projection_job,
                    cost_envelope_unknown,
                )
                .group_by(cost_unknown_reason)
            )
        ).all()
        ai_cost_unknown_counts: dict[str, int] = {}
        for reason, count in ai_cost_unknown_rows:
            reason_key = str(reason or "unspecified")
            if reason_key not in _AI_COST_UNKNOWN_REASONS:
                reason_key = "other"
            ai_cost_unknown_counts[reason_key] = (
                ai_cost_unknown_counts.get(reason_key, 0) + int(count)
            )
        rollout_rows = (
            await self.session.execute(
                select(
                    ChapterProjectionRollout.owner,
                    ChapterProjectionRollout.state,
                    func.count(ChapterProjectionRollout.id),
                ).group_by(
                    ChapterProjectionRollout.owner,
                    ChapterProjectionRollout.state,
                )
            )
        ).all()
        rollout_counts = {
            f"{owner}.{state}": int(count)
            for owner, state, count in rollout_rows
        }
        rollout_transition_rows = (
            await self.session.execute(
                select(
                    ChapterProjectionRolloutTransition.from_owner,
                    ChapterProjectionRolloutTransition.from_state,
                    ChapterProjectionRolloutTransition.to_owner,
                    ChapterProjectionRolloutTransition.to_state,
                    func.count(ChapterProjectionRolloutTransition.id),
                ).group_by(
                    ChapterProjectionRolloutTransition.from_owner,
                    ChapterProjectionRolloutTransition.from_state,
                    ChapterProjectionRolloutTransition.to_owner,
                    ChapterProjectionRolloutTransition.to_state,
                )
            )
        ).all()
        rollout_transition_counts = {
            f"{from_owner or 'none'}.{from_state or 'none'}->"
            f"{to_owner}.{to_state}": int(count)
            for from_owner, from_state, to_owner, to_state, count in rollout_transition_rows
        }
        shadow_rollout_filter = ChapterProjectionRollout.state.in_(("shadow", "draining"))
        shadow_failed_filter = or_(
            ChapterProjectionRollout.failed_observations > 0,
            and_(
                ChapterProjectionRollout.observation_deadline_at.is_not(None),
                ChapterProjectionRollout.observation_deadline_at <= checked_at,
                ChapterProjectionRollout.successful_observations
                < ChapterProjectionRollout.required_observations,
            ),
            ChapterProjectionRollout.shadow_diff["unexplained_count"].as_integer() > 0,
        )
        (
            shadow_rollout_count,
            shadow_required_observations,
            shadow_successful_observations,
            shadow_failed_observations,
            oldest_shadow_started_at,
            next_shadow_deadline_at,
            latest_shadow_observed_at,
            shadow_window_expired_count,
            shadow_failed_rollout_count,
        ) = (
            await self.session.execute(
                select(
                    func.count(ChapterProjectionRollout.id),
                    func.coalesce(func.sum(ChapterProjectionRollout.required_observations), 0),
                    func.coalesce(func.sum(ChapterProjectionRollout.successful_observations), 0),
                    func.coalesce(func.sum(ChapterProjectionRollout.failed_observations), 0),
                    func.min(ChapterProjectionRollout.observation_started_at),
                    func.min(ChapterProjectionRollout.observation_deadline_at),
                    func.max(ChapterProjectionRollout.last_observed_at),
                    func.coalesce(
                        func.sum(
                            case(
                                (
                                    and_(
                                        ChapterProjectionRollout.observation_deadline_at.is_not(None),
                                        ChapterProjectionRollout.observation_deadline_at
                                        <= checked_at,
                                    ),
                                    1,
                                ),
                                else_=0,
                            )
                        ),
                        0,
                    ),
                    func.coalesce(
                        func.sum(case((shadow_failed_filter, 1), else_=0)),
                        0,
                    ),
                ).where(shadow_rollout_filter)
            )
        ).one()
        shadow_observation_rows = (
            await self.session.execute(
                select(
                    ChapterProjectionShadowObservation.outcome,
                    func.count(ChapterProjectionShadowObservation.id),
                )
                .select_from(ChapterProjectionShadowObservation)
                .join(
                    ChapterProjectionRollout,
                    ChapterProjectionRollout.id
                    == ChapterProjectionShadowObservation.rollout_id,
                )
                .where(
                    shadow_rollout_filter,
                    ChapterProjectionShadowObservation.rollout_generation
                    == ChapterProjectionRollout.generation,
                )
                .group_by(ChapterProjectionShadowObservation.outcome)
            )
        ).all()
        shadow_observation_outcome_counts = {
            str(outcome): int(count)
            for outcome, count in shadow_observation_rows
        }
        next_shadow_deadline_seconds = None
        if isinstance(next_shadow_deadline_at, datetime):
            next_shadow_deadline_seconds = max(
                0.0,
                (next_shadow_deadline_at - checked_at).total_seconds(),
            )

        alerts: list[str] = []
        if int(backlog_count or 0) > 0:
            alerts.append("chapter_outbox_backlog")
        if oldest_backlog_age is not None and oldest_backlog_age > 300:
            alerts.append("chapter_outbox_stuck")
        if (
            projection_job_status_counts.get("needs_attention", 0) > 0
            or ambiguous_external > 0
        ):
            alerts.append("chapter_projection_needs_attention")
        if projection_job_status_counts.get("dead_letter", 0) > 0:
            alerts.append("chapter_projection_dead_letter")
        if int(expired_lease_count or 0) > 0:
            alerts.append("chapter_projection_expired_lease")
        if projection_job_oldest_age_seconds.get("retry_wait", 0) > 300:
            alerts.append("chapter_projection_retry_stuck")
        if int(shadow_failed_rollout_count or 0) > 0:
            alerts.append("chapter_projection_shadow_failed")
        if status_counts.get("stale", 0) > 0:
            alerts.append("chapter_projection_stale")
        if generation_mismatch > 0:
            alerts.append("chapter_projection_generation_mismatch")
        if int(ai_cost_unknown_count or 0) > 0:
            alerts.append("chapter_projection_cost_unknown")
        if int(ai_usage_incomplete_count or 0) > 0:
            alerts.append("chapter_projection_usage_incomplete")
        if any(
            external_status_counts.get(status, 0) > 0
            for status in ("failed", "retryable_failed")
        ):
            alerts.append("chapter_projection_external_failed")

        return {
            "outbox_total": outbox_total,
            "projection_outbox_total": projection_outbox_total,
            "legacy_outbox_total": legacy_outbox_total,
            "outbox_backlog": int(backlog_count or 0),
            "outbox_oldest_age_seconds": oldest_backlog_age,
            "status_counts": status_counts,
            "projection_status_counts": projection_status_counts,
            "history_status_counts": history_status_counts,
            "history_projection_status_counts": history_projection_status_counts,
            "projection_job_status_counts": projection_job_status_counts,
            "projection_job_oldest_age_seconds": projection_job_oldest_age_seconds,
            "projection_expired_lease_count": int(expired_lease_count or 0),
            "projection_oldest_expired_lease_age_seconds": age_seconds(
                oldest_expired_lease_at
            ),
            "projection_reclaim_event_count": projection_reclaim_event_count,
            "reconcile_success_count": int(reconcile_count or 0),
            "reconcile_latency_seconds_avg": (
                float(reconcile_latency) if reconcile_latency is not None else None
            ),
            "generation_mismatch": generation_mismatch,
            "external_success_count": int(external_count or 0),
            "external_latency_seconds_avg": (
                float(external_latency) if external_latency is not None else None
            ),
            "ambiguous_external": ambiguous_external,
            "external_status_counts": external_status_counts,
            "ai_usage_record_count": int(ai_usage_record_count or 0),
            "ai_usage_incomplete_count": int(ai_usage_incomplete_count or 0),
            "ai_usage_token_totals": {
                "input": int(input_tokens_total or 0),
                "output": int(output_tokens_total or 0),
                "total": int(total_tokens_total or 0),
                "cached_input": int(cached_input_tokens_total or 0),
                "cache_write_input": int(cache_write_input_tokens_total or 0),
                "reasoning": int(reasoning_tokens_total or 0),
            },
            "ai_cost_known_count": int(ai_cost_known_count or 0),
            "ai_cost_unknown_count": int(ai_cost_unknown_count or 0),
            "ai_cost_totals": ai_cost_totals,
            "ai_cost_unknown_counts": ai_cost_unknown_counts,
            "rollout_counts": rollout_counts,
            "rollout_transition_counts": rollout_transition_counts,
            "shadow_rollout_count": int(shadow_rollout_count or 0),
            "shadow_required_observations": int(shadow_required_observations or 0),
            "shadow_successful_observations": int(shadow_successful_observations or 0),
            "shadow_failed_observations": int(shadow_failed_observations or 0),
            "shadow_observation_outcome_counts": shadow_observation_outcome_counts,
            "shadow_oldest_window_age_seconds": age_seconds(oldest_shadow_started_at),
            "shadow_next_deadline_seconds": next_shadow_deadline_seconds,
            "shadow_last_observed_age_seconds": age_seconds(latest_shadow_observed_at),
            "shadow_window_expired_count": int(shadow_window_expired_count or 0),
            "shadow_failed_rollout_count": int(shadow_failed_rollout_count or 0),
            "alerts": alerts,
        }


__all__ = [
    "CanonicalFinalizeResult",
    "ChapterFinalizeConflictError",
    "ChapterProjectionService",
    "FINALIZE_EVENT_TYPE",
    "FINALIZE_PAYLOAD_VERSION",
    "PROJECTION_JOB_PAYLOAD_VERSION",
    "payload_fingerprint",
]
