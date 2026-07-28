# AIMETA P=durable_worker运维命令测试|R=验证CLI输出_退出码_清理顺序|NR=不连接真实数据库|E=pytest|X=test|A=单元测试|D=pytest|S=none|RD=../app/README.ai
import argparse
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import worker as worker_cli
from app.schemas.chapter_projection import (
    ChapterProjectionOperationResponse,
    ChapterProjectionRetentionResponse,
)
from app.services.chapter_projection_ops import ChapterProjectionNotFoundError
from app.services.job_service import JobRuntimeMetrics, JobWorkerHealth


class _SessionFactory:
    def __init__(self) -> None:
        self.session = MagicMock()
        self.session.rollback = AsyncMock()

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
    projection_service = MagicMock()
    projection_service.get_runtime_metrics = AsyncMock(
        return_value={
            "outbox_backlog": 1,
            "status_counts": {"needs_attention": 1},
            "alerts": ["chapter_outbox_backlog"],
        }
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(worker_cli, "JobService", lambda _session: service)
    monkeypatch.setattr(
        worker_cli,
        "ChapterProjectionService",
        lambda _session: projection_service,
    )

    exit_code = await worker_cli._run_metrics()
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["command"] == "metrics"
    assert payload["queue_depth"] == 2
    assert payload["expired_leases"] == 1
    assert payload["status_counts"] == {"failed": 1, "queued": 2}
    assert payload["chapter_projections"]["outbox_backlog"] == 1
    assert payload["chapter_projections"]["alerts"] == ["chapter_outbox_backlog"]


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_dry_run_command_uses_shared_contract(monkeypatch, capsys) -> None:
    args = worker_cli.build_parser().parse_args(
        [
            "projection-dry-run",
            "--operator-user-id",
            "42",
            "--project-id",
            "11111111-1111-1111-1111-111111111111",
            "--chapter-id",
            "7",
            "--revision",
            "2",
            "--projection-name",
            "memory",
            "--idempotency-key",
            "ops-dry-run-1",
            "--reason",
            "repair projection",
        ]
    )
    service = MagicMock()
    service.execute = AsyncMock(
        return_value=ChapterProjectionOperationResponse(
            mode="dry_run",
            status="eligible",
            idempotency_key="ops-dry-run-1",
            project_id="11111111-1111-1111-1111-111111111111",
            chapter_id=7,
            chapter_number=3,
            revision=2,
            current_revision=2,
            projection_name="memory",
            run_status_counts={"memory.failed": 1},
            active_projections=["summary"],
        )
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(
        worker_cli,
        "ChapterProjectionOpsService",
        lambda _session: service,
    )
    exit_code = await worker_cli._run_projection_operation(args, mode="dry_run")
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {
        "active_projections": ["summary"],
        "chapter_id": 7,
        "chapter_number": 3,
        "command": "projection-dry-run",
        "current_revision": 2,
        "idempotency_key": "ops-dry-run-1",
        "job_id": None,
        "mode": "dry_run",
        "project_id": "11111111-1111-1111-1111-111111111111",
        "projection_name": "memory",
        "projection_run_id": None,
        "reason_code": None,
        "revision": 2,
        "run_status_counts": {"memory.failed": 1},
        "status": "eligible",
    }
    request = service.execute.await_args.kwargs["request"]
    assert request.reason == "repair projection"
    assert request.outbox_event_id is None
    assert service.execute.await_args.kwargs["operator_user_id"] == 42


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_replay_command_emits_allowlisted_error(monkeypatch, capsys) -> None:
    args = worker_cli.build_parser().parse_args(
        [
            "projection-replay",
            "--operator-user-id",
            "43",
            "--project-id",
            "22222222-2222-2222-2222-222222222222",
            "--chapter-id",
            "8",
            "--revision",
            "1",
            "--projection-name",
            "summary",
            "--idempotency-key",
            "ops-replay-1",
            "--reason",
            "repair summary",
        ]
    )
    service = MagicMock()
    service.execute = AsyncMock(
        side_effect=ChapterProjectionNotFoundError("operator_not_authorized")
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(
        worker_cli,
        "ChapterProjectionOpsService",
        lambda _session: service,
    )
    exit_code = await worker_cli._run_projection_operation(args, mode="replay")
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.out == ""
    assert json.loads(captured.err) == {
        "command": "projection-replay",
        "error": "operator_not_authorized",
        "status": "failed",
    }
    worker_cli.AsyncSessionLocal.session.rollback.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_retention_preview_command_uses_bounded_contract(
    monkeypatch,
    capsys,
) -> None:
    args = worker_cli.build_parser().parse_args(
        [
            "projection-retention-preview",
            "--operator-user-id",
            "44",
            "--project-id",
            "33333333-3333-3333-3333-333333333333",
            "--chapter-number",
            "3",
            "--revision",
            "1",
            "--artifact-generation",
            "44444444-4444-4444-4444-444444444444",
            "--artifact-kind",
            "rag",
            "--idempotency-key",
            "retention-preview-1",
            "--reason",
            "inspect stale artifacts",
            "--max-rows",
            "25",
        ]
    )
    service = MagicMock()
    service.execute = AsyncMock(
        return_value=ChapterProjectionRetentionResponse(
            mode="preview",
            status="eligible",
            idempotency_key="retention-preview-1",
            audit_id="55555555-5555-5555-5555-555555555555",
            project_id="33333333-3333-3333-3333-333333333333",
            chapter_id=9,
            chapter_number=3,
            revision=1,
            artifact_generation="44444444-4444-4444-4444-444444444444",
            artifact_kind="rag",
            candidate_rows={"rag_chunks": 2, "rag_summaries": 1},
        )
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(
        worker_cli,
        "ChapterProjectionRetentionService",
        lambda _session: service,
    )

    exit_code = await worker_cli._run_projection_retention(args, mode="preview")
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["command"] == "projection-retention-preview"
    assert payload["candidate_rows"] == {"rag_chunks": 2, "rag_summaries": 1}
    assert payload["deleted_rows"] == {}
    request = service.execute.await_args.kwargs["request"]
    assert request.max_rows == 25
    assert request.artifact_kind == "rag"
    assert service.execute.await_args.kwargs["operator_user_id"] == 44


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
