# AIMETA P=持久任务服务_任务与事件原子写入|R=幂等入队_事件游标查询|NR=不执行具体任务handler|E=JobService|X=internal|A=transition_service|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import re
from typing import Any, Awaitable, Callable, Optional
from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.job import JobActivity, JobEvent, JobWorkerHeartbeat
from ..repositories.job_repository import JobRepository
from ..schemas.task import BackgroundTaskResponse
from .event_bus import publish_background_task
from .job_registry import SideEffectClass


class LeaseLostError(RuntimeError):
    """worker 的 lease 或 fencing token 已失效。"""


class AmbiguousActivityError(RuntimeError):
    """外部调用可能已发生，禁止自动重放。"""


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
            return raw_delay
        digest = sha256(f"{job_id}:{attempt}".encode("utf-8")).digest()
        unit = int.from_bytes(digest[:8], "big") / ((1 << 64) - 1)
        factor = 1 - self.jitter_ratio + (2 * self.jitter_ratio * unit)
        return min(self.max_delay_seconds, raw_delay * factor)


@dataclass(frozen=True)
class HeartbeatResult:
    """heartbeat 返回 worker 是否应停止当前 handler。"""

    cancel_requested: bool


@dataclass(frozen=True)
class ActivityExecution:
    """handler 应执行 provider 调用，或直接复用已持久化结果。"""

    provider_request_key: str
    should_execute: bool
    result: Optional[dict[str, Any]] = None


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


@dataclass(frozen=True)
class ExecutorRolloutResult:
    """一次 compare-and-swap worker generation 切换结果。"""

    previous_generation: int
    active_generation: int
    fencing_token: int
    reassigned_waiting_jobs: int


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _log_entry(message: str, *, level: str = "info", now: Optional[datetime] = None) -> dict[str, str]:
    return {
        "timestamp": (now or _utc_now()).isoformat(),
        "level": level,
        "message": message,
    }


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _sanitize_public_text(value: str, *, max_length: int = 300) -> str:
    normalized = re.sub(r"\s+", " ", value).strip() or "任务执行失败"
    redacted = re.sub(
        r"(?i)\b(api[_-]?key|authorization|bearer|token|secret|password)\b(\s*[=:]\s*)([^,\s;]+)",
        r"\1\2[已隐藏]",
        normalized,
    )
    return redacted if len(redacted) <= max_length else f"{redacted[:max_length].rstrip()}..."


def _public_task_snapshot(job: BackgroundTask) -> dict[str, Any]:
    """构造可进入 SSE event log 的白名单任务快照。"""
    return {
        "id": job.id,
        "user_id": job.user_id,
        "project_id": job.project_id,
        "stream_type": job.stream_type,
        "stream_id": job.stream_id,
        "task_type": job.task_type,
        "title": job.title,
        "status": BackgroundTaskResponse.public_status(job.status),
        "progress": job.progress,
        "error": job.error,
        "log_entries": list(job.log_entries or []),
        "created_at": _isoformat(job.created_at),
        "updated_at": _isoformat(job.updated_at),
        "started_at": _isoformat(job.started_at),
        "completed_at": _isoformat(job.completed_at),
    }


