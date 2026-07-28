# AIMETA P=durable_worker运维命令测试|R=验证CLI输出_退出码_清理顺序|NR=不连接真实数据库|E=pytest|X=test|A=单元测试|D=pytest|S=none|RD=../app/README.ai
import argparse
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import worker as worker_cli
from app.services.job_service import JobRuntimeMetrics, JobWorkerHealth


class _SessionFactory:
    def __init__(self) -> None:
        self.session = object()

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, _exc_type, _exc, _traceback):
        return False


@pytest.mark.asyncio(loop_scope="session")
async def test_health_command_emits_json_and_uses_exit_code(monkeypatch, capsys) -> None:
    service = MagicMock()
    service.get_worker_health = AsyncMock(
        return_value=JobWorkerHealth(
            healthy=False,
            worker_id="worker-a",
            state="draining",
            heartbeat_age_seconds=2.5,
        )
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(worker_cli, "JobService", lambda _session: service)

    exit_code = await worker_cli._run_health()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload == {
        "command": "health",
        "healthy": False,
        "heartbeat_age_seconds": 2.5,
        "state": "draining",
        "worker_id": "worker-a",
    }
    service.get_worker_health.assert_awaited_once_with(
        executor_generation=worker_cli.settings.job_worker_generation,
        stale_after_seconds=worker_cli.settings.job_worker_health_stale_seconds,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_metrics_command_emits_json(monkeypatch, capsys) -> None:
    service = MagicMock()
    service.get_runtime_metrics = AsyncMock(
        return_value=JobRuntimeMetrics(
            status_counts={"queued": 2, "failed": 1},
            queue_depth=2,
            oldest_queued_age_seconds=12.0,
            expired_leases=1,
            latest_event_cursor=9,
            retained_event_count=8,
            retention_users=1,
        )
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(worker_cli, "JobService", lambda _session: service)

    exit_code = await worker_cli._run_metrics()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["command"] == "metrics"
    assert payload["queue_depth"] == 2
    assert payload["expired_leases"] == 1
    assert payload["status_counts"] == {"failed": 1, "queued": 2}


@pytest.mark.asyncio(loop_scope="session")
async def test_command_closes_event_bus_before_database_engine(monkeypatch) -> None:
    calls: list[str] = []

    async def run_health() -> int:
        calls.append("health")
        return 0

    async def close_event_bus() -> None:
        calls.append("event_bus")

    async def dispose_engine() -> None:
        calls.append("engine")

    monkeypatch.setattr(worker_cli, "_run_health", run_health)
    monkeypatch.setattr(worker_cli, "shutdown_event_bus", close_event_bus)
    fake_engine = MagicMock()
    fake_engine.dispose = dispose_engine
    monkeypatch.setattr(worker_cli, "engine", fake_engine)

    result = await worker_cli._run_command(argparse.Namespace(command="health"))

    assert result == 0
    assert calls == ["health", "event_bus", "engine"]


def test_main_emits_structured_failure(monkeypatch, capsys) -> None:
    async def fail(_args) -> int:
        raise RuntimeError("private failure detail")

    monkeypatch.setattr(worker_cli, "_run_command", fail)
    logger_error = MagicMock()
    monkeypatch.setattr(worker_cli.logger, "error", logger_error)

    exit_code = worker_cli.main(["metrics"])
    payload = json.loads(capsys.readouterr().err)

    assert exit_code == 1
    assert payload == {
        "command": "metrics",
        "error": "worker_operation_failed",
        "status": "failed",
    }
    assert "private failure detail" not in json.dumps(payload)
    logger_error.assert_called_once_with(
        "durable worker 命令失败: command=%s error_type=%s",
        "metrics",
        "RuntimeError",
    )
    assert "private failure detail" not in repr(logger_error.call_args)
