# AIMETA P=持久任务worker_版本化handler执行|R=claim_heartbeat_dispatch_retry|NR=不迁移或引导数据库|E=JobWorker|X=job|A=worker_runtime|D=asyncio,sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .job_registry import JobHandlerDefinition, JobHandlerRegistry, SideEffectClass
from .job_service import (
    AmbiguousActivityError,
    ExecutorGenerationInactiveError,
    JobLease,
    JobService,
    LeaseLostError,
    RetryPolicy,
)
from ..utils.ai_telemetry import AICallResult

logger = logging.getLogger(__name__)

MaintenanceCallback = Callable[[AsyncSession], Awaitable[int]]


class _JobCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class JobOutcome:
    """handler 结果；outcome_writer 与 success event 在同一事务提交。"""

    result: dict[str, Any]
    outcome_writer: Optional[Callable[[AsyncSession], Awaitable[None]]] = None


class RetryableJobError(RuntimeError):
    def __init__(self, category: str, public_message: str):
        super().__init__(public_message)
        self.category = category
        self.public_message = public_message


class PermanentJobError(RuntimeError):
    def __init__(self, category: str, public_message: str):
        super().__init__(public_message)
        self.category = category
        self.public_message = public_message


class JobExecutionContext:
    """handler 可用能力；不暴露 HTTP request 或长生命周期 session。"""

    def __init__(
        self,
        *,
        lease: JobLease,
        side_effect_class: SideEffectClass,
        session_factory,
    ) -> None:
        self.lease = lease
        self.side_effect_class = side_effect_class
        self._session_factory = session_factory

    @property
    def session_factory(self):
        """供 handler 创建显式短事务，不暴露长生命周期 session。"""

        return self._session_factory

    async def progress(self, message: str, *, progress: Optional[int] = None) -> None:
        async with self._session_factory() as session:
            await JobService(session).record_progress(
                self.lease,
                message,
                progress=progress,
            )

    async def begin_activity(
        self,
        activity_key: str,
        *,
        request_payload: Optional[dict[str, Any]] = None,
    ):
        async with self._session_factory() as session:
            return await JobService(session).begin_activity(
                self.lease,
                activity_key=activity_key,
                side_effect_class=self.side_effect_class,
                request_payload=request_payload,
            )

    async def complete_activity(
        self,
        activity_key: str,
        *,
        provider_request_key: str,
        result: dict[str, Any],
        ai_call: Optional[AICallResult[Any]] = None,
    ) -> None:
        async with self._session_factory() as session:
            await JobService(session).complete_activity(
                self.lease,
                activity_key=activity_key,
                provider_request_key=provider_request_key,
                result=result,
                ai_call=ai_call,
            )

    async def mark_activity_ambiguous(
        self,
        activity_key: str,
        *,
        provider_request_key: str,
        public_message: str,
    ) -> None:
        async with self._session_factory() as session:
            await JobService(session).mark_activity_ambiguous(
                self.lease,
                activity_key=activity_key,
                provider_request_key=provider_request_key,
                public_message=public_message,
            )
        raise AmbiguousActivityError(public_message)

    async def mark_activity_failed(
        self,
        activity_key: str,
        *,
        provider_request_key: str,
        error_category: str,
        retryable: bool,
    ) -> None:
        async with self._session_factory() as session:
            await JobService(session).mark_activity_failed(
                self.lease,
                activity_key=activity_key,
                provider_request_key=provider_request_key,
                error_category=error_category,
                retryable=retryable,
            )


