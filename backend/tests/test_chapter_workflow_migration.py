"""Durable Chapter workflow schema and pinned checkpointer contract."""

from __future__ import annotations

import asyncio
import multiprocessing
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_chapter_workflow_start import _seed_project

from alembic import command
from app.core.config import settings
from app.db.base import Base
from app.db.chapter_workflow_checkpointer import open_chapter_workflow_checkpointer
from app.db.migration import build_alembic_config, run_migrations
from app.db.readiness import (
    CHECKPOINT_MIGRATION_VERSIONS,
    CHECKPOINT_TABLES,
    inspect_database_state,
)
from app.models import (
    BackgroundTask,
    Chapter,
    ChapterGenerationTrace,
    ChapterGenerationTraceProjectionCheckpoint,
    ChapterOutboxEvent,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
    ChapterVersion,
    ChapterWorkflowCommand,
    ChapterWorkflowRun,
    JobActivity,
    JobEvent,
)
from app.models.job import JobWorkerHeartbeat
from app.schemas.chapter_context import stable_digest
from app.schemas.chapter_workflow import (
    ChapterWorkflowCommandEnvelope,
    ChapterWorkflowStateV1,
)
from app.schemas.job import (
    ChapterProjectionJobPayload,
    ChapterWorkflowJobPayload,
    ChapterWorkflowRetrievalInputs,
    ChapterWorkflowRuntimeInputs,
)
from app.schemas.novel import ChapterGenerationStatus
from app.services.chapter_generation_trace_projector import (
    project_chapter_generation_traces,
)
from app.services.chapter_projection_runtime import (
    CurrentProjection,
    enqueue_downstream_projections,
    maybe_enqueue_reconciler,
)
from app.services.chapter_workflow_activities import (
    ChapterWorkflowCandidateOutput,
    ChapterWorkflowPlanOutput,
    ChapterWorkflowPostReviewOutput,
    ChapterWorkflowReviewOutput,
)
from app.services.chapter_workflow_graph import (
    ChapterWorkflowGraphBindingsV1,
    build_chapter_workflow_graph_registry,
    chapter_workflow_graph_config,
)
from app.services.chapter_workflow_handler import ChapterWorkflowBindingAssemblerV1
from app.services.chapter_workflow_reconciler import (
    ChapterWorkflowReconcileCandidate,
    ChapterWorkflowReconciler,
    PostgresChapterWorkflowCheckpointReader,
)
from app.services.chapter_workflow_retention import (
    ChapterWorkflowRetentionService,
    PostgresChapterWorkflowCheckpointCleaner,
)
from app.services.chapter_workflow_runtime import ChapterWorkflowRuntime
from app.services.chapter_workflow_start import ChapterWorkflowStartService
from app.services.event_bus import shutdown_event_bus
from app.services.job_handlers import build_job_handler_registry
from app.services.job_registry import SideEffectClass
from app.services.job_service import (
    ChapterWorkflowPendingResume,
    JobLease,
    JobService,
    LeaseLostError,
)
from app.services.job_worker import JobExecutionContext, JobOutcome, JobWaitOutcome, JobWorker