class JobService:
    """持有 durable job current row 与 append-only event 的事务边界。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = JobRepository(session)

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
        canonical_payload = payload or {}
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
                    payload={"task": _public_task_snapshot(job)},
                )
            )
            await self.session.commit()
        except IntegrityError:
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
        return await self.repo.list_user_jobs(
            user_id=user_id,
            limit=max(1, min(limit, 50)),
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

    async def mark_succeeded(
        self,
        lease: JobLease,
        *,
        result: Optional[dict[str, Any]] = None,
        outcome_writer: Optional[Callable[[AsyncSession], Awaitable[None]]] = None,
        now: Optional[datetime] = None,
    ) -> BackgroundTask:
        completed_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=completed_at)
        except LeaseLostError:
            await self.session.rollback()
            raise

        if job.cancel_requested_at is not None:
            job.status = "cancelled"
            job.completed_at = completed_at
            job.lease_owner = None
            job.lease_expires_at = None
            job.log_entries = [
                *(job.log_entries or []),
                _log_entry("任务在提交结果前完成取消", level="warning", now=completed_at),
            ]
            await self._append_event(job, "job.cancelled", now=completed_at)
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
        await self._append_event(job, "job.succeeded", now=completed_at)
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
            _log_entry(_sanitize_public_text(message), level=level, now=recorded_at),
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
        job.error = _sanitize_public_text(public_message)
        job.dead_lettered_at = dead_lettered_at
        job.completed_at = dead_lettered_at
        job.lease_owner = None
        job.lease_expires_at = None
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry(f"任务进入死信：{job.error}", level="error", now=dead_lettered_at),
        ]
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
        safe_message = _sanitize_public_text(public_message)
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
                _log_entry(f"任务暂时失败，将在 {delay:.1f} 秒后重试", level="warning", now=failed_at),
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
        if job.status in {"queued", "retry_wait"}:
            job.status = "cancelled"
            job.completed_at = requested_at
            job.lease_owner = None
            job.lease_expires_at = None
            event_type = "job.cancelled"
        else:
            event_type = "job.cancel_requested"

        await self._append_event(job, event_type, now=requested_at)
        await self.session.commit()
        await self.session.refresh(job)
        await publish_background_task(job.user_id)
        return job

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

        activity = await self.repo.get_activity_for_update(
            job_id=job.id,
            activity_key=activity_key,
        )
        if activity is not None:
            if activity.side_effect_class != side_effect_class.value:
                await self.session.rollback()
                raise ValueError("同一 activity_key 的 side-effect class 不可变")
            if activity.status == "succeeded":
                await self.session.commit()
                return ActivityExecution(
                    provider_request_key=activity.provider_request_key,
                    should_execute=False,
                    result=dict(activity.result_payload or {}),
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
                    _log_entry("外部调用结果未知，任务已停止自动重试", level="error", now=started_at),
                ]
                await self._append_event(job, "job.needs_attention", now=started_at)
                await self.session.commit()
                await publish_background_task(job.user_id)
                raise AmbiguousActivityError("外部调用结果未知，禁止自动重放")
            await self.session.commit()
            return ActivityExecution(
                provider_request_key=activity.provider_request_key,
                should_execute=True,
            )

        provider_request_key = str(uuid4())
        await self.repo.add_activity(
            JobActivity(
                id=str(uuid4()),
                job_id=job.id,
                activity_key=activity_key,
                side_effect_class=side_effect_class.value,
                status="started",
                provider_request_key=provider_request_key,
                attempt=lease.attempt,
                fencing_token=lease.fencing_token,
                request_payload=request_payload or {},
                result_payload=None,
                started_at=started_at,
                updated_at=started_at,
            )
        )
        await self._append_event(job, "activity.started", now=started_at)
        await self.session.commit()
        await publish_background_task(job.user_id)
        return ActivityExecution(
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
        now: Optional[datetime] = None,
    ) -> JobActivity:
        completed_at = now or _utc_now()
        try:
            job = await self._require_lease(lease, now=completed_at)
        except LeaseLostError:
            await self.session.rollback()
            raise
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

        activity.status = "succeeded"
        activity.result_payload = result
        activity.attempt = lease.attempt
        activity.fencing_token = lease.fencing_token
        activity.completed_at = completed_at
        activity.updated_at = completed_at
        await self.session.flush()
        await self._append_event(job, "activity.succeeded", now=completed_at)
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

        safe_message = _sanitize_public_text(public_message)
        activity.status = "ambiguous"
        activity.error_category = "ambiguous_external_result"
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
        await self._append_event(job, "job.needs_attention", now=recorded_at)
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
        job.log_entries = [
            *(job.log_entries or []),
            _log_entry("任务已取消", level="warning", now=cancelled_at),
        ]
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
        retained_through_cursor = await self.repo.get_retained_through_cursor(
            user_id=user_id
        )
        if after_cursor < retained_through_cursor:
            raise EventCursorExpiredError(retained_through_cursor)
        return await self.repo.list_events(
            user_id=user_id,
            after_cursor=after_cursor,
            limit=max(1, min(limit, 500)),
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
        return await self.repo.list_stream_events(
            user_id=user_id,
            stream_type=normalized_type,
            stream_id=normalized_id,
            after_cursor=after_cursor,
            limit=max(1, min(limit, 500)),
        )

    async def cleanup_events(self, *, before: datetime) -> JobEventCleanupResult:
        """清理过期事件；删除与 retention 水位推进在同一事务提交。"""

        deleted_events, affected_user_ids = await self.repo.delete_events_before(
            before=before
        )
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
    ) -> JobRuntimeMetrics:
        checked_at = now or _utc_now()
        values = await self.repo.get_runtime_metric_values(now=checked_at)
        status_counts = values["status_counts"]
        if not isinstance(status_counts, dict):
            raise RuntimeError("job runtime status 聚合无效")
        oldest_queued_at = values["oldest_queued_at"]
        oldest_age = None
        if isinstance(oldest_queued_at, datetime):
            oldest_age = max(0.0, (checked_at - oldest_queued_at).total_seconds())
        normalized_counts = {
            str(status): int(count)
            for status, count in status_counts.items()
        }
        return JobRuntimeMetrics(
            status_counts=normalized_counts,
            queue_depth=normalized_counts.get("queued", 0)
            + normalized_counts.get("retry_wait", 0),
            oldest_queued_age_seconds=oldest_age,
            expired_leases=int(values["expired_leases"]),
            latest_event_cursor=int(values["latest_event_cursor"]),
            retained_event_count=int(values["retained_event_count"]),
            retention_users=int(values["retention_users"]),
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
        job.log_entries = [*(job.log_entries or []), log_entry]
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

    async def _append_event(
        self,
        job: BackgroundTask,
        event_type: str,
        *,
        now: datetime,
    ) -> JobEvent:
        sequence = await self._next_stream_sequence(job)
        job.updated_at = now
        await self.session.flush()
        return await self.repo.add_event(
            JobEvent(
                job_id=job.id,
                user_id=job.user_id,
                project_id=job.project_id,
                stream_type=job.stream_type,
                stream_id=job.stream_id,
                sequence=sequence,
                event_type=event_type,
                payload={"task": _public_task_snapshot(job)},
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
        return stream.last_sequence

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
