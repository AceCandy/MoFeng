# AIMETA P=持久任务worker入口_独立进程与运维命令|R=运行worker_健康检查_指标_retention清理|NR=不提供HTTP服务|E=python:-m-app.worker|X=cli|A=argparse命令|D=asyncio,sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import socket
import sys
from collections.abc import Sequence
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .core.config import settings
from .db.readiness import check_database_readiness
from .db.session import AsyncSessionLocal, engine
from .schemas.chapter_projection import (
    ChapterProjectionOperationRequest,
    ChapterProjectionRetentionRequest,
)
from .services.chapter_generation_trace_projector import (
    project_chapter_generation_traces,
)
from .services.chapter_outbox_dispatcher import repair_chapter_outbox_backlog
from .services.chapter_projection_ops import (
    ChapterProjectionOperationError,
    ChapterProjectionOpsService,
)
from .services.chapter_projection_retention import (
    ChapterProjectionRetentionError,
    ChapterProjectionRetentionService,
)
from .services.chapter_projection_service import ChapterProjectionService
from .services.chapter_workflow_observability import (
    ChapterWorkflowObservabilityService,
)
from .services.chapter_workflow_reconciler import (
    ChapterWorkflowReconciler,
    PostgresChapterWorkflowCheckpointReader,
)
from .services.chapter_workflow_retention import (
    ChapterWorkflowRetentionService,
    PostgresChapterWorkflowCheckpointCleaner,
)
from .services.event_bus import shutdown_event_bus
from .services.job_handlers import build_job_handler_registry
from .services.job_service import JobService
from .services.job_worker import JobWorker

logger = logging.getLogger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.worker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="运行 durable job worker")
    subparsers.add_parser("health", help="检查 worker heartbeat")
    subparsers.add_parser("metrics", help="输出 durable runtime 聚合指标")
    subparsers.add_parser("cleanup-events", help="立即执行一次 JobEvent retention cleanup")
    subparsers.add_parser("cleanup-workflows", help="立即清理过期 terminal workflow 私有状态")
    for command, help_text in (
        ("projection-dry-run", "检查指定章节投影是否可重放"),
        ("projection-replay", "重放指定章节投影"),
    ):
        operation = subparsers.add_parser(command, help=help_text)
        operation.add_argument("--operator-user-id", type=int, required=True)
        operation.add_argument("--project-id", required=True)
        operation.add_argument("--chapter-id", type=int, required=True)
        operation.add_argument("--revision", type=int, required=True)
        operation.add_argument(
            "--projection-name",
            choices=sorted(ChapterProjectionOpsService.ALLOWED_PROJECTIONS),
            required=True,
        )
        operation.add_argument("--idempotency-key", required=True)
        operation.add_argument("--reason", required=True)
        operation.add_argument("--outbox-event-id")
    for command, help_text in (
        ("projection-retention-preview", "预览指定章节投影 generation 的可清理制品"),
        ("projection-retention-purge", "清理指定章节投影 generation 的失活制品"),
    ):
        retention = subparsers.add_parser(command, help=help_text)
        retention.add_argument("--operator-user-id", type=int, required=True)
        retention.add_argument("--project-id", required=True)
        retention.add_argument("--chapter-number", type=int, required=True)
        retention.add_argument("--revision", type=int, required=True)
        retention.add_argument("--artifact-generation", required=True)
        retention.add_argument(
            "--artifact-kind",
            choices=("rag", "foreshadowing"),
            required=True,
        )
        retention.add_argument("--idempotency-key", required=True)
        retention.add_argument("--reason", required=True)
        retention.add_argument("--max-rows", type=int, default=500)
    return parser


def _emit(payload: dict[str, object], *, stream=None) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True),
        file=stream or sys.stdout,
    )


def _configured_worker_name() -> str | None:
    value = settings.job_worker_name
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _runtime_worker_id() -> str:
    name = _configured_worker_name() or socket.gethostname()
    return f"{name}:{os.getpid()}:{uuid4().hex[:12]}"


async def _require_database_ready() -> None:
    readiness = await check_database_readiness()
    if not readiness.ready:
        raise RuntimeError("database_not_ready:" + ",".join(readiness.codes))