class JobWorker:
    """数据库扫描 worker；Redis 仅可作为外部 wake-up 优化。"""

    def __init__(
        self,
        *,
        session_factory,
        registry: JobHandlerRegistry,
        worker_id: str,
        lease_seconds: int,
        heartbeat_interval_seconds: float,
        retry_policy: Optional[RetryPolicy] = None,
        executor_generation: int = 1,
        worker_heartbeat_interval_seconds: float = 10.0,
        poll_interval_seconds: float = 1.0,
        maintenance_callbacks: tuple[MaintenanceCallback, ...] = (),
    ) -> None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds 必须大于等于 1")
        if heartbeat_interval_seconds <= 0 or heartbeat_interval_seconds >= lease_seconds:
            raise ValueError("heartbeat interval 必须大于 0 且小于 lease")
        if worker_heartbeat_interval_seconds <= 0:
            raise ValueError("worker heartbeat interval 必须大于 0")
        if poll_interval_seconds <= 0:
            raise ValueError("poll interval 必须大于 0")
        self.session_factory = session_factory
        self.registry = registry
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.retry_policy = retry_policy or RetryPolicy()
        self.executor_generation = executor_generation
        self.worker_heartbeat_interval_seconds = worker_heartbeat_interval_seconds
        self.poll_interval_seconds = poll_interval_seconds
        self.maintenance_callbacks = maintenance_callbacks

    async def run_once(self) -> bool:
        for callback in self.maintenance_callbacks:
            async with self.session_factory() as maintenance_session:
                try:
                    await callback(maintenance_session)
                    await maintenance_session.commit()
                except Exception:
                    await maintenance_session.rollback()
                    logger.exception(
                        "worker maintenance 失败: callback=%s",
                        getattr(callback, "__name__", type(callback).__name__),
                    )
        async with self.session_factory() as session:
            lease = await JobService(session).claim_next(
                worker_id=self.worker_id,
                lease_seconds=self.lease_seconds,
                executor_generation=self.executor_generation,
            )
        if lease is None:
            return False

        definition = self.registry.get(lease.job_type, lease.payload_version)
        if definition is None:
            async with self.session_factory() as session:
                await JobService(session).mark_dead_letter(
                    lease,
                    error_category="unknown_payload_version",
                    public_message="任务类型或 payload 版本没有可用 handler",
                )
            return True

        context = JobExecutionContext(
            lease=lease,
            side_effect_class=definition.side_effect_class,
            session_factory=self.session_factory,
        )
        try:
            outcome = await self._run_handler(definition, context)
            async with self.session_factory() as session:
                await JobService(session).mark_succeeded(
                    lease,
                    result=outcome.result,
                    outcome_writer=outcome.outcome_writer,
                )
        except AmbiguousActivityError:
            return True
        except _JobCancelled:
            return True
        except LeaseLostError:
            logger.warning("任务 lease 已失效，放弃提交: job_id=%s", lease.job_id)
        except PermanentJobError as exc:
            await self._record_failure(lease, exc.category, exc.public_message, retryable=False)
        except RetryableJobError as exc:
            await self._record_failure(lease, exc.category, exc.public_message, retryable=True)
        except Exception:
            logger.exception("任务 handler 未处理异常: job_id=%s", lease.job_id)
            await self._record_failure(
                lease,
                "unhandled_handler_error",
                "任务执行暂时失败",
                retryable=True,
            )
        return True

    async def run_forever(self, stop_event: asyncio.Event) -> None:
        async with self.session_factory() as session:
            await JobService(session).register_worker(
                worker_id=self.worker_id,
                executor_generation=self.executor_generation,
            )

        lifecycle_task = asyncio.create_task(self._heartbeat_worker(stop_event))
        lifecycle_task.add_done_callback(lambda _task: stop_event.set())
        try:
            while not stop_event.is_set():
                try:
                    worked = await self.run_once()
                except ExecutorGenerationInactiveError:
                    logger.info(
                        "worker generation 已停止 claim: worker_id=%s generation=%s",
                        self.worker_id,
                        self.executor_generation,
                    )
                    stop_event.set()
                    break
                if not worked:
                    try:
                        await asyncio.wait_for(
                            stop_event.wait(),
                            timeout=self.poll_interval_seconds,
                        )
                    except TimeoutError:
                        pass
        finally:
            if not lifecycle_task.done():
                lifecycle_task.cancel()
            lifecycle_result = await asyncio.gather(lifecycle_task, return_exceptions=True)
            async with self.session_factory() as session:
                await JobService(session).mark_worker_stopped(
                    worker_id=self.worker_id,
                    executor_generation=self.executor_generation,
                )
            lifecycle_error = lifecycle_result[0]
            if isinstance(lifecycle_error, BaseException) and not isinstance(
                lifecycle_error,
                asyncio.CancelledError,
            ):
                raise lifecycle_error

    async def _run_handler(
        self,
        definition: JobHandlerDefinition,
        context: JobExecutionContext,
    ) -> JobOutcome:
        handler_task = asyncio.create_task(definition.handler(context))
        heartbeat_task = asyncio.create_task(self._heartbeat_until_done(context.lease, handler_task))
        try:
            done, _ = await asyncio.wait(
                {handler_task, heartbeat_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if handler_task in done:
                heartbeat_task.cancel()
                await asyncio.gather(heartbeat_task, return_exceptions=True)
                result = await handler_task
                if not isinstance(result, JobOutcome):
                    raise PermanentJobError("invalid_handler_result", "任务 handler 返回了无效结果")
                return result

            try:
                signal = await heartbeat_task
            finally:
                handler_task.cancel()
                await asyncio.gather(handler_task, return_exceptions=True)
            if signal == "cancel":
                async with self.session_factory() as session:
                    await JobService(session).mark_cancelled(context.lease)
                raise _JobCancelled("任务已取消")
            raise LeaseLostError("heartbeat 未能续租")
        finally:
            for task in (handler_task, heartbeat_task):
                if not task.done():
                    task.cancel()
            await asyncio.gather(handler_task, heartbeat_task, return_exceptions=True)

    async def _heartbeat_until_done(self, lease: JobLease, handler_task: asyncio.Task) -> str:
        while not handler_task.done():
            await asyncio.sleep(self.heartbeat_interval_seconds)
            async with self.session_factory() as session:
                result = await JobService(session).heartbeat(
                    lease,
                    lease_seconds=self.lease_seconds,
                )
            if result.cancel_requested:
                return "cancel"
        return "done"

    async def _heartbeat_worker(self, stop_event: asyncio.Event) -> None:
        while True:
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self.worker_heartbeat_interval_seconds,
                )
            except TimeoutError:
                async with self.session_factory() as session:
                    await JobService(session).heartbeat_worker(
                        worker_id=self.worker_id,
                        executor_generation=self.executor_generation,
                    )
                continue

            async with self.session_factory() as session:
                await JobService(session).mark_worker_draining(
                    worker_id=self.worker_id,
                    executor_generation=self.executor_generation,
                )
            return

    async def _record_failure(
        self,
        lease: JobLease,
        category: str,
        public_message: str,
        *,
        retryable: bool,
    ) -> None:
        async with self.session_factory() as session:
            await JobService(session).record_failure(
                lease,
                error_category=category,
                public_message=public_message,
                retryable=retryable,
                retry_policy=self.retry_policy,
            )
