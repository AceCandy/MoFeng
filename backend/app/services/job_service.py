# AIMETA P=持久任务服务_任务与事件原子写入|R=幂等入队_事件游标查询|NR=不执行具体任务handler|E=JobService|X=internal|A=transition_service|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from hashlib import sha256
from typing import Any, Awaitable, Callable, Optional, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.background_task import BackgroundTask
from ..models.chapter_generation_trace import ChapterGenerationTrace
from ..models.chapter_projection import ChapterProjectionRun, ChapterRevision
from ..models.chapter_workflow import ChapterWorkflowCommand, ChapterWorkflowRun
from ..models.job import AIUsageRecord, JobActivity, JobEvent, JobWorkerHeartbeat
from ..models.novel import Chapter, ChapterEvaluation, ChapterVersion
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..repositories.job_repository import JobRepository
from ..schemas.chapter_workflow import (
    ChapterWorkflowCommandEnvelope,
    ChapterWorkflowCommandType,
    ChapterWorkflowSnapshot,
    ChapterWorkflowStateV1,
)
from ..schemas.job import ChapterWorkflowJobPayload
from ..utils.ai_telemetry import AICallResult
from .chapter_projection_state import retryable_projection_names
from .chapter_workflow_transition import (
    CHAPTER_WORKFLOW_NODE_LABELS,
    ChapterWorkflowEvent,
    ChapterWorkflowTransition,
    ChapterWorkflowTransitionAdapter,
    LockedChapterWorkflowTransition,
)
from .event_bus import publish_background_task
from .job_public_projection import public_job_snapshot, sanitize_public_text
from .job_registry import SideEffectClass


class LeaseLostError(RuntimeError):
    """worker 的 lease 或 fencing token 已失效。"""


class AmbiguousActivityError(RuntimeError):
    """外部调用可能已发生，禁止自动重放。"""


class ChapterWorkflowCommandRejectedError(ValueError):
    """持久 workflow command 未通过锁内审计校验。"""

    def __init__(self, reason_code: str):
        super().__init__(f"workflow command 已拒绝：{reason_code}")
        self.reason_code = reason_code


class ExecutorGenerationInactiveError(RuntimeError):
    """worker 所属 generation 已失去新任务 claim 权。"""

    def __init__(self, requested_generation: int, active_generation: int):
        super().__init__(
            f"executor generation {requested_generation} 已停用，当前为 {active_generation}"
        )
        self.requested_generation = requested_generation
        self.active_generation = active_generation


class EventCursorExpiredError(RuntimeError):
    """客户端游标早于已清理事件，必须重新获取 snapshot。"""

    def __init__(self, retained_through_cursor: int):
        super().__init__("任务事件游标已过期，必须重新获取快照")
        self.retained_through_cursor = retained_through_cursor


class JobStreamNotFoundError(LookupError):
    """事件流不存在或不属于当前用户；对外统一映射为 404。"""


@dataclass(frozen=True)
class JobLease:
    """claim 后交给 handler 的不可变执行凭证。"""

    job_id: str
    worker_id: str
    fencing_token: int
    attempt: int
    max_attempts: int
    job_type: str
    payload_version: int
    payload: dict[str, Any]
    user_id: int
    project_id: Optional[str]
    executor_generation: int
    lease_expires_at: datetime


@dataclass(frozen=True)
class RetryPolicy:
    """指数 backoff；按 job/attempt 生成确定性 jitter，避免 worker 重启改变计划。"""

    base_delay_seconds: float = 5.0
    max_delay_seconds: float = 300.0
    jitter_ratio: float = 0.2

    def delay_seconds(self, *, job_id: str, attempt: int) -> float:
        if self.base_delay_seconds < 0 or self.max_delay_seconds < 0:
            raise ValueError("retry delay 不能小于 0")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio 必须在 0 到 1 之间")
        raw_delay = min(
            self.max_delay_seconds,
            self.base_delay_seconds * (2 ** max(0, attempt - 1)),
        )
        if self.jitter_ratio == 0 or raw_delay == 0:
            return float(raw_delay)
        digest = sha256(f"{job_id}:{attempt}".encode("utf-8")).digest()
        unit = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
        factor = 1 - self.jitter_ratio + (2 * self.jitter_ratio * unit)
        return float(min(self.max_delay_seconds, raw_delay * factor))


@dataclass(frozen=True)
class HeartbeatResult:
    """heartbeat 返回 worker 是否应停止当前 handler。"""

    cancel_requested: bool


@dataclass(frozen=True)
class ActivityExecution:
    """handler 应执行 provider 调用，或直接复用已持久化结果。"""

    activity_key: str
    provider_request_key: str
    should_execute: bool
    result: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class ChapterWorkflowPendingResume:
    """已在 root lease 与 workflow 锁序下验证的 checkpoint resume。"""

    command_id: str
    command_type: str
    expected_checkpoint_id: str
    resume_value: dict[str, object]


@dataclass(frozen=True)
class ChapterWorkflowAutomaticResume:
    """由 canonical Chapter projection 事实触发的非人工 checkpoint resume。"""

    resume_value: dict[str, object]


@dataclass(frozen=True)
class ChapterWorkflowCheckpointEvidence:
    """在 SQLAlchemy 锁事务之前读取的 latest checkpoint 只读证据。"""

    checkpoint_id: Optional[str]
    state: Optional[ChapterWorkflowStateV1]
    reason_code: Optional[str] = None


@dataclass(frozen=True)
class ChapterWorkflowReconcileResult:
    """单个 run 的稳定 reconciliation outcome。"""

    action: str
    reason_code: Optional[str] = None


@dataclass(frozen=True)
class JobSnapshot:
    """同一数据库快照中的当前任务列表与事件续传游标。"""

    jobs: list[BackgroundTask]
    resume_cursor: int
    snapshot_revision: str
    stream_type: Optional[str] = None
    stream_id: Optional[str] = None


@dataclass(frozen=True)
class JobEventCleanupResult:
    """一次事件保留清理的可观测结果。"""

    deleted_events: int
    affected_user_ids: tuple[int, ...]


@dataclass(frozen=True)
class JobWorkerHealth:
    """worker heartbeat 的只读健康判断。"""

    healthy: bool
    worker_id: Optional[str]
    state: Optional[str]
    heartbeat_age_seconds: Optional[float]


@dataclass(frozen=True)
class JobRuntimeMetrics:
    """durable runtime 的无敏感聚合指标。"""

    status_counts: dict[str, int]
    queue_depth: int
    oldest_queued_age_seconds: Optional[float]
    expired_leases: int
    latest_event_cursor: int
    retained_event_count: int
    retention_users: int
    event_lag: int = 0
    oldest_event_lag_seconds: Optional[float] = None
    retained_event_bytes: int = 0
    retention_budget_bytes: int = 0
    alerts: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExecutorRolloutResult:
    """一次 compare-and-swap worker generation 切换结果。"""

    previous_generation: int
    active_generation: int
    fencing_token: int
    reassigned_waiting_jobs: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _log_entry(
    message: str, *, level: str = "info", now: Optional[datetime] = None
) -> dict[str, str]:
    return {
        "timestamp": (now or _utc_now()).isoformat(),
        "level": level,
        "message": message,
    }


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


