# AIMETA P=章节工作流stale_run收敛测试|R=状态矩阵_幂等_checkpoint补偿_projection唤醒|NR=不覆盖真实provider或finalize实现|E=test_*|X=internal|A=integration_test|D=pytest,postgresql|S=test|RD=./README.ai
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.models import (
    BackgroundTask,
    Chapter,
    ChapterWorkflowCommand,
    ChapterWorkflowRun,
    JobEvent,
    NovelProject,
)
from app.models.user import User
from app.schemas.chapter_workflow import ChapterWorkflowStateV1
from app.services import chapter_workflow_reconciler as reconciler_module
from app.services.chapter_workflow_reconciler import (
    ChapterWorkflowReconcileCandidate,
    ChapterWorkflowReconciler,
    PostgresChapterWorkflowCheckpointReader,
)
from app.services.job_service import (
    ChapterWorkflowAutomaticResume,
    ChapterWorkflowCheckpointEvidence,
    JobService,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _CheckpointReader:
    def __init__(self, evidence: dict[str, ChapterWorkflowCheckpointEvidence]) -> None:
        self.evidence = evidence

    async def read(
        self,
        candidates: list[ChapterWorkflowReconcileCandidate],
    ) -> dict[str, ChapterWorkflowCheckpointEvidence]:
        return {candidate.run_id: self.evidence[candidate.run_id] for candidate in candidates}


async def _create_workflow(session) -> tuple[BackgroundTask, ChapterWorkflowRun, Chapter]:
    run_id = str(uuid4())
    project_id = str(uuid4())
    session.add(User(username=f"reconcile-{run_id}", hashed_password="secret"))
    await session.flush()
    user_id = (
        await session.execute(select(User.id).where(User.username == f"reconcile-{run_id}"))
    ).scalar_one()
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="Workflow reconcile",
            initial_prompt="test",
        )
    )
    chapter = Chapter(project_id=project_id, chapter_number=1)
    session.add(chapter)
    await session.commit()

    job = await JobService(session).enqueue_job(
        user_id=user_id,
        project_id=project_id,
        job_type="chapter_workflow",
        title="Durable Chapter workflow",
        payload={"run_id": run_id},
        idempotency_key=f"workflow:{run_id}",
        stream_type="workflow",
        stream_id=run_id,
    )
    run = ChapterWorkflowRun(
        id=run_id,
        user_id=user_id,
        project_id=project_id,
        chapter_id=chapter.id,
        chapter_number=1,
        base_revision=0,
        root_job_id=job.id,
        workflow_version=1,
        state_schema_version=1,
        context_schema_version=1,
        context_snapshot={},
        context_hash="a" * 64,
        runtime_input_hash="b" * 64,
        status="queued",
        node_key="freeze_context",
    )
    session.add(run)
    await session.commit()
    return job, run, chapter


def _state(
    run: ChapterWorkflowRun,
    *,
    node_key: str,
    command_id: str | None = None,
    selected_version_id: int | None = None,
    target_revision: int | None = None,
) -> ChapterWorkflowStateV1:
    return ChapterWorkflowStateV1(
        run_id=run.id,
        node_key=node_key,
        context_hash=run.context_hash,
        last_applied_command_id=command_id,
        selected_version_id=selected_version_id,
        target_chapter_revision=target_revision,
    )


def _reconciler(evidence: dict[str, ChapterWorkflowCheckpointEvidence]):
    return ChapterWorkflowReconciler(
        database_url="postgresql+asyncpg://unused/unused",
        checkpoint_reader=_CheckpointReader(evidence),
        interval_seconds=1,
    )


async def _event_count(session, run_id: str) -> int:
    return int(
        (
            await session.execute(
                select(func.count(JobEvent.cursor)).where(
                    JobEvent.stream_type == "workflow",
                    JobEvent.stream_id == run_id,
                )
            )
        ).scalar_one()
    )