@asynccontextmanager
async def _temporary_database(source_engine):
    database_name = f"mofeng_workflow_{uuid4().hex}"
    admin_engine = create_async_engine(
        source_engine.url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as connection:
            quoted = connection.dialect.identifier_preparer.quote(database_name)
            await connection.execute(sa.text(f"CREATE DATABASE {quoted}"))
        yield source_engine.url.set(database=database_name).render_as_string(hide_password=False)
    finally:
        try:
            async with admin_engine.connect() as connection:
                await connection.execute(
                    sa.text(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": database_name},
                )
                quoted = connection.dialect.identifier_preparer.quote(database_name)
                await connection.execute(sa.text(f"DROP DATABASE IF EXISTS {quoted}"))
        finally:
            await admin_engine.dispose()


def _downgrade(connection, database_url: str) -> None:
    config = build_alembic_config(database_url)
    config.attributes["connection"] = connection
    command.downgrade(config, "f2a6c9d4e8b1")


def _checkpoint_smoke_bindings(
    calls: list[str] | None = None,
) -> ChapterWorkflowGraphBindingsV1:
    async def empty(state):
        if calls is not None:
            calls.append(state.node_key)
        return {}

    async def persist(_state):
        if calls is not None:
            calls.append("persist_candidates")
        return {"candidate_version_ids": [1]}

    async def selection_resume(_state, resume_value):
        if calls is not None:
            calls.append("apply_selection_resume")
        return {
            "selected_version_id": resume_value["selected_version_id"],
            "last_applied_command_id": resume_value["command_id"],
        }

    async def projection_resume(_state, resume_value):
        if calls is not None:
            calls.append("apply_projection_resume")
        if isinstance(resume_value, dict) and isinstance(resume_value.get("command_id"), str):
            return {"last_applied_command_id": resume_value["command_id"]}
        return {}

    async def finalize(_state):
        if calls is not None:
            calls.append("finalize_revision")
        return {"target_chapter_revision": 1}

    return ChapterWorkflowGraphBindingsV1(
        freeze_context=empty,
        plan_and_direct=empty,
        generate_candidates=empty,
        review_candidates=empty,
        persist_candidates=persist,
        apply_selection_resume=selection_resume,
        finalize_revision=finalize,
        apply_projection_resume=projection_resume,
        observe_projection=empty,
    )


def _runtime_execution(run_id: str) -> JobExecutionContext:
    runtime_inputs = ChapterWorkflowRuntimeInputs(
        project_id="workflow-project",
        chapter_number=1,
        retrieval_inputs=ChapterWorkflowRetrievalInputs(
            enabled=False,
            mode="simple",
            query_text="第一章",
        ),
    )
    payload = ChapterWorkflowJobPayload(
        run_id=run_id,
        project_id="workflow-project",
        chapter_id=1,
        chapter_number=1,
        base_revision=0,
        context_hash="a" * 64,
        runtime_input_hash=stable_digest(runtime_inputs.model_dump(mode="json")),
        runtime_inputs=runtime_inputs,
    )
    lease = JobLease(
        job_id=str(uuid4()),
        worker_id="workflow-runtime-test",
        fencing_token=1,
        attempt=1,
        max_attempts=3,
        job_type="chapter_workflow",
        payload_version=1,
        payload=payload.model_dump(mode="json"),
        user_id=1,
        project_id="workflow-project",
        executor_generation=1,
        lease_expires_at=datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    return JobExecutionContext(
        lease=lease,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        session_factory=None,
    )


class _ProductionTestProviders:
    def __init__(self, calls: list[str]) -> None:
        self.calls = calls

    async def plan(self, _request, *, provider_request_key):
        assert provider_request_key
        self.calls.append("plan")
        return ChapterWorkflowPlanOutput(mission={"goal": "持久化测试"})

    async def candidate(self, request, *, provider_request_key):
        assert provider_request_key
        self.calls.append(f"candidate:{request.ordinal}")
        return ChapterWorkflowCandidateOutput(
            ordinal=request.ordinal,
            content=f"候选正文-{request.ordinal}",
        )

    async def review(self, request, *, provider_request_key):
        assert provider_request_key
        self.calls.append("review")
        return ChapterWorkflowReviewOutput(
            best_ordinal=request.candidates[0].ordinal,
            report={"summary": "采用第一版"},
        )

    async def post_review(self, request, *, provider_request_key):
        assert provider_request_key
        self.calls.append(f"post_review:{request.stage}")
        return ChapterWorkflowPostReviewOutput(
            stage=request.stage,
            content=f"{request.source_candidate.content}-已润色",
            report={"applied": True},
        )


async def _complete_required_projection_jobs(
    session_factory,
    *,
    run_id: str,
    chapter_id: int,
    user_id: int,
) -> str:
    async with session_factory() as session:
        chapter = await session.get(Chapter, chapter_id)
        revision = (
            await session.execute(
                select(ChapterRevision).where(ChapterRevision.chapter_id == chapter_id)
            )
        ).scalar_one()
        summary_run = (
            await session.execute(
                select(ChapterProjectionRun).where(
                    ChapterProjectionRun.chapter_revision_id == revision.id,
                    ChapterProjectionRun.projection_name == "summary",
                )
            )
        ).scalar_one()
        summary_job = await session.get(BackgroundTask, summary_run.job_id)
        rollout = (
            await session.execute(
                select(ChapterProjectionRollout).where(
                    ChapterProjectionRollout.chapter_id == chapter_id
                )
            )
        ).scalar_one()
        assert chapter is not None and summary_job is not None
        summary_run.status = "succeeded"
        summary_run.is_active = True
        summary_job.status = "succeeded"
        summary_payload = ChapterProjectionJobPayload.model_validate(summary_job.payload)
        current = CurrentProjection(
            chapter,
            revision,
            summary_run,
            rollout,
            None,
        )
        downstream = await enqueue_downstream_projections(
            session,
            payload=summary_payload,
            current=current,
            user_id=user_id,
        )
        for projection_run in downstream:
            projection_run.status = "succeeded"
            projection_run.is_active = True
            projection_job = await session.get(
                BackgroundTask,
                projection_run.job_id,
            )
            assert projection_job is not None
            projection_job.status = "succeeded"
        reconcile_run = await maybe_enqueue_reconciler(
            session,
            payload=summary_payload,
            current=current,
            user_id=user_id,
        )
        assert reconcile_run is not None and reconcile_run.job_id is not None
        assert summary_job.stream_id == run_id
        reconcile_job_id = reconcile_run.job_id
        assert isinstance(reconcile_job_id, str)
        await session.commit()
        return reconcile_job_id


def _run_production_workflow_worker_process(
    database_url: str,
    worker_id: str,
    executor_generation: int,
    pause_before_review: Any,
    hold_after_turn: bool,
    resume_after_review: Any = None,
    max_turns: int = 1,
) -> None:
    """在独立进程运行一个 production workflow turn，并可停在候选 checkpoint。"""

    async def run() -> None:
        settings.redis_url = None
        await shutdown_event_bus()
        engine = create_async_engine(database_url)
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            stop_event = asyncio.Event()

            if pause_before_review is not None:
                blocker = asyncio.Event()
                review_candidates = ChapterWorkflowBindingAssemblerV1.review_candidates

                async def pause_review(
                    _assembler: ChapterWorkflowBindingAssemblerV1,
                    _state: ChapterWorkflowStateV1,
                ) -> dict[str, object]:
                    pause_before_review.set()
                    if resume_after_review is None:
                        await blocker.wait()
                    else:
                        await asyncio.to_thread(resume_after_review.wait)
                    result = await review_candidates(_assembler, _state)
                    if not isinstance(result, dict):
                        raise AssertionError("review_candidates 必须返回字典")
                    typed_result: dict[str, object] = {}
                    for key, value in result.items():
                        if not isinstance(key, str):
                            raise AssertionError("review_candidates 字典键必须是字符串")
                        typed_result[key] = value
                    return typed_result

                setattr(
                    ChapterWorkflowBindingAssemblerV1,
                    "review_candidates",
                    pause_review,
                )

            def provider_factory(_execution):
                return _ProductionTestProviders([])

            registry = build_job_handler_registry(
                database_url=database_url,
                chapter_workflow_provider_factory=provider_factory,
            )

            async def rollout_probe(_execution: JobExecutionContext) -> JobOutcome:
                return JobOutcome(
                    result={
                        "worker_id": worker_id,
                        "executor_generation": executor_generation,
                    }
                )

            registry.register(
                job_type="phase7_rollout_probe",
                payload_version=1,
                side_effect_class=SideEffectClass.TRANSACTIONAL,
                handler=rollout_probe,
            )

            class PhaseWorker(JobWorker):
                completed_turns = 0

                async def run_once(self) -> bool:
                    if self.completed_turns >= max_turns:
                        return False
                    worked = bool(await super().run_once())
                    if worked:
                        self.completed_turns += 1
                        if self.completed_turns >= max_turns and not hold_after_turn:
                            stop_event.set()
                    return worked

            worker = PhaseWorker(
                session_factory=session_factory,
                registry=registry,
                worker_id=worker_id,
                lease_seconds=1,
                heartbeat_interval_seconds=0.2,
                executor_generation=executor_generation,
                worker_heartbeat_interval_seconds=0.2,
                poll_interval_seconds=0.05,
            )
            await worker.run_forever(stop_event)
        finally:
            await engine.dispose()
            await shutdown_event_bus()

    asyncio.run(run())


async def _wait_for_workflow_state(
    session_factory,
    *,
    run_id: str,
    root_job_id: str,
    run_status: str,
    node_key: str,
    root_status: str,
    timeout: float = 30,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        async with session_factory() as session:
            run = await session.get(ChapterWorkflowRun, run_id)
            root = await session.get(BackgroundTask, root_job_id)
            if (
                run is not None
                and root is not None
                and run.status == run_status
                and run.node_key == node_key
                and root.status == root_status
            ):
                return
        await asyncio.sleep(0.05)
    raise AssertionError(f"workflow 未在 {timeout} 秒内进入 {run_status}/{node_key}/{root_status}")


async def _wait_for_worker_state(
    session_factory,
    *,
    worker_id: str,
    state: str,
    timeout: float = 10,
) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        async with session_factory() as session:
            heartbeat = await session.get(JobWorkerHeartbeat, worker_id)
            if heartbeat is not None and heartbeat.state == state:
                return
        await asyncio.sleep(0.05)
    raise AssertionError(f"worker 未在 {timeout} 秒内进入 {state} 状态")


async def _wait_for_checkpoint_node(
    database_url: str,
    *,
    run_id: str,
    node_key: str,
    timeout: float = 30,
) -> tuple[str, ChapterWorkflowStateV1]:
    reader = PostgresChapterWorkflowCheckpointReader(database_url)
    candidate = ChapterWorkflowReconcileCandidate(
        run_id=run_id,
        workflow_version=1,
        state_schema_version=1,
        is_active=True,
    )
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        evidence = (await reader.read([candidate]))[run_id]
        if (
            evidence.checkpoint_id is not None
            and evidence.state is not None
            and evidence.state.node_key == node_key
        ):
            return evidence.checkpoint_id, evidence.state
        await asyncio.sleep(0.05)
    raise AssertionError(f"checkpoint 未在 {timeout} 秒内进入 {node_key}")


async def _terminate_worker_process(process) -> None:
    assert process.is_alive(), f"worker process 已提前退出: exitcode={process.exitcode}"
    process.terminate()
    await asyncio.to_thread(process.join, 10)
    assert not process.is_alive()
    assert process.exitcode is not None and process.exitcode != 0


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_migration_adopts_matching_precreated_trace_checkpoint_table() -> None:
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with _temporary_database(source_engine) as database_url:
            engine = create_async_engine(database_url)
            try:
                async with engine.begin() as connection:

                    def upgrade_to_b7(sync_connection) -> None:
                        config = build_alembic_config(database_url)
                        config.attributes["connection"] = sync_connection
                        command.upgrade(config, "b7d4e2f1a9c3")

                    await connection.run_sync(upgrade_to_b7)
                    await connection.run_sync(Base.metadata.create_all)
                    await connection.execute(
                        sa.insert(ChapterGenerationTraceProjectionCheckpoint).values(
                            projector_name="chapter_generation_trace_v1",
                            last_event_cursor=17,
                        )
                    )

                await run_migrations(database_url)
                with pytest.raises(RuntimeError, match="binary rollback floor"):
                    async with engine.begin() as connection:

                        def downgrade_to_b7(sync_connection) -> None:
                            config = build_alembic_config(database_url)
                            config.attributes["connection"] = sync_connection
                            command.downgrade(config, "b7d4e2f1a9c3")

                        await connection.run_sync(downgrade_to_b7)

                state = await inspect_database_state(engine)
                async with engine.connect() as connection:
                    cursor = await connection.scalar(
                        sa.text(
                            "SELECT last_event_cursor FROM "
                            "chapter_generation_trace_projection_checkpoints "
                            "WHERE projector_name = 'chapter_generation_trace_v1'"
                        )
                    )
            finally:
                await engine.dispose()

            assert state.database_revisions == ("c8e5f2a1d4b6",)
            assert cursor == 17
    finally:
        await source_engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_migration_rejects_incompatible_precreated_trace_checkpoint_table() -> None:
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with _temporary_database(source_engine) as database_url:
            engine = create_async_engine(database_url)
            try:
                async with engine.begin() as connection:

                    def upgrade_to_b7(sync_connection) -> None:
                        config = build_alembic_config(database_url)
                        config.attributes["connection"] = sync_connection
                        command.upgrade(config, "b7d4e2f1a9c3")

                    await connection.run_sync(upgrade_to_b7)
                    await connection.run_sync(Base.metadata.create_all)
                    await connection.execute(
                        sa.text(
                            "ALTER TABLE chapter_generation_trace_projection_checkpoints "
                            "ADD COLUMN unexpected INTEGER"
                        )
                    )

                with pytest.raises(
                    RuntimeError,
                    match="incompatible_preexisting_generation_trace_projection_checkpoint_schema",
                ):
                    await run_migrations(database_url)

                async with engine.connect() as connection:
                    revision = await connection.scalar(
                        sa.text("SELECT version_num FROM alembic_version")
                    )
                    trace_columns = await connection.run_sync(
                        lambda sync: {
                            item["name"]
                            for item in sa.inspect(sync).get_columns("chapter_generation_traces")
                        }
                    )
            finally:
                await engine.dispose()

            assert revision == "b7d4e2f1a9c3"
            assert "source_run_id" not in trace_columns
            assert "source_event_cursor" not in trace_columns
    finally:
        await source_engine.dispose()


def test_workflow_migration_rejects_offline_sql_generation() -> None:
    config = build_alembic_config(settings.sqlalchemy_database_uri)
    output = StringIO()
    config.output_buffer = output

    with pytest.raises(RuntimeError, match="requires an online migration"):
        command.upgrade(
            config,
            "b7d4e2f1a9c3:c8e5f2a1d4b6",
            sql=True,
        )

    generated_sql = output.getvalue().upper()
    assert "ALTER TABLE" not in generated_sql
    assert "CREATE TABLE" not in generated_sql
    assert "INSERT INTO" not in generated_sql


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_migration_installs_pinned_checkpoint_schema() -> None:
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with _temporary_database(source_engine) as database_url:
            await run_migrations(database_url)
            engine = create_async_engine(database_url)
            try:
                async with engine.begin() as connection:

                    def check_schema(sync_connection) -> None:
                        config = build_alembic_config(database_url)
                        config.attributes["connection"] = sync_connection
                        command.check(config)

                    await connection.run_sync(check_schema)

                state = await inspect_database_state(engine)
                assert state.database_revisions == ("c8e5f2a1d4b6",)
                assert state.checkpoint_tables == CHECKPOINT_TABLES
                assert state.checkpoint_migration_versions == CHECKPOINT_MIGRATION_VERSIONS

                async with engine.connect() as sql:
                    indexes = await sql.run_sync(
                        lambda sync: {
                            table: {item["name"] for item in sa.inspect(sync).get_indexes(table)}
                            for table in (
                                "checkpoints",
                                "checkpoint_blobs",
                                "checkpoint_writes",
                            )
                        }
                    )
                    table_names = await sql.run_sync(
                        lambda sync: set(sa.inspect(sync).get_table_names())
                    )
                    trace_columns = await sql.run_sync(
                        lambda sync: {
                            item["name"]
                            for item in sa.inspect(sync).get_columns("chapter_generation_traces")
                        }
                    )
                    trace_unique_constraints = await sql.run_sync(
                        lambda sync: {
                            item["name"]
                            for item in sa.inspect(sync).get_unique_constraints(
                                "chapter_generation_traces"
                            )
                        }
                    )
                    trace_projection_cursor = await sql.scalar(
                        sa.text(
                            "SELECT last_event_cursor FROM "
                            "chapter_generation_trace_projection_checkpoints "
                            "WHERE projector_name = 'chapter_generation_trace_v1'"
                        )
                    )
                assert {
                    "chapter_generation_trace_projection_checkpoints",
                    "chapter_workflow_runs",
                    "chapter_workflow_commands",
                    *CHECKPOINT_TABLES,
                } <= table_names
                assert {"source_run_id", "source_event_cursor"} <= trace_columns
                assert "uq_chapter_generation_trace_source" in trace_unique_constraints
                assert trace_projection_cursor == 0
                assert indexes == {
                    "checkpoints": {"checkpoints_thread_id_idx"},
                    "checkpoint_blobs": {"checkpoint_blobs_thread_id_idx"},
                    "checkpoint_writes": {"checkpoint_writes_thread_id_idx"},
                }

                workflow_state = ChapterWorkflowStateV1.initial(
                    run_id=str(uuid4()),
                    context_hash="a" * 64,
                )
                sentinel_state = ChapterWorkflowStateV1.initial(
                    run_id=str(uuid4()),
                    context_hash="b" * 64,
                )
                config = chapter_workflow_graph_config(workflow_state.run_id)
                sentinel_config = chapter_workflow_graph_config(sentinel_state.run_id)
                async with open_chapter_workflow_checkpointer(database_url) as saver:
                    app = build_chapter_workflow_graph_registry().compile(
                        workflow_state.workflow_version,
                        checkpointer=saver,
                        bindings=_checkpoint_smoke_bindings(),
                    )
                    result = await app.ainvoke(
                        workflow_state.model_dump(mode="json"),
                        config,
                    )
                    snapshot = await app.aget_state(config)
                    assert result["__interrupt__"][0].value["kind"] == "selection"
                    assert snapshot.values["node_key"] == "waiting_for_selection"
                    assert snapshot.next == ("waiting_for_selection",)
                    assert snapshot.config["configurable"]["thread_id"] == workflow_state.run_id
                    assert snapshot.config["configurable"]["checkpoint_id"]
                    sentinel_result = await app.ainvoke(
                        sentinel_state.model_dump(mode="json"),
                        sentinel_config,
                    )
                    assert sentinel_result["__interrupt__"][0].value["kind"] == "selection"
                    async with engine.connect() as sql:
                        sentinel_counts_before = {
                            table: await sql.scalar(
                                sa.text(
                                    f"SELECT count(*) FROM {table} " "WHERE thread_id = :thread_id"
                                ),
                                {"thread_id": sentinel_state.run_id},
                            )
                            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
                        }
                    assert sentinel_counts_before["checkpoints"] > 0
                    await saver.adelete_thread(workflow_state.run_id)
                    assert await saver.aget_tuple(config) is None
                    assert await saver.aget_tuple(sentinel_config) is not None

                async with engine.connect() as sql:
                    deleted_thread_counts = {
                        table: await sql.scalar(
                            sa.text(f"SELECT count(*) FROM {table} WHERE thread_id = :thread_id"),
                            {"thread_id": workflow_state.run_id},
                        )
                        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
                    }
                    sentinel_counts_after = {
                        table: await sql.scalar(
                            sa.text(f"SELECT count(*) FROM {table} WHERE thread_id = :thread_id"),
                            {"thread_id": sentinel_state.run_id},
                        )
                        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
                    }
                assert deleted_thread_counts == {
                    "checkpoints": 0,
                    "checkpoint_blobs": 0,
                    "checkpoint_writes": 0,
                }
                assert sentinel_counts_after == sentinel_counts_before

                calls: list[str] = []
                bindings = _checkpoint_smoke_bindings(calls)
                execution = _runtime_execution(str(uuid4()))
                first_turn = await ChapterWorkflowRuntime(
                    execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute()
                calls_after_first_turn = list(calls)

                assert isinstance(first_turn, JobWaitOutcome)
                assert first_turn.workflow_transition.status == "waiting_for_selection"
                assert first_turn.workflow_transition.checkpoint_id

                recovered_wait = await ChapterWorkflowRuntime(
                    execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute()
                assert isinstance(recovered_wait, JobWaitOutcome)
                assert recovered_wait.workflow_transition == first_turn.workflow_transition
                assert calls == calls_after_first_turn

                selection_turn = await ChapterWorkflowRuntime(
                    execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute(
                    resume_value={
                        "command_id": str(uuid4()),
                        "selected_version_id": 1,
                    }
                )
                assert isinstance(selection_turn, JobWaitOutcome)
                assert selection_turn.workflow_transition.status == "projection_pending"
                assert selection_turn.workflow_transition.checkpoint_id
                assert (
                    selection_turn.workflow_transition.checkpoint_id
                    != first_turn.workflow_transition.checkpoint_id
                )

                final_turn = await ChapterWorkflowRuntime(
                    execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute(resume_value={"ready": True})
                assert isinstance(final_turn, JobOutcome)
                assert final_turn.result["run_id"] == execution.lease.payload["run_id"]
                assert final_turn.result["selected_version_id"] == 1
                assert final_turn.result["target_chapter_revision"] == 1

                calls_after_terminal = list(calls)
                with pytest.raises(ValueError, match="当前 interrupt checkpoint"):
                    await ChapterWorkflowRuntime(
                        execution,
                        database_url=database_url,
                        bindings=bindings,
                    ).execute(resume_value={"stale": True})
                assert calls == calls_after_terminal

                with pytest.raises(RuntimeError, match="binary rollback floor"):
                    async with engine.begin() as sql:
                        await sql.run_sync(_downgrade, database_url)
            finally:
                await engine.dispose()
    finally:
        await source_engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_retention_service_deletes_only_target_checkpoint_thread() -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with _temporary_database(source_engine) as database_url:
            await run_migrations(database_url)
            engine = create_async_engine(database_url)
            try:
                session_factory = async_sessionmaker(engine, expire_on_commit=False)
                async with session_factory() as session:
                    await _seed_project(
                        session,
                        user_id=8905,
                        project_id="workflow-retention-checkpoint",
                    )
                    started = await ChapterWorkflowStartService(session).start(
                        user_id=8905,
                        project_id="workflow-retention-checkpoint",
                        chapter_number=1,
                        flow_config={"preset": "basic", "enable_rag": False},
                    )
                    target_state = ChapterWorkflowStateV1.initial(
                        run_id=started.run.id,
                        context_hash=started.run.context_hash,
                    )
                    sentinel_state = ChapterWorkflowStateV1.initial(
                        run_id=str(uuid4()),
                        context_hash="f" * 64,
                    )
                    target_config = chapter_workflow_graph_config(target_state.run_id)
                    sentinel_config = chapter_workflow_graph_config(sentinel_state.run_id)

                    async with open_chapter_workflow_checkpointer(database_url) as saver:
                        app = build_chapter_workflow_graph_registry().compile(
                            target_state.workflow_version,
                            checkpointer=saver,
                            bindings=_checkpoint_smoke_bindings(),
                        )
                        await app.ainvoke(target_state.model_dump(mode="json"), target_config)
                        target_snapshot = await app.aget_state(target_config)
                        await app.ainvoke(
                            sentinel_state.model_dump(mode="json"),
                            sentinel_config,
                        )

                    async with engine.connect() as sql:
                        sentinel_counts_before = {
                            table: await sql.scalar(
                                sa.text(
                                    f"SELECT count(*) FROM {table} WHERE thread_id = :thread_id"
                                ),
                                {"thread_id": sentinel_state.run_id},
                            )
                            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
                        }
                    assert sentinel_counts_before["checkpoints"] > 0

                    checkpoint_id = target_snapshot.config["configurable"]["checkpoint_id"]
                    started.root_job.status = "failed"
                    started.root_job.completed_at = old
                    started.run.status = "failed"
                    started.run.node_key = "failed"
                    started.run.is_active = False
                    started.run.completed_at = old
                    started.run.checkpoint_id = checkpoint_id
                    command_row = ChapterWorkflowCommand(
                        id=str(uuid4()),
                        run_id=started.run.id,
                        type="cancel",
                        payload_version=1,
                        payload={"private": "retention smoke"},
                        actor_user_id=started.run.user_id,
                        expected_run_revision=started.run.row_revision,
                        expected_chapter_revision=started.run.base_revision,
                        expected_checkpoint_id=checkpoint_id,
                        status="rejected",
                        rejection_code="stale_checkpoint",
                        result_payload={"private": "retention result"},
                    )
                    session.add(command_row)
                    await session.commit()

                    result = await ChapterWorkflowRetentionService(
                        session,
                        checkpoint_reader=PostgresChapterWorkflowCheckpointReader(database_url),
                        checkpoint_cleaner=PostgresChapterWorkflowCheckpointCleaner(database_url),
                    ).cleanup(before=now - timedelta(days=30), limit=1)
                    await session.refresh(started.run)
                    await session.refresh(command_row)

                    assert result.scanned == 1
                    assert result.cleaned_runs == 1
                    assert result.deleted_threads == 1
                    assert result.scrubbed_commands == 1
                    assert started.run.checkpoint_id is None
                    assert command_row.payload == {}
                    assert command_row.result_payload is None

                async with open_chapter_workflow_checkpointer(database_url) as saver:
                    assert await saver.aget_tuple(target_config) is None
                    assert await saver.aget_tuple(sentinel_config) is not None

                async with engine.connect() as sql:
                    target_counts_after = {
                        table: await sql.scalar(
                            sa.text(f"SELECT count(*) FROM {table} WHERE thread_id = :thread_id"),
                            {"thread_id": target_state.run_id},
                        )
                        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
                    }
                    sentinel_counts_after = {
                        table: await sql.scalar(
                            sa.text(f"SELECT count(*) FROM {table} WHERE thread_id = :thread_id"),
                            {"thread_id": sentinel_state.run_id},
                        )
                        for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes")
                    }

                assert target_counts_after == {
                    "checkpoints": 0,
                    "checkpoint_blobs": 0,
                    "checkpoint_writes": 0,
                }
                assert sentinel_counts_after == sentinel_counts_before
            finally:
                await engine.dispose()
    finally:
        await source_engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_checkpointed_select_command_recovers_without_second_resume() -> None:
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with _temporary_database(source_engine) as database_url:
            await run_migrations(database_url)
            engine = create_async_engine(database_url)
            try:
                session_factory = async_sessionmaker(engine, expire_on_commit=False)
                async with session_factory() as session:
                    await _seed_project(
                        session,
                        user_id=8902,
                        project_id="workflow-command-checkpoint",
                    )
                    started = await ChapterWorkflowStartService(session).start(
                        user_id=8902,
                        project_id="workflow-command-checkpoint",
                        chapter_number=1,
                        flow_config={"preset": "basic", "enable_rag": False},
                    )
                    first_lease = await JobService(session).claim_next(
                        worker_id="workflow-command-first",
                        lease_seconds=60,
                    )
                assert first_lease is not None

                calls: list[str] = []
                bindings = _checkpoint_smoke_bindings(calls)
                first_execution = JobExecutionContext(
                    lease=first_lease,
                    side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
                    session_factory=session_factory,
                )
                first_turn = await ChapterWorkflowRuntime(
                    first_execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute()
                assert isinstance(first_turn, JobWaitOutcome)

                async with session_factory() as session:
                    await JobService(session).wait_for_resume(
                        first_lease,
                        workflow_transition=first_turn.workflow_transition,
                    )
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert run is not None and chapter is not None
                    version_content = "checkpoint smoke content"
                    version = ChapterVersion(
                        chapter_id=chapter.id,
                        version_label="v1",
                        content=version_content,
                        metadata={
                            "_chapter_workflow": {
                                "run_id": run.id,
                                "ordinal": 1,
                                "content_hash": stable_digest(version_content),
                            }
                        },
                    )
                    session.add(version)
                    await session.flush()
                    selected_version_id = version.id
                    expected_chapter_revision = chapter.current_revision
                    command = await JobService(session).submit_chapter_workflow_command(
                        run.id,
                        actor_user_id=8902,
                        envelope=ChapterWorkflowCommandEnvelope(
                            command_id=str(uuid4()),
                            type="select",
                            payload={"selected_version_id": selected_version_id},
                            expected_run_revision=run.row_revision,
                            expected_chapter_revision=expected_chapter_revision,
                            expected_checkpoint_id=run.checkpoint_id,
                        ),
                    )
                    command_id = command.id
                    second_lease = await JobService(session).claim_next(
                        worker_id="workflow-command-second",
                        lease_seconds=60,
                    )
                assert second_lease is not None

                second_execution = JobExecutionContext(
                    lease=second_lease,
                    side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
                    session_factory=session_factory,
                )
                async with session_factory() as session:
                    pending = await JobService(session).prepare_chapter_workflow_resume(
                        second_lease
                    )
                assert isinstance(pending, ChapterWorkflowPendingResume)
                assert pending.command_id == command_id

                async with session_factory() as session:
                    with pytest.raises(ValueError, match="resume 后的新 checkpoint"):
                        await JobService(session).apply_checkpointed_workflow_command(
                            second_lease,
                            command_id=pending.command_id,
                            marker_checkpoint_id=pending.expected_checkpoint_id,
                        )

                resume_checkpoint_ids: list[str] = []

                async def crash_before_inbox_apply(_command_id: str, checkpoint_id: str) -> None:
                    async with session_factory() as session:
                        chapter = await session.get(Chapter, started.run.chapter_id)
                        assert chapter is not None
                        chapter.current_revision = expected_chapter_revision + 1
                        chapter.selected_version_id = selected_version_id
                        chapter.status = ChapterGenerationStatus.FINALIZING.value
                        await session.commit()
                    resume_checkpoint_ids.append(checkpoint_id)
                    raise RuntimeError("injected crash before command apply")

                calls_before_rejections = list(calls)
                with pytest.raises(ValueError, match="expected checkpoint 已漂移"):
                    await ChapterWorkflowRuntime(
                        second_execution,
                        database_url=database_url,
                        bindings=bindings,
                    ).execute(
                        resume_value=pending.resume_value,
                        command_id=pending.command_id,
                        expected_checkpoint_id="stale-checkpoint",
                        on_command_checkpointed=crash_before_inbox_apply,
                    )
                with pytest.raises(ValueError, match="未引用当前 checkpoint candidate"):
                    await ChapterWorkflowRuntime(
                        second_execution,
                        database_url=database_url,
                        bindings=bindings,
                    ).execute(
                        resume_value={
                            "command_id": pending.command_id,
                            "selected_version_id": 999,
                        },
                        command_id=pending.command_id,
                        expected_checkpoint_id=pending.expected_checkpoint_id,
                        on_command_checkpointed=crash_before_inbox_apply,
                    )
                assert calls == calls_before_rejections

                with pytest.raises(RuntimeError, match="injected crash"):
                    await ChapterWorkflowRuntime(
                        second_execution,
                        database_url=database_url,
                        bindings=bindings,
                    ).execute(
                        resume_value=pending.resume_value,
                        command_id=pending.command_id,
                        expected_checkpoint_id=pending.expected_checkpoint_id,
                        on_command_checkpointed=crash_before_inbox_apply,
                    )
                assert calls.count("apply_selection_resume") == 1
                assert len(resume_checkpoint_ids) == 1

                async with session_factory() as session:
                    recovered_pending = await JobService(session).prepare_chapter_workflow_resume(
                        second_lease
                    )
                assert isinstance(recovered_pending, ChapterWorkflowPendingResume)
                assert recovered_pending.command_id == command_id

                async with session_factory() as session:
                    persisted = await session.get(ChapterWorkflowCommand, command_id)
                    assert persisted is not None and persisted.status == "pending"
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert chapter is not None
                    chapter.selected_version_id = None
                    await session.commit()

                async with session_factory() as session:
                    with pytest.raises(
                        ValueError, match="pending select command 的 Chapter identity"
                    ):
                        await JobService(session).prepare_chapter_workflow_resume(second_lease)

                async with session_factory() as session:
                    with pytest.raises(ValueError, match="select command 时 Chapter identity"):
                        await JobService(session).apply_checkpointed_workflow_command(
                            second_lease,
                            command_id=command_id,
                            marker_checkpoint_id=resume_checkpoint_ids[0],
                        )

                async with session_factory() as session:
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert chapter is not None
                    chapter.selected_version_id = selected_version_id
                    await session.commit()

                async def apply_checkpointed(command_id: str, checkpoint_id: str) -> None:
                    async with session_factory() as session:
                        await JobService(session).apply_checkpointed_workflow_command(
                            second_lease,
                            command_id=command_id,
                            marker_checkpoint_id=checkpoint_id,
                        )

                recovered_turn = await ChapterWorkflowRuntime(
                    second_execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute(
                    resume_value=pending.resume_value,
                    command_id=pending.command_id,
                    expected_checkpoint_id=pending.expected_checkpoint_id,
                    on_command_checkpointed=apply_checkpointed,
                )
                assert isinstance(recovered_turn, JobWaitOutcome)
                assert recovered_turn.workflow_transition.status == "projection_pending"
                assert calls.count("apply_selection_resume") == 1

                replayed_turn = await ChapterWorkflowRuntime(
                    second_execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute(
                    resume_value=pending.resume_value,
                    command_id=pending.command_id,
                    expected_checkpoint_id=pending.expected_checkpoint_id,
                    on_command_checkpointed=apply_checkpointed,
                )
                assert replayed_turn == recovered_turn
                assert calls.count("apply_selection_resume") == 1

                async with session_factory() as session:
                    assert (
                        await JobService(session).prepare_chapter_workflow_resume(second_lease)
                        is None
                    )
                recovered_before_root_wait = await ChapterWorkflowRuntime(
                    second_execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute()
                assert recovered_before_root_wait == recovered_turn
                assert calls.count("apply_selection_resume") == 1

                async with session_factory() as session:
                    persisted = await session.get(ChapterWorkflowCommand, command_id)
                    assert persisted is not None and persisted.status == "applied"
                    assert persisted.result_payload["marker_checkpoint_id"] == (
                        recovered_turn.workflow_transition.checkpoint_id
                    )
                    applied_events = list(
                        (
                            await session.execute(
                                select(JobEvent).where(
                                    JobEvent.job_id == started.root_job.id,
                                    JobEvent.event_type == "workflow.command.applied",
                                )
                            )
                        ).scalars()
                    )
                    assert len(applied_events) == 1

                    await JobService(session).wait_for_resume(
                        second_lease,
                        workflow_transition=recovered_turn.workflow_transition,
                    )
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert run is not None and chapter is not None
                    source_hash = "b" * 64
                    source_generation = str(uuid4())
                    chapter.status = "finalizing"
                    chapter.current_revision = 1
                    chapter.source_hash = source_hash
                    chapter.required_projection_snapshot = ["summary"]
                    chapter.projection_generation = source_generation
                    revision = ChapterRevision(
                        id=str(uuid4()),
                        chapter_id=chapter.id,
                        project_id=chapter.project_id,
                        chapter_number=chapter.chapter_number,
                        revision=1,
                        source_hash=source_hash,
                        source_content="checkpoint smoke content",
                        projection_context={},
                        lifecycle="finalizing",
                        required_projections=["summary"],
                        skipped_projections=[],
                        source_generation=source_generation,
                    )
                    session.add(revision)
                    await session.flush()
                    session.add(
                        ChapterProjectionRun(
                            id=str(uuid4()),
                            chapter_revision_id=revision.id,
                            chapter_id=chapter.id,
                            project_id=chapter.project_id,
                            revision=revision.revision,
                            projection_name="summary",
                            source_hash=source_hash,
                            artifact_generation=str(uuid4()),
                            status="failed",
                            required=True,
                            is_active=False,
                            checkpoint={},
                        )
                    )
                    projection_command = await JobService(session).submit_chapter_workflow_command(
                        run.id,
                        actor_user_id=8902,
                        envelope=ChapterWorkflowCommandEnvelope(
                            command_id=str(uuid4()),
                            type="retry_projection",
                            payload={},
                            expected_run_revision=run.row_revision,
                            expected_chapter_revision=chapter.current_revision,
                            expected_checkpoint_id=run.checkpoint_id,
                        ),
                    )
                    third_lease = await JobService(session).claim_next(
                        worker_id="workflow-command-third",
                        lease_seconds=60,
                    )
                assert third_lease is not None

                third_execution = JobExecutionContext(
                    lease=third_lease,
                    side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
                    session_factory=session_factory,
                )
                async with session_factory() as session:
                    projection_pending = await JobService(session).prepare_chapter_workflow_resume(
                        third_lease
                    )
                assert isinstance(projection_pending, ChapterWorkflowPendingResume)
                assert projection_pending.command_id == projection_command.id
                assert projection_pending.resume_value == {"command_id": projection_command.id}

                projection_checkpoint_ids: list[str] = []

                async def crash_before_projection_apply(
                    _command_id: str,
                    checkpoint_id: str,
                ) -> None:
                    projection_checkpoint_ids.append(checkpoint_id)
                    raise RuntimeError("injected crash before projection command apply")

                with pytest.raises(RuntimeError, match="projection command apply"):
                    await ChapterWorkflowRuntime(
                        third_execution,
                        database_url=database_url,
                        bindings=bindings,
                    ).execute(
                        resume_value=projection_pending.resume_value,
                        command_id=projection_pending.command_id,
                        expected_checkpoint_id=projection_pending.expected_checkpoint_id,
                        on_command_checkpointed=crash_before_projection_apply,
                    )
                assert len(projection_checkpoint_ids) == 1
                assert calls.count("apply_projection_resume") == 1

                async with session_factory() as session:
                    recovered_projection = await JobService(
                        session
                    ).prepare_chapter_workflow_resume(third_lease)
                assert isinstance(recovered_projection, ChapterWorkflowPendingResume)
                assert recovered_projection.command_id == projection_command.id

                async with session_factory() as session:
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert chapter is not None
                    chapter.current_revision = 2
                    await session.commit()

                async with session_factory() as session:
                    with pytest.raises(
                        ValueError,
                        match="pending retry_projection command 的 Chapter revision",
                    ):
                        await JobService(session).prepare_chapter_workflow_resume(third_lease)

                async with session_factory() as session:
                    with pytest.raises(ValueError, match="应用 command 时 Chapter revision"):
                        await JobService(session).apply_checkpointed_workflow_command(
                            third_lease,
                            command_id=projection_command.id,
                            marker_checkpoint_id=projection_checkpoint_ids[0],
                        )

                async with session_factory() as session:
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert chapter is not None
                    chapter.current_revision = 1
                    await session.commit()

                async def apply_projection(command_id: str, checkpoint_id: str) -> None:
                    async with session_factory() as session:
                        await JobService(session).apply_checkpointed_workflow_command(
                            third_lease,
                            command_id=command_id,
                            marker_checkpoint_id=checkpoint_id,
                        )

                retry_turn = await ChapterWorkflowRuntime(
                    third_execution,
                    database_url=database_url,
                    bindings=bindings,
                ).execute(
                    resume_value=projection_pending.resume_value,
                    command_id=projection_pending.command_id,
                    expected_checkpoint_id=projection_pending.expected_checkpoint_id,
                    on_command_checkpointed=apply_projection,
                )
                assert isinstance(retry_turn, JobWaitOutcome)
                assert retry_turn.workflow_transition.status == "projection_pending"
                assert calls.count("apply_projection_resume") == 1
                async with session_factory() as session:
                    persisted_projection = await session.get(
                        ChapterWorkflowCommand,
                        projection_command.id,
                    )
                    assert (
                        persisted_projection is not None
                        and persisted_projection.status == "applied"
                    )
            finally:
                await engine.dispose()
    finally:
        await source_engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_production_handler_runs_selection_finalize_and_projection_resume() -> None:
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with _temporary_database(source_engine) as database_url:
            await run_migrations(database_url)
            engine = create_async_engine(database_url)
            try:
                session_factory = async_sessionmaker(engine, expire_on_commit=False)
                async with session_factory() as session:
                    await _seed_project(
                        session,
                        user_id=8901,
                        project_id="workflow-production-handler",
                    )
                    started = await ChapterWorkflowStartService(session).start(
                        user_id=8901,
                        project_id="workflow-production-handler",
                        chapter_number=1,
                        flow_config={"preset": "basic", "enable_rag": False, "versions": 1},
                    )

                provider_calls: list[str] = []

                def provider_factory(_execution):
                    return _ProductionTestProviders(provider_calls)

                registry = build_job_handler_registry(
                    database_url=database_url,
                    chapter_workflow_provider_factory=provider_factory,
                )
                definition = registry.get("chapter_workflow", 1)
                assert definition is not None
                assert definition.side_effect_class == SideEffectClass.AMBIGUOUS_EXTERNAL
                worker = JobWorker(
                    session_factory=session_factory,
                    registry=registry,
                    worker_id="workflow-production-handler-worker",
                    lease_seconds=60,
                    heartbeat_interval_seconds=5,
                )

                assert await worker.run_once() is True
                assert await worker.run_once() is False

                async with session_factory() as session:
                    projection_batch = await project_chapter_generation_traces(session)
                    await session.commit()
                    job = await session.get(BackgroundTask, started.root_job.id)
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    versions = list(
                        (
                            await session.execute(
                                select(ChapterVersion).where(
                                    ChapterVersion.chapter_id == started.run.chapter_id,
                                )
                            )
                        ).scalars()
                    )
                    activities = list(
                        (
                            await session.execute(
                                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                            )
                        ).scalars()
                    )
                    trace_count = await session.scalar(
                        select(func.count())
                        .select_from(ChapterGenerationTrace)
                        .where(ChapterGenerationTrace.source_run_id == started.run.id)
                    )

                assert job is not None
                assert job.status == "waiting"
                assert job.lease_owner is None
                assert job.lease_expires_at is None
                assert job.heartbeat_at is None
                assert job.result is None
                assert run is not None
                assert run.status == "waiting_for_selection"
                assert run.node_key == "waiting_for_selection"
                assert run.checkpoint_id
                assert run.is_active is True
                assert len(versions) == 1
                assert versions[0].content == "候选正文-1-已润色"
                assert len(activities) == 6
                assert all(activity.status == "succeeded" for activity in activities)
                assert projection_batch.projected_traces > 0
                assert trace_count > 0
                assert provider_calls == [
                    "plan",
                    "candidate:1",
                    "review",
                    "post_review:review_guided_refinement",
                ]

                assert run.checkpoint_id is not None
                selection_checkpoint_id = run.checkpoint_id
                selected_version_id = versions[0].id
                async with session_factory() as session:
                    deleted = await session.execute(
                        delete(ChapterGenerationTrace).where(
                            ChapterGenerationTrace.source_run_id == started.run.id
                        )
                    )
                    await session.commit()
                    assert deleted.rowcount == trace_count
                    assert (
                        await session.scalar(
                            select(func.count())
                            .select_from(ChapterGenerationTrace)
                            .where(ChapterGenerationTrace.source_run_id == started.run.id)
                        )
                        == 0
                    )

                selection_envelope: ChapterWorkflowCommandEnvelope
                async with session_factory() as session:
                    current_run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert current_run is not None and chapter is not None
                    selection_envelope = ChapterWorkflowCommandEnvelope(
                        command_id=str(uuid4()),
                        type="select",
                        payload={"selected_version_id": selected_version_id},
                        expected_run_revision=current_run.row_revision,
                        expected_chapter_revision=chapter.current_revision,
                        expected_checkpoint_id=selection_checkpoint_id,
                    )
                    selection_command = await JobService(session).submit_chapter_workflow_command(
                        current_run.id,
                        actor_user_id=current_run.user_id,
                        envelope=selection_envelope,
                    )

                assert selection_command.status == "pending"
                async with session_factory() as session:
                    pending_replay = await JobService(session).submit_chapter_workflow_command(
                        started.run.id,
                        actor_user_id=started.run.user_id,
                        envelope=selection_envelope,
                    )
                assert pending_replay.id == selection_command.id
                assert pending_replay.status == "pending"

                assert await worker.run_once() is True
                async with session_factory() as session:
                    job = await session.get(BackgroundTask, started.root_job.id)
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    command_row = await session.get(
                        ChapterWorkflowCommand,
                        selection_command.id,
                    )
                    revision = (
                        await session.execute(
                            select(ChapterRevision).where(
                                ChapterRevision.chapter_id == started.run.chapter_id
                            )
                        )
                    ).scalar_one()
                    dispatcher_jobs = list(
                        (
                            await session.execute(
                                select(BackgroundTask).where(
                                    BackgroundTask.task_type == "chapter_outbox_dispatch",
                                    BackgroundTask.stream_id == started.run.id,
                                )
                            )
                        ).scalars()
                    )
                    activities = list(
                        (
                            await session.execute(
                                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                            )
                        ).scalars()
                    )

                assert job is not None and job.status == "waiting"
                assert run is not None
                assert run.status == "projection_pending"
                assert run.node_key == "projection_pending"
                assert run.checkpoint_id and run.checkpoint_id != selection_checkpoint_id
                assert chapter is not None
                assert chapter.status == ChapterGenerationStatus.FINALIZING.value
                assert chapter.current_revision == 1
                assert chapter.selected_version_id == selected_version_id
                assert revision.lifecycle == "finalizing"
                assert command_row is not None and command_row.status == "applied"
                assert command_row.result_payload["marker_checkpoint_id"] == run.checkpoint_id
                assert len(dispatcher_jobs) == 1
                assert dispatcher_jobs[0].status == "queued"
                assert len(activities) == 7
                assert all(activity.status == "succeeded" for activity in activities)
                assert provider_calls == [
                    "plan",
                    "candidate:1",
                    "review",
                    "post_review:review_guided_refinement",
                ]

                async with session_factory() as session:
                    applied_replay = await JobService(session).submit_chapter_workflow_command(
                        started.run.id,
                        actor_user_id=started.run.user_id,
                        envelope=selection_envelope,
                    )
                assert applied_replay.id == selection_command.id
                assert applied_replay.status == "applied"

                assert await worker.run_once() is True
                reconcile_job_id = await _complete_required_projection_jobs(
                    session_factory,
                    run_id=started.run.id,
                    chapter_id=started.run.chapter_id,
                    user_id=started.run.user_id,
                )

                assert await worker.run_once() is True
                async with session_factory() as session:
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    revision = (
                        await session.execute(
                            select(ChapterRevision).where(
                                ChapterRevision.chapter_id == started.run.chapter_id
                            )
                        )
                    ).scalar_one()
                    root = await session.get(BackgroundTask, started.root_job.id)
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    reconcile_job = await session.get(BackgroundTask, reconcile_job_id)

                assert chapter is not None
                assert chapter.status == ChapterGenerationStatus.SUCCESSFUL.value
                assert revision.lifecycle == "successful"
                assert reconcile_job is not None and reconcile_job.status == "succeeded"
                assert root is not None and root.status == "waiting"
                assert run is not None and run.status == "projection_pending"

                reconciler = ChapterWorkflowReconciler(
                    database_url=database_url,
                    batch_size=10,
                    interval_seconds=1,
                )
                async with session_factory() as session:
                    reconciled = await reconciler.reconcile_once(session)
                assert reconciled.scanned == 1
                assert reconciled.reconciled == 1

                assert await worker.run_once() is True
                assert await worker.run_once() is False
                async with session_factory() as session:
                    job = await session.get(BackgroundTask, started.root_job.id)
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    command_row = await session.get(
                        ChapterWorkflowCommand,
                        selection_command.id,
                    )
                    revision_count = await session.scalar(
                        select(func.count()).select_from(ChapterRevision)
                    )
                    outboxes = list(
                        (
                            await session.execute(
                                select(ChapterOutboxEvent).where(
                                    ChapterOutboxEvent.chapter_id == started.run.chapter_id
                                )
                            )
                        ).scalars()
                    )
                    activities = list(
                        (
                            await session.execute(
                                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                            )
                        ).scalars()
                    )
                    command_count = await session.scalar(
                        select(func.count())
                        .select_from(ChapterWorkflowCommand)
                        .where(
                            ChapterWorkflowCommand.run_id == started.run.id,
                            ChapterWorkflowCommand.type == "select",
                        )
                    )
                    traces = list(
                        (
                            await session.execute(
                                select(ChapterGenerationTrace)
                                .where(ChapterGenerationTrace.source_run_id == started.run.id)
                                .order_by(ChapterGenerationTrace.source_event_cursor)
                            )
                        ).scalars()
                    )

                assert job is not None and job.status == "succeeded"
                assert job.result == {
                    "run_id": started.run.id,
                    "selected_version_id": selected_version_id,
                    "target_chapter_revision": 1,
                }
                assert run is not None
                assert run.status == "successful"
                assert run.node_key == "successful"
                assert run.is_active is False
                assert chapter is not None
                assert chapter.status == ChapterGenerationStatus.SUCCESSFUL.value
                assert command_row is not None and command_row.status == "applied"
                assert revision_count == 1
                assert len(outboxes) == 2
                assert all(outbox.workflow_stream_id == started.run.id for outbox in outboxes)
                assert len(activities) == 7
                assert all(activity.status == "succeeded" for activity in activities)
                assert len({activity.activity_key for activity in activities}) == 7
                assert len({activity.provider_request_key for activity in activities}) == 7
                assert command_count == 1
                assert [(trace.node_key, trace.status) for trace in traces] == [
                    ("finalize_revision", "running"),
                    ("finalize_revision", "success"),
                ]
                assert provider_calls == [
                    "plan",
                    "candidate:1",
                    "review",
                    "post_review:review_guided_refinement",
                ]
            finally:
                await engine.dispose()
    finally:
        await source_engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_production_workflow_recovers_across_process_kills_redis_off_and_rollout(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "redis_url", None)
    await shutdown_event_bus()
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    processes: list[Any] = []
    try:
        async with _temporary_database(source_engine) as database_url:
            await run_migrations(database_url)
            engine = create_async_engine(database_url)
            try:
                session_factory = async_sessionmaker(engine, expire_on_commit=False)
                async with session_factory() as session:
                    await _seed_project(
                        session,
                        user_id=8902,
                        project_id="workflow-process-recovery",
                    )
                    started = await ChapterWorkflowStartService(session).start(
                        user_id=8902,
                        project_id="workflow-process-recovery",
                        chapter_number=1,
                        flow_config={"preset": "basic", "enable_rag": False, "versions": 1},
                    )

                process_context = multiprocessing.get_context("spawn")
                candidate_pause = process_context.Event()
                old_worker = process_context.Process(
                    target=_run_production_workflow_worker_process,
                    args=(
                        database_url,
                        "workflow-generation-one",
                        1,
                        candidate_pause,
                        True,
                    ),
                )
                old_worker.start()
                processes.append(old_worker)
                assert await asyncio.to_thread(candidate_pause.wait, 30)

                candidate_checkpoint_id, candidate_state = await _wait_for_checkpoint_node(
                    database_url,
                    run_id=started.run.id,
                    node_key="review_candidates",
                )
                assert candidate_state.run_id == started.run.id
                assert set(candidate_state.activity_refs) == {
                    "retrieval_context",
                    "plan",
                    "candidate:1",
                }
                async with session_factory() as session:
                    root = await session.get(BackgroundTask, started.root_job.id)
                    assert root is not None and root.lease_expires_at is not None
                    stale_lease = JobLease(
                        job_id=root.id,
                        worker_id=str(root.lease_owner),
                        fencing_token=root.fencing_token,
                        attempt=root.attempt,
                        max_attempts=root.max_attempts,
                        job_type=root.task_type,
                        payload_version=root.payload_version,
                        payload=dict(root.payload or {}),
                        user_id=root.user_id,
                        project_id=root.project_id,
                        executor_generation=root.executor_generation,
                        lease_expires_at=root.lease_expires_at,
                    )
                    activities = list(
                        (
                            await session.execute(
                                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                            )
                        ).scalars()
                    )
                    job_service = JobService(session)
                    rollout_probe = await job_service.enqueue_job(
                        user_id=started.run.user_id,
                        project_id=started.run.project_id,
                        job_type="phase7_rollout_probe",
                        title="验证 executor generation 安全重分配",
                        payload={
                            "run_id": started.run.id,
                            "chapter_id": started.run.chapter_id,
                        },
                        idempotency_key=f"phase7-rollout:{started.run.id}",
                        max_attempts=1,
                    )
                    rollout_probe_id = rollout_probe.id
                    rollout = await job_service.switch_executor_generation(
                        expected_generation=1,
                        new_generation=2,
                        rollout_owner="workflow-process-rollout",
                    )
                    await session.refresh(rollout_probe)
                    root = await session.get(BackgroundTask, started.root_job.id)

                assert root is not None
                assert root.status == "running"
                assert root.executor_generation == 1
                assert root.attempt == 1
                assert root.fencing_token == 1
                assert rollout.active_generation == 2
                assert rollout.reassigned_waiting_jobs == 1
                assert rollout_probe.status == "queued"
                assert rollout_probe.executor_generation == 2
                assert len(activities) == 3
                assert all(activity.status == "succeeded" for activity in activities)

                reclaimed_pause = process_context.Event()
                reclaimed_resume = process_context.Event()
                selection_worker = process_context.Process(
                    target=_run_production_workflow_worker_process,
                    args=(
                        database_url,
                        "workflow-selection-wait",
                        2,
                        reclaimed_pause,
                        True,
                        reclaimed_resume,
                        2,
                    ),
                )
                selection_worker.start()
                processes.append(selection_worker)
                await _wait_for_worker_state(
                    session_factory,
                    worker_id="workflow-selection-wait",
                    state="running",
                )

                completed_probe: BackgroundTask | None = None
                probe_deadline = asyncio.get_running_loop().time() + 10
                while asyncio.get_running_loop().time() < probe_deadline:
                    async with session_factory() as session:
                        completed_probe = await session.get(BackgroundTask, rollout_probe_id)
                    if completed_probe is not None and completed_probe.status == "succeeded":
                        break
                    await asyncio.sleep(0.05)
                assert completed_probe is not None and completed_probe.status == "succeeded"

                async with session_factory() as session:
                    root = await session.get(BackgroundTask, started.root_job.id)
                    old_heartbeat = await session.get(
                        JobWorkerHeartbeat,
                        "workflow-generation-one",
                    )
                    new_heartbeat = await session.get(
                        JobWorkerHeartbeat,
                        "workflow-selection-wait",
                    )
                    active_run_count = await session.scalar(
                        select(func.count())
                        .select_from(ChapterWorkflowRun)
                        .where(
                            ChapterWorkflowRun.chapter_id == started.run.chapter_id,
                            ChapterWorkflowRun.is_active.is_(True),
                        )
                    )
                    active_root_lease_count = await session.scalar(
                        select(func.count())
                        .select_from(BackgroundTask)
                        .join(
                            ChapterWorkflowRun,
                            ChapterWorkflowRun.root_job_id == BackgroundTask.id,
                        )
                        .where(
                            ChapterWorkflowRun.chapter_id == started.run.chapter_id,
                            BackgroundTask.status == "running",
                            BackgroundTask.lease_expires_at > func.now(),
                        )
                    )
                    overlap_events = list(
                        (
                            await session.execute(
                                select(JobEvent)
                                .where(JobEvent.job_id == started.root_job.id)
                                .order_by(JobEvent.cursor)
                            )
                        ).scalars()
                    )

                assert old_worker.is_alive() and selection_worker.is_alive()
                assert completed_probe.executor_generation == 2
                assert completed_probe.result == {
                    "worker_id": "workflow-selection-wait",
                    "executor_generation": 2,
                }
                assert root is not None
                assert root.status == "running"
                assert root.lease_owner == "workflow-generation-one"
                assert root.executor_generation == 1
                assert root.attempt == 1
                assert root.fencing_token == 1
                assert root.lease_expires_at is not None
                assert root.lease_expires_at > datetime.now(timezone.utc)
                assert old_heartbeat is not None
                assert old_heartbeat.state == "running"
                assert old_heartbeat.executor_generation == 1
                assert new_heartbeat is not None
                assert new_heartbeat.state == "running"
                assert new_heartbeat.executor_generation == 2
                assert active_run_count == 1
                assert active_root_lease_count == 1
                assert (
                    sum(
                        event.event_type == "workflow.phase_changed"
                        and event.payload.get("workflow", {}).get("status") == "running"
                        for event in overlap_events
                    )
                    == 1
                )

                await _terminate_worker_process(old_worker)
                assert await asyncio.to_thread(reclaimed_pause.wait, 30)

                async with session_factory() as session:
                    reclaimed_root = await session.get(BackgroundTask, started.root_job.id)
                    event_count_before_stale = await session.scalar(
                        select(func.count())
                        .select_from(JobEvent)
                        .where(JobEvent.job_id == started.root_job.id)
                    )
                    activity_count_before_stale = await session.scalar(
                        select(func.count())
                        .select_from(JobActivity)
                        .where(JobActivity.job_id == started.root_job.id)
                    )
                    version_count_before_stale = await session.scalar(
                        select(func.count())
                        .select_from(ChapterVersion)
                        .where(ChapterVersion.chapter_id == started.run.chapter_id)
                    )
                    reclaimed_events = list(
                        (
                            await session.execute(
                                select(JobEvent)
                                .where(JobEvent.job_id == started.root_job.id)
                                .order_by(JobEvent.cursor)
                            )
                        ).scalars()
                    )

                assert reclaimed_root is not None
                assert reclaimed_root.status == "running"
                assert reclaimed_root.lease_owner == "workflow-selection-wait"
                assert reclaimed_root.executor_generation == 2
                assert reclaimed_root.attempt == 2
                assert reclaimed_root.fencing_token == 2
                assert reclaimed_root.lease_expires_at is not None
                assert reclaimed_root.lease_expires_at > datetime.now(timezone.utc)
                assert activity_count_before_stale == 3
                assert version_count_before_stale == 0
                assert (
                    sum(
                        event.event_type == "workflow.phase_changed"
                        and event.payload.get("workflow", {}).get("status") == "running"
                        for event in reclaimed_events
                    )
                    == 2
                )

                stale_title = reclaimed_root.title
                stale_outcome_writer_called = False

                async def stale_outcome_writer(stale_session) -> None:
                    nonlocal stale_outcome_writer_called
                    stale_outcome_writer_called = True
                    await stale_session.execute(
                        sa.update(BackgroundTask)
                        .where(BackgroundTask.id == started.root_job.id)
                        .values(title="stale generation committed")
                    )

                async with session_factory() as session:
                    with pytest.raises(LeaseLostError):
                        await JobService(session).mark_succeeded(
                            stale_lease,
                            result={"stale": True},
                            outcome_writer=stale_outcome_writer,
                        )
                assert stale_outcome_writer_called is False

                async with session_factory() as session:
                    root_after_stale = await session.get(BackgroundTask, started.root_job.id)
                    event_count_after_stale = await session.scalar(
                        select(func.count())
                        .select_from(JobEvent)
                        .where(JobEvent.job_id == started.root_job.id)
                    )
                    activity_count_after_stale = await session.scalar(
                        select(func.count())
                        .select_from(JobActivity)
                        .where(JobActivity.job_id == started.root_job.id)
                    )
                    version_count_after_stale = await session.scalar(
                        select(func.count())
                        .select_from(ChapterVersion)
                        .where(ChapterVersion.chapter_id == started.run.chapter_id)
                    )

                assert root_after_stale is not None
                assert root_after_stale.status == "running"
                assert root_after_stale.title == stale_title
                assert root_after_stale.lease_owner == "workflow-selection-wait"
                assert root_after_stale.fencing_token == 2
                assert event_count_after_stale == event_count_before_stale
                assert activity_count_after_stale == activity_count_before_stale
                assert version_count_after_stale == version_count_before_stale

                reclaimed_resume.set()
                await _wait_for_workflow_state(
                    session_factory,
                    run_id=started.run.id,
                    root_job_id=started.root_job.id,
                    run_status="waiting_for_selection",
                    node_key="waiting_for_selection",
                    root_status="waiting",
                )
                selection_checkpoint_id, selection_state = await _wait_for_checkpoint_node(
                    database_url,
                    run_id=started.run.id,
                    node_key="waiting_for_selection",
                )
                assert selection_checkpoint_id != candidate_checkpoint_id
                assert selection_state.run_id == started.run.id

                async with session_factory() as session:
                    root = await session.get(BackgroundTask, started.root_job.id)
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    versions = list(
                        (
                            await session.execute(
                                select(ChapterVersion).where(
                                    ChapterVersion.chapter_id == started.run.chapter_id
                                )
                            )
                        ).scalars()
                    )
                    activities = list(
                        (
                            await session.execute(
                                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                            )
                        ).scalars()
                    )

                assert root is not None
                assert root.attempt == 2
                assert root.fencing_token == 2
                assert root.executor_generation == 2
                assert root.lease_owner is None
                assert run is not None and run.checkpoint_id == selection_checkpoint_id
                assert len(versions) == 1
                assert versions[0].content == "候选正文-1-已润色"
                assert len(activities) == 6
                assert all(activity.status == "succeeded" for activity in activities)

                await _terminate_worker_process(selection_worker)
                persisted_selection_checkpoint, _ = await _wait_for_checkpoint_node(
                    database_url,
                    run_id=started.run.id,
                    node_key="waiting_for_selection",
                )
                assert persisted_selection_checkpoint == selection_checkpoint_id

                projection_worker = process_context.Process(
                    target=_run_production_workflow_worker_process,
                    args=(
                        database_url,
                        "workflow-projection-wait",
                        2,
                        None,
                        True,
                    ),
                )
                projection_worker.start()
                processes.append(projection_worker)
                await _wait_for_worker_state(
                    session_factory,
                    worker_id="workflow-projection-wait",
                    state="running",
                )

                async with session_factory() as session:
                    current_run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    assert current_run is not None and chapter is not None
                    selection_command = await JobService(session).submit_chapter_workflow_command(
                        current_run.id,
                        actor_user_id=current_run.user_id,
                        envelope=ChapterWorkflowCommandEnvelope(
                            command_id=str(uuid4()),
                            type="select",
                            payload={"selected_version_id": versions[0].id},
                            expected_run_revision=current_run.row_revision,
                            expected_chapter_revision=chapter.current_revision,
                            expected_checkpoint_id=selection_checkpoint_id,
                        ),
                    )

                assert selection_command.status == "pending"
                await _wait_for_workflow_state(
                    session_factory,
                    run_id=started.run.id,
                    root_job_id=started.root_job.id,
                    run_status="projection_pending",
                    node_key="projection_pending",
                    root_status="waiting",
                )
                projection_checkpoint_id, projection_state = await _wait_for_checkpoint_node(
                    database_url,
                    run_id=started.run.id,
                    node_key="projection_pending",
                )
                assert projection_checkpoint_id != selection_checkpoint_id
                assert projection_state.run_id == started.run.id
                assert projection_state.selected_version_id == versions[0].id

                async with session_factory() as session:
                    root = await session.get(BackgroundTask, started.root_job.id)
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    command_row = await session.get(
                        ChapterWorkflowCommand,
                        selection_command.id,
                    )
                    activities = list(
                        (
                            await session.execute(
                                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                            )
                        ).scalars()
                    )

                assert root is not None
                assert root.attempt == 3
                assert root.fencing_token == 3
                assert root.executor_generation == 2
                assert root.lease_owner is None
                assert run is not None and run.checkpoint_id == projection_checkpoint_id
                assert chapter is not None and chapter.current_revision == 1
                assert chapter.selected_version_id == versions[0].id
                assert command_row is not None and command_row.status == "applied"
                assert command_row.result_payload["marker_checkpoint_id"] == (
                    projection_checkpoint_id
                )
                assert len(activities) == 7
                assert all(activity.status == "succeeded" for activity in activities)

                await _terminate_worker_process(projection_worker)
                persisted_projection_checkpoint, _ = await _wait_for_checkpoint_node(
                    database_url,
                    run_id=started.run.id,
                    node_key="projection_pending",
                )
                assert persisted_projection_checkpoint == projection_checkpoint_id

                def provider_factory(_execution):
                    return _ProductionTestProviders([])

                registry = build_job_handler_registry(
                    database_url=database_url,
                    chapter_workflow_provider_factory=provider_factory,
                )
                projection_driver = JobWorker(
                    session_factory=session_factory,
                    registry=registry,
                    worker_id="workflow-projection-driver",
                    lease_seconds=60,
                    heartbeat_interval_seconds=5,
                    executor_generation=2,
                )
                assert await projection_driver.run_once() is True
                reconcile_job_id = await _complete_required_projection_jobs(
                    session_factory,
                    run_id=started.run.id,
                    chapter_id=started.run.chapter_id,
                    user_id=started.run.user_id,
                )
                assert await projection_driver.run_once() is True

                async with session_factory() as session:
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    reconcile_job = await session.get(BackgroundTask, reconcile_job_id)
                assert chapter is not None
                assert chapter.status == ChapterGenerationStatus.SUCCESSFUL.value
                assert reconcile_job is not None and reconcile_job.status == "succeeded"

                reconciler = ChapterWorkflowReconciler(
                    database_url=database_url,
                    batch_size=10,
                    interval_seconds=1,
                )
                async with session_factory() as session:
                    reconciled = await reconciler.reconcile_once(session)
                assert reconciled.scanned == 1
                assert reconciled.reconciled == 1

                final_worker = process_context.Process(
                    target=_run_production_workflow_worker_process,
                    args=(
                        database_url,
                        "workflow-terminal-resume",
                        2,
                        None,
                        False,
                    ),
                )
                final_worker.start()
                processes.append(final_worker)
                await asyncio.to_thread(final_worker.join, 30)
                assert not final_worker.is_alive()
                assert final_worker.exitcode == 0

                await _wait_for_workflow_state(
                    session_factory,
                    run_id=started.run.id,
                    root_job_id=started.root_job.id,
                    run_status="successful",
                    node_key="successful",
                    root_status="succeeded",
                )
                final_checkpoint_id, final_state = await _wait_for_checkpoint_node(
                    database_url,
                    run_id=started.run.id,
                    node_key="successful",
                )
                assert final_checkpoint_id != projection_checkpoint_id
                assert final_state.run_id == started.run.id

                async with session_factory() as session:
                    root = await session.get(BackgroundTask, started.root_job.id)
                    run = await session.get(ChapterWorkflowRun, started.run.id)
                    chapter = await session.get(Chapter, started.run.chapter_id)
                    completed_probe = await session.get(BackgroundTask, rollout_probe_id)
                    workflow_run_count = await session.scalar(
                        select(func.count())
                        .select_from(ChapterWorkflowRun)
                        .where(ChapterWorkflowRun.chapter_id == started.run.chapter_id)
                    )
                    revision_count = await session.scalar(
                        select(func.count()).select_from(ChapterRevision)
                    )
                    versions = list(
                        (
                            await session.execute(
                                select(ChapterVersion).where(
                                    ChapterVersion.chapter_id == started.run.chapter_id
                                )
                            )
                        ).scalars()
                    )
                    outboxes = list(
                        (
                            await session.execute(
                                select(ChapterOutboxEvent).where(
                                    ChapterOutboxEvent.chapter_id == started.run.chapter_id
                                )
                            )
                        ).scalars()
                    )
                    activities = list(
                        (
                            await session.execute(
                                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
                            )
                        ).scalars()
                    )
                    root_events = list(
                        (
                            await session.execute(
                                select(JobEvent)
                                .where(JobEvent.job_id == started.root_job.id)
                                .order_by(JobEvent.cursor)
                            )
                        ).scalars()
                    )
                    probe_events = list(
                        (
                            await session.execute(
                                select(JobEvent)
                                .where(JobEvent.job_id == rollout_probe_id)
                                .order_by(JobEvent.cursor)
                            )
                        ).scalars()
                    )

                assert root is not None
                assert root.status == "succeeded"
                assert root.attempt == 4
                assert root.fencing_token == 4
                assert root.executor_generation == 2
                assert root.lease_owner is None
                assert run is not None
                assert run.status == "successful"
                assert run.node_key == "successful"
                assert run.is_active is False
                assert chapter is not None
                assert chapter.status == ChapterGenerationStatus.SUCCESSFUL.value
                assert completed_probe is not None
                assert completed_probe.status == "succeeded"
                assert completed_probe.executor_generation == 2
                assert completed_probe.attempt == 1
                assert completed_probe.fencing_token == 1
                assert [event.event_type for event in probe_events] == [
                    "job.queued",
                    "job.started",
                    "job.succeeded",
                ]
                assert workflow_run_count == 1
                assert revision_count == 1
                assert len(versions) == 1
                assert len(outboxes) == 2
                assert all(outbox.workflow_stream_id == started.run.id for outbox in outboxes)
                assert len(activities) == 7
                assert len({activity.activity_key for activity in activities}) == 7
                assert all(activity.status == "succeeded" for activity in activities)
                running_events = [
                    event
                    for event in root_events
                    if event.event_type == "workflow.phase_changed"
                    and event.payload.get("workflow", {}).get("status") == "running"
                ]
                assert [event.event_type for event in root_events[:2]] == [
                    "job.queued",
                    "workflow.started",
                ]
                assert len(running_events) == 4
                assert sum(event.event_type == "workflow.completed" for event in root_events) == 1
            finally:
                for process in processes:
                    if process.is_alive():
                        process.terminate()
                        await asyncio.to_thread(process.join, 10)
                    process.close()
                await engine.dispose()
    finally:
        await shutdown_event_bus()
        await source_engine.dispose()


def test_runtime_does_not_call_checkpointer_setup() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    offenders = [
        str(path)
        for path in app_root.rglob("*.py")
        if "AsyncPostgresSaver.setup(" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_active_slot_and_command_identity_are_database_enforced() -> None:
    source_engine = create_async_engine(settings.sqlalchemy_database_uri)
    try:
        async with _temporary_database(source_engine) as database_url:
            await run_migrations(database_url)
            engine = create_async_engine(database_url)
            run_values = {
                "user_id": 8801,
                "project_id": "workflow-project",
                "chapter_id": 8802,
                "chapter_number": 1,
                "base_revision": 0,
                "workflow_version": 1,
                "state_schema_version": 1,
                "context_schema_version": 1,
                "context_snapshot": "{}",
                "context_hash": "a" * 64,
                "runtime_input_hash": "b" * 64,
                "status": "queued",
                "node_key": "freeze_context",
                "is_active": True,
            }
            try:
                async with engine.begin() as sql:
                    await sql.execute(
                        sa.text(
                            "INSERT INTO users "
                            "(id, username, hashed_password, is_admin, is_active) "
                            "VALUES (8801, 'workflow-user', 'secret', false, true)"
                        )
                    )
                    await sql.execute(
                        sa.text(
                            "INSERT INTO novel_projects (id, user_id, title, status) "
                            "VALUES ('workflow-project', 8801, 'workflow', 'draft')"
                        )
                    )
                    await sql.execute(
                        sa.text(
                            "INSERT INTO chapters "
                            "(id, project_id, chapter_number, status, generation_progress, "
                            "generation_step_index, generation_step_total, word_count) "
                            "VALUES (8802, 'workflow-project', 1, 'pending', 0, 0, 0, 0)"
                        )
                    )
                    for job_id in ("workflow-job-1", "workflow-job-2"):
                        await sql.execute(
                            sa.text(
                                "INSERT INTO background_tasks "
                                "(id, user_id, project_id, task_type, title, status, progress, "
                                "payload, result, error, log_entries, stream_type, stream_id) "
                                "VALUES (:id, 8801, 'workflow-project', 'chapter_workflow', "
                                "'workflow', 'queued', 0, '{}'::json, NULL, NULL, '[]'::json, "
                                "'workflow', :id)"
                            ),
                            {"id": job_id},
                        )
                    await sql.execute(
                        sa.text(
                            "INSERT INTO chapter_workflow_runs "
                            "(id, root_job_id, user_id, project_id, chapter_id, chapter_number, "
                            "base_revision, workflow_version, state_schema_version, "
                            "context_schema_version, context_snapshot, context_hash, "
                            "runtime_input_hash, status, node_key, is_active) VALUES "
                            "(:id, :root_job_id, :user_id, :project_id, :chapter_id, "
                            ":chapter_number, :base_revision, :workflow_version, "
                            ":state_schema_version, :context_schema_version, "
                            ":context_snapshot, :context_hash, :runtime_input_hash, "
                            ":status, :node_key, :is_active)"
                        ),
                        {**run_values, "id": "workflow-run-1", "root_job_id": "workflow-job-1"},
                    )

                with pytest.raises(sa.exc.IntegrityError):
                    async with engine.begin() as sql:
                        await sql.execute(
                            sa.text(
                                "INSERT INTO chapter_workflow_runs "
                                "(id, root_job_id, user_id, project_id, chapter_id, chapter_number, "
                                "base_revision, workflow_version, state_schema_version, "
                                "context_schema_version, context_snapshot, context_hash, "
                                "runtime_input_hash, status, node_key, is_active) VALUES "
                                "(:id, :root_job_id, :user_id, :project_id, :chapter_id, "
                                ":chapter_number, :base_revision, :workflow_version, "
                                ":state_schema_version, :context_schema_version, "
                                ":context_snapshot, :context_hash, :runtime_input_hash, "
                                ":status, :node_key, :is_active)"
                            ),
                            {**run_values, "id": "workflow-run-2", "root_job_id": "workflow-job-2"},
                        )

                async with engine.begin() as sql:
                    await sql.execute(
                        sa.text(
                            "UPDATE chapter_workflow_runs SET status = 'failed', "
                            "is_active = false WHERE id = 'workflow-run-1'"
                        )
                    )
                    await sql.execute(
                        sa.text(
                            "INSERT INTO chapter_workflow_runs "
                            "(id, root_job_id, user_id, project_id, chapter_id, chapter_number, "
                            "base_revision, workflow_version, state_schema_version, "
                            "context_schema_version, context_snapshot, context_hash, "
                            "runtime_input_hash, status, node_key, is_active) VALUES "
                            "(:id, :root_job_id, :user_id, :project_id, :chapter_id, "
                            ":chapter_number, :base_revision, :workflow_version, "
                            ":state_schema_version, :context_schema_version, "
                            ":context_snapshot, :context_hash, :runtime_input_hash, "
                            ":status, :node_key, :is_active)"
                        ),
                        {**run_values, "id": "workflow-run-2", "root_job_id": "workflow-job-2"},
                    )
                    await sql.execute(
                        sa.text(
                            "INSERT INTO chapter_workflow_commands "
                            "(id, run_id, type, payload_version, payload, actor_user_id, "
                            "expected_run_revision, expected_chapter_revision, status) "
                            "VALUES ('workflow-command-1', 'workflow-run-2', 'cancel', 1, "
                            "'{}'::json, 8801, 0, 0, 'pending')"
                        )
                    )

                with pytest.raises(sa.exc.IntegrityError):
                    async with engine.begin() as sql:
                        await sql.execute(
                            sa.text(
                                "INSERT INTO chapter_workflow_commands "
                                "(id, run_id, type, payload_version, payload, actor_user_id, "
                                "expected_run_revision, expected_chapter_revision, status) "
                                "VALUES ('workflow-command-1', 'workflow-run-2', 'cancel', 1, "
                                "'{}'::json, 8801, 0, 0, 'pending')"
                            )
                        )
            finally:
                await engine.dispose()
    finally:
        await source_engine.dispose()