async def _cleanup_events_once() -> dict[str, object]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.job_event_retention_days)
    async with AsyncSessionLocal() as session:
        result = await JobService(session).cleanup_events(before=cutoff)
    return {
        "deleted_events": result.deleted_events,
        "affected_users": len(result.affected_user_ids),
        "retention_days": settings.job_event_retention_days,
    }


async def _cleanup_workflows_once() -> dict[str, object]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.chapter_workflow_retention_days)
    async with AsyncSessionLocal() as session:
        result = await ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=PostgresChapterWorkflowCheckpointReader(
                settings.sqlalchemy_database_uri
            ),
            checkpoint_cleaner=PostgresChapterWorkflowCheckpointCleaner(
                settings.sqlalchemy_database_uri
            ),
        ).cleanup(
            before=cutoff,
            limit=settings.chapter_workflow_retention_batch_size,
        )
    return {
        **asdict(result),
        "retention_days": settings.chapter_workflow_retention_days,
    }


async def _retention_loop(stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        try:
            result = await _cleanup_events_once()
            if result["deleted_events"]:
                logger.info("JobEvent retention cleanup 完成: %s", result)
        except Exception:
            logger.exception("JobEvent retention cleanup 失败")
        try:
            result = await _cleanup_workflows_once()
            if result["cleaned_runs"]:
                logger.info("Chapter workflow retention cleanup 完成: %s", result)
        except Exception:
            logger.exception("Chapter workflow retention cleanup 失败")
        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=settings.job_event_cleanup_interval_seconds,
            )
        except TimeoutError:
            continue


def _install_signal_handlers(stop_event: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, stop_event.set)
        except NotImplementedError:  # pragma: no cover - Windows fallback
            signal.signal(signum, lambda _signum, _frame: stop_event.set())


async def _run_worker() -> int:
    await _require_database_ready()
    stop_event = asyncio.Event()
    _install_signal_handlers(stop_event)
    workflow_reconciler = ChapterWorkflowReconciler(
        database_url=settings.sqlalchemy_database_uri,
    )
    worker = JobWorker(
        session_factory=AsyncSessionLocal,
        registry=build_job_handler_registry(
            database_url=settings.sqlalchemy_database_uri,
        ),
        worker_id=_runtime_worker_id(),
        lease_seconds=settings.job_lease_seconds,
        heartbeat_interval_seconds=settings.job_heartbeat_interval_seconds,
        executor_generation=settings.job_worker_generation,
        worker_heartbeat_interval_seconds=settings.job_worker_heartbeat_interval_seconds,
        poll_interval_seconds=settings.job_worker_poll_interval_seconds,
        maintenance_callbacks=(
            repair_chapter_outbox_backlog,
            project_chapter_generation_traces,
            workflow_reconciler,
        ),
    )
    retention_task = asyncio.create_task(_retention_loop(stop_event))
    try:
        await worker.run_forever(stop_event)
    finally:
        stop_event.set()
        await asyncio.gather(retention_task, return_exceptions=True)
    return 0


async def _run_health() -> int:
    await _require_database_ready()
    async with AsyncSessionLocal() as session:
        health = await JobService(session).get_worker_health(
            executor_generation=settings.job_worker_generation,
            stale_after_seconds=settings.job_worker_health_stale_seconds,
        )
    _emit({"command": "health", **asdict(health)})
    return 0 if health.healthy else 1