async def test_reconciler_repairs_terminal_root_and_is_idempotent(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, _chapter = await _create_workflow(session)
        job.status = "succeeded"
        job.progress = 100
        job.completed_at = datetime.now(timezone.utc)
        await session.commit()
        before_events = await _event_count(session, run.id)

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id=None,
                state=None,
                reason_code="checkpoint_missing",
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        result = await reconciler.reconcile_once(session)
        assert result.reconciled == 1
        repaired_run = await session.get(ChapterWorkflowRun, run.id)
        repaired_job = await session.get(BackgroundTask, job.id)
        assert repaired_run is not None
        assert repaired_run.status == "successful"
        assert repaired_run.is_active is False
        assert repaired_job is not None and repaired_job.status == "succeeded"
        first_event_count = await _event_count(session, run.id)
        assert first_event_count == before_events + 1
        event = (
            await session.execute(
                select(JobEvent)
                .where(JobEvent.stream_id == run.id)
                .order_by(JobEvent.cursor.desc())
                .limit(1)
            )
        ).scalar_one()
        assert event.event_type == "workflow.reconciled"
        assert event.payload["workflow"]["reason_code"] == "root_terminal_run_active"

        second = await reconciler.reconcile_once(session)
        assert second.scanned == 0
        assert await _event_count(session, run.id) == first_event_count


async def test_reconciler_supersedes_revision_drift(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, chapter = await _create_workflow(session)
        job.status = "waiting"
        run.status = "waiting_for_selection"
        run.node_key = "waiting_for_selection"
        run.checkpoint_id = "checkpoint-selection"
        chapter.current_revision = 1
        await session.commit()

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id="checkpoint-selection",
                state=_state(run, node_key="waiting_for_selection"),
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        result = await reconciler.reconcile_once(session)
        assert result.reconciled == 1
        repaired_run = await session.get(ChapterWorkflowRun, run.id)
        repaired_job = await session.get(BackgroundTask, job.id)
        assert repaired_run is not None
        assert (repaired_run.status, repaired_run.is_active) == ("superseded", False)
        assert repaired_job is not None
        assert (repaired_job.status, repaired_job.error_category) == (
            "cancelled",
            "chapter_revision_superseded",
        )


async def test_reconciler_fails_closed_on_missing_checkpoint_once(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, _chapter = await _create_workflow(session)
        job.status = "waiting"
        run.status = "waiting_for_selection"
        run.node_key = "waiting_for_selection"
        run.checkpoint_id = "missing-checkpoint"
        await session.commit()

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id=None,
                state=None,
                reason_code="checkpoint_missing",
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        first = await reconciler.reconcile_once(session)
        assert first.needs_attention == 1
        repaired_run = await session.get(ChapterWorkflowRun, run.id)
        repaired_job = await session.get(BackgroundTask, job.id)
        assert repaired_run is not None and repaired_run.status == "needs_attention"
        assert repaired_job is not None
        assert repaired_job.error_category == "checkpoint_missing"
        first_events = await _event_count(session, run.id)

        second = await reconciler.reconcile_once(session)
        assert second.needs_attention == 0
        assert await _event_count(session, run.id) == first_events


async def test_reconciler_applies_checkpointed_pending_command(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, chapter = await _create_workflow(session)
        run.node_key = "waiting_for_selection"
        run.checkpoint_id = "checkpoint-before-command"
        run.row_revision = 1
        command_id = str(uuid4())
        command = ChapterWorkflowCommand(
            id=command_id,
            run_id=run.id,
            type="select",
            payload_version=1,
            payload={"selected_version_id": 1},
            actor_user_id=run.user_id,
            expected_run_revision=0,
            expected_chapter_revision=chapter.current_revision,
            expected_checkpoint_id=run.checkpoint_id,
            status="pending",
        )
        session.add(command)
        await session.commit()

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id="checkpoint-after-command",
                state=_state(
                    run,
                    node_key="finalize_revision",
                    command_id=command_id,
                    selected_version_id=1,
                ),
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        result = await reconciler.reconcile_once(session)
        assert result.command_applied == 1
        repaired_command = await session.get(ChapterWorkflowCommand, command_id)
        assert repaired_command is not None and repaired_command.status == "applied"
        assert repaired_command.result_payload == {
            "command_id": command_id,
            "status": "applied",
            "marker_checkpoint_id": "checkpoint-after-command",
        }
        repaired_run = await session.get(ChapterWorkflowRun, run.id)
        assert repaired_run is not None
        assert repaired_run.checkpoint_id == "checkpoint-before-command"


@pytest.mark.parametrize(
    "invalid_case",
    ["actor", "run_revision", "node", "payload", "multiple_pending"],
)
async def test_reconciler_rejects_invalid_checkpoint_command_marker(
    isolated_pg,
    invalid_case: str,
) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, chapter = await _create_workflow(session)
        run.node_key = "waiting_for_selection"
        run.checkpoint_id = "checkpoint-before-command"
        run.row_revision = 1
        command_id = str(uuid4())
        actor_user_id = run.user_id
        expected_run_revision = 0
        marker_node = "finalize_revision"
        if invalid_case == "actor":
            other_user = User(
                username=f"reconcile-other-{run.id}",
                hashed_password="secret",
            )
            session.add(other_user)
            await session.flush()
            actor_user_id = other_user.id
        elif invalid_case == "run_revision":
            expected_run_revision = run.row_revision
        elif invalid_case == "node":
            marker_node = "waiting_for_selection"
        command_payload: dict[str, object] = {"selected_version_id": 1}
        if invalid_case == "payload":
            command_payload = {"selected_version_id": "1"}
        command = ChapterWorkflowCommand(
            id=command_id,
            run_id=run.id,
            type="select",
            payload_version=1,
            payload=command_payload,
            actor_user_id=actor_user_id,
            expected_run_revision=expected_run_revision,
            expected_chapter_revision=chapter.current_revision,
            expected_checkpoint_id=run.checkpoint_id,
            status="pending",
        )
        session.add(command)
        if invalid_case == "multiple_pending":
            session.add(
                ChapterWorkflowCommand(
                    id=str(uuid4()),
                    run_id=run.id,
                    type="select",
                    payload_version=1,
                    payload={"selected_version_id": 1},
                    actor_user_id=run.user_id,
                    expected_run_revision=0,
                    expected_chapter_revision=chapter.current_revision,
                    expected_checkpoint_id=run.checkpoint_id,
                    status="pending",
                )
            )
        await session.commit()

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id="checkpoint-after-command",
                state=_state(
                    run,
                    node_key=marker_node,
                    command_id=command_id,
                    selected_version_id=1,
                ),
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        result = await reconciler.reconcile_once(session)
        repaired_job = await session.get(BackgroundTask, job.id)
        repaired_run = await session.get(ChapterWorkflowRun, run.id)
        repaired_command = await session.get(ChapterWorkflowCommand, command_id)

    assert result.needs_attention == 1
    assert repaired_job is not None
    assert repaired_job.error_category == "checkpoint_command_mismatch"
    assert repaired_run is not None and repaired_run.status == "needs_attention"
    assert repaired_command is not None and repaired_command.status == "pending"


async def test_reconciler_applies_checkpointed_retry_projection_command(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, chapter = await _create_workflow(session)
        run.node_key = "projection_pending"
        run.checkpoint_id = "checkpoint-before-projection-retry"
        run.row_revision = 1
        command_id = str(uuid4())
        session.add(
            ChapterWorkflowCommand(
                id=command_id,
                run_id=run.id,
                type="retry_projection",
                payload_version=1,
                payload={},
                actor_user_id=run.user_id,
                expected_run_revision=0,
                expected_chapter_revision=chapter.current_revision,
                expected_checkpoint_id=run.checkpoint_id,
                status="pending",
            )
        )
        await session.commit()

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id="checkpoint-after-projection-retry",
                state=_state(run, node_key="projection_pending", command_id=command_id),
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        result = await reconciler.reconcile_once(session)
        repaired_command = await session.get(ChapterWorkflowCommand, command_id)

    assert result.command_applied == 1
    assert repaired_command is not None and repaired_command.status == "applied"


async def test_checkpoint_read_unavailable_leaves_workflow_unchanged(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, _chapter = await _create_workflow(session)
        before_events = await _event_count(session, run.id)
        before = (job.status, run.status, run.node_key, run.row_revision)
        result = await JobService(session).reconcile_chapter_workflow(
            run.id,
            checkpoint=ChapterWorkflowCheckpointEvidence(
                checkpoint_id=None,
                state=None,
                reason_code="checkpoint_read_unavailable",
            ),
        )
        repaired_job = await session.get(BackgroundTask, job.id)
        repaired_run = await session.get(ChapterWorkflowRun, run.id)

        assert result.reason_code == "checkpoint_read_unavailable"
        assert result.action == "skipped"
        assert repaired_job is not None and repaired_run is not None
        assert (
            repaired_job.status,
            repaired_run.status,
            repaired_run.node_key,
            repaired_run.row_revision,
        ) == before
        assert await _event_count(session, run.id) == before_events


async def test_checkpoint_reader_isolates_one_tuple_read_failure(monkeypatch) -> None:
    first_run_id = str(uuid4())
    second_run_id = str(uuid4())

    class _Saver:
        async def aget_tuple(self, config):
            if config["configurable"]["thread_id"] == first_run_id:
                raise RuntimeError("checkpoint unavailable")
            return None

    @asynccontextmanager
    async def open_fake_checkpointer(_database_url):
        yield _Saver()

    monkeypatch.setattr(
        reconciler_module,
        "open_chapter_workflow_checkpointer",
        open_fake_checkpointer,
    )
    reader = PostgresChapterWorkflowCheckpointReader("postgresql://unused/unused")
    evidence = await reader.read(
        [
            ChapterWorkflowReconcileCandidate(first_run_id, 1, 1, True),
            ChapterWorkflowReconcileCandidate(second_run_id, 1, 1, True),
        ]
    )

    assert evidence[first_run_id].reason_code == "checkpoint_read_unavailable"
    assert evidence[second_run_id].reason_code == "checkpoint_missing"


async def test_projection_success_requeues_and_prepares_automatic_resume(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        job, run, chapter = await _create_workflow(session)
        job.status = "waiting"
        run.status = "projection_pending"
        run.node_key = "projection_pending"
        run.checkpoint_id = "checkpoint-projection"
        chapter.current_revision = 1
        chapter.status = "successful"
        await session.commit()

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id="checkpoint-projection",
                state=_state(
                    run,
                    node_key="projection_pending",
                    target_revision=1,
                ),
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        result = await reconciler.reconcile_once(session)
        assert result.reconciled == 1
        repaired_job = await session.get(BackgroundTask, job.id)
        repaired_run = await session.get(ChapterWorkflowRun, run.id)
        assert repaired_job is not None and repaired_job.status == "queued"
        assert repaired_run is not None
        assert (repaired_run.status, repaired_run.node_key) == (
            "queued",
            "projection_pending",
        )

        lease = await JobService(session).claim_next(
            worker_id="projection-resumer",
            lease_seconds=30,
        )
        assert lease is not None and lease.job_id == job.id
        pending = await JobService(session).prepare_chapter_workflow_resume(lease)
        assert isinstance(pending, ChapterWorkflowAutomaticResume)
        assert pending.resume_value == {
            "reason": "projection_completed",
            "target_chapter_revision": 1,
        }


async def test_reconciler_leaves_live_lease_to_worker(isolated_pg) -> None:
    now = datetime.now(timezone.utc)
    async with isolated_pg.session_factory() as session:
        job, run, _chapter = await _create_workflow(session)
        job.status = "running"
        job.lease_owner = "live-worker"
        job.lease_expires_at = now + timedelta(minutes=1)
        run.status = "running"
        await session.commit()
        before_events = await _event_count(session, run.id)

    reconciler = _reconciler(
        {
            run.id: ChapterWorkflowCheckpointEvidence(
                checkpoint_id=None,
                state=None,
                reason_code="checkpoint_missing",
            )
        }
    )
    async with isolated_pg.session_factory() as session:
        result = await reconciler.reconcile_once(session)
        assert result.scanned == 1
        assert (result.reconciled, result.needs_attention) == (0, 0)
        unchanged_job = await session.get(BackgroundTask, job.id)
        unchanged_run = await session.get(ChapterWorkflowRun, run.id)
        assert unchanged_job is not None and unchanged_job.status == "running"
        assert unchanged_run is not None and unchanged_run.status == "running"
        assert await _event_count(session, run.id) == before_events


async def test_checkpoint_tuple_parser_ignores_internal_langgraph_channels() -> None:
    run_id = str(uuid4())
    candidate = ChapterWorkflowReconcileCandidate(
        run_id=run_id,
        workflow_version=1,
        state_schema_version=1,
        is_active=True,
    )
    state = ChapterWorkflowStateV1.initial(run_id=run_id, context_hash="a" * 64)

    class TupleValue:
        config = {
            "configurable": {
                "thread_id": run_id,
                "checkpoint_id": "checkpoint-1",
            }
        }
        checkpoint = {
            "id": "checkpoint-1",
            "channel_values": {
                **state.model_dump(mode="json"),
                "branch:to:freeze_context": None,
            },
        }

    evidence = PostgresChapterWorkflowCheckpointReader._parse_tuple(
        candidate,
        TupleValue(),
    )
    assert evidence.reason_code is None
    assert evidence.checkpoint_id == "checkpoint-1"
    assert evidence.state == state


async def test_reconcile_waits_on_root_lock_then_observes_committed_revision(
    isolated_pg,
) -> None:
    async with isolated_pg.session_factory() as seed_session:
        job, run, _chapter = await _create_workflow(seed_session)
        job.status = "waiting"
        run.status = "waiting_for_selection"
        run.node_key = "waiting_for_selection"
        run.checkpoint_id = "checkpoint-selection"
        await seed_session.commit()

    evidence = ChapterWorkflowCheckpointEvidence(
        checkpoint_id="checkpoint-selection",
        state=_state(run, node_key="waiting_for_selection"),
    )
    async with (
        isolated_pg.session_factory() as blocker,
        isolated_pg.session_factory() as contender,
    ):
        await blocker.execute(
            select(BackgroundTask).where(BackgroundTask.id == job.id).with_for_update()
        )
        blocker_pid = int(await blocker.scalar(select(func.pg_backend_pid())))
        contender_pid = int(await contender.scalar(select(func.pg_backend_pid())))
        task = asyncio.create_task(
            JobService(contender).reconcile_chapter_workflow(
                run.id,
                checkpoint=evidence,
            )
        )

        async def wait_until_blocked() -> None:
            async with isolated_pg.session_factory() as observer:
                for _ in range(200):
                    blocking = set(
                        await observer.scalar(select(func.pg_blocking_pids(contender_pid))) or []
                    )
                    if blocker_pid in blocking:
                        return
                    await asyncio.sleep(0.01)
            raise AssertionError("reconciler 未阻塞在 root JobRun 行锁")

        await asyncio.wait_for(wait_until_blocked(), timeout=3)
        locked_run = (
            await blocker.execute(
                select(ChapterWorkflowRun).where(ChapterWorkflowRun.id == run.id).with_for_update()
            )
        ).scalar_one()
        locked_chapter = (
            await blocker.execute(
                select(Chapter).where(Chapter.id == locked_run.chapter_id).with_for_update()
            )
        ).scalar_one()
        locked_chapter.current_revision = 1
        await blocker.commit()

        result = await asyncio.wait_for(task, timeout=3)
        assert result.action == "reconciled"
        assert result.reason_code == "chapter_revision_superseded"

    async with isolated_pg.session_factory() as verify:
        repaired_run = await verify.get(ChapterWorkflowRun, run.id)
        repaired_job = await verify.get(BackgroundTask, job.id)
        assert repaired_run is not None and repaired_run.status == "superseded"
        assert repaired_job is not None and repaired_job.status == "cancelled"
