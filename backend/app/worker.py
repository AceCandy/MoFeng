# AIMETA P=持久任务worker入口_独立进程与运维命令|R=运行worker_健康检查_指标_retention清理|NR=不提供HTTP服务|E=python:-m-app.worker|X=cli|A=argparse命令|D=asyncio,sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import logging
import os
import signal
import socket
import sys
from uuid import uuid4
from collections.abc import Sequence

from .core.config import settings
from .db.readiness import check_database_readiness
from .db.session import AsyncSessionLocal, engine
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
    cutoff = datetime.now(timezone.utc) - timedelta(
        days=settings.job_event_retention_days
    )
    async with AsyncSessionLocal() as session:
        result = await JobService(session).cleanup_events(before=cutoff)
    return {
        "deleted_events": result.deleted_events,
        "affected_users": len(result.affected_user_ids),
        "retention_days": settings.job_event_retention_days,
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
    worker = JobWorker(
        session_factory=AsyncSessionLocal,
        registry=build_job_handler_registry(),
        worker_id=_runtime_worker_id(),
        lease_seconds=settings.job_lease_seconds,
        heartbeat_interval_seconds=settings.job_heartbeat_interval_seconds,
        executor_generation=settings.job_worker_generation,
        worker_heartbeat_interval_seconds=settings.job_worker_heartbeat_interval_seconds,
        poll_interval_seconds=settings.job_worker_poll_interval_seconds,
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
    _emit({"command": "metrics", **asdict(metrics)})
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