async def _run_metrics() -> int:
    await _require_database_ready()
    async with AsyncSessionLocal() as session:
        metrics = await JobService(session).get_runtime_metrics()
        chapter_projections = await ChapterProjectionService(session).get_runtime_metrics()
        chapter_workflows = await ChapterWorkflowObservabilityService(
            session,
            checkpoint_reader=PostgresChapterWorkflowCheckpointReader(
                settings.sqlalchemy_database_uri
            ),
        ).get_runtime_metrics(
            projection_alert_after_seconds=settings.job_projection_lag_alert_seconds,
        )
    _emit(
        {
            "command": "metrics",
            "production_readiness": {
                "peak_concurrency": settings.job_peak_concurrency,
                "load_test_concurrency": settings.job_load_test_concurrency,
                "payload_max_bytes": settings.job_payload_max_bytes,
                "max_duration_seconds": settings.job_max_duration_seconds,
                "retention_days": settings.job_event_retention_days,
                "retention_max_bytes": settings.job_retention_max_bytes,
                "recovery_slo_seconds": settings.job_recovery_slo_seconds,
                "queue_age_alert_seconds": settings.job_queue_age_alert_seconds,
                "projection_lag_alert_seconds": settings.job_projection_lag_alert_seconds,
            },
            **asdict(metrics),
            "chapter_projections": chapter_projections,
            "chapter_workflows": asdict(chapter_workflows),
        }
    )
    return 0


async def _run_projection_operation(
    args: argparse.Namespace,
    *,
    mode: str,
) -> int:
    await _require_database_ready()
    request = ChapterProjectionOperationRequest(
        project_id=args.project_id,
        chapter_id=args.chapter_id,
        revision=args.revision,
        projection_name=args.projection_name,
        idempotency_key=args.idempotency_key,
        reason=args.reason,
        outbox_event_id=args.outbox_event_id,
    )
    async with AsyncSessionLocal() as session:
        try:
            response = await ChapterProjectionOpsService(session).execute(
                request=request,
                operator_user_id=args.operator_user_id,
                mode=mode,
            )
        except ChapterProjectionOperationError as exc:
            await session.rollback()
            _emit(
                {
                    "command": args.command,
                    "status": "failed",
                    "error": exc.code,
                },
                stream=sys.stderr,
            )
            return 1
    _emit({"command": args.command, **response.model_dump(mode="json")})
    return 0


async def _run_projection_retention(
    args: argparse.Namespace,
    *,
    mode: str,
) -> int:
    await _require_database_ready()
    request = ChapterProjectionRetentionRequest(
        project_id=args.project_id,
        chapter_number=args.chapter_number,
        revision=args.revision,
        artifact_generation=args.artifact_generation,
        artifact_kind=args.artifact_kind,
        idempotency_key=args.idempotency_key,
        reason=args.reason,
        max_rows=args.max_rows,
    )
    async with AsyncSessionLocal() as session:
        try:
            response = await ChapterProjectionRetentionService(session).execute(
                request=request,
                operator_user_id=args.operator_user_id,
                mode=mode,
            )
        except ChapterProjectionRetentionError as exc:
            await session.rollback()
            _emit(
                {
                    "command": args.command,
                    "status": "failed",
                    "error": exc.code,
                },
                stream=sys.stderr,
            )
            return 1
    _emit({"command": args.command, **response.model_dump(mode="json")})
    return 0


async def _run_command(args: argparse.Namespace) -> int:
    try:
        if args.command == "run":
            return await _run_worker()
        if args.command == "health":
            return await _run_health()
        if args.command == "metrics":
            return await _run_metrics()
        if args.command == "cleanup-events":
            await _require_database_ready()
            _emit({"command": args.command, **await _cleanup_events_once()})
            return 0
        if args.command == "cleanup-workflows":
            await _require_database_ready()
            _emit({"command": args.command, **await _cleanup_workflows_once()})
            return 0
        if args.command == "projection-dry-run":
            return await _run_projection_operation(args, mode="dry_run")
        if args.command == "projection-replay":
            return await _run_projection_operation(args, mode="replay")
        if args.command == "projection-retention-preview":
            return await _run_projection_retention(args, mode="preview")
        if args.command == "projection-retention-purge":
            return await _run_projection_retention(args, mode="purge")
        raise RuntimeError("unknown_worker_command")
    finally:
        await shutdown_event_bus()
        await engine.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(
        level=getattr(logging, settings.logging_level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    args = build_parser().parse_args(argv)
    try:
        return asyncio.run(_run_command(args))
    except Exception as exc:
        logger.error(
            "durable worker 命令失败: command=%s error_type=%s",
            args.command,
            type(exc).__name__,
        )
        _emit(
            {
                "command": args.command,
                "status": "failed",
                "error": "worker_operation_failed",
            },
            stream=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
