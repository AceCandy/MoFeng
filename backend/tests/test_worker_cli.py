# AIMETA P=durable_worker运维命令测试|R=验证CLI输出_退出码_清理顺序|NR=不连接真实数据库|E=pytest|X=test|A=单元测试|D=pytest|S=none|RD=../app/README.ai
import argparse
import json
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app import worker as worker_cli
from app.schemas.chapter_projection import (
    ChapterProjectionOperationResponse,
    ChapterProjectionRetentionResponse,
)
from app.services.chapter_projection_ops import ChapterProjectionNotFoundError
from app.services.chapter_workflow_observability import ChapterWorkflowRuntimeMetrics
from app.services.chapter_workflow_retention import ChapterWorkflowRetentionResult
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
    workflow_service = MagicMock()
    workflow_service.get_runtime_metrics = AsyncMock(
        return_value=ChapterWorkflowRuntimeMetrics(
            window_seconds=3600,
            status_counts={"waiting_for_selection": 1},
            oldest_state_age_seconds={"waiting_for_selection": 12.0},
            active_runs=1,
            oldest_active_age_seconds=20.0,
            waiting_runs=1,
            oldest_waiting_duration_seconds=12.0,
            command_rejections=0,
            command_rejection_type_counts={},
            command_rejection_reason_counts={},
            needs_attention=0,
            oldest_needs_attention_age_seconds=None,
            checkpoint_runs_observed=1,
            checkpoint_lag=0,
            checkpoint_problem_counts={},
            projection_lag=0,
            oldest_projection_lag_seconds=None,
            reconciler_fix_counts={"projection_completed": 1},
            alerts=(),
        )
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", _SessionFactory())
    monkeypatch.setattr(worker_cli, "JobService", lambda _session: service)
    monkeypatch.setattr(
        worker_cli,
        "ChapterProjectionService",
        lambda _session: projection_service,
    )
    monkeypatch.setattr(
        worker_cli,
        "ChapterWorkflowObservabilityService",
        lambda _session, checkpoint_reader: workflow_service,
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
    assert payload["chapter_workflows"]["waiting_runs"] == 1
    assert payload["chapter_workflows"]["reconciler_fix_counts"] == {"projection_completed": 1}
    assert payload["chapter_workflows"]["alerts"] == []


@pytest.mark.asyncio(loop_scope="session")
async def test_cleanup_workflows_command_emits_bounded_result(monkeypatch, capsys) -> None:
    cleanup = AsyncMock(
        return_value={
            "scanned": 3,
            "cleaned_runs": 1,
            "deleted_threads": 1,
            "scrubbed_commands": 2,
            "scrubbed_activities": 4,
            "protected_current_revision": 1,
            "checkpoint_unavailable": 1,
            "retention_days": 30,
        }
    )
    monkeypatch.setattr(worker_cli, "_require_database_ready", AsyncMock())
    monkeypatch.setattr(worker_cli, "_cleanup_workflows_once", cleanup)
    monkeypatch.setattr(worker_cli, "shutdown_event_bus", AsyncMock())
    fake_engine = MagicMock()
    fake_engine.dispose = AsyncMock()
    monkeypatch.setattr(worker_cli, "engine", fake_engine)

    exit_code = await worker_cli._run_command(argparse.Namespace(command="cleanup-workflows"))
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload == {
        "checkpoint_unavailable": 1,
        "cleaned_runs": 1,
        "command": "cleanup-workflows",
        "deleted_threads": 1,
        "protected_current_revision": 1,
        "retention_days": 30,
        "scanned": 3,
        "scrubbed_activities": 4,
        "scrubbed_commands": 2,
    }
    worker_cli._require_database_ready.assert_awaited_once_with()
    cleanup.assert_awaited_once_with()


@pytest.mark.asyncio(loop_scope="session")
async def test_cleanup_workflows_uses_retention_settings(monkeypatch) -> None:
    fixed_now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)

    class _FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz == timezone.utc
            return fixed_now

    result = ChapterWorkflowRetentionResult(
        scanned=3,
        cleaned_runs=1,
        deleted_threads=1,
        scrubbed_commands=2,
        scrubbed_activities=4,
        protected_current_revision=1,
        checkpoint_unavailable=1,
    )
    service = MagicMock()
    service.cleanup = AsyncMock(return_value=result)
    service_factory = MagicMock(return_value=service)
    checkpoint_reader = object()
    checkpoint_cleaner = object()
    reader_factory = MagicMock(return_value=checkpoint_reader)
    cleaner_factory = MagicMock(return_value=checkpoint_cleaner)
    settings = SimpleNamespace(
        chapter_workflow_retention_days=45,
        chapter_workflow_retention_batch_size=7,
        sqlalchemy_database_uri="postgresql+asyncpg://workflow-retention",
    )
    session_factory = _SessionFactory()
    monkeypatch.setattr(worker_cli, "datetime", _FrozenDateTime)
    monkeypatch.setattr(worker_cli, "settings", settings)
    monkeypatch.setattr(worker_cli, "AsyncSessionLocal", session_factory)
    monkeypatch.setattr(worker_cli, "ChapterWorkflowRetentionService", service_factory)
    monkeypatch.setattr(worker_cli, "PostgresChapterWorkflowCheckpointReader", reader_factory)
    monkeypatch.setattr(worker_cli, "PostgresChapterWorkflowCheckpointCleaner", cleaner_factory)

    payload = await worker_cli._cleanup_workflows_once()

    reader_factory.assert_called_once_with(settings.sqlalchemy_database_uri)
    cleaner_factory.assert_called_once_with(settings.sqlalchemy_database_uri)
    service_factory.assert_called_once_with(
        session_factory.session,
        checkpoint_reader=checkpoint_reader,
        checkpoint_cleaner=checkpoint_cleaner,
    )
    service.cleanup.assert_awaited_once_with(
        before=fixed_now - timedelta(days=45),
        limit=7,
    )
    assert payload == {**result.__dict__, "retention_days": 45}


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize("failing_cleanup", ["events", "workflows"])
async def test_retention_loop_isolates_cleanup_failures(
    monkeypatch,
    failing_cleanup,
) -> None:
    stop_event = worker_cli.asyncio.Event()
    events_cleanup = AsyncMock(return_value={"deleted_events": 0})

    async def finish_or_fail_workflow_cleanup():
        stop_event.set()
        if failing_cleanup == "workflows":
            raise RuntimeError("workflow cleanup failed")
        return {"cleaned_runs": 0}

    workflows_cleanup = AsyncMock(side_effect=finish_or_fail_workflow_cleanup)
    if failing_cleanup == "events":
        events_cleanup.side_effect = RuntimeError("event cleanup failed")
    monkeypatch.setattr(worker_cli, "_cleanup_events_once", events_cleanup)
    monkeypatch.setattr(worker_cli, "_cleanup_workflows_once", workflows_cleanup)

    await worker_cli._retention_loop(stop_event)

    events_cleanup.assert_awaited_once_with()
    workflows_cleanup.assert_awaited_once_with()


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