class JobService:
    """持有 durable job current row 与 append-only event 的事务边界。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = JobRepository(session)
        self.workflow_repo = ChapterWorkflowRepository(session)
        self.workflow_transitions = ChapterWorkflowTransitionAdapter(session)

    async def enqueue_job(
        self,
        *,
        user_id: int,
        job_type: str,
        title: str,
        project_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        payload_version: int = 1,
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
        stream_type: Optional[str] = None,
        stream_id: Optional[str] = None,
    ) -> BackgroundTask:
        """Create and publish a job, committing the caller's current transaction."""

        return await self._enqueue_job(
            user_id=user_id,
            job_type=job_type,
            title=title,
            project_id=project_id,
            payload=payload,
            payload_version=payload_version,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
            stream_type=stream_type,
            stream_id=stream_id,
            commit=True,
        )

    async def enqueue_job_in_transaction(
        self,
        *,
        user_id: int,
        job_type: str,
        title: str,
        project_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
        payload_version: int = 1,
        idempotency_key: Optional[str] = None,
        max_attempts: int = 3,
        stream_type: Optional[str] = None,
        stream_id: Optional[str] = None,
    ) -> BackgroundTask:
        """Flush a queued job into the caller-owned transaction without publishing."""

        return await self._enqueue_job(
            user_id=user_id,
            job_type=job_type,
            title=title,
            project_id=project_id,
            payload=payload,
            payload_version=payload_version,
            idempotency_key=idempotency_key,
            max_attempts=max_attempts,
            stream_type=stream_type,
            stream_id=stream_id,
            commit=False,
        )

    async def append_workflow_started_in_transaction(
        self,
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        now: Optional[datetime] = None,
    ) -> JobEvent:
        """为同事务新建的 root job/run 追加首个 workflow 领域事件。"""

        self.assert_workflow_root_identity(job=job, run=run)
        created_at = now or _utc_now()
        sequence = await self._next_stream_sequence(job)
        job.updated_at = created_at
        await self.session.flush()
        return await self.repo.add_event(
            JobEvent(
                job_id=job.id,
                user_id=job.user_id,
                project_id=job.project_id,
                stream_type="workflow",
                stream_id=run.id,
                sequence=sequence,
                event_type="workflow.started",
                payload={
                    "task": public_job_snapshot(job),
                    "workflow": {
                        "run_id": run.id,
                        "row_revision": run.row_revision,
                        "node_key": run.node_key,
                        "status": run.status,
                        "checkpoint_id": run.checkpoint_id,
                        "progress": run.progress,
                    },
                },
                created_at=created_at,
            )
        )

    @staticmethod
    def assert_workflow_root_identity(
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
    ) -> None:
        """失败关闭任何 root job、run、冻结输入之间的身份漂移。"""

        try:
            payload = ChapterWorkflowJobPayload.model_validate(job.payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("workflow root JobRun payload 无效") from exc
        if (
            job.task_type != "chapter_workflow"
            or job.payload_version != 1
            or job.stream_type != "workflow"
            or job.stream_id != run.id
            or job.id != run.root_job_id
            or job.user_id != run.user_id
            or job.project_id != run.project_id
            or payload.run_id != run.id
            or payload.project_id != run.project_id
            or payload.chapter_id != run.chapter_id
            or payload.chapter_number != run.chapter_number
            or payload.base_revision != run.base_revision
            or payload.workflow_version != run.workflow_version
            or payload.state_schema_version != run.state_schema_version
            or payload.context_schema_version != run.context_schema_version
            or payload.context_hash != run.context_hash
            or payload.runtime_input_hash != run.runtime_input_hash
        ):
            raise ValueError("workflow root JobRun 与 run 冻结身份不一致")

    async def _enqueue_job(
        self,
        *,
        user_id: int,
        job_type: str,
        title: str,
        project_id: Optional[str],
        payload: Optional[dict[str, Any]],
        payload_version: int,
        idempotency_key: Optional[str],
        max_attempts: int,
        stream_type: Optional[str],
        stream_id: Optional[str],
        commit: bool,
    ) -> BackgroundTask:
        if payload_version < 1:
            raise ValueError("payload_version 必须大于等于 1")
        if max_attempts < 1:
            raise ValueError("max_attempts 必须大于等于 1")
        if idempotency_key is not None and not idempotency_key.strip():
            raise ValueError("idempotency_key 不能为空")
        if idempotency_key is not None and len(idempotency_key) > 255:
            raise ValueError("idempotency_key 长度不能超过 255")
        requested_stream = self._validate_requested_stream(stream_type, stream_id)
        if project_id is not None and not await self.repo.is_project_owned_by_user(
            project_id=project_id,
            user_id=user_id,
        ):
            raise ValueError("项目不存在")

        normalized_key = idempotency_key.strip() if idempotency_key is not None else None
        canonical_payload = payload if payload is not None else {}
        if not isinstance(canonical_payload, dict):
            raise ValueError("payload 必须是 JSON 对象")
        try:
            payload_size_bytes = len(_canonical_json(canonical_payload).encode("utf-8"))
        except (TypeError, ValueError) as exc:
            raise ValueError("payload 必须是 JSON 可序列化对象") from exc
        if payload_size_bytes > settings.job_payload_max_bytes:
            raise ValueError("payload 大小不能超过 " f"{settings.job_payload_max_bytes} 字节")
        if normalized_key is not None:
            existing = await self.repo.get_by_idempotency_key(
                user_id=user_id,
                job_type=job_type,
                idempotency_key=normalized_key,
            )
            if existing is not None:
                expected_stream = requested_stream or ("job", existing.id)
                self._assert_idempotent_request(
                    existing,
                    project_id,
                    payload_version,
                    canonical_payload,
                    expected_stream,
                )
                return existing

        now = _utc_now()
        job_id = str(uuid4())
        resolved_stream_type, resolved_stream_id = requested_stream or ("job", job_id)
        control = await self.repo.get_executor_control()
        if control is None:
            await self.session.rollback()
            raise RuntimeError("缺少 job executor control，请先执行数据库迁移")
        job = BackgroundTask(
            id=job_id,
            user_id=user_id,
            project_id=project_id,
            task_type=job_type,
            title=title,
            status="queued",
            progress=0,
            payload=canonical_payload,
            result=None,
            error=None,
            log_entries=[_log_entry("任务已创建，等待后台执行", now=now)],
            payload_version=payload_version,
            idempotency_key=normalized_key,
            available_at=now,
            attempt=0,
            max_attempts=max_attempts,
            fencing_token=0,
            executor_generation=control.active_generation,
            stream_type=resolved_stream_type,
            stream_id=resolved_stream_id,
            event_sequence=0,
            created_at=now,
            updated_at=now,
        )

        try:
            sequence = await self._next_stream_sequence(job)
            await self.repo.add(job)
            await self.repo.add_event(
                JobEvent(
                    job_id=job.id,
                    user_id=job.user_id,
                    project_id=job.project_id,
                    stream_type=job.stream_type,
                    stream_id=job.stream_id,
                    sequence=sequence,
                    event_type="job.queued",
                    payload={"task": public_job_snapshot(job)},
                )
            )
            if commit:
                await self.session.commit()
            else:
                await self.session.flush()
        except IntegrityError:
            if not commit:
                raise
            await self.session.rollback()
            if normalized_key is None:
                raise
            existing = await self.repo.get_by_idempotency_key(
                user_id=user_id,
                job_type=job_type,
                idempotency_key=normalized_key,
            )
            if existing is None:
                raise
            expected_stream = requested_stream or ("job", existing.id)
            self._assert_idempotent_request(
                existing,
                project_id,
                payload_version,
                canonical_payload,
                expected_stream,
            )
            return existing

        if commit:
            await self.session.refresh(job)
            await publish_background_task(job.user_id)
        return job

    async def get_job(self, job_id: str) -> Optional[BackgroundTask]:
        return await self.repo.get(id=job_id)

    async def get_user_task(
        self,
        job_id: str,
        *,
        user_id: int,
    ) -> Optional[BackgroundTask]:
        return await self.repo.get_user_job(job_id, user_id=user_id)

    async def list_user_tasks(
        self,
        *,
        user_id: int,
        limit: int = 20,
    ) -> list[BackgroundTask]:
        return cast(
            list[BackgroundTask],
            await self.repo.list_user_jobs(
                user_id=user_id,
                limit=max(1, min(limit, 50)),
            ),
        )

    async def get_snapshot(
        self,
        *,
        user_id: int,
        limit: int = 20,
    ) -> JobSnapshot:
        jobs, resume_cursor = await self.repo.get_user_snapshot(
            user_id=user_id,
            limit=max(1, min(limit, 50)),
        )
        return JobSnapshot(
            jobs=jobs,
            resume_cursor=resume_cursor,
            snapshot_revision=f"cursor:{resume_cursor}",
        )

    async def get_stream_snapshot(
        self,
        *,
        user_id: int,
        stream_type: str,
        stream_id: str,
        limit: int = 20,
    ) -> JobSnapshot:
        normalized_type, normalized_id = self._validate_stream_identity(
            stream_type,
            stream_id,
        )
        snapshot = await self.repo.get_user_stream_snapshot(
            user_id=user_id,
            stream_type=normalized_type,
            stream_id=normalized_id,
            limit=max(1, min(limit, 50)),
        )
        if snapshot is None:
            raise JobStreamNotFoundError("未找到任务事件流")
        jobs, resume_cursor, last_sequence = snapshot
        return JobSnapshot(
            jobs=jobs,
            resume_cursor=resume_cursor,
            snapshot_revision=(
                f"stream:{normalized_type}:{normalized_id}:"
                f"sequence:{last_sequence}:cursor:{resume_cursor}"
            ),
            stream_type=normalized_type,
            stream_id=normalized_id,
        )

    async def get_chapter_workflow_snapshot(
        self,
        run_id: str,
        *,
        user_id: int,
    ) -> ChapterWorkflowSnapshot:
        """按 workflow 锁序返回事实一致且不含私有 payload 的 command 快照。"""

        run_ref = await self.workflow_repo.get_user_run(run_id, user_id=user_id)
        if run_ref is None:
            await self.session.rollback()
            raise ValueError("workflow run 不存在")
        job = await self.repo.get_for_update(run_ref.root_job_id)
        if job is None:
            await self.session.rollback()
            raise ValueError("workflow run 绑定的 root JobRun 不存在")
        workflow_context = await self.workflow_transitions.lock_for_job(job)
        if workflow_context is None or workflow_context.run.id != run_id:
            await self.session.rollback()
            raise ValueError("workflow run 与 root JobRun 身份不一致")
        ambiguous_activities = await self.repo.list_ambiguous_activities(job_id=job.id)
        projection_retry_available = await self._has_retryable_workflow_projection(workflow_context)
        stream_snapshot = await self.repo.get_user_stream_snapshot(
            user_id=user_id,
            stream_type="workflow",
            stream_id=run_id,
            limit=1,
        )
        if stream_snapshot is None:
            await self.session.rollback()
            raise ValueError("workflow run 缺少事件流")
        _, resume_cursor, _ = stream_snapshot
        run = workflow_context.run
        retry_activity_key = self._retryable_external_activity_key(
            ambiguous_activities=ambiguous_activities,
            workflow_context=workflow_context,
        )
        snapshot = ChapterWorkflowSnapshot(
            run_id=run.id,
            root_job_id=job.id,
            project_id=run.project_id,
            chapter_id=workflow_context.chapter.id,
            chapter_number=run.chapter_number,
            base_revision=run.base_revision,
            current_chapter_revision=workflow_context.chapter.current_revision,
            workflow_version=run.workflow_version,
            state_schema_version=run.state_schema_version,
            context_schema_version=run.context_schema_version,
            status=run.status,
            root_job_status=job.status,
            node_key=run.node_key,
            checkpoint_id=run.checkpoint_id,
            progress=run.progress,
            row_revision=run.row_revision,
            is_active=run.is_active,
            successor_run_id=run.successor_run_id,
            error_category=run.error_category,
            public_error=(
                sanitize_public_text(run.public_error) if run.public_error is not None else None
            ),
            allowed_commands=self._allowed_workflow_command_types(
                job=job,
                workflow_context=workflow_context,
                ambiguous_activities=ambiguous_activities,
                projection_retry_available=projection_retry_available,
            ),
            retry_activity_key=retry_activity_key,
            resume_cursor=resume_cursor,
        )
        await self.session.commit()
        return snapshot

    async def get_current_chapter_workflow_snapshot(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
    ) -> Optional[ChapterWorkflowSnapshot]:
        """按 owner scope 恢复当前 workflow，并有界追随并发产生的 successor。"""

        run_ref = await self.workflow_repo.get_current_user_run(
            user_id=user_id,
            project_id=project_id,
            chapter_number=chapter_number,
        )
        if run_ref is None:
            await self.session.rollback()
            return None

        snapshot = await self.get_chapter_workflow_snapshot(run_ref.id, user_id=user_id)
        if snapshot.successor_run_id is None:
            return snapshot

        successor = await self.workflow_repo.get_user_run(
            snapshot.successor_run_id,
            user_id=user_id,
        )
        if (
            successor is None
            or successor.project_id != project_id
            or successor.chapter_number != chapter_number
        ):
            await self.session.rollback()
            raise ValueError("workflow run 后继不可用")

        successor_snapshot = await self.get_chapter_workflow_snapshot(
            successor.id,
            user_id=user_id,
        )
        if successor_snapshot.successor_run_id is not None:
            raise ValueError("workflow current lineage 已再次变更")
        return successor_snapshot

    async def reconcile_chapter_workflow(
        self,
        run_id: str,
        *,
        checkpoint: ChapterWorkflowCheckpointEvidence,
        now: Optional[datetime] = None,
    ) -> ChapterWorkflowReconcileResult:
        """按 root JobRun -> run -> Chapter 锁序收敛一个 stale workflow。"""

        reconciled_at = now or _utc_now()
        run_ref = await self.workflow_repo.get(id=run_id)
        if run_ref is None:
            await self.session.commit()
            return ChapterWorkflowReconcileResult("skipped", "workflow_run_missing")

        job = await self.repo.get_for_update(run_ref.root_job_id)
        if job is None:
            await self.session.rollback()
            return ChapterWorkflowReconcileResult("skipped", "root_job_missing")
        run = await self.workflow_repo.get_by_root_job_for_update(job.id)
        if run is None:
            await self._move_job_to_reconcile_attention(
                job,
                reason_code="workflow_run_missing",
                now=reconciled_at,
            )
            await self._append_event(job, "job.needs_attention", now=reconciled_at)
            await self.session.commit()
            await publish_background_task(job.user_id)
            return ChapterWorkflowReconcileResult("needs_attention", "workflow_run_missing")
        if run.id != run_id:
            await self.session.commit()
            return ChapterWorkflowReconcileResult("skipped", "candidate_changed")

        if (
            job.status == "running"
            and job.lease_expires_at is not None
            and job.lease_expires_at > reconciled_at
        ):
            await self.session.commit()
            return ChapterWorkflowReconcileResult("skipped", "active_lease")
        if job.status == "running":
            await self.session.commit()
            return ChapterWorkflowReconcileResult("skipped", "expired_lease_reaper")

        chapter = await self.workflow_transitions.novel_repo.get_chapter_for_update(
            project_id=run.project_id,
            chapter_number=run.chapter_number,
        )
        identity_reason = self._workflow_reconciliation_identity_reason(
            job=job,
            run=run,
            chapter=chapter,
        )
        if identity_reason is not None:
            return await self._fail_closed_workflow_reconciliation(
                job=job,
                run=run,
                reason_code=identity_reason,
                now=reconciled_at,
            )
        assert chapter is not None

        terminal_target = {
            "succeeded": "successful",
            "failed": "failed",
            "dead_letter": "failed",
            "cancelled": "cancelled",
        }.get(job.status)
        if terminal_target is not None and run.is_active:
            return await self._apply_workflow_reconciliation_transition(
                job=job,
                run=run,
                transition=ChapterWorkflowTransition(
                    status=terminal_target,
                    node_key=terminal_target,
                    checkpoint_id=run.checkpoint_id,
                    progress=job.progress,
                    reason_code="root_terminal_run_active",
                ),
                now=reconciled_at,
            )

        if not self._workflow_job_run_status_pair_is_valid(job.status, run.status):
            return await self._fail_closed_workflow_reconciliation(
                job=job,
                run=run,
                reason_code="job_run_status_mismatch",
                now=reconciled_at,
            )

        if (
            job.status == "needs_attention"
            and run.status == "needs_attention"
            and job.error_category == "ambiguous_external_result"
            and run.error_category == "ambiguous_external_result"
        ):
            await self.session.commit()
            return ChapterWorkflowReconcileResult("unchanged", "ambiguous_external_result")

        state = checkpoint.state
        checkpoint_reason = checkpoint.reason_code
        if checkpoint_reason == "checkpoint_read_unavailable":
            await self.session.commit()
            return ChapterWorkflowReconcileResult("skipped", checkpoint_reason)
        expected_initial_without_checkpoint = (
            run.checkpoint_id is None
            and run.status in {"queued", "retry_wait"}
            and run.node_key == "freeze_context"
        )
        if checkpoint_reason is not None and not (
            checkpoint_reason == "checkpoint_missing" and expected_initial_without_checkpoint
        ):
            return await self._fail_closed_workflow_reconciliation(
                job=job,
                run=run,
                reason_code=checkpoint_reason,
                now=reconciled_at,
            )

        if state is not None:
            state_reason = self._workflow_checkpoint_state_reason(run=run, state=state)
            if state_reason is not None:
                return await self._fail_closed_workflow_reconciliation(
                    job=job,
                    run=run,
                    reason_code=state_reason,
                    now=reconciled_at,
                )
            marker_result = await self._reconcile_checkpoint_command_marker(
                job=job,
                run=run,
                chapter=chapter,
                checkpoint=checkpoint,
                now=reconciled_at,
            )
            if marker_result is not None:
                return marker_result
            if checkpoint.checkpoint_id != run.checkpoint_id and job.status in {
                "waiting",
                "needs_attention",
            }:
                return await self._fail_closed_workflow_reconciliation(
                    job=job,
                    run=run,
                    reason_code="checkpoint_drift",
                    now=reconciled_at,
                )
            if (
                checkpoint.checkpoint_id == run.checkpoint_id
                and run.status in {"waiting_for_selection", "projection_pending", "needs_attention"}
                and state.node_key != run.node_key
            ):
                return await self._fail_closed_workflow_reconciliation(
                    job=job,
                    run=run,
                    reason_code="checkpoint_node_drift",
                    now=reconciled_at,
                )

        current_revision = int(chapter.current_revision or 0)
        expected_revision = (
            state.target_chapter_revision
            if run.status == "projection_pending" and state is not None
            else run.base_revision
        )
        if expected_revision is not None and current_revision != expected_revision:
            return await self._supersede_workflow_reconciliation(
                job=job,
                run=run,
                now=reconciled_at,
            )

        if (
            job.status == "waiting"
            and run.status == "projection_pending"
            and state is not None
            and state.target_chapter_revision == current_revision
            and chapter.status == "successful"
        ):
            job.status = "queued"
            job.available_at = reconciled_at
            job.completed_at = None
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry("章节投影已完成，工作流重新排队", now=reconciled_at),
            ]
            return await self._apply_workflow_reconciliation_transition(
                job=job,
                run=run,
                transition=ChapterWorkflowTransition(
                    status="queued",
                    node_key="projection_pending",
                    checkpoint_id=run.checkpoint_id,
                    progress=run.progress,
                    reason_code="projection_completed",
                ),
                now=reconciled_at,
            )

        await self.session.commit()
        return ChapterWorkflowReconcileResult("unchanged")

    @staticmethod
    def _workflow_reconciliation_identity_reason(
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        chapter: Optional[Chapter],
    ) -> Optional[str]:
        if (
            job.stream_type != "workflow"
            or job.stream_id != run.id
            or job.user_id != run.user_id
            or job.project_id != run.project_id
        ):
            return "workflow_identity_mismatch"
        if chapter is None:
            return "chapter_missing"
        if run.chapter_id is None or chapter.id != run.chapter_id:
            return "chapter_binding_mismatch"
        return None

    @staticmethod
    def _workflow_job_run_status_pair_is_valid(job_status: str, run_status: str) -> bool:
        allowed = {
            "queued": {"queued"},
            "running": {"running", "finalizing"},
            "retry_wait": {"retry_wait"},
            "waiting": {"waiting_for_selection", "projection_pending"},
            "needs_attention": {"needs_attention"},
            "succeeded": {"successful"},
            "failed": {"failed"},
            "dead_letter": {"failed"},
            "cancelled": {"cancelled", "superseded"},
        }
        return run_status in allowed.get(job_status, set())

    @staticmethod
    def _workflow_checkpoint_state_reason(
        *,
        run: ChapterWorkflowRun,
        state: ChapterWorkflowStateV1,
    ) -> Optional[str]:
        if state.run_id != run.id or state.context_hash != run.context_hash:
            return "checkpoint_identity_mismatch"
        if (
            state.workflow_version != run.workflow_version
            or state.state_schema_version != run.state_schema_version
        ):
            return "checkpoint_version_unknown"
        return None

    async def _move_job_to_reconcile_attention(
        self,
        job: BackgroundTask,
        *,
        reason_code: str,
        now: datetime,
    ) -> None:
        job.status = "needs_attention"
        job.error_category = reason_code
        job.error = "工作流持久状态不一致，需要人工处理"
        job.completed_at = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("工作流持久状态不一致，已停止自动推进", level="error", now=now),
        ]

    async def _fail_closed_workflow_reconciliation(
        self,
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        reason_code: str,
        now: datetime,
    ) -> ChapterWorkflowReconcileResult:
        if (
            job.status == "needs_attention"
            and job.error_category == reason_code
            and (not run.is_active or run.status == "needs_attention")
        ):
            await self.session.commit()
            return ChapterWorkflowReconcileResult("unchanged", reason_code)

        await self._move_job_to_reconcile_attention(job, reason_code=reason_code, now=now)
        if run.is_active:
            await self._apply_workflow_reconciliation_transition(
                job=job,
                run=run,
                transition=ChapterWorkflowTransition(
                    status="needs_attention",
                    node_key=run.node_key,
                    checkpoint_id=run.checkpoint_id,
                    progress=run.progress,
                    reason_code=reason_code,
                ),
                now=now,
            )
            return ChapterWorkflowReconcileResult("needs_attention", reason_code)

        workflow_event = self.workflow_transitions.reconciliation_snapshot(
            run=run,
            reason_code=reason_code,
        )
        await self._append_event(
            job,
            "workflow.reconciled",
            now=now,
            workflow_event=workflow_event,
        )
        await self.session.commit()
        await publish_background_task(job.user_id)
        return ChapterWorkflowReconcileResult("needs_attention", reason_code)

    async def _supersede_workflow_reconciliation(
        self,
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        now: datetime,
    ) -> ChapterWorkflowReconcileResult:
        job.status = "cancelled"
        job.error_category = "chapter_revision_superseded"
        job.error = "章节 revision 已变化，旧工作流已终止"
        job.cancel_requested_at = job.cancel_requested_at or now
        job.completed_at = now
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("章节 revision 已变化，旧工作流已终止", level="warning", now=now),
        ]
        return await self._apply_workflow_reconciliation_transition(
            job=job,
            run=run,
            transition=ChapterWorkflowTransition(
                status="superseded",
                node_key="superseded",
                checkpoint_id=run.checkpoint_id,
                progress=run.progress,
                reason_code="chapter_revision_superseded",
            ),
            now=now,
        )

    async def _apply_workflow_reconciliation_transition(
        self,
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        transition: ChapterWorkflowTransition,
        now: datetime,
    ) -> ChapterWorkflowReconcileResult:
        workflow_event = self.workflow_transitions.apply_reconciliation(
            job=job,
            run=run,
            now=now,
            transition=transition,
        )
        await self._append_event(
            job,
            "workflow.reconciled",
            now=now,
            workflow_event=workflow_event,
        )
        await self.session.commit()
        await publish_background_task(job.user_id)
        return ChapterWorkflowReconcileResult(
            "reconciled",
            transition.reason_code,
        )

    async def _reconcile_checkpoint_command_marker(
        self,
        *,
        job: BackgroundTask,
        run: ChapterWorkflowRun,
        chapter: Chapter,
        checkpoint: ChapterWorkflowCheckpointEvidence,
        now: datetime,
    ) -> Optional[ChapterWorkflowReconcileResult]:
        state = checkpoint.state
        if (
            state is None
            or state.last_applied_command_id is None
            or checkpoint.checkpoint_id == run.checkpoint_id
        ):
            return None
        pending_commands = await self.workflow_repo.list_pending_commands_for_update(run.id)
        if len(pending_commands) > 1:
            return await self._fail_closed_workflow_reconciliation(
                job=job,
                run=run,
                reason_code="checkpoint_command_mismatch",
                now=now,
            )
        command = (
            pending_commands[0]
            if pending_commands and pending_commands[0].id == state.last_applied_command_id
            else await self.workflow_repo.get_command_for_update(state.last_applied_command_id)
        )
        command_payload = command.payload if command is not None else None
        valid_command_payload = command is not None and (
            (
                command.type == "select"
                and isinstance(command_payload, dict)
                and set(command_payload) == {"selected_version_id"}
                and isinstance(command_payload.get("selected_version_id"), int)
                and not isinstance(command_payload.get("selected_version_id"), bool)
                and command_payload["selected_version_id"] == state.selected_version_id
            )
            or (command.type == "retry_projection" and command_payload == {})
        )
        valid_command = (
            command is not None
            and command.run_id == run.id
            and command.actor_user_id == run.user_id
            and command.payload_version == 1
            and command.type in {"select", "retry_projection"}
            and command.expected_run_revision < run.row_revision
            and command.expected_checkpoint_id == run.checkpoint_id
            and command.expected_chapter_revision == int(chapter.current_revision or 0)
            and self._workflow_command_marker_node_is_valid(
                command_type=command.type,
                node_key=state.node_key,
            )
            and valid_command_payload
            and (
                command.status != "pending"
                or (len(pending_commands) == 1 and pending_commands[0].id == command.id)
            )
        )
        if not valid_command:
            return await self._fail_closed_workflow_reconciliation(
                job=job,
                run=run,
                reason_code="checkpoint_command_mismatch",
                now=now,
            )
        assert command is not None
        if command.status == "applied":
            result = command.result_payload if isinstance(command.result_payload, dict) else {}
            if result.get("marker_checkpoint_id") != checkpoint.checkpoint_id:
                return await self._fail_closed_workflow_reconciliation(
                    job=job,
                    run=run,
                    reason_code="checkpoint_command_mismatch",
                    now=now,
                )
            return None
        if command.status != "pending":
            return await self._fail_closed_workflow_reconciliation(
                job=job,
                run=run,
                reason_code="checkpoint_command_mismatch",
                now=now,
            )

        command.status = "applied"
        command.rejection_code = None
        command.applied_at = now
        command.result_payload = {
            "command_id": command.id,
            "status": "applied",
            "marker_checkpoint_id": checkpoint.checkpoint_id,
        }
        await self._append_event(
            job,
            "workflow.command.applied",
            now=now,
            workflow_context=LockedChapterWorkflowTransition(run=run, chapter=chapter),
            workflow_command=command,
        )
        await self.session.commit()
        await publish_background_task(job.user_id)
        return ChapterWorkflowReconcileResult(
            "command_applied",
            "checkpoint_command_applied",
        )

    @staticmethod
    def _workflow_command_marker_node_is_valid(*, command_type: str, node_key: str) -> bool:
        valid_nodes = {
            "select": {
                "finalize_revision",
                "projection_pending",
                "observe_projection",
                "successful",
            },
            "retry_projection": {"projection_pending"},
        }
        return node_key in valid_nodes.get(command_type, set())

    async def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        now: Optional[datetime] = None,
        executor_generation: int = 1,
    ) -> Optional[JobLease]:
        if not worker_id.strip():
            raise ValueError("worker_id 不能为空")
        if lease_seconds < 1:
            raise ValueError("lease_seconds 必须大于等于 1")

        claimed_at = now or _utc_now()
        while True:
            control = await self.repo.get_executor_control(for_update=True)
            if control is None:
                await self.session.rollback()
                raise RuntimeError("缺少 job executor control，请先执行数据库迁移")
            if control.active_generation != executor_generation:
                active_generation = control.active_generation
                await self.session.commit()
                raise ExecutorGenerationInactiveError(
                    executor_generation,
                    active_generation,
                )

            job = await self.repo.claim_candidate(
                now=claimed_at,
                active_generation=control.active_generation,
            )
            if job is None:
                await self.session.commit()
                return None

            reclaimed = job.status == "running"
            if reclaimed and await self._reap_expired_job(job, now=claimed_at):
                continue

            job.status = "running"
            job.attempt += 1
            job.fencing_token += 1
            job.executor_generation = control.active_generation
            job.lease_owner = worker_id
            job.heartbeat_at = claimed_at
            job.lease_expires_at = claimed_at + timedelta(seconds=lease_seconds)
            job.started_at = job.started_at or claimed_at
            job.progress = max(job.progress, 5)
            job.error = None
            job.error_category = None
            message = "任务 lease 过期，已由新 worker 接管" if reclaimed else "任务开始执行"
            job.log_entries = [*(job.log_entries or []), _log_entry(message, now=claimed_at)]
            await self._append_event(
                job,
                "job.reclaimed" if reclaimed else "job.started",
                now=claimed_at,
            )
            await self.session.commit()
            await self.session.refresh(job)
            await publish_background_task(job.user_id)
            return self._lease_from_job(job)

    async def switch_executor_generation(
        self,
        *,
        expected_generation: int,
        new_generation: int,
        rollout_owner: str,
        now: Optional[datetime] = None,
    ) -> ExecutorRolloutResult:
        if new_generation <= expected_generation:
            raise ValueError("new_generation 必须大于 expected_generation")
        normalized_owner = rollout_owner.strip()
        if not normalized_owner or len(normalized_owner) > 128:
            raise ValueError("rollout_owner 必须为 1 到 128 个字符")

        control = await self.repo.get_executor_control(for_update=True)
        if control is None:
            await self.session.rollback()
            raise RuntimeError("缺少 job executor control，请先执行数据库迁移")
        if control.active_generation != expected_generation:
            active_generation = control.active_generation
            await self.session.rollback()
            raise ExecutorGenerationInactiveError(
                expected_generation,
                active_generation,
            )

        reassigned = await self.repo.reassign_waiting_jobs(
            previous_generation=expected_generation,
            new_generation=new_generation,
        )
        control.active_generation = new_generation
        control.rollout_owner = normalized_owner
        control.fencing_token += 1
        control.updated_at = now or _utc_now()
        await self.session.commit()
        await self.session.refresh(control)
        return ExecutorRolloutResult(
            previous_generation=expected_generation,
            active_generation=control.active_generation,
            fencing_token=control.fencing_token,
            reassigned_waiting_jobs=reassigned,
        )

    async def wait_for_resume(
        self,
        lease: JobLease,
        *,
        outcome_writer: Optional[Callable[[AsyncSession], Awaitable[None]]] = None,
        workflow_transition: Optional[ChapterWorkflowTransition] = None,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        """以当前执行 fence 暂停任务，并在同一事务释放 worker lease。"""

        waiting_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=waiting_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        workflow_context = await self.workflow_transitions.lock_for_job(job)

        if job.cancel_requested_at is not None:
            job.status = "cancelled"
            job.completed_at = waiting_at
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry("任务已取消", level="warning", now=waiting_at),
            ]
            await self._sync_projection_run_status(
                job,
                status="failed",
                error_category="job_cancelled",
            )
            await self._append_event(
                job,
                "job.cancelled",
                now=waiting_at,
                workflow_context=workflow_context,
            )
            await self.session.commit()
            await self.session.refresh(job)
            await publish_background_task(job.user_id)
            return job

        try:
            if outcome_writer is not None:
                await outcome_writer(self.session)
        except Exception:
            await self.session.rollback()
            raise

        job.status = "waiting"
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("任务等待工作流恢复", now=waiting_at),
        ]
        await self._append_event(
            job,
            "workflow.waiting",
            now=waiting_at,
            workflow_context=workflow_context,
            workflow_transition=workflow_transition,
        )
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def resume_waiting(
        self,
        job_id: str,
        *,
        expected_fencing_token: int,
        outcome_writer: Optional[Callable[[AsyncSession], Awaitable[None]]] = None,
        workflow_transition: Optional[ChapterWorkflowTransition] = None,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        """按 waiting 行的 fence 原子重新入队；新 lease 由下一次 claim 创建。"""

        resumed_at = now or _utc_now()
        job = await self.repo.get_for_update(job_id)
        if (
            job is None
            or job.status != "waiting"
            or job.fencing_token != expected_fencing_token
            or job.cancel_requested_at is not None
        ):
            await self.session.rollback()
            raise LeaseLostError("任务 waiting fence 已失效")
        workflow_context = await self.workflow_transitions.lock_for_job(job)
        try:
            if outcome_writer is not None:
                await outcome_writer(self.session)
        except Exception:
            await self.session.rollback()
            raise

        job.status = "queued"
        job.available_at = resumed_at
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("工作流已恢复，任务重新排队", now=resumed_at),
        ]
        await self._append_event(
            job,
            "workflow.phase_changed",
            now=resumed_at,
            workflow_context=workflow_context,
            workflow_transition=workflow_transition,
        )
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def mark_succeeded(
        self,
        lease: JobLease,
        *,
        result: Optional[dict[str, Any]] = None,
        outcome_writer: Optional[Callable[[AsyncSession], Awaitable[None]]] = None,
        workflow_transition: Optional[ChapterWorkflowTransition] = None,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        completed_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=completed_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        workflow_context = await self.workflow_transitions.lock_for_job(job)

        if job.cancel_requested_at is not None:
            job.status = "cancelled"
            job.completed_at = completed_at
            job.lease_owner = None
            job.lease_expires_at = None
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry("任务在提交结果前完成取消", level="warning", now=completed_at),
            ]
            await self._sync_projection_run_status(
                job,
                status="failed",
                error_category="job_cancelled",
            )
            await self._append_event(
                job,
                "job.cancelled",
                now=completed_at,
                workflow_context=workflow_context,
            )
            await self.session.commit()
            await self.session.refresh(job)
            await publish_background_task(job.user_id)
            return job

        try:
            if outcome_writer is not None:
                await outcome_writer(self.session)
        except Exception:
            await self.session.rollback()
            raise

        job.status = "succeeded"
        job.progress = 100
        job.result = result or {}
        job.error = None
        job.error_category = None
        job.completed_at = completed_at
        job.lease_owner = None
        job.lease_expires_at = None
        job.log_entries = [*(job.log_entries or []), _log_entry("任务执行完成", now=completed_at)]
        await self._append_event(
            job,
            "job.succeeded",
            now=completed_at,
            workflow_context=workflow_context,
            workflow_transition=workflow_transition,
        )
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def record_progress(
        self,
        lease: JobLease,
        message: str,
        *,
        progress: Optional[int] = None,
        level: str = "info",
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        recorded_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=recorded_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        if progress is not None:
            job.progress = max(0, min(100, int(progress)))
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry(sanitize_public_text(message), level=level, now=recorded_at),
        ]
        await self._append_event(job, "job.progress", now=recorded_at)
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def mark_dead_letter(
        self,
        lease: JobLease,
        *,
        error_category: str,
        public_message: str,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        dead_lettered_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=dead_lettered_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        job.status = "dead_letter"
        job.error_category = re.sub(r"[^a-z0-9_.-]", "_", error_category.lower())[:64]
        job.error = sanitize_public_text(public_message)
        job.dead_lettered_at = dead_lettered_at
        job.completed_at = dead_lettered_at
        job.lease_owner = None
        job.lease_expires_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry(f"任务进入死信：{job.error}", level="error", now=dead_lettered_at),
        ]
        await self._sync_projection_run_status(
            job,
            status="dead_letter",
            error_category=job.error_category,
        )
        await self._append_event(job, "job.dead_lettered", now=dead_lettered_at)
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def record_failure(
        self,
        lease: JobLease,
        *,
        error_category: str,
        public_message: str,
        retryable: bool,
        retry_policy: Optional[RetryPolicy] = None,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        failed_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=failed_at)
        except LeaseLostError:
            await self.session.rollback()
            raise

        safe_category = re.sub(r"[^a-z0-9_.-]", "_", error_category.strip().lower())[:64]
        safe_category = safe_category or "job_error"
        safe_message = sanitize_public_text(public_message)
        job.error = safe_message
        job.error_category = safe_category
        job.lease_owner = None
        job.lease_expires_at = None

        if retryable and job.attempt < job.max_attempts:
            policy = retry_policy or RetryPolicy()
            delay = policy.delay_seconds(job_id=job.id, attempt=job.attempt)
            job.status = "retry_wait"
            job.available_at = failed_at + timedelta(seconds=delay)
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry(
                    f"任务暂时失败，将在 {delay:.1f} 秒后重试", level="warning", now=failed_at
                ),
            ]
            event_type = "job.retry_scheduled"
        elif retryable:
            job.status = "dead_letter"
            job.dead_lettered_at = failed_at
            job.completed_at = failed_at
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry(f"任务超过最大重试次数：{safe_message}", level="error", now=failed_at),
            ]
            event_type = "job.dead_lettered"
        else:
            job.status = "failed"
            job.completed_at = failed_at
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry(f"任务失败：{safe_message}", level="error", now=failed_at),
            ]
            event_type = "job.failed"

        await self._sync_projection_run_status(
            job,
            status=job.status,
            error_category=safe_category,
        )
        await self._append_event(job, event_type, now=failed_at)
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def request_cancel(
        self,
        job_id: str,
        *,
        user_id: int,
        now: Optional[datetime] = None,
    ) -> Optional[BackgroundTask]:
        requested_at = now or _utc_now()
        job = await self.repo.get_user_job_for_update(job_id, user_id=user_id)
        if job is None:
            await self.session.rollback()
            return None
        if job.status in {"succeeded", "failed", "dead_letter", "needs_attention", "cancelled"}:
            await self.session.commit()
            return job

        if job.cancel_requested_at is not None:
            await self.session.commit()
            return job

        job.cancel_requested_at = requested_at
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("已请求取消任务", level="warning", now=requested_at),
        ]
        if job.status in {"queued", "retry_wait", "waiting"}:
            job.status = "cancelled"
            job.completed_at = requested_at
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
            event_type = "job.cancelled"
            await self._sync_projection_run_status(
                job,
                status="failed",
                error_category="job_cancelled",
            )
        else:
            event_type = "job.cancel_requested"

        await self._append_event(job, event_type, now=requested_at)
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def submit_chapter_workflow_command(
        self,
        run_id: str,
        *,
        actor_user_id: int,
        envelope: ChapterWorkflowCommandEnvelope,
        now: Optional[datetime] = None,
    ) -> ChapterWorkflowCommand:
        """持久化或重放 command，并原子记录接收结果与 waiting requeue。"""

        submitted_at = now or _utc_now()
        run_ref = await self.workflow_repo.get_user_run(run_id, user_id=actor_user_id)
        if run_ref is None:
            await self.session.rollback()
            raise ValueError("workflow run 不存在")

        job = await self.repo.get_for_update(run_ref.root_job_id)
        if job is None:
            await self.session.rollback()
            raise ValueError("workflow command 绑定的 root JobRun 不存在")
        workflow_context = await self.workflow_transitions.lock_for_job(job)
        if workflow_context is None or workflow_context.run.id != run_id:
            await self.session.rollback()
            raise ValueError("workflow command 与 root JobRun 身份不一致")

        existing = await self.workflow_repo.get_command_for_update(envelope.command_id)
        if existing is not None:
            if not self._workflow_command_identity_matches(
                existing,
                run_id=run_id,
                actor_user_id=actor_user_id,
                envelope=envelope,
            ):
                await self.session.rollback()
                raise ValueError("workflow command id 已绑定不同请求")
            rejection_code = existing.rejection_code
            await self.session.commit()
            if existing.status == "rejected":
                raise ChapterWorkflowCommandRejectedError(rejection_code or "command_rejected")
            return existing

        command = ChapterWorkflowCommand(
            id=envelope.command_id,
            run_id=run_id,
            type=envelope.type,
            payload_version=envelope.payload_version,
            payload=dict(envelope.payload),
            actor_user_id=actor_user_id,
            expected_run_revision=envelope.expected_run_revision,
            expected_chapter_revision=envelope.expected_chapter_revision,
            expected_checkpoint_id=envelope.expected_checkpoint_id,
            status="pending",
        )
        self.session.add(command)
        await self.session.flush()

        ambiguous_activities = await self.repo.list_ambiguous_activities(job_id=job.id)
        projection_retry_available = await self._has_retryable_workflow_projection(workflow_context)
        applied_retry = None
        if command.type == "retry":
            applied_retry = await self.workflow_repo.get_applied_retry_for_expected_state(
                run_id=run_id,
                expected_run_revision=command.expected_run_revision,
                expected_chapter_revision=command.expected_chapter_revision,
                expected_checkpoint_id=command.expected_checkpoint_id,
            )
        rejection_code = self._workflow_command_submission_rejection(
            command=command,
            job=job,
            workflow_context=workflow_context,
            ambiguous_activities=ambiguous_activities,
            applied_retry=applied_retry,
            projection_retry_available=projection_retry_available,
        )
        if rejection_code is None:
            command.result_payload = {
                "command_id": command.id,
                "status": "accepted",
            }
            if command.type in {"select", "retry_projection"}:
                job.status = "queued"
                job.available_at = submitted_at
                job.completed_at = None
                job.lease_owner = None
                job.lease_expires_at = None
                job.heartbeat_at = None
                job.log_entries = [
                    *(job.log_entries or []),
                    _log_entry("工作流命令已接收，任务重新排队", now=submitted_at),
                ]
                await self._append_event(
                    job,
                    "workflow.phase_changed",
                    now=submitted_at,
                    workflow_context=workflow_context,
                    workflow_transition=ChapterWorkflowTransition(
                        status="queued",
                        node_key=workflow_context.run.node_key,
                        checkpoint_id=workflow_context.run.checkpoint_id,
                        progress=workflow_context.run.progress,
                    ),
                )
                event_type = "workflow.command.accepted"
            elif command.type == "retry_external" or (command.type == "cancel" and command.payload):
                await self._append_event(
                    job,
                    "workflow.command.accepted",
                    now=submitted_at,
                    workflow_context=workflow_context,
                    workflow_command=command,
                )
                activity_key = command.payload.get("activity_key")
                original = next(
                    (
                        activity
                        for activity in ambiguous_activities
                        if activity.activity_key == activity_key
                    ),
                    None,
                )
                if original is None:
                    await self.session.rollback()
                    raise ValueError("ambiguous command 缺少已验证的 activity")
                if command.type == "retry_external":
                    await self._apply_retry_external_command(
                        command=command,
                        job=job,
                        original=original,
                        workflow_context=workflow_context,
                        applied_at=submitted_at,
                    )
                else:
                    await self._apply_ambiguous_cancel_command(
                        command=command,
                        job=job,
                        original=original,
                        workflow_context=workflow_context,
                        applied_at=submitted_at,
                    )
                await self._append_event(
                    job,
                    "workflow.command.applied",
                    now=submitted_at,
                    workflow_context=workflow_context,
                    workflow_command=command,
                )
                event_type = None
            else:
                await self._append_event(
                    job,
                    "workflow.command.accepted",
                    now=submitted_at,
                    workflow_context=workflow_context,
                    workflow_command=command,
                )
                if command.type == "cancel":
                    await self._apply_standard_cancel_command(
                        command=command,
                        job=job,
                        workflow_context=workflow_context,
                        applied_at=submitted_at,
                    )
                else:
                    await self._apply_determinate_retry_command(
                        command=command,
                        job=job,
                        workflow_context=workflow_context,
                        applied_retry=applied_retry,
                        applied_at=submitted_at,
                    )
                await self._append_event(
                    job,
                    "workflow.command.applied",
                    now=submitted_at,
                    workflow_context=workflow_context,
                    workflow_command=command,
                )
                event_type = None
        else:
            command.status = "rejected"
            command.rejection_code = rejection_code
            command.result_payload = {
                "command_id": command.id,
                "status": "rejected",
                "reason_code": rejection_code,
            }
            event_type = "workflow.command.rejected"

        if event_type is not None:
            await self._append_event(
                job,
                event_type,
                now=submitted_at,
                workflow_context=workflow_context,
                workflow_command=command,
            )
        await self.session.commit()
        await self.session.refresh(command)
        await publish_background_task(job.user_id)
        if rejection_code is not None:
            raise ChapterWorkflowCommandRejectedError(rejection_code)
        return command

    async def prepare_chapter_workflow_resume(
        self,
        lease: JobLease,
        *,
        now: Optional[datetime] = None,
    ) -> Optional[ChapterWorkflowPendingResume | ChapterWorkflowAutomaticResume]:
        """锁定并验证当前 root claim 对应的唯一 checkpoint command。"""

        checked_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=checked_at)
            workflow_context = await self.workflow_transitions.lock_for_job(job)
            if workflow_context is None:
                raise ValueError("Chapter workflow root 缺少 workflow run")
            commands = await self.workflow_repo.list_pending_commands_for_update(
                workflow_context.run.id
            )
            if not commands:
                run = workflow_context.run
                chapter = workflow_context.chapter
                if run.node_key == "projection_pending" and chapter.status == "successful":
                    pending_projection = ChapterWorkflowAutomaticResume(
                        resume_value={
                            "reason": "projection_completed",
                            "target_chapter_revision": int(chapter.current_revision or 0),
                        }
                    )
                    await self.session.commit()
                    return pending_projection
                await self.session.commit()
                return None
            if len(commands) != 1:
                raise ValueError("Chapter workflow 同时存在多个 pending command")

            command = commands[0]
            run = workflow_context.run
            chapter = workflow_context.chapter
            if command.actor_user_id != run.user_id:
                raise ValueError("pending workflow command actor 与 run 不一致")
            if command.expected_checkpoint_id != run.checkpoint_id:
                raise ValueError("pending workflow command 的 checkpoint 已漂移")
            if command.payload_version != 1:
                raise ValueError("pending workflow command payload version 不受支持")

            payload = command.payload if isinstance(command.payload, dict) else {}
            if command.type == "select":
                selected_version_id = payload.get("selected_version_id")
                if (
                    set(payload) != {"selected_version_id"}
                    or isinstance(selected_version_id, bool)
                    or not isinstance(selected_version_id, int)
                    or selected_version_id < 1
                    or run.node_key != "waiting_for_selection"
                ):
                    raise ValueError("pending select command payload 或 checkpoint node 无效")
                if not self._checkpoint_command_chapter_state_matches(
                    command,
                    chapter,
                    allow_pre_resume=True,
                ):
                    raise ValueError("pending select command 的 Chapter identity 已漂移")
                resume_value: dict[str, object] = {
                    "command_id": command.id,
                    "selected_version_id": selected_version_id,
                }
            elif command.type == "retry_projection":
                if payload or run.node_key != "projection_pending":
                    raise ValueError(
                        "pending retry_projection command payload 或 checkpoint node 无效"
                    )
                if not self._checkpoint_command_chapter_state_matches(
                    command,
                    chapter,
                    allow_pre_resume=True,
                ):
                    raise ValueError("pending retry_projection command 的 Chapter revision 已漂移")
                resume_value = {"command_id": command.id}
            else:
                raise ValueError("pending command 不是 checkpoint resume 类型")

            pending = ChapterWorkflowPendingResume(
                command_id=command.id,
                command_type=command.type,
                expected_checkpoint_id=command.expected_checkpoint_id,
                resume_value=resume_value,
            )
            await self.session.commit()
            return pending
        except Exception:
            await self.session.rollback()
            raise

    async def apply_checkpointed_workflow_command(
        self,
        lease: JobLease,
        *,
        command_id: str,
        marker_checkpoint_id: str,
        now: Optional[datetime] = None,
    ) -> ChapterWorkflowCommand:
        """接受同 thread runtime callback 的 marker 并补记 applied；重复调用只重放结果。"""

        applied_at = now or _utc_now()
        if not marker_checkpoint_id.strip():
            raise ValueError("command marker checkpoint id 不能为空")
        try:
            job = await self._require_lease(lease, now=applied_at)
            workflow_context = await self.workflow_transitions.lock_for_job(job)
            if workflow_context is None:
                raise ValueError("Chapter workflow root 缺少 workflow run")
            command = await self.workflow_repo.get_command_for_update(command_id)
            if command is None or command.run_id != workflow_context.run.id:
                raise ValueError("checkpoint marker 与 workflow command 身份不一致")
            if command.status == "applied":
                result = command.result_payload if isinstance(command.result_payload, dict) else {}
                if result.get("marker_checkpoint_id") != marker_checkpoint_id:
                    raise ValueError("已应用 command 的 marker checkpoint 身份漂移")
                await self.session.commit()
                return command
            if command.status != "pending" or command.type not in {
                "select",
                "retry_projection",
            }:
                raise ValueError("checkpoint marker 只能应用 pending resume command")
            if marker_checkpoint_id == command.expected_checkpoint_id:
                raise ValueError("command marker 必须来自 resume 后的新 checkpoint")
            if command.expected_checkpoint_id != workflow_context.run.checkpoint_id:
                raise ValueError("应用 command 时 workflow checkpoint 已漂移")
            chapter = workflow_context.chapter
            if not self._checkpoint_command_chapter_state_matches(
                command,
                chapter,
                allow_pre_resume=False,
            ):
                if command.type == "select":
                    raise ValueError("应用 select command 时 Chapter identity 已漂移")
                raise ValueError("应用 command 时 Chapter revision 已漂移")

            command.status = "applied"
            command.rejection_code = None
            command.applied_at = applied_at
            command.result_payload = {
                "command_id": command.id,
                "status": "applied",
                "marker_checkpoint_id": marker_checkpoint_id,
            }
            await self._append_event(
                job,
                "workflow.command.applied",
                now=applied_at,
                workflow_context=workflow_context,
                workflow_command=command,
            )
            await self.session.commit()
            await self.session.refresh(command)
            await publish_background_task(job.user_id)
            return command
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _checkpoint_command_chapter_state_matches(
        command: ChapterWorkflowCommand,
        chapter: Chapter,
        *,
        allow_pre_resume: bool,
    ) -> bool:
        """区分 resume 前置 revision 与 select finalize 后置 revision。"""

        current_revision = int(chapter.current_revision or 0)
        expected_revision = int(command.expected_chapter_revision)
        if command.type == "retry_projection":
            return current_revision == expected_revision
        if command.type != "select":
            return False
        payload = command.payload if isinstance(command.payload, dict) else {}
        selected_version_id = payload.get("selected_version_id")
        if isinstance(selected_version_id, bool) or not isinstance(selected_version_id, int):
            return False
        if allow_pre_resume and current_revision == expected_revision:
            return True
        return (
            current_revision == expected_revision + 1
            and int(chapter.selected_version_id or 0) == selected_version_id
        )

    @staticmethod
    def _workflow_command_identity_matches(
        command: ChapterWorkflowCommand,
        *,
        run_id: str,
        actor_user_id: int,
        envelope: ChapterWorkflowCommandEnvelope,
    ) -> bool:
        return (
            command.run_id == run_id
            and command.actor_user_id == actor_user_id
            and command.type == envelope.type
            and command.payload_version == envelope.payload_version
            and _canonical_json(command.payload or {}) == _canonical_json(envelope.payload)
            and command.expected_run_revision == envelope.expected_run_revision
            and command.expected_chapter_revision == envelope.expected_chapter_revision
            and command.expected_checkpoint_id == envelope.expected_checkpoint_id
        )

    @staticmethod
    def _workflow_command_submission_rejection(
        *,
        command: ChapterWorkflowCommand,
        job: BackgroundTask,
        workflow_context: LockedChapterWorkflowTransition,
        ambiguous_activities: list[JobActivity],
        applied_retry: Optional[ChapterWorkflowCommand],
        projection_retry_available: bool,
    ) -> Optional[str]:
        run = workflow_context.run
        chapter = workflow_context.chapter
        if command.actor_user_id != run.user_id:
            return "actor_mismatch"
        if command.expected_run_revision != run.row_revision and applied_retry is None:
            return "stale_run_revision"
        if command.expected_chapter_revision != chapter.current_revision:
            return "stale_chapter_revision"
        if command.expected_checkpoint_id != run.checkpoint_id:
            return "stale_checkpoint"

        if applied_retry is not None and command.type == "retry":
            return None
        allowed = JobService._allowed_workflow_command_types(
            job=job,
            workflow_context=workflow_context,
            ambiguous_activities=ambiguous_activities,
            projection_retry_available=projection_retry_available,
        )
        if command.type not in allowed:
            return "command_not_allowed_in_current_state"
        payload = command.payload if isinstance(command.payload, dict) else {}
        if command.type in {"retry_external", "cancel"} and payload:
            activity_key = payload.get("activity_key")
            matching = next(
                (
                    activity
                    for activity in ambiguous_activities
                    if activity.activity_key == activity_key
                ),
                None,
            )
            if matching is None:
                return "ambiguous_activity_required"
            if (
                command.type == "retry_external"
                and not JobService._is_canonical_workflow_provider_request(
                    matching.request_payload,
                    workflow_context=workflow_context,
                )
            ):
                return "invalid_ambiguous_activity_request"
        return None

    @staticmethod
    def _allowed_workflow_command_types(
        *,
        job: BackgroundTask,
        workflow_context: LockedChapterWorkflowTransition,
        ambiguous_activities: list[JobActivity],
        projection_retry_available: bool,
    ) -> list[ChapterWorkflowCommandType]:
        run = workflow_context.run
        allowed: list[ChapterWorkflowCommandType] = []
        if job.status == "waiting" and run.status == "waiting_for_selection":
            allowed.append("select")
        if (
            job.status == "needs_attention"
            and run.status == "needs_attention"
            and any(
                JobService._is_canonical_workflow_provider_request(
                    activity.request_payload,
                    workflow_context=workflow_context,
                )
                for activity in ambiguous_activities
            )
        ):
            allowed.append("retry_external")
        if (
            job.status == "waiting"
            and run.status == "projection_pending"
            and projection_retry_available
        ):
            allowed.append("retry_projection")
        if (job.status == "retry_wait" and run.status == "retry_wait") or (
            job.status in {"failed", "dead_letter"} and run.status == "failed"
        ):
            allowed.append("retry")
        if run.is_active and job.status in {
            "queued",
            "running",
            "retry_wait",
            "waiting",
            "needs_attention",
        }:
            allowed.append("cancel")
        return allowed

    @staticmethod
    def _retryable_external_activity_key(
        *,
        ambiguous_activities: list[JobActivity],
        workflow_context: LockedChapterWorkflowTransition,
    ) -> Optional[str]:
        return next(
            (
                activity.activity_key
                for activity in ambiguous_activities
                if JobService._is_canonical_workflow_provider_request(
                    activity.request_payload,
                    workflow_context=workflow_context,
                )
            ),
            None,
        )

    async def _has_retryable_workflow_projection(
        self,
        workflow_context: LockedChapterWorkflowTransition,
    ) -> bool:
        run = workflow_context.run
        chapter = workflow_context.chapter
        if run.status != "projection_pending" or chapter.current_revision < 1:
            return False
        revision = (
            (
                await self.session.execute(
                    select(ChapterRevision).where(
                        ChapterRevision.chapter_id == chapter.id,
                        ChapterRevision.revision == chapter.current_revision,
                    )
                )
            )
            .scalars()
            .first()
        )
        if revision is None or revision.lifecycle != "finalizing":
            return False
        runs = list(
            (
                await self.session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.chapter_revision_id == revision.id
                    )
                )
            ).scalars()
        )
        return bool(
            retryable_projection_names(
                runs,
                required_projections=revision.required_projections or [],
            )
        )

    async def _apply_standard_cancel_command(
        self,
        *,
        command: ChapterWorkflowCommand,
        job: BackgroundTask,
        workflow_context: LockedChapterWorkflowTransition,
        applied_at: datetime,
    ) -> None:
        job.cancel_requested_at = job.cancel_requested_at or applied_at
        cancel_pending = job.status == "running"
        if cancel_pending:
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry("已通过工作流命令请求取消任务", level="warning", now=applied_at),
            ]
            await self._append_event(
                job,
                "job.cancel_requested",
                now=applied_at,
                workflow_context=workflow_context,
            )
        else:
            job.status = "cancelled"
            job.completed_at = applied_at
            job.error = "任务已取消"
            job.error_category = "job_cancelled"
            job.lease_owner = None
            job.lease_expires_at = None
            job.heartbeat_at = None
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry("已通过工作流命令取消任务", level="warning", now=applied_at),
            ]
            await self._append_event(
                job,
                "job.cancelled",
                now=applied_at,
                workflow_context=workflow_context,
            )
        command.status = "applied"
        command.rejection_code = None
        command.result_payload = {
            "command_id": command.id,
            "status": "applied",
            "cancelled_job_id": job.id,
            "cancel_pending": cancel_pending,
        }
        command.applied_at = applied_at

    async def _apply_determinate_retry_command(
        self,
        *,
        command: ChapterWorkflowCommand,
        job: BackgroundTask,
        workflow_context: LockedChapterWorkflowTransition,
        applied_retry: Optional[ChapterWorkflowCommand],
        applied_at: datetime,
    ) -> None:
        if applied_retry is not None:
            result = applied_retry.result_payload
            if (
                not isinstance(result, dict)
                or result.get("retry_run_id") != workflow_context.run.id
            ):
                raise ValueError("已应用 retry command 的 target 身份漂移")
            command.status = "applied"
            command.rejection_code = None
            command.result_payload = dict(result)
            command.result_payload["command_id"] = command.id
            command.applied_at = applied_at
            return

        job.status = "queued"
        job.available_at = applied_at
        job.completed_at = None
        job.dead_lettered_at = None
        job.cancel_requested_at = None
        job.error = None
        job.error_category = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("确定失败节点已通过命令重新排队", level="warning", now=applied_at),
        ]
        await self._append_event(
            job,
            "workflow.phase_changed",
            now=applied_at,
            workflow_context=workflow_context,
            workflow_transition=ChapterWorkflowTransition(
                status="queued",
                node_key=workflow_context.run.node_key,
                checkpoint_id=workflow_context.run.checkpoint_id,
                progress=workflow_context.run.progress,
            ),
        )
        command.status = "applied"
        command.rejection_code = None
        command.result_payload = {
            "command_id": command.id,
            "status": "applied",
            "retry_run_id": workflow_context.run.id,
            "reused_checkpoint_id": workflow_context.run.checkpoint_id,
        }
        command.applied_at = applied_at

    async def apply_ambiguous_activity_command(
        self,
        command_id: str,
        *,
        now: Optional[datetime] = None,
    ) -> ChapterWorkflowCommand:
        """执行已持久化的 ambiguous retry/cancel command，不直接调用 provider。"""

        applied_at = now or _utc_now()
        command_ref = await self.workflow_repo.get_command(command_id)
        if command_ref is None:
            await self.session.rollback()
            raise ValueError("workflow command 不存在")
        run_ref = await self.workflow_repo.get(id=command_ref.run_id)
        if run_ref is None:
            await self.session.rollback()
            raise ValueError("workflow command 绑定的 run 不存在")

        job = await self.repo.get_for_update(run_ref.root_job_id)
        if job is None:
            await self.session.rollback()
            raise ValueError("workflow command 绑定的 root JobRun 不存在")
        workflow_context = await self.workflow_transitions.lock_for_job(job)
        if workflow_context is None or workflow_context.run.id != command_ref.run_id:
            await self.session.rollback()
            raise ValueError("workflow command 与 root JobRun 身份不一致")

        command = await self.workflow_repo.get_command_for_update(command_id)
        if command is None or command.run_id != workflow_context.run.id:
            await self.session.rollback()
            raise ValueError("workflow command 身份在锁定期间发生漂移")
        if command.status == "rejected":
            reason_code = command.rejection_code or "command_rejected"
            await self.session.commit()
            raise ChapterWorkflowCommandRejectedError(reason_code)
        if command.status == "applied":
            try:
                await self._validate_applied_ambiguous_command_replay(
                    command=command,
                    job=job,
                    workflow_context=workflow_context,
                )
            except Exception:
                await self.session.rollback()
                raise
            await self.session.commit()
            return command

        if command.status != "pending":
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="invalid_command_status",
            )
        if command.type not in {"retry_external", "cancel"}:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="ambiguous_command_type_required",
            )
        if command.payload_version != 1:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="unsupported_payload_version",
            )

        run = workflow_context.run
        chapter = workflow_context.chapter
        if command.actor_user_id != run.user_id:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="actor_mismatch",
            )
        if command.expected_run_revision != run.row_revision:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="stale_run_revision",
            )
        if command.expected_chapter_revision != chapter.current_revision:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="stale_chapter_revision",
            )
        if command.expected_checkpoint_id != run.checkpoint_id:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="stale_checkpoint",
            )
        if job.status != "needs_attention" or run.status != "needs_attention" or not run.is_active:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="run_not_awaiting_ambiguous_resolution",
            )

        payload = command.payload if isinstance(command.payload, dict) else {}
        allowed_payload_keys = (
            {"activity_key", "acknowledge_possible_duplicate"}
            if command.type == "retry_external"
            else {"activity_key"}
        )
        if set(payload) != allowed_payload_keys:
            missing_ack = command.type == "retry_external" and set(payload) == {"activity_key"}
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code=(
                    "possible_duplicate_ack_required" if missing_ack else "invalid_command_payload"
                ),
            )
        if (
            command.type == "retry_external"
            and payload.get("acknowledge_possible_duplicate") is not True
        ):
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="possible_duplicate_ack_required",
            )
        activity_key = payload.get("activity_key")
        if not isinstance(activity_key, str) or not activity_key.strip() or len(activity_key) > 128:
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="invalid_activity_key",
            )

        original = await self.repo.get_activity_for_update(
            job_id=job.id,
            activity_key=activity_key,
        )
        if (
            original is None
            or original.side_effect_class != SideEffectClass.AMBIGUOUS_EXTERNAL.value
            or original.status != "ambiguous"
        ):
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="ambiguous_activity_required",
            )
        if command.type == "retry_external" and not self._is_canonical_workflow_provider_request(
            original.request_payload,
            workflow_context=workflow_context,
        ):
            return await self._reject_workflow_command(
                command,
                job=job,
                workflow_context=workflow_context,
                reason_code="invalid_ambiguous_activity_request",
            )

        if command.type == "retry_external":
            await self._apply_retry_external_command(
                command=command,
                job=job,
                original=original,
                workflow_context=workflow_context,
                applied_at=applied_at,
            )
        else:
            await self._apply_ambiguous_cancel_command(
                command=command,
                job=job,
                original=original,
                workflow_context=workflow_context,
                applied_at=applied_at,
            )

        await self._append_event(
            job,
            "workflow.command.applied",
            now=applied_at,
            workflow_context=workflow_context,
            workflow_command=command,
        )

        await self.session.commit()
        await self.session.refresh(command)
        await publish_background_task(job.user_id)
        return command

    @staticmethod
    def _is_canonical_workflow_provider_request(
        request_payload: object,
        *,
        workflow_context: LockedChapterWorkflowTransition,
    ) -> bool:
        if not isinstance(request_payload, dict):
            return False
        required_keys = {
            "schema_version",
            "workflow_version",
            "state_schema_version",
            "run_id",
            "node_key",
            "stage",
            "input_hash",
        }
        if set(request_payload) != required_keys:
            return False
        run = workflow_context.run
        input_hash = request_payload.get("input_hash")
        return (
            request_payload.get("schema_version") == 1
            and request_payload.get("workflow_version") == run.workflow_version
            and request_payload.get("state_schema_version") == run.state_schema_version
            and request_payload.get("run_id") == run.id
            and request_payload.get("node_key")
            in {"plan_and_direct", "generate_candidates", "review_candidates"}
            and isinstance(request_payload.get("stage"), str)
            and bool(str(request_payload["stage"]).strip())
            and isinstance(input_hash, str)
            and re.fullmatch(r"[0-9a-f]{64}", input_hash) is not None
        )

    async def _apply_retry_external_command(
        self,
        *,
        command: ChapterWorkflowCommand,
        job: BackgroundTask,
        original: JobActivity,
        workflow_context: LockedChapterWorkflowTransition,
        applied_at: datetime,
    ) -> None:
        """以 command id 创建唯一人工重试 intent，并恢复 root job。"""

        manual_activity_key = f"manual_retry:{command.id}"
        provider_request_key = str(
            uuid5(
                NAMESPACE_URL,
                f"mofeng:chapter-workflow:{command.id}:retry_external",
            )
        )
        manual_request = {
            "logical_step_key": original.activity_key,
            "manual_retry_command_id": command.id,
            "acknowledge_possible_duplicate": True,
            "provider_request": dict(original.request_payload or {}),
            "replaces_activity": {
                "id": original.id,
                "activity_key": original.activity_key,
                "provider_request_key": original.provider_request_key,
            },
        }
        activity = await self.repo.get_activity_for_update(
            job_id=job.id,
            activity_key=manual_activity_key,
        )
        if activity is None:
            activity = await self.repo.add_activity(
                JobActivity(
                    id=str(uuid5(NAMESPACE_URL, f"mofeng:job-activity:{command.id}")),
                    job_id=job.id,
                    activity_key=manual_activity_key,
                    side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL.value,
                    status="manual_retry_pending",
                    provider_request_key=provider_request_key,
                    attempt=job.attempt,
                    fencing_token=job.fencing_token,
                    request_payload=manual_request,
                    result_payload=None,
                    started_at=applied_at,
                    updated_at=applied_at,
                )
            )
        elif (
            activity.side_effect_class != SideEffectClass.AMBIGUOUS_EXTERNAL.value
            or activity.status != "manual_retry_pending"
            or activity.provider_request_key != provider_request_key
            or _canonical_json(activity.request_payload or {}) != _canonical_json(manual_request)
        ):
            await self.session.rollback()
            raise ValueError("command 派生的 manual retry intent 身份冲突")

        job.status = "queued"
        job.available_at = applied_at
        job.completed_at = None
        job.error = None
        job.error_category = None
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("已确认外部调用可能重复，任务重新排队", level="warning", now=applied_at),
        ]
        await self._append_event(
            job,
            "workflow.phase_changed",
            now=applied_at,
            workflow_context=workflow_context,
        )
        command.status = "applied"
        command.rejection_code = None
        command.result_payload = {
            "command_id": command.id,
            "status": "applied",
            "activity_id": activity.id,
            "activity_key": activity.activity_key,
            "provider_request_key": activity.provider_request_key,
            "replaces_activity_id": original.id,
        }
        command.applied_at = applied_at

    async def _apply_ambiguous_cancel_command(
        self,
        *,
        command: ChapterWorkflowCommand,
        job: BackgroundTask,
        original: JobActivity,
        workflow_context: LockedChapterWorkflowTransition,
        applied_at: datetime,
    ) -> None:
        """在不触碰 ambiguous activity 的前提下终止 root job 与 run。"""

        job.status = "cancelled"
        job.cancel_requested_at = applied_at
        job.completed_at = applied_at
        job.error = "任务已取消"
        job.error_category = "job_cancelled"
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("已通过审计命令取消任务", level="warning", now=applied_at),
        ]
        await self._append_event(
            job,
            "job.cancelled",
            now=applied_at,
            workflow_context=workflow_context,
        )
        command.status = "applied"
        command.rejection_code = None
        command.result_payload = {
            "command_id": command.id,
            "status": "applied",
            "cancelled_job_id": job.id,
            "ambiguous_activity_id": original.id,
        }
        command.applied_at = applied_at

    async def _validate_applied_ambiguous_command_replay(
        self,
        *,
        command: ChapterWorkflowCommand,
        job: BackgroundTask,
        workflow_context: LockedChapterWorkflowTransition,
    ) -> None:
        result = command.result_payload if isinstance(command.result_payload, dict) else {}
        if command.type == "retry_external":
            activity_key = result.get("activity_key")
            provider_request_key = result.get("provider_request_key")
            if not isinstance(activity_key, str) or not isinstance(provider_request_key, str):
                raise ValueError("已应用 retry_external command 缺少稳定 intent identity")
            activity = await self.repo.get_activity_for_update(
                job_id=job.id,
                activity_key=activity_key,
            )
            if (
                activity is None
                or activity.provider_request_key != provider_request_key
                or activity.request_payload.get("manual_retry_command_id") != command.id
            ):
                raise ValueError("已应用 retry_external command 的 intent 身份漂移")
        elif command.type == "cancel":
            if job.status != "cancelled" or workflow_context.run.status != "cancelled":
                raise ValueError("已应用 cancel command 的 terminal 状态漂移")
        else:
            raise ValueError("已应用 command 不是 ambiguous resolution 类型")

    async def _resolve_manual_retry_activity(
        self,
        *,
        job: BackgroundTask,
        workflow_context: LockedChapterWorkflowTransition,
        original: JobActivity,
        canonical_request: dict[str, Any],
    ) -> Optional[JobActivity]:
        manual = await self.repo.get_latest_manual_retry_for_update(
            job_id=job.id,
            logical_step_key=original.activity_key,
        )
        if manual is None:
            return None

        request = manual.request_payload if isinstance(manual.request_payload, dict) else {}
        command_id = request.get("manual_retry_command_id")
        replaces = request.get("replaces_activity")
        provider_request = request.get("provider_request")
        command = (
            await self.workflow_repo.get_command_for_update(command_id)
            if isinstance(command_id, str)
            else None
        )
        command_result = (
            command.result_payload
            if command is not None and isinstance(command.result_payload, dict)
            else {}
        )
        command_payload = (
            command.payload if command is not None and isinstance(command.payload, dict) else {}
        )
        if (
            command is None
            or command.type != "retry_external"
            or command.status != "applied"
            or command.run_id != workflow_context.run.id
            or manual.activity_key != f"manual_retry:{command.id}"
            or command_result.get("activity_id") != manual.id
            or command_result.get("activity_key") != manual.activity_key
            or command_result.get("provider_request_key") != manual.provider_request_key
            or command_payload.get("activity_key") != original.activity_key
            or command_payload.get("acknowledge_possible_duplicate") is not True
            or request.get("logical_step_key") != original.activity_key
            or request.get("acknowledge_possible_duplicate") is not True
            or not isinstance(replaces, dict)
            or replaces.get("id") != original.id
            or replaces.get("activity_key") != original.activity_key
            or replaces.get("provider_request_key") != original.provider_request_key
            or not isinstance(provider_request, dict)
            or _canonical_json(provider_request) != _canonical_json(canonical_request)
            or _canonical_json(original.request_payload or {}) != _canonical_json(canonical_request)
        ):
            await self.session.rollback()
            raise ValueError("manual retry intent 与已应用 command 身份不一致")
        return manual

    async def _reject_workflow_command(
        self,
        command: ChapterWorkflowCommand,
        *,
        job: BackgroundTask,
        workflow_context: LockedChapterWorkflowTransition,
        reason_code: str,
    ) -> ChapterWorkflowCommand:
        command.status = "rejected"
        command.rejection_code = reason_code
        command.result_payload = {
            "command_id": command.id,
            "status": "rejected",
            "reason_code": reason_code,
        }
        await self._append_event(
            job,
            "workflow.command.rejected",
            now=_utc_now(),
            workflow_context=workflow_context,
            workflow_command=command,
        )
        await self.session.commit()
        raise ChapterWorkflowCommandRejectedError(reason_code)

    async def begin_activity(
        self,
        lease: JobLease,
        *,
        activity_key: str,
        side_effect_class: SideEffectClass,
        request_payload: Optional[dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> ActivityExecution:
        if not activity_key.strip() or len(activity_key) > 128:
            raise ValueError("activity_key 必须为 1 到 128 个字符")
        started_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=started_at)
        except LeaseLostError:
            await self.session.rollback()
            raise

        workflow_context = await self.workflow_transitions.lock_for_job(job)

        canonical_request = dict(request_payload or {})
        activity = await self.repo.get_activity_for_update(
            job_id=job.id,
            activity_key=activity_key,
        )
        is_manual_retry = False
        if (
            workflow_context is not None
            and activity is not None
            and activity.status == "ambiguous"
            and side_effect_class == SideEffectClass.AMBIGUOUS_EXTERNAL
        ):
            manual_activity = await self._resolve_manual_retry_activity(
                job=job,
                workflow_context=workflow_context,
                original=activity,
                canonical_request=canonical_request,
            )
            if manual_activity is not None:
                activity = manual_activity
                is_manual_retry = True
        if activity is not None:
            if activity.side_effect_class != side_effect_class.value:
                await self.session.rollback()
                raise ValueError("同一 activity_key 的 side-effect class 不可变")
            if not is_manual_retry and _canonical_json(
                activity.request_payload or {}
            ) != _canonical_json(canonical_request):
                await self.session.rollback()
                raise ValueError("同一 activity_key 的 canonical request 不可变")
            if activity.status == "succeeded":
                await self.session.commit()
                return ActivityExecution(
                    activity_key=activity.activity_key,
                    provider_request_key=activity.provider_request_key,
                    should_execute=False,
                    result=dict(activity.result_payload or {}),
                )
            if activity.status == "manual_retry_pending":
                manual_command_id = activity.request_payload.get("manual_retry_command_id")
                if (
                    side_effect_class != SideEffectClass.AMBIGUOUS_EXTERNAL
                    or not isinstance(manual_command_id, str)
                    or activity.activity_key != f"manual_retry:{manual_command_id}"
                ):
                    await self.session.rollback()
                    raise ValueError("manual retry intent 缺少有效的 command identity")
                activity.status = "started"
                activity.attempt = lease.attempt
                activity.fencing_token = lease.fencing_token
                activity.started_at = started_at
                activity.updated_at = started_at
                await self._append_activity_event(
                    job,
                    "activity.retried",
                    activity=activity,
                    now=started_at,
                    workflow_context=workflow_context,
                )
                await self.session.commit()
                await publish_background_task(job.user_id)
                return ActivityExecution(
                    activity_key=activity.activity_key,
                    provider_request_key=activity.provider_request_key,
                    should_execute=True,
                )
            if activity.status == "retryable_failed":
                activity.status = "started"
                activity.error_category = None
                activity.attempt = lease.attempt
                activity.fencing_token = lease.fencing_token
                activity.updated_at = started_at
                await self._append_activity_event(
                    job,
                    "activity.retried",
                    activity=activity,
                    now=started_at,
                    workflow_context=workflow_context,
                )
                await self.session.commit()
                await publish_background_task(job.user_id)
                return ActivityExecution(
                    activity_key=activity.activity_key,
                    provider_request_key=activity.provider_request_key,
                    should_execute=True,
                )
            if side_effect_class == SideEffectClass.AMBIGUOUS_EXTERNAL:
                job.status = "needs_attention"
                job.error_category = "ambiguous_external_result"
                job.error = "外部调用结果未知，需要人工确认"
                job.completed_at = started_at
                job.lease_owner = None
                job.lease_expires_at = None
                job.log_entries = [
                    *(job.log_entries or []),
                    _log_entry(
                        "外部调用结果未知，任务已停止自动重试", level="error", now=started_at
                    ),
                ]
                await self._sync_projection_run_status(
                    job,
                    status="needs_attention",
                    error_category="ambiguous_external_result",
                )
                await self._append_event(
                    job,
                    "job.needs_attention",
                    now=started_at,
                    workflow_context=workflow_context,
                )
                await self.session.commit()
                await publish_background_task(job.user_id)
                raise AmbiguousActivityError("外部调用结果未知，禁止自动重放")
            await self.session.commit()
            return ActivityExecution(
                activity_key=activity.activity_key,
                provider_request_key=activity.provider_request_key,
                should_execute=True,
            )

        provider_request_key = str(uuid4())
        activity = await self.repo.add_activity(
            JobActivity(
                id=str(uuid4()),
                job_id=job.id,
                activity_key=activity_key,
                side_effect_class=side_effect_class.value,
                status="started",
                provider_request_key=provider_request_key,
                attempt=lease.attempt,
                fencing_token=lease.fencing_token,
                request_payload=canonical_request,
                result_payload=None,
                started_at=started_at,
                updated_at=started_at,
            )
        )
        await self._append_activity_event(
            job,
            "activity.started",
            activity=activity,
            now=started_at,
            workflow_context=workflow_context,
        )
        await self.session.commit()
        await publish_background_task(job.user_id)
        return ActivityExecution(
            activity_key=activity.activity_key,
            provider_request_key=provider_request_key,
            should_execute=True,
        )

    async def complete_activity(
        self,
        lease: JobLease,
        *,
        activity_key: str,
        provider_request_key: str,
        result: dict[str, Any],
        ai_call: Optional[AICallResult[Any]] = None,
        outcome_writer: Optional[Callable[[AsyncSession], Awaitable[None]]] = None,
        now: Optional[datetime] = None,
    ) -> JobActivity:
        completed_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=completed_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        workflow_context = await self.workflow_transitions.lock_for_job(job)
        activity = await self.repo.get_activity_for_update(
            job_id=job.id,
            activity_key=activity_key,
        )
        if activity is None:
            await self.session.rollback()
            raise ValueError("activity intent 不存在")
        if activity.provider_request_key != provider_request_key:
            await self.session.rollback()
            raise ValueError("provider_request_key 与 activity intent 不匹配")
        if activity.status == "succeeded":
            await self.session.commit()
            return activity

        try:
            if outcome_writer is not None:
                await outcome_writer(self.session)
        except Exception:
            await self.session.rollback()
            raise

        activity_result = dict(result)
        if ai_call is not None:
            activity_result["ai_telemetry"] = ai_call.telemetry_dict()
            usage = ai_call.usage
            await self.repo.add_ai_usage(
                AIUsageRecord(
                    job_activity_id=activity.id,
                    job_id=job.id,
                    user_id=job.user_id,
                    project_id=job.project_id,
                    provider_type=ai_call.provider_type,
                    model_name=ai_call.model,
                    model_id=ai_call.model_id,
                    stage=ai_call.stage,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    total_tokens=usage.total_tokens,
                    cached_input_tokens=usage.cached_input_tokens,
                    cache_write_input_tokens=usage.cache_write_input_tokens,
                    reasoning_tokens=usage.reasoning_tokens,
                    usage_complete=usage.is_complete,
                    cost_amount=(
                        Decimal(ai_call.cost_amount) if ai_call.cost_amount is not None else None
                    ),
                    cost_currency=ai_call.cost_currency,
                    cost_known=ai_call.cost_unknown_reason is None,
                    cost_unknown_reason=ai_call.cost_unknown_reason,
                    created_at=completed_at,
                )
            )

        activity.status = "succeeded"
        activity.result_payload = activity_result
        activity.attempt = lease.attempt
        activity.fencing_token = lease.fencing_token
        activity.completed_at = completed_at
        activity.updated_at = completed_at
        await self.session.flush()
        await self._append_activity_event(
            job,
            "activity.succeeded",
            activity=activity,
            now=completed_at,
            workflow_context=workflow_context,
            result_payload=activity_result,
        )
        await self.session.commit()
        await self.session.refresh(activity)
        await publish_background_task(job.user_id)
        return activity

    async def mark_activity_failed(
        self,
        lease: JobLease,
        *,
        activity_key: str,
        provider_request_key: str,
        error_category: str,
        retryable: bool,
        now: Optional[datetime] = None,
    ) -> JobActivity:
        """记录明确失败的 activity；不会把确定失败误判为 ambiguous。"""

        recorded_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=recorded_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        workflow_context = await self.workflow_transitions.lock_for_job(job)
        activity = await self.repo.get_activity_for_update(
            job_id=job.id,
            activity_key=activity_key,
        )
        if activity is None:
            await self.session.rollback()
            raise ValueError("activity intent 不存在")
        if activity.provider_request_key != provider_request_key:
            await self.session.rollback()
            raise ValueError("provider_request_key 与 activity intent 不匹配")
        if activity.status == "succeeded":
            await self.session.rollback()
            raise ValueError("已完成的 activity 不可标记为失败")

        safe_category = (
            re.sub(
                r"[^a-z0-9_.-]",
                "_",
                error_category.strip().lower(),
            )[:64]
            or "activity_error"
        )
        activity.status = "retryable_failed" if retryable else "failed"
        activity.error_category = safe_category
        activity.attempt = lease.attempt
        activity.fencing_token = lease.fencing_token
        activity.updated_at = recorded_at
        await self._append_activity_event(
            job,
            "activity.retryable_failed" if retryable else "activity.failed",
            activity=activity,
            now=recorded_at,
            workflow_context=workflow_context,
            error=safe_category,
        )
        await self.session.commit()
        await self.session.refresh(activity)
        await publish_background_task(job.user_id)
        return activity

    async def mark_activity_ambiguous(
        self,
        lease: JobLease,
        *,
        activity_key: str,
        provider_request_key: str,
        public_message: str,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        """记录外部调用结果不明，并终止该 job 的自动重放。"""

        recorded_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=recorded_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        workflow_context = await self.workflow_transitions.lock_for_job(job)
        activity = await self.repo.get_activity_for_update(
            job_id=job.id,
            activity_key=activity_key,
        )
        if activity is None:
            await self.session.rollback()
            raise ValueError("activity intent 不存在")
        if activity.side_effect_class != SideEffectClass.AMBIGUOUS_EXTERNAL.value:
            await self.session.rollback()
            raise ValueError("只有 ambiguous_external activity 可标记为结果不明")
        if activity.provider_request_key != provider_request_key:
            await self.session.rollback()
            raise ValueError("provider_request_key 与 activity intent 不匹配")
        if activity.status == "succeeded":
            await self.session.rollback()
            raise ValueError("已完成的 activity 不可标记为结果不明")

        safe_message = sanitize_public_text(public_message)
        activity.status = "ambiguous"
        activity.error_category = "ambiguous_external_result"
        activity.attempt = lease.attempt
        activity.fencing_token = lease.fencing_token
        activity.updated_at = recorded_at
        job.status = "needs_attention"
        job.error_category = "ambiguous_external_result"
        job.error = safe_message
        job.completed_at = recorded_at
        job.lease_owner = None
        job.lease_expires_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry(safe_message, level="error", now=recorded_at),
        ]
        await self._sync_projection_run_status(
            job,
            status="needs_attention",
            error_category="ambiguous_external_result",
        )
        await self._append_event(
            job,
            "job.needs_attention",
            now=recorded_at,
            workflow_context=workflow_context,
        )
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def heartbeat(
        self,
        lease: JobLease,
        *,
        lease_seconds: int,
        now: Optional[datetime] = None,
    ) -> HeartbeatResult:
        if lease_seconds < 1:
            raise ValueError("lease_seconds 必须大于等于 1")
        heartbeat_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=heartbeat_at)
        except LeaseLostError:
            await self.session.rollback()
            raise

        if job.cancel_requested_at is not None:
            await self.session.commit()
            return HeartbeatResult(cancel_requested=True)

        job.heartbeat_at = heartbeat_at
        job.lease_expires_at = heartbeat_at + timedelta(seconds=lease_seconds)
        await self.session.commit()
        return HeartbeatResult(cancel_requested=False)

    async def mark_cancelled(
        self,
        lease: JobLease,
        *,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        cancelled_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=cancelled_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
        if job.cancel_requested_at is None:
            await self.session.rollback()
            raise ValueError("任务尚未请求取消")

        job.status = "cancelled"
        job.completed_at = cancelled_at
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("任务已取消", level="warning", now=cancelled_at),
        ]
        await self._sync_projection_run_status(
            job,
            status="failed",
            error_category="job_cancelled",
        )
        await self._append_event(job, "job.cancelled", now=cancelled_at)
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

    async def register_worker(
        self,
        *,
        worker_id: str,
        executor_generation: int,
        now: Optional[datetime] = None,
    ) -> JobWorkerHeartbeat:
        normalized_id = worker_id.strip()
        if not normalized_id or len(normalized_id) > 128:
            raise ValueError("worker_id 必须为 1 到 128 个字符")
        registered_at = now or _utc_now()
        control = await self.repo.get_executor_control(for_update=True)
        if control is None:
            await self.session.rollback()
            raise RuntimeError("缺少 job executor control，请先执行数据库迁移")
        if control.active_generation != executor_generation:
            active_generation = control.active_generation
            await self.session.commit()
            raise ExecutorGenerationInactiveError(
                executor_generation,
                active_generation,
            )

        heartbeat = await self.repo.get_worker_heartbeat_for_update(worker_id=normalized_id)
        if heartbeat is None:
            heartbeat = await self.repo.add_worker_heartbeat(
                JobWorkerHeartbeat(
                    worker_id=normalized_id,
                    executor_generation=executor_generation,
                    state="running",
                    started_at=registered_at,
                    heartbeat_at=registered_at,
                    stopped_at=None,
                )
            )
        elif heartbeat.state != "stopped":
            await self.session.rollback()
            raise RuntimeError(f"worker_id 已被活跃进程占用: {normalized_id}")
        else:
            heartbeat.executor_generation = executor_generation
            heartbeat.state = "running"
            heartbeat.started_at = registered_at
            heartbeat.heartbeat_at = registered_at
            heartbeat.stopped_at = None

        await self.session.commit()
        await self.session.refresh(heartbeat)
        return heartbeat

    async def heartbeat_worker(
        self,
        *,
        worker_id: str,
        executor_generation: int,
        now: Optional[datetime] = None,
    ) -> JobWorkerHeartbeat:
        heartbeat = await self._require_worker_heartbeat(
            worker_id,
            executor_generation=executor_generation,
        )
        if heartbeat.state == "stopped":
            await self.session.rollback()
            raise RuntimeError("已停止的 worker 不能继续 heartbeat")
        heartbeat.heartbeat_at = now or _utc_now()
        await self.session.commit()
        await self.session.refresh(heartbeat)
        return heartbeat

    async def mark_worker_draining(
        self,
        *,
        worker_id: str,
        executor_generation: int,
        now: Optional[datetime] = None,
    ) -> JobWorkerHeartbeat:
        heartbeat = await self._require_worker_heartbeat(
            worker_id,
            executor_generation=executor_generation,
        )
        if heartbeat.state != "stopped":
            heartbeat.state = "draining"
            heartbeat.heartbeat_at = now or _utc_now()
        await self.session.commit()
        await self.session.refresh(heartbeat)
        return heartbeat

    async def mark_worker_stopped(
        self,
        *,
        worker_id: str,
        executor_generation: int,
        now: Optional[datetime] = None,
    ) -> JobWorkerHeartbeat:
        stopped_at = now or _utc_now()
        heartbeat = await self._require_worker_heartbeat(
            worker_id,
            executor_generation=executor_generation,
        )
        heartbeat.state = "stopped"
        heartbeat.heartbeat_at = stopped_at
        heartbeat.stopped_at = stopped_at
        await self.session.commit()
        await self.session.refresh(heartbeat)
        return heartbeat

    async def list_events(
        self,
        *,
        user_id: int,
        after_cursor: int,
        limit: int = 100,
    ) -> list[JobEvent]:
        if after_cursor < 0:
            raise ValueError("after_cursor 不能小于 0")
        retained_through_cursor = await self.repo.get_retained_through_cursor(user_id=user_id)
        if after_cursor < retained_through_cursor:
            raise EventCursorExpiredError(retained_through_cursor)
        return cast(
            list[JobEvent],
            await self.repo.list_events(
                user_id=user_id,
                after_cursor=after_cursor,
                limit=max(1, min(limit, 500)),
            ),
        )

    async def list_stream_events(
        self,
        *,
        user_id: int,
        stream_type: str,
        stream_id: str,
        after_cursor: int,
        limit: int = 100,
    ) -> list[JobEvent]:
        if after_cursor < 0:
            raise ValueError("after_cursor 不能小于 0")
        normalized_type, normalized_id = self._validate_stream_identity(
            stream_type,
            stream_id,
        )
        stream = await self.repo.get_user_stream(
            stream_type=normalized_type,
            stream_id=normalized_id,
            user_id=user_id,
        )
        if stream is None:
            raise JobStreamNotFoundError("未找到任务事件流")
        retained_through_cursor = stream.retained_through_cursor
        if after_cursor < retained_through_cursor:
            raise EventCursorExpiredError(retained_through_cursor)
        return cast(
            list[JobEvent],
            await self.repo.list_stream_events(
                user_id=user_id,
                stream_type=normalized_type,
                stream_id=normalized_id,
                after_cursor=after_cursor,
                limit=max(1, min(limit, 500)),
            ),
        )

    async def cleanup_events(self, *, before: datetime) -> JobEventCleanupResult:
        """清理过期事件；删除与 retention 水位推进在同一事务提交。"""

        deleted_events, affected_user_ids = await self.repo.delete_events_before(before=before)
        await self.session.commit()
        for user_id in affected_user_ids:
            await publish_background_task(user_id)
        return JobEventCleanupResult(
            deleted_events=deleted_events,
            affected_user_ids=tuple(affected_user_ids),
        )

    async def get_worker_health(
        self,
        *,
        executor_generation: int,
        stale_after_seconds: float,
        worker_id: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> JobWorkerHealth:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds 必须大于 0")
        heartbeat = await self.repo.get_latest_worker_heartbeat(
            executor_generation=executor_generation,
            worker_id=worker_id,
        )
        if heartbeat is None:
            return JobWorkerHealth(False, None, None, None)
        checked_at = now or _utc_now()
        age_seconds = max(0.0, (checked_at - heartbeat.heartbeat_at).total_seconds())
        healthy = heartbeat.state == "running" and age_seconds <= stale_after_seconds
        return JobWorkerHealth(
            healthy=healthy,
            worker_id=heartbeat.worker_id,
            state=heartbeat.state,
            heartbeat_age_seconds=age_seconds,
        )

    async def get_runtime_metrics(
        self,
        *,
        now: Optional[datetime] = None,
        queue_age_alert_after_seconds: Optional[int] = None,
        retention_max_bytes: Optional[int] = None,
    ) -> JobRuntimeMetrics:
        queue_alert_after = (
            settings.job_queue_age_alert_seconds
            if queue_age_alert_after_seconds is None
            else queue_age_alert_after_seconds
        )
        retention_budget = (
            settings.job_retention_max_bytes if retention_max_bytes is None else retention_max_bytes
        )
        if queue_alert_after < 1:
            raise ValueError("queue_age_alert_after_seconds 必须大于 0")
        if retention_budget < 1:
            raise ValueError("retention_max_bytes 必须大于 0")
        checked_at = now or _utc_now()
        values = await self.repo.get_runtime_metric_values(now=checked_at)
        status_counts = values["status_counts"]
        if not isinstance(status_counts, dict):
            raise RuntimeError("job runtime status 聚合无效")
        oldest_queued_at = values["oldest_queued_at"]
        oldest_age = None
        if isinstance(oldest_queued_at, datetime):
            oldest_age = max(0.0, (checked_at - oldest_queued_at).total_seconds())
        oldest_unprojected_event_at = values["oldest_unprojected_event_at"]
        oldest_event_lag = None
        if isinstance(oldest_unprojected_event_at, datetime):
            oldest_event_lag = max(
                0.0,
                (checked_at - oldest_unprojected_event_at).total_seconds(),
            )
        normalized_counts = {str(status): int(count) for status, count in status_counts.items()}
        integer_metrics: dict[str, int] = {}
        for key in (
            "expired_leases",
            "latest_event_cursor",
            "projected_event_cursor",
            "retained_event_count",
            "retention_users",
            "retained_event_bytes",
        ):
            value = values[key]
            if isinstance(value, bool) or not isinstance(value, int):
                raise RuntimeError(f"job runtime metric {key} 无效")
            integer_metrics[key] = value
        event_lag = max(
            0,
            integer_metrics["latest_event_cursor"] - integer_metrics["projected_event_cursor"],
        )
        alerts: list[str] = []
        if oldest_age is not None and oldest_age > queue_alert_after:
            alerts.append("job_queue_age")
        if integer_metrics["expired_leases"] > 0:
            alerts.append("job_expired_lease")
        if normalized_counts.get("dead_letter", 0) > 0:
            alerts.append("job_dead_letter")
        if (
            oldest_event_lag is not None
            and oldest_event_lag > settings.job_projection_lag_alert_seconds
        ):
            alerts.append("job_event_lag")
        if integer_metrics["retained_event_bytes"] > retention_budget:
            alerts.append("job_retention_budget")
        return JobRuntimeMetrics(
            status_counts=normalized_counts,
            queue_depth=normalized_counts.get("queued", 0) + normalized_counts.get("retry_wait", 0),
            oldest_queued_age_seconds=oldest_age,
            expired_leases=integer_metrics["expired_leases"],
            latest_event_cursor=integer_metrics["latest_event_cursor"],
            retained_event_count=integer_metrics["retained_event_count"],
            retention_users=integer_metrics["retention_users"],
            event_lag=event_lag,
            oldest_event_lag_seconds=oldest_event_lag,
            retained_event_bytes=integer_metrics["retained_event_bytes"],
            retention_budget_bytes=retention_budget,
            alerts=tuple(sorted(alerts)),
        )

    async def _reap_expired_job(
        self,
        job: BackgroundTask,
        *,
        now: datetime,
    ) -> bool:
        """在 claim 持有任务行锁时收敛不可安全接管的过期执行。"""

        if job.cancel_requested_at is not None:
            job.status = "cancelled"
            job.error = None
            job.error_category = None
            event_type = "job.cancelled"
            log_entry = _log_entry("worker 退出后任务已完成取消", level="warning", now=now)
        elif await self.repo.has_unresolved_ambiguous_activity(job_id=job.id):
            job.status = "needs_attention"
            job.error_category = "ambiguous_external_result"
            job.error = "外部调用结果未知，需要人工确认"
            event_type = "job.needs_attention"
            log_entry = _log_entry(
                "外部调用结果未知，任务已停止自动重试",
                level="error",
                now=now,
            )
        elif job.attempt >= job.max_attempts:
            job.status = "dead_letter"
            job.error_category = "lease_expired_attempts_exhausted"
            job.error = "任务执行进程退出，且已达到最大尝试次数"
            job.dead_lettered_at = now
            event_type = "job.dead_lettered"
            log_entry = _log_entry(job.error, level="error", now=now)
        else:
            return False

        job.completed_at = now
        job.lease_owner = None
        job.lease_expires_at = None
        job.heartbeat_at = None
        job.log_entries = [*(job.log_entries or []), log_entry]
        await self._sync_projection_run_status(
            job,
            status="failed" if job.status == "cancelled" else job.status,
            error_category=job.error_category or "job_cancelled",
        )
        await self._append_event(job, event_type, now=now)
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return True

    async def _require_worker_heartbeat(
        self,
        worker_id: str,
        *,
        executor_generation: int,
    ) -> JobWorkerHeartbeat:
        heartbeat = await self.repo.get_worker_heartbeat_for_update(worker_id=worker_id)
        if heartbeat is None:
            raise RuntimeError(f"worker 尚未注册: {worker_id}")
        if heartbeat.executor_generation != executor_generation:
            raise RuntimeError("worker heartbeat generation 不匹配")
        return heartbeat

    async def _sync_projection_run_status(
        self,
        job: BackgroundTask,
        *,
        status: str,
        error_category: Optional[str],
    ) -> None:
        """在 JobRun 终态事务内镜像 typed projection 的领域状态。"""

        payload = job.payload if isinstance(job.payload, dict) else {}
        run_id = payload.get("projection_run_id")
        if not isinstance(run_id, str) or not run_id:
            return
        run = await self.session.get(
            ChapterProjectionRun,
            run_id,
            with_for_update=True,
        )
        if run is None or run.job_id not in (None, job.id):
            return
        run.job_id = job.id
        run.status = status
        run.is_active = False
        run.error_category = error_category
        run.checkpoint = {
            **(run.checkpoint or {}),
            "job_status": job.status,
            "job_attempt": job.attempt,
        }

    async def _append_event(
        self,
        job: BackgroundTask,
        event_type: str,
        *,
        now: datetime,
        workflow_context: Optional[LockedChapterWorkflowTransition] = None,
        workflow_transition: Optional[ChapterWorkflowTransition] = None,
        workflow_command: Optional[ChapterWorkflowCommand] = None,
        workflow_event: Optional[ChapterWorkflowEvent] = None,
    ) -> JobEvent:
        if workflow_event is not None and any(
            value is not None for value in (workflow_context, workflow_transition, workflow_command)
        ):
            raise ValueError("预构造 workflow event 不可与其他 workflow 参数合并")
        if workflow_context is None and workflow_event is None:
            workflow_context = await self.workflow_transitions.lock_for_job(job)
        workflow_payload: Optional[dict[str, object]] = None
        if workflow_transition is not None and workflow_command is not None:
            raise ValueError("workflow transition 与 command event 不可合并")
        if workflow_event is not None:
            event_type = workflow_event.event_type
            workflow_payload = workflow_event.payload
        elif event_type == "job.cancelled" and workflow_context is not None:
            await self._cleanup_cancelled_chapter_workflow(workflow_context)
            workflow_event = self.workflow_transitions.apply_event(
                job=job,
                context=workflow_context,
                source_event_type=event_type,
                now=now,
                transition=workflow_transition,
            )
            event_type = workflow_event.event_type
            workflow_payload = workflow_event.payload
        elif workflow_context is not None and workflow_command is not None:
            workflow_event = self.workflow_transitions.command_event(
                context=workflow_context,
                command=workflow_command,
                event_type=event_type,
            )
            event_type = workflow_event.event_type
            workflow_payload = workflow_event.payload
        elif workflow_context is not None and (
            workflow_transition is not None
            or self.workflow_transitions.is_transition_event(event_type)
        ):
            workflow_event = self.workflow_transitions.apply_event(
                job=job,
                context=workflow_context,
                source_event_type=event_type,
                now=now,
                transition=workflow_transition,
            )
            event_type = workflow_event.event_type
            workflow_payload = workflow_event.payload
        elif workflow_transition is not None or workflow_command is not None:
            raise ValueError("root JobRun 未绑定 Chapter workflow run")

        sequence = await self._next_stream_sequence(job)
        job.updated_at = now
        await self.session.flush()
        payload: dict[str, object] = {"task": public_job_snapshot(job)}
        if workflow_payload is not None:
            payload["workflow"] = workflow_payload
        return await self.repo.add_event(
            JobEvent(
                job_id=job.id,
                user_id=job.user_id,
                project_id=job.project_id,
                stream_type=job.stream_type,
                stream_id=job.stream_id,
                sequence=sequence,
                event_type=event_type,
                payload=payload,
                created_at=now,
            )
        )

    async def _cleanup_cancelled_chapter_workflow(
        self,
        workflow_context: LockedChapterWorkflowTransition,
    ) -> None:
        """丢弃当前 run 的未确认派生结果，保留正式版本与 durable 审计。"""

        chapter = workflow_context.chapter
        run = workflow_context.run
        versions = list(
            (
                await self.session.execute(
                    select(ChapterVersion)
                    .where(ChapterVersion.chapter_id == chapter.id)
                    .order_by(ChapterVersion.id.asc())
                    .with_for_update()
                    .execution_options(populate_existing=True)
                )
            ).scalars()
        )
        revision_version_ids = set(
            (
                await self.session.execute(
                    select(ChapterRevision.selected_version_id).where(
                        ChapterRevision.chapter_id == chapter.id,
                        ChapterRevision.selected_version_id.is_not(None),
                    )
                )
            ).scalars()
        )
        protected_version_ids = {
            version_id
            for version_id in {chapter.selected_version_id, *revision_version_ids}
            if version_id is not None
        }
        cancelled_version_ids = [
            version.id
            for version in versions
            if version.id not in protected_version_ids
            and isinstance(version.metadata_, dict)
            and isinstance(version.metadata_.get("_chapter_workflow"), dict)
            and version.metadata_["_chapter_workflow"].get("run_id") == run.id
        ]
        if cancelled_version_ids:
            await self.session.execute(
                delete(ChapterEvaluation).where(
                    ChapterEvaluation.version_id.in_(cancelled_version_ids)
                )
            )
            await self.session.execute(
                delete(ChapterVersion).where(ChapterVersion.id.in_(cancelled_version_ids))
            )
        await self.session.execute(
            delete(ChapterGenerationTrace).where(ChapterGenerationTrace.source_run_id == run.id)
        )

        if chapter.selected_version_id is None and int(chapter.current_revision or 0) == 0:
            chapter.status = "not_generated"
            chapter.generation_progress = 0
            chapter.generation_step = None
            chapter.generation_step_index = 0
            chapter.generation_step_total = 0
            chapter.generation_started_at = None
            chapter.real_summary = None
            chapter.word_count = 0
            chapter.source_hash = None
            chapter.required_projection_snapshot = []
            chapter.projection_generation = None

    async def _append_activity_event(
        self,
        job: BackgroundTask,
        event_type: str,
        *,
        activity: JobActivity,
        now: datetime,
        workflow_context: Optional[LockedChapterWorkflowTransition],
        result_payload: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> JobEvent:
        workflow_event = None
        if workflow_context is not None:
            workflow_event = self.workflow_transitions.apply_activity_event(
                job=job,
                context=workflow_context,
                source_event_type=event_type,
                request_payload=dict(activity.request_payload or {}),
                now=now,
            )
        event = await self._append_event(
            job,
            event_type,
            now=now,
            workflow_context=workflow_context if workflow_event is None else None,
            workflow_event=workflow_event,
        )
        if workflow_context is not None and workflow_event is not None:
            self._add_activity_trace(
                event=event,
                activity=activity,
                workflow_context=workflow_context,
                result_payload=result_payload,
                error=error,
                now=now,
            )
        return event

    def _add_activity_trace(
        self,
        *,
        event: JobEvent,
        activity: JobActivity,
        workflow_context: LockedChapterWorkflowTransition,
        result_payload: Optional[dict[str, Any]],
        error: Optional[str],
        now: datetime,
    ) -> None:
        request_payload = dict(activity.request_payload or {})
        node_key = str(request_payload["node_key"])
        node_label = CHAPTER_WORKFLOW_NODE_LABELS[node_key]
        uses_llm = node_key in {
            "plan_and_direct",
            "generate_candidates",
            "review_candidates",
        }
        status = (
            "success"
            if event.event_type == "activity.succeeded"
            else "failed" if error is not None else "running"
        )
        output_payload: Optional[dict[str, Any]] = None
        if result_payload is not None:
            nested_output = result_payload.get("output")
            output_payload = (
                dict(nested_output)
                if isinstance(nested_output, dict)
                else {
                    key: value
                    for key, value in result_payload.items()
                    if key not in {"ai_telemetry", "context_snapshot"}
                }
            )
        duration_ms = None
        if status != "running" and activity.started_at is not None:
            duration_ms = max(0, round((now - activity.started_at).total_seconds() * 1000))
        action = {
            "running": "开始执行",
            "success": "完成",
            "failed": "执行失败",
        }[status]
        summary_status = {
            "running": "进行中",
            "success": "已完成",
            "failed": "执行失败",
        }[status]
        call_type = {
            "freeze_context": "rag_retrieval",
            "plan_and_direct": "chat_llm",
            "generate_candidates": "chat_llm",
            "review_candidates": "chat_llm",
        }.get(node_key, "database_write")
        metadata: dict[str, Any] = {
            "source": "job_activity",
            "event_cursor": event.cursor,
            "event_type": event.event_type,
            "run_id": workflow_context.run.id,
            "activity_key": activity.activity_key,
            "input_payload": request_payload,
            "actions": [f"{action}{node_label}"],
            "summary": f"{node_label}{summary_status}",
            "uses_llm": uses_llm,
            "call_type": call_type,
        }
        if output_payload is not None:
            metadata["output_payload"] = output_payload
        if duration_ms is not None:
            metadata["duration_ms"] = duration_ms
        if uses_llm:
            metadata["model_calls"] = [
                {
                    "call_type": "chat_llm",
                    "stage": request_payload.get("stage", node_key),
                    "status": status,
                }
            ]
        self.session.add(
            ChapterGenerationTrace(
                chapter_id=workflow_context.chapter.id,
                project_id=workflow_context.run.project_id,
                chapter_number=workflow_context.run.chapter_number,
                node_key=node_key,
                node_label=node_label,
                stage=str(request_payload.get("stage") or node_key)[:64],
                status=status,
                system_prompt=None,
                user_prompt=None,
                raw_response=None,
                cleaned_output=None,
                error=error,
                metadata=metadata,
                source_run_id=workflow_context.run.id,
                source_event_cursor=event.cursor,
                started_at=activity.started_at,
                ended_at=now if status != "running" else None,
                created_at=now,
            )
        )

    async def _next_stream_sequence(self, job: BackgroundTask) -> int:
        stream = await self.repo.get_or_create_stream_for_update(
            stream_type=job.stream_type,
            stream_id=job.stream_id,
            user_id=job.user_id,
            project_id=job.project_id,
        )
        if stream.user_id != job.user_id or stream.project_id != job.project_id:
            raise ValueError("任务事件流归属与任务不一致")
        stream.last_sequence += 1
        job.event_sequence = stream.last_sequence
        await self.session.flush()
        return int(stream.last_sequence)

    async def _require_lease(self, lease: JobLease, *, now: datetime) -> BackgroundTask:
        job = await self.repo.get_for_update(lease.job_id)
        if (
            job is None
            or job.status != "running"
            or job.lease_owner != lease.worker_id
            or job.fencing_token != lease.fencing_token
            or job.executor_generation != lease.executor_generation
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise LeaseLostError("任务 lease 已失效")
        return job

    @staticmethod
    def _lease_from_job(job: BackgroundTask) -> JobLease:
        if job.lease_owner is None or job.lease_expires_at is None:
            raise RuntimeError("claimed job 缺少 lease 字段")
        return JobLease(
            job_id=job.id,
            worker_id=job.lease_owner,
            fencing_token=job.fencing_token,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            job_type=job.task_type,
            payload_version=job.payload_version,
            payload=dict(job.payload or {}),
            user_id=job.user_id,
            project_id=job.project_id,
            executor_generation=job.executor_generation,
            lease_expires_at=job.lease_expires_at,
        )

    @staticmethod
    def _assert_idempotent_request(
        existing: BackgroundTask,
        project_id: Optional[str],
        payload_version: int,
        payload: dict[str, Any],
        stream: tuple[str, str],
    ) -> None:
        if (
            existing.project_id != project_id
            or existing.payload_version != payload_version
            or (existing.payload or {}) != payload
            or (existing.stream_type, existing.stream_id) != stream
        ):
            raise ValueError("同一 idempotency_key 不能用于不同的任务参数")

    @staticmethod
    def _validate_requested_stream(
        stream_type: Optional[str],
        stream_id: Optional[str],
    ) -> Optional[tuple[str, str]]:
        if stream_type is None and stream_id is None:
            return None
        if stream_type is None or stream_id is None:
            raise ValueError("stream_type 与 stream_id 必须同时提供")
        normalized_type, normalized_id = JobService._validate_stream_identity(
            stream_type,
            stream_id,
        )
        if normalized_type != "workflow":
            raise ValueError("显式共享事件流只支持 workflow 类型")
        return normalized_type, normalized_id

    @staticmethod
    def _validate_stream_identity(stream_type: str, stream_id: str) -> tuple[str, str]:
        normalized_type = stream_type.strip()
        normalized_id = stream_id.strip()
        if normalized_type not in {"job", "workflow"}:
            raise ValueError("stream_type 仅支持 job 或 workflow")
        if not normalized_id:
            raise ValueError("stream_id 不能为空")
        if len(normalized_id) > 64:
            raise ValueError("stream_id 长度不能超过 64")
        return normalized_type, normalized_id
