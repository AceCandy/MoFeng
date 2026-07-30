import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    AIUsageRecord,
    BackgroundTask,
    Chapter,
    ChapterWorkflowRun,
    JobActivity,
    JobEvent,
    JobExecutorControl,
    NovelProject,
)
from app.models.user import User
from app.services.chapter_workflow_transition import ChapterWorkflowTransition
from app.services.job_public_projection import public_job_snapshot
from app.services.job_registry import SideEffectClass
from app.services.job_service import (
    ExecutorGenerationInactiveError,
    HeartbeatResult,
    JobService,
    LeaseLostError,
    RetryPolicy,
)
from app.utils.ai_telemetry import AICallResult, TokenUsage


async def _create_workflow_root(
    session,
    *,
    user_id: int,
    project_id: str,
    chapter_number: int,
    run_id: str,
    max_attempts: int = 3,
) -> tuple[BackgroundTask, ChapterWorkflowRun]:
    session.add(User(id=user_id, username=f"workflow-{user_id}", hashed_password="secret"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="Workflow transition",
            initial_prompt="test",
        )
    )
    chapter = Chapter(project_id=project_id, chapter_number=chapter_number)
    session.add(chapter)
    await session.commit()

    job = await JobService(session).enqueue_job(
        user_id=user_id,
        project_id=project_id,
        job_type="chapter_workflow",
        title="Durable Chapter workflow",
        payload={"run_id": run_id},
        idempotency_key=f"workflow:{run_id}",
        max_attempts=max_attempts,
        stream_type="workflow",
        stream_id=run_id,
    )
    run = ChapterWorkflowRun(
        id=run_id,
        user_id=user_id,
        project_id=project_id,
        chapter_id=chapter.id,
        chapter_number=chapter_number,
        base_revision=chapter.current_revision,
        root_job_id=job.id,
        workflow_version=1,
        state_schema_version=1,
        context_schema_version=1,
        context_snapshot={},
        context_hash="a" * 64,
        runtime_input_hash="b" * 64,
        status="queued",
        node_key="queued",
    )
    session.add(run)
    await session.commit()
    return job, run


def test_public_job_snapshot_redacts_legacy_error_and_allowlists_logs() -> None:
    now = datetime.now(timezone.utc)
    job = BackgroundTask(
        id="public-projection-job",
        user_id=1,
        task_type="test",
        title="Public projection",
        status="failed",
        progress=50,
        stream_type="job",
        stream_id="public-projection-job",
        error="Authorization: Bearer private-token",
        log_entries=[
            {
                "timestamp": now.isoformat(),
                "level": "ERROR",
                "message": "token=private-log-token",
                "private_context": "prompt body",
            },
            {"message": "malformed private-token"},
        ],
        created_at=now,
        updated_at=now,
    )

    snapshot = public_job_snapshot(job)

    assert snapshot["error"] == "Authorization: [已隐藏]"
    assert snapshot["log_entries"] == [
        {
            "timestamp": now.isoformat(),
            "level": "error",
            "message": "token=[已隐藏]",
        }
    ]
    assert "private-token" not in str(snapshot)
    assert "prompt body" not in str(snapshot)


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_idempotency_key_returns_one_job_and_one_queued_event(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试")
        )
        await session.commit()

        service = JobService(session)
        first = await service.enqueue_job(
            user_id=1,
            job_type="chapter_outline",
            title="生成后续章节大纲",
            project_id="project-1",
            payload={"start_chapter": 3, "num_chapters": 2},
            idempotency_key="outline-project-1-3-2",
        )
        duplicate = await service.enqueue_job(
            user_id=1,
            job_type="chapter_outline",
            title="生成后续章节大纲",
            project_id="project-1",
            payload={"start_chapter": 3, "num_chapters": 2},
            idempotency_key="outline-project-1-3-2",
        )

        events = await service.list_events(user_id=1, after_cursor=0)

        assert duplicate.id == first.id
        assert first.status == "queued"
        assert [(event.job_id, event.sequence, event.event_type) for event in events] == [
            (first.id, 1, "job.queued"),
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_claim_and_fencing_reject_stale_worker(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        session.add(User(id=1001, username="claim-writer", hashed_password="secret"))
        session.add(
            NovelProject(id="claim-project", user_id=1001, title="测试项目", initial_prompt="测试")
        )
        await session.commit()
        job = await JobService(session).enqueue_job(
            user_id=1001,
            job_type="claim-test",
            title="并发 claim",
            project_id="claim-project",
            idempotency_key="claim-once",
        )
        now = job.available_at + timedelta(seconds=1)

    async def claim(worker_id: str):
        async with session_factory() as session:
            return await JobService(session).claim_next(
                worker_id=worker_id,
                lease_seconds=30,
                now=now,
            )

    try:
        claims = await asyncio.gather(claim("worker-a"), claim("worker-b"))
        first_lease = next(lease for lease in claims if lease is not None)

        assert sum(lease is not None for lease in claims) == 1
        assert (first_lease.attempt, first_lease.fencing_token) == (1, 1)

        async with session_factory() as session:
            second_lease = await JobService(session).claim_next(
                worker_id="worker-c",
                lease_seconds=30,
                now=now + timedelta(seconds=31),
            )

        assert second_lease is not None
        assert (second_lease.attempt, second_lease.fencing_token) == (2, 2)

        stale_outcome_writes: list[str] = []

        async def stale_outcome_writer(_session) -> None:
            stale_outcome_writes.append(first_lease.worker_id)

        async with session_factory() as session:
            with pytest.raises(LeaseLostError):
                await JobService(session).mark_succeeded(
                    first_lease,
                    result={"winner": first_lease.worker_id},
                    outcome_writer=stale_outcome_writer,
                    now=now + timedelta(seconds=32),
                )
        assert stale_outcome_writes == []

        async with session_factory() as session:
            await JobService(session).mark_succeeded(
                second_lease,
                result={"winner": second_lease.worker_id},
                now=now + timedelta(seconds=32),
            )
            refreshed = await JobService(session).get_job(job.id)
            events = await JobService(session).list_events(user_id=1001, after_cursor=0)

        assert refreshed is not None
        assert refreshed.result == {"winner": "worker-c"}
        assert [event.event_type for event in events] == [
            "job.queued",
            "job.started",
            "job.reclaimed",
            "job.succeeded",
        ]
    finally:
        async with session_factory() as session:
            await session.execute(delete(User).where(User.id == 1001))
            await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_locked_job_reads_refresh_cached_state(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as setup_session:
        setup_session.add(User(id=1002, username="lock-refresh-writer", hashed_password="secret"))
        await setup_session.commit()
        cancel_job = await JobService(setup_session).enqueue_job(
            user_id=1002,
            job_type="lock-refresh-cancel",
            title="锁定取消刷新",
            idempotency_key="lock-refresh-cancel",
        )
        claim_job = await JobService(setup_session).enqueue_job(
            user_id=1002,
            job_type="lock-refresh-claim",
            title="锁定 claim 刷新",
            idempotency_key="lock-refresh-claim",
            max_attempts=3,
        )

    async with session_factory() as stale_session, session_factory() as writer_session:
        cached_cancel = await stale_session.get(BackgroundTask, cancel_job.id)
        cached_claim = await stale_session.get(BackgroundTask, claim_job.id)
        assert cached_cancel is not None and cached_cancel.status == "queued"
        assert cached_claim is not None and cached_claim.max_attempts == 3

        claimed_cancel = await JobService(writer_session).claim_next(
            worker_id="lock-refresh-owner",
            lease_seconds=30,
            now=cancel_job.available_at + timedelta(seconds=1),
        )
        assert claimed_cancel is not None and claimed_cancel.job_id == cancel_job.id
        persisted_claim = await writer_session.get(BackgroundTask, claim_job.id)
        assert persisted_claim is not None
        persisted_claim.max_attempts = 1
        await writer_session.commit()

        cancel_requested = await JobService(stale_session).request_cancel(
            cancel_job.id,
            user_id=1002,
            now=cancel_job.available_at + timedelta(seconds=2),
        )
        assert cancel_requested is cached_cancel
        assert cancel_requested.status == "running"
        assert cancel_requested.cancel_requested_at is not None

        claimed = await JobService(stale_session).claim_next(
            worker_id="lock-refresh-claim-worker",
            lease_seconds=30,
            now=claim_job.available_at + timedelta(seconds=2),
        )
        assert claimed is not None and claimed.job_id == claim_job.id
        assert claimed.max_attempts == 1
        assert cached_claim.max_attempts == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_workflow_runs_contend_for_one_active_slot(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as setup_session:
        setup_session.add(User(id=1003, username="active-slot-writer", hashed_password="secret"))
        setup_session.add(
            NovelProject(
                id="active-slot-project",
                user_id=1003,
                title="Active slot",
                initial_prompt="test",
            )
        )
        chapter = Chapter(project_id="active-slot-project", chapter_number=1)
        setup_session.add(chapter)
        await setup_session.commit()
        first_job = await JobService(setup_session).enqueue_job(
            user_id=1003,
            project_id="active-slot-project",
            job_type="chapter_workflow",
            title="Active slot contender A",
            idempotency_key="active-slot-a",
            stream_type="workflow",
            stream_id="active-slot-run-a",
        )
        second_job = await JobService(setup_session).enqueue_job(
            user_id=1003,
            project_id="active-slot-project",
            job_type="chapter_workflow",
            title="Active slot contender B",
            idempotency_key="active-slot-b",
            stream_type="workflow",
            stream_id="active-slot-run-b",
        )
        chapter_id = chapter.id
        base_revision = chapter.current_revision

    release_inserts = asyncio.Event()
    ready_connections = 0
    backend_pids: set[int] = set()

    async def insert_run(run_id: str, root_job_id: str) -> str:
        nonlocal ready_connections
        async with session_factory() as session:
            backend_pid = await session.scalar(select(func.pg_backend_pid()))
            assert backend_pid is not None
            backend_pids.add(backend_pid)
            ready_connections += 1
            if ready_connections == 2:
                release_inserts.set()
            await release_inserts.wait()
            session.add(
                ChapterWorkflowRun(
                    id=run_id,
                    user_id=1003,
                    project_id="active-slot-project",
                    chapter_id=chapter_id,
                    chapter_number=1,
                    base_revision=base_revision,
                    root_job_id=root_job_id,
                    workflow_version=1,
                    state_schema_version=1,
                    context_schema_version=1,
                    context_snapshot={},
                    context_hash="a" * 64,
                    runtime_input_hash="b" * 64,
                    status="queued",
                    node_key="queued",
                )
            )
            try:
                await session.commit()
            except IntegrityError:
                await session.rollback()
                return "conflict"
            return "created"

    outcomes = await asyncio.wait_for(
        asyncio.gather(
            insert_run("active-slot-run-a", first_job.id),
            insert_run("active-slot-run-b", second_job.id),
        ),
        timeout=5,
    )

    async with session_factory() as session:
        active_count = await session.scalar(
            select(func.count())
            .select_from(ChapterWorkflowRun)
            .where(
                ChapterWorkflowRun.project_id == "active-slot-project",
                ChapterWorkflowRun.chapter_number == 1,
                ChapterWorkflowRun.base_revision == base_revision,
                ChapterWorkflowRun.is_active.is_(True),
            )
        )
        persisted_ids = set(
            (
                await session.execute(
                    select(ChapterWorkflowRun.id).where(
                        ChapterWorkflowRun.project_id == "active-slot-project"
                    )
                )
            ).scalars()
        )

    assert sorted(outcomes) == ["conflict", "created"]
    assert len(backend_pids) == 2
    assert active_count == 1
    assert persisted_ids in ({"active-slot-run-a"}, {"active-slot-run-b"})


@pytest.mark.asyncio(loop_scope="session")
async def test_wait_resume_releases_lease_skips_claim_and_rejects_stale_fence(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=34, username="waiting-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=34,
            job_type="workflow-root",
            title="等待工作流命令",
            idempotency_key="workflow-waiting",
            stream_type="workflow",
            stream_id="workflow-run-34",
        )
        started_at = job.available_at + timedelta(seconds=1)
        first_lease = await service.claim_next(
            worker_id="workflow-worker-a",
            lease_seconds=30,
            now=started_at,
        )
        assert first_lease is not None

        waiting = await service.wait_for_resume(
            first_lease,
            now=started_at + timedelta(seconds=1),
        )

        assert waiting.status == "waiting"
        assert waiting.lease_owner is None
        assert waiting.lease_expires_at is None
        assert waiting.heartbeat_at is None
        assert (waiting.attempt, waiting.fencing_token) == (1, 1)
        assert (
            await service.claim_next(
                worker_id="workflow-worker-b",
                lease_seconds=30,
                now=started_at + timedelta(seconds=60),
            )
            is None
        )

        resumed = await service.resume_waiting(
            job.id,
            expected_fencing_token=first_lease.fencing_token,
            now=started_at + timedelta(seconds=61),
        )
        assert resumed.status == "queued"
        assert resumed.available_at == started_at + timedelta(seconds=61)

        stale_writes: list[str] = []

        async def stale_writer(_session) -> None:
            stale_writes.append("called")

        with pytest.raises(LeaseLostError):
            await service.resume_waiting(
                job.id,
                expected_fencing_token=first_lease.fencing_token,
                outcome_writer=stale_writer,
                now=started_at + timedelta(seconds=62),
            )
        assert stale_writes == []

        second_lease = await service.claim_next(
            worker_id="workflow-worker-b",
            lease_seconds=30,
            now=started_at + timedelta(seconds=62),
        )
        assert second_lease is not None
        assert (second_lease.attempt, second_lease.fencing_token) == (2, 2)
        with pytest.raises(LeaseLostError):
            await service.wait_for_resume(
                first_lease,
                outcome_writer=stale_writer,
                now=started_at + timedelta(seconds=63),
            )
        assert stale_writes == []

        events = await service.list_events(user_id=34, after_cursor=0)
        assert [event.event_type for event in events] == [
            "job.queued",
            "job.started",
            "workflow.waiting",
            "workflow.phase_changed",
            "job.started",
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_backoff_stops_at_dead_letter(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=2, username="retry-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=2,
            job_type="retry-test",
            title="重试测试",
            idempotency_key="retry-once",
            max_attempts=2,
        )
        started_at = job.available_at + timedelta(seconds=1)
        first_lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=30,
            now=started_at,
        )
        assert first_lease is not None

        retrying = await service.record_failure(
            first_lease,
            error_category="provider_timeout",
            public_message="上游服务暂时不可用",
            retryable=True,
            retry_policy=RetryPolicy(base_delay_seconds=10, max_delay_seconds=60, jitter_ratio=0),
            now=started_at + timedelta(seconds=1),
        )

        assert retrying.status == "retry_wait"
        assert retrying.available_at == started_at + timedelta(seconds=11)
        assert (
            await service.claim_next(
                worker_id="worker-b",
                lease_seconds=30,
                now=started_at + timedelta(seconds=10),
            )
            is None
        )

        second_lease = await service.claim_next(
            worker_id="worker-b",
            lease_seconds=30,
            now=started_at + timedelta(seconds=11),
        )
        assert second_lease is not None
        dead_letter = await service.record_failure(
            second_lease,
            error_category="provider_timeout",
            public_message="上游服务仍不可用",
            retryable=True,
            retry_policy=RetryPolicy(base_delay_seconds=10, max_delay_seconds=60, jitter_ratio=0),
            now=started_at + timedelta(seconds=12),
        )

        assert dead_letter.status == "dead_letter"
        assert dead_letter.dead_lettered_at == started_at + timedelta(seconds=12)
        assert (
            await service.claim_next(
                worker_id="worker-c",
                lease_seconds=30,
                now=started_at + timedelta(minutes=10),
            )
            is None
        )
        events = await service.list_events(user_id=2, after_cursor=0)
        assert [event.event_type for event in events] == [
            "job.queued",
            "job.started",
            "job.retry_scheduled",
            "job.started",
            "job.dead_lettered",
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_cancel_is_durable_before_and_during_execution(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=3, username="cancel-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)

        queued = await service.enqueue_job(
            user_id=3,
            job_type="cancel-test",
            title="取消排队任务",
            idempotency_key="cancel-queued",
        )
        cancelled_queued = await service.request_cancel(queued.id, user_id=3)

        assert cancelled_queued is not None
        assert cancelled_queued.status == "cancelled"
        assert await service.claim_next(worker_id="worker-a", lease_seconds=30) is None

        running = await service.enqueue_job(
            user_id=3,
            job_type="cancel-test",
            title="取消运行任务",
            idempotency_key="cancel-running",
        )
        claimed_at = running.available_at + timedelta(seconds=1)
        lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=30,
            now=claimed_at,
        )
        assert lease is not None

        requested = await service.request_cancel(
            running.id,
            user_id=3,
            now=claimed_at + timedelta(seconds=1),
        )
        heartbeat = await service.heartbeat(
            lease,
            lease_seconds=30,
            now=claimed_at + timedelta(seconds=2),
        )
        cancelled_running = await service.mark_cancelled(
            lease,
            now=claimed_at + timedelta(seconds=2),
        )

        assert requested is not None
        assert requested.cancel_requested_at is not None
        assert heartbeat == HeartbeatResult(cancel_requested=True)
        assert cancelled_running.status == "cancelled"

        cancel_before_wait = await service.enqueue_job(
            user_id=3,
            job_type="workflow-root",
            title="取消后进入等待",
            idempotency_key="cancel-before-wait",
            stream_type="workflow",
            stream_id="cancel-before-wait",
        )
        cancel_before_wait_lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=30,
        )
        assert cancel_before_wait_lease is not None
        await service.request_cancel(cancel_before_wait.id, user_id=3)
        cancelled_outcome_writes: list[str] = []

        async def cancelled_outcome_writer(_session) -> None:
            cancelled_outcome_writes.append("called")

        cancelled_before_wait = await service.wait_for_resume(
            cancel_before_wait_lease,
            outcome_writer=cancelled_outcome_writer,
        )
        assert cancelled_before_wait.status == "cancelled"
        assert cancelled_before_wait.heartbeat_at is None
        assert cancelled_outcome_writes == []

        wait_before_cancel = await service.enqueue_job(
            user_id=3,
            job_type="workflow-root",
            title="等待后取消",
            idempotency_key="wait-before-cancel",
            stream_type="workflow",
            stream_id="wait-before-cancel",
        )
        wait_before_cancel_lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=30,
        )
        assert wait_before_cancel_lease is not None
        await service.wait_for_resume(wait_before_cancel_lease)
        cancelled_after_wait = await service.request_cancel(
            wait_before_cancel.id,
            user_id=3,
        )
        assert cancelled_after_wait is not None
        assert cancelled_after_wait.status == "cancelled"
        assert await service.claim_next(worker_id="worker-b", lease_seconds=30) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_expired_cancelled_job_is_reaped_after_worker_crash(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=31, username="cancel-reaper", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=31,
            job_type="cancel-reaper-test",
            title="崩溃后取消",
            idempotency_key="cancel-after-crash",
        )
        claimed_at = job.available_at + timedelta(seconds=1)
        lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=5,
            now=claimed_at,
        )
        assert lease is not None
        await service.request_cancel(
            job.id,
            user_id=31,
            now=claimed_at + timedelta(seconds=1),
        )

        assert (
            await service.claim_next(
                worker_id="worker-b",
                lease_seconds=30,
                now=claimed_at + timedelta(seconds=6),
            )
            is None
        )

        refreshed = await service.get_job(job.id)
        assert refreshed is not None
        assert refreshed.status == "cancelled"
        events = await service.list_events(user_id=31, after_cursor=0)
        assert [event.event_type for event in events][-2:] == [
            "job.cancel_requested",
            "job.cancelled",
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_expired_final_attempt_is_dead_lettered_without_another_claim(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=32, username="attempt-reaper", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=32,
            job_type="attempt-reaper-test",
            title="最后一次执行崩溃",
            idempotency_key="attempt-exhausted",
            max_attempts=1,
        )
        claimed_at = job.available_at + timedelta(seconds=1)
        lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=5,
            now=claimed_at,
        )
        assert lease is not None

        assert (
            await service.claim_next(
                worker_id="worker-b",
                lease_seconds=30,
                now=claimed_at + timedelta(seconds=6),
            )
            is None
        )

        refreshed = await service.get_job(job.id)
        assert refreshed is not None
        assert refreshed.status == "dead_letter"
        assert refreshed.attempt == 1
        assert refreshed.error_category == "lease_expired_attempts_exhausted"


@pytest.mark.asyncio(loop_scope="session")
async def test_executor_generation_rollout_fences_old_claimers_and_moves_waiting_jobs(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=33, username="rollout-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        waiting = await service.enqueue_job(
            user_id=33,
            job_type="rollout-test",
            title="等待切代",
            idempotency_key="rollout-waiting",
            stream_type="workflow",
            stream_id="rollout-workflow",
        )
        waiting_lease = await service.claim_next(
            worker_id="old-worker",
            lease_seconds=30,
        )
        assert waiting_lease is not None
        waiting_id = waiting.id
        await service.wait_for_resume(waiting_lease)

        rollout = await service.switch_executor_generation(
            expected_generation=1,
            new_generation=2,
            rollout_owner="deploy-2",
        )

        assert rollout.previous_generation == 1
        assert rollout.active_generation == 2
        assert rollout.reassigned_waiting_jobs == 1
        with pytest.raises(ExecutorGenerationInactiveError) as rollout_error:
            await service.switch_executor_generation(
                expected_generation=1,
                new_generation=3,
                rollout_owner="stale-deploy",
            )
        assert rollout_error.value.active_generation == 2
        with pytest.raises(ExecutorGenerationInactiveError):
            await service.claim_next(
                worker_id="old-worker",
                lease_seconds=30,
                executor_generation=1,
            )

        assert (
            await service.claim_next(
                worker_id="new-worker",
                lease_seconds=30,
                executor_generation=2,
            )
            is None
        )
        await service.resume_waiting(
            waiting_id,
            expected_fencing_token=waiting_lease.fencing_token,
        )
        lease = await service.claim_next(
            worker_id="new-worker",
            lease_seconds=30,
            executor_generation=2,
        )
        assert lease is not None
        assert lease.job_id == waiting_id
        assert lease.executor_generation == 2

        control = await session.get(JobExecutorControl, "default")
        assert control is not None
        assert control.rollout_owner == "deploy-2"


@pytest.mark.asyncio(loop_scope="session")
async def test_ambiguous_external_activity_is_not_replayed_after_lease_loss(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=4, username="activity-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=4,
            job_type="ambiguous-test",
            title="不确定外部调用",
            idempotency_key="ambiguous-once",
        )
        started_at = job.available_at + timedelta(seconds=1)
        first_lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=5,
            now=started_at,
        )
        assert first_lease is not None

        first_intent = await service.begin_activity(
            first_lease,
            activity_key="provider-call",
            side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
            request_payload={"operation": "generate"},
            now=started_at + timedelta(seconds=1),
        )
        assert first_intent.should_execute is True

        second_lease = await service.claim_next(
            worker_id="worker-b",
            lease_seconds=30,
            now=started_at + timedelta(seconds=6),
        )
        assert second_lease is None

        refreshed = await service.get_job(job.id)
        assert refreshed is not None
        assert refreshed.status == "needs_attention"
        assert refreshed.dead_lettered_at is None
        events = await service.list_events(user_id=4, after_cursor=0)
        assert [event.event_type for event in events][-1] == "job.needs_attention"


@pytest.mark.asyncio(loop_scope="session")
async def test_idempotent_external_activity_reuses_provider_key_after_lease_loss(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=5, username="provider-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=5,
            job_type="idempotent-provider-test",
            title="可去重外部调用",
            idempotency_key="provider-once",
        )
        started_at = job.available_at + timedelta(seconds=1)
        first_lease = await service.claim_next(
            worker_id="worker-a",
            lease_seconds=5,
            now=started_at,
        )
        assert first_lease is not None
        first_intent = await service.begin_activity(
            first_lease,
            activity_key="provider-call",
            side_effect_class=SideEffectClass.IDEMPOTENT_EXTERNAL,
            now=started_at + timedelta(seconds=1),
        )

        provider_results: dict[str, dict[str, str]] = {}
        provider_call_count = 0

        def call_provider(request_key: str) -> dict[str, str]:
            nonlocal provider_call_count
            if request_key not in provider_results:
                provider_call_count += 1
                provider_results[request_key] = {"provider_id": "result-1"}
            return provider_results[request_key]

        first_result = call_provider(first_intent.provider_request_key)

        second_lease = await service.claim_next(
            worker_id="worker-b",
            lease_seconds=30,
            now=started_at + timedelta(seconds=6),
        )
        assert second_lease is not None
        retry_intent = await service.begin_activity(
            second_lease,
            activity_key="provider-call",
            side_effect_class=SideEffectClass.IDEMPOTENT_EXTERNAL,
            now=started_at + timedelta(seconds=7),
        )
        retry_result = call_provider(retry_intent.provider_request_key)
        await service.complete_activity(
            second_lease,
            activity_key="provider-call",
            provider_request_key=retry_intent.provider_request_key,
            result=retry_result,
            now=started_at + timedelta(seconds=8),
        )
        cached = await service.begin_activity(
            second_lease,
            activity_key="provider-call",
            side_effect_class=SideEffectClass.IDEMPOTENT_EXTERNAL,
            now=started_at + timedelta(seconds=9),
        )

        assert retry_intent.provider_request_key == first_intent.provider_request_key
        assert retry_result == first_result
        assert provider_call_count == 1
        assert cached.should_execute is False
        assert cached.result == {"provider_id": "result-1"}


@pytest.mark.asyncio(loop_scope="session")
async def test_activity_key_rejects_canonical_request_drift(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=35, username="activity-contract-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        await service.enqueue_job(
            user_id=35,
            job_type="activity-contract-test",
            title="Activity contract",
            idempotency_key="activity-contract",
        )
        lease = await service.claim_next(worker_id="activity-worker", lease_seconds=30)
        assert lease is not None

        first = await service.begin_activity(
            lease,
            activity_key="persist-candidates",
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            request_payload={
                "run_id": "run-35",
                "candidate_ids": ["a", "b"],
                "revision": 1,
            },
        )
        same_request = await service.begin_activity(
            lease,
            activity_key="persist-candidates",
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            request_payload={
                "candidate_ids": ["a", "b"],
                "revision": 1,
                "run_id": "run-35",
            },
        )
        assert same_request.provider_request_key == first.provider_request_key

        with pytest.raises(ValueError, match="canonical request"):
            await service.begin_activity(
                lease,
                activity_key="persist-candidates",
                side_effect_class=SideEffectClass.TRANSACTIONAL,
                request_payload={
                    "run_id": "run-35",
                    "candidate_ids": ["a", "b"],
                    "revision": True,
                },
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_activity_result_and_ai_usage_ledger_commit_atomically_and_idempotently(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=6, username="telemetry-writer", hashed_password="secret"))
        session.add(
            NovelProject(
                id="telemetry-project",
                user_id=6,
                title="Telemetry",
                initial_prompt="test",
            )
        )
        await session.commit()
        service = JobService(session)
        job = await service.enqueue_job(
            user_id=6,
            project_id="telemetry-project",
            job_type="chapter_finalize",
            title="Telemetry activity",
            idempotency_key="telemetry-activity",
        )
        job_id = job.id
        lease = await service.claim_next(worker_id="telemetry-worker", lease_seconds=30)
        assert lease is not None
        intent = await service.begin_activity(
            lease,
            activity_key="summary_generation",
            side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        )
        ai_call = AICallResult.from_config(
            "summary",
            config={
                "provider_type": "openai_compatible",
                "model": "chat-model",
                "model_id": 12,
                "input_price_per_million": "2",
                "output_price_per_million": "8",
                "cached_input_price_per_million": "0.5",
                "cache_write_input_price_per_million": None,
                "pricing_currency": "USD",
            },
            usage=TokenUsage(
                input_tokens=10,
                output_tokens=2,
                total_tokens=12,
                cached_input_tokens=4,
                cache_write_input_tokens=0,
                reasoning_tokens=1,
                is_complete=True,
            ),
            stage="summary_memory",
        )

        async def failing_outcome_writer(writer_session) -> None:
            project = await writer_session.get(NovelProject, "telemetry-project")
            assert project is not None
            project.title = "should-roll-back"
            raise RuntimeError("domain write failed")

        with pytest.raises(RuntimeError, match="domain write failed"):
            await service.complete_activity(
                lease,
                activity_key="summary_generation",
                provider_request_key=intent.provider_request_key,
                result={"response": "summary"},
                ai_call=ai_call,
                outcome_writer=failing_outcome_writer,
            )
        rolled_back_project = await session.get(NovelProject, "telemetry-project")
        rolled_back_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == job_id,
                    JobActivity.activity_key == "summary_generation",
                )
            )
        ).scalar_one()
        assert rolled_back_project is not None
        assert rolled_back_project.title == "Telemetry"
        assert rolled_back_activity.status == "started"

        async def outcome_writer(writer_session) -> None:
            project = await writer_session.get(NovelProject, "telemetry-project")
            assert project is not None
            project.title = "Committed atomically"

        first = await service.complete_activity(
            lease,
            activity_key="summary_generation",
            provider_request_key=intent.provider_request_key,
            result={"response": "summary"},
            ai_call=ai_call,
            outcome_writer=outcome_writer,
        )
        replayed_outcome_writes: list[str] = []

        async def replay_outcome_writer(_writer_session) -> None:
            replayed_outcome_writes.append("called")

        second = await service.complete_activity(
            lease,
            activity_key="summary_generation",
            provider_request_key=intent.provider_request_key,
            result={"response": "summary"},
            ai_call=ai_call,
            outcome_writer=replay_outcome_writer,
        )

        records = list((await session.execute(select(AIUsageRecord))).scalars())
        activity = await session.get(JobActivity, first.id)
        assert second.id == first.id
        assert replayed_outcome_writes == []
        assert len(records) == 1
        assert records[0].job_activity_id == first.id
        assert records[0].job_id == job_id
        assert records[0].project_id == "telemetry-project"
        assert records[0].input_tokens == 10
        assert records[0].output_tokens == 2
        assert str(records[0].cost_amount) == "0.000030000000"
        assert records[0].cost_currency == "USD"
        assert records[0].cost_unknown_reason is None
        assert activity is not None
        assert activity.result_payload == {
            "response": "summary",
            "ai_telemetry": ai_call.telemetry_dict(),
        }
        committed_project = await session.get(NovelProject, "telemetry-project")
        assert committed_project is not None
        assert committed_project.title == "Committed atomically"


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_health_covers_fresh_stale_draining_and_stopped(db_session_factory):
    checked_at = datetime(2026, 7, 28, 8, 0, tzinfo=timezone.utc)

    async with db_session_factory() as session:
        service = JobService(session)
        missing = await service.get_worker_health(
            executor_generation=1,
            stale_after_seconds=10,
            now=checked_at,
        )
        assert missing.healthy is False
        assert missing.worker_id is None

        await service.register_worker(
            worker_id="health-worker",
            executor_generation=1,
            now=checked_at - timedelta(seconds=10),
        )
        fresh = await service.get_worker_health(
            executor_generation=1,
            stale_after_seconds=10,
            now=checked_at,
        )
        stale = await service.get_worker_health(
            executor_generation=1,
            stale_after_seconds=10,
            now=checked_at + timedelta(microseconds=1),
        )

        assert fresh.healthy is True
        assert fresh.state == "running"
        assert fresh.heartbeat_age_seconds == 10
        assert stale.healthy is False

        await service.mark_worker_draining(
            worker_id="health-worker",
            executor_generation=1,
            now=checked_at,
        )
        draining = await service.get_worker_health(
            executor_generation=1,
            stale_after_seconds=10,
            now=checked_at,
        )
        assert draining.healthy is False
        assert draining.state == "draining"

        await service.mark_worker_stopped(
            worker_id="health-worker",
            executor_generation=1,
            now=checked_at,
        )
        stopped = await service.get_worker_health(
            executor_generation=1,
            stale_after_seconds=10,
            now=checked_at,
        )
        assert stopped.healthy is False
        assert stopped.state == "stopped"

        with pytest.raises(ValueError, match="stale_after_seconds"):
            await service.get_worker_health(
                executor_generation=1,
                stale_after_seconds=0,
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_runtime_metrics_report_queue_age_statuses_and_expired_leases(
    db_session_factory,
):
    checked_at = datetime(2026, 7, 28, 9, 0, tzinfo=timezone.utc)

    async with db_session_factory() as session:
        session.add(User(id=1301, username="metrics-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        queued = await service.enqueue_job(
            user_id=1301,
            job_type="metrics-test",
            title="排队指标",
            idempotency_key="metrics-queued",
        )
        retrying = await service.enqueue_job(
            user_id=1301,
            job_type="metrics-test",
            title="重试指标",
            idempotency_key="metrics-retry",
        )
        expired = await service.enqueue_job(
            user_id=1301,
            job_type="metrics-test",
            title="过期 lease 指标",
            idempotency_key="metrics-expired",
        )
        waiting = await service.enqueue_job(
            user_id=1301,
            job_type="metrics-test",
            title="工作流等待指标",
            idempotency_key="metrics-waiting",
        )

        queued.created_at = checked_at - timedelta(seconds=30)
        queued.available_at = queued.created_at
        retrying.status = "retry_wait"
        retrying.created_at = checked_at - timedelta(seconds=50)
        retrying.available_at = checked_at + timedelta(seconds=10)
        expired.status = "running"
        expired.created_at = checked_at - timedelta(seconds=20)
        expired.lease_owner = "dead-worker"
        expired.lease_expires_at = checked_at - timedelta(seconds=1)
        waiting.status = "waiting"
        waiting.created_at = checked_at - timedelta(seconds=90)
        await session.commit()

        metrics = await service.get_runtime_metrics(now=checked_at)

        assert queued.status == "queued"
        assert metrics.status_counts == {
            "queued": 1,
            "retry_wait": 1,
            "running": 1,
            "waiting": 1,
        }
        assert metrics.queue_depth == 2
        assert metrics.oldest_queued_age_seconds == 50
        assert metrics.expired_leases == 1
        assert metrics.latest_event_cursor > 0
        assert metrics.retained_event_count == 4
        assert metrics.retention_users == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_transition_adapter_syncs_wait_resume_retry_and_success(
    isolated_pg,
):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, _ = await _create_workflow_root(
            session,
            user_id=1401,
            project_id="workflow-transition-main",
            chapter_number=1,
            run_id="workflow-transition-main",
        )
        started_at = datetime.now(timezone.utc)
        service = JobService(session)
        first_lease = await service.claim_next(
            worker_id="workflow-worker-1",
            lease_seconds=30,
            now=started_at,
        )
        assert first_lease is not None
        waiting = await service.wait_for_resume(
            first_lease,
            workflow_transition=ChapterWorkflowTransition(
                status="waiting_for_selection",
                node_key="waiting_for_selection",
                checkpoint_id="checkpoint-waiting",
                progress=60,
            ),
            now=started_at + timedelta(seconds=1),
        )
        waiting_run = await session.get(ChapterWorkflowRun, "workflow-transition-main")
        assert waiting.status == "waiting"
        assert waiting.lease_owner is None
        assert waiting.lease_expires_at is None
        assert waiting_run is not None
        assert waiting_run.status == "waiting_for_selection"
        assert waiting_run.is_active is True
        await service.resume_waiting(
            job.id,
            expected_fencing_token=waiting.fencing_token,
            workflow_transition=ChapterWorkflowTransition(
                status="queued",
                node_key="waiting_for_selection",
                checkpoint_id="checkpoint-waiting",
                progress=60,
            ),
            now=started_at + timedelta(seconds=2),
        )
        resumed_run = await session.get(ChapterWorkflowRun, "workflow-transition-main")
        assert resumed_run is not None
        assert resumed_run.status == "queued"
        assert resumed_run.is_active is True
        second_lease = await service.claim_next(
            worker_id="workflow-worker-2",
            lease_seconds=30,
            now=started_at + timedelta(seconds=3),
        )
        assert second_lease is not None
        retrying = await service.record_failure(
            second_lease,
            error_category="temporary_failure",
            public_message="暂时失败",
            retryable=True,
            retry_policy=RetryPolicy(base_delay_seconds=0, max_delay_seconds=0),
            now=started_at + timedelta(seconds=4),
        )
        retrying_run = await session.get(ChapterWorkflowRun, "workflow-transition-main")
        assert retrying.status == "retry_wait"
        assert retrying.lease_owner is None
        assert retrying.lease_expires_at is None
        assert retrying_run is not None
        assert retrying_run.status == "retry_wait"
        assert retrying_run.is_active is True
        third_lease = await service.claim_next(
            worker_id="workflow-worker-3",
            lease_seconds=30,
            now=started_at + timedelta(seconds=5),
        )
        assert third_lease is not None
        await service.mark_succeeded(
            third_lease,
            result={"run_id": job.stream_id},
            workflow_transition=ChapterWorkflowTransition(
                status="successful",
                node_key="successful",
                checkpoint_id="checkpoint-successful",
                progress=100,
            ),
            now=started_at + timedelta(seconds=6),
        )

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job.id)
        persisted_run = await session.get(ChapterWorkflowRun, "workflow-transition-main")
        events = list(
            (
                await session.execute(
                    select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.sequence)
                )
            ).scalars()
        )

    assert persisted_job is not None
    assert persisted_job.status == "succeeded"
    assert persisted_run is not None
    assert persisted_run.status == "successful"
    assert persisted_run.node_key == "successful"
    assert persisted_run.checkpoint_id == "checkpoint-successful"
    assert persisted_run.row_revision == 7
    assert persisted_run.is_active is False
    assert persisted_run.completed_at is not None
    assert [event.event_type for event in events] == [
        "job.queued",
        "workflow.phase_changed",
        "workflow.waiting",
        "workflow.phase_changed",
        "workflow.phase_changed",
        "workflow.phase_changed",
        "workflow.phase_changed",
        "workflow.completed",
    ]
    expected_statuses = [
        "running",
        "waiting_for_selection",
        "queued",
        "running",
        "retry_wait",
        "running",
        "successful",
    ]
    for revision, event, expected_status in zip(
        range(1, 8),
        events[1:],
        expected_statuses,
        strict=True,
    ):
        assert event.payload["task"]["id"] == job.id
        assert "payload" not in event.payload["task"]
        assert "result" not in event.payload["task"]
        assert set(event.payload["workflow"]) <= {
            "run_id",
            "row_revision",
            "node_key",
            "status",
            "checkpoint_id",
            "progress",
            "error_category",
            "public_error",
        }
        assert event.payload["workflow"]["row_revision"] == revision
        assert event.payload["workflow"]["status"] == expected_status


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_transition_adapter_maps_ambiguity_cancel_and_failure(
    isolated_pg,
):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        ambiguous_job, _ = await _create_workflow_root(
            session,
            user_id=1402,
            project_id="workflow-transition-ambiguous",
            chapter_number=1,
            run_id="workflow-transition-ambiguous",
        )
        started_at = datetime.now(timezone.utc)
        service = JobService(session)
        lease = await service.claim_next(
            worker_id="workflow-ambiguous-worker",
            lease_seconds=30,
            now=started_at,
        )
        assert lease is not None
        activity = await service.begin_activity(
            lease,
            activity_key="generate:0",
            side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        )
        await service.mark_activity_ambiguous(
            lease,
            activity_key="generate:0",
            provider_request_key=activity.provider_request_key,
            public_message="provider 结果未知",
            now=started_at + timedelta(seconds=1),
        )

    async with session_factory() as session:
        persisted_ambiguous_job = await session.get(BackgroundTask, ambiguous_job.id)
        ambiguous_run = await session.get(
            ChapterWorkflowRun,
            "workflow-transition-ambiguous",
        )
        persisted_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == ambiguous_job.id,
                    JobActivity.activity_key == "generate:0",
                )
            )
        ).scalar_one()
        ambiguous_events = list(
            (
                await session.execute(
                    select(JobEvent)
                    .where(JobEvent.job_id == ambiguous_job.id)
                    .order_by(JobEvent.sequence)
                )
            ).scalars()
        )

    assert persisted_ambiguous_job is not None
    assert persisted_ambiguous_job.status == "needs_attention"
    assert ambiguous_run is not None
    assert ambiguous_run.status == "needs_attention"
    assert ambiguous_run.is_active is True
    assert ambiguous_run.completed_at is None
    assert ambiguous_run.error_category == "ambiguous_external_result"
    assert ambiguous_run.row_revision == 2
    assert persisted_activity.status == "ambiguous"
    assert persisted_activity.attempt == lease.attempt
    assert persisted_activity.fencing_token == lease.fencing_token
    assert [event.event_type for event in ambiguous_events] == [
        "job.queued",
        "workflow.phase_changed",
        "activity.started",
        "workflow.needs_attention",
    ]
    assert ambiguous_events[-1].event_type == "workflow.needs_attention"

    async with session_factory() as session:
        cancelled_job, _ = await _create_workflow_root(
            session,
            user_id=1403,
            project_id="workflow-transition-cancelled",
            chapter_number=1,
            run_id="workflow-transition-cancelled",
        )
        cancel_service = JobService(session)
        cancelled_lease = await cancel_service.claim_next(
            worker_id="workflow-cancel-worker",
            lease_seconds=30,
            now=started_at + timedelta(seconds=2),
        )
        assert cancelled_lease is not None
        cancel_requested = await cancel_service.request_cancel(
            cancelled_job.id,
            user_id=1403,
            now=started_at + timedelta(seconds=3),
        )
        assert cancel_requested is not None
        assert cancel_requested.status == "running"
        cancelled = await cancel_service.mark_cancelled(
            cancelled_lease,
            now=started_at + timedelta(seconds=4),
        )
        assert cancelled.status == "cancelled"

    async with session_factory() as session:
        cancelled_run = await session.get(
            ChapterWorkflowRun,
            "workflow-transition-cancelled",
        )
        cancelled_event = (
            await session.execute(
                select(JobEvent)
                .where(JobEvent.job_id == cancelled_job.id)
                .order_by(JobEvent.sequence.desc())
                .limit(1)
            )
        ).scalar_one()

    assert cancelled_run is not None
    assert cancelled_run.status == "cancelled"
    assert cancelled_run.is_active is False
    assert cancelled_event.event_type == "workflow.completed"

    async with session_factory() as session:
        failed_job, _ = await _create_workflow_root(
            session,
            user_id=1404,
            project_id="workflow-transition-failed",
            chapter_number=1,
            run_id="workflow-transition-failed",
        )
        service = JobService(session)
        failed_lease = await service.claim_next(
            worker_id="workflow-failed-worker",
            lease_seconds=30,
            now=started_at + timedelta(seconds=5),
        )
        assert failed_lease is not None
        await service.record_failure(
            failed_lease,
            error_category="permanent_failure",
            public_message="Authorization: Bearer workflow-private-token",
            retryable=False,
            now=started_at + timedelta(seconds=6),
        )

    async with session_factory() as session:
        persisted_failed_job = await session.get(BackgroundTask, failed_job.id)
        failed_run = await session.get(ChapterWorkflowRun, "workflow-transition-failed")
        failed_event = (
            await session.execute(
                select(JobEvent)
                .where(JobEvent.job_id == failed_job.id)
                .order_by(JobEvent.sequence.desc())
                .limit(1)
            )
        ).scalar_one()

    assert persisted_failed_job is not None
    assert persisted_failed_job.status == "failed"
    assert persisted_failed_job.lease_owner is None
    assert persisted_failed_job.lease_expires_at is None
    assert failed_run is not None
    assert failed_run.status == "failed"
    assert failed_run.is_active is False
    assert failed_run.error_category == "permanent_failure"
    assert failed_run.public_error == "Authorization: [已隐藏]"
    assert persisted_failed_job.error == "Authorization: [已隐藏]"
    assert failed_event.payload["task"]["error"] == "Authorization: [已隐藏]"
    assert failed_event.payload["workflow"]["public_error"] == "Authorization: [已隐藏]"
    assert "workflow-private-token" not in str(failed_event.payload)
    assert failed_event.event_type == "workflow.completed"


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_transition_rolls_back_job_run_slot_and_event_together(
    isolated_pg,
    monkeypatch,
):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, _ = await _create_workflow_root(
            session,
            user_id=1405,
            project_id="workflow-transition-rollback",
            chapter_number=1,
            run_id="workflow-transition-rollback",
        )
        started_at = datetime.now(timezone.utc)
        lease = await JobService(session).claim_next(
            worker_id="workflow-rollback-worker",
            lease_seconds=30,
            now=started_at,
        )
        assert lease is not None
        persisted_run = await session.get(ChapterWorkflowRun, "workflow-transition-rollback")
        assert persisted_run is not None
        before_revision = persisted_run.row_revision
        before_sequence = lease.fencing_token

    async with session_factory() as session:
        service = JobService(session)

        async def fail_event_write(_event):
            raise RuntimeError("event write failed")

        monkeypatch.setattr(service.repo, "add_event", fail_event_write)
        with pytest.raises(RuntimeError, match="event write failed"):
            await service.record_failure(
                lease,
                error_category="temporary_failure",
                public_message="暂时失败",
                retryable=True,
                retry_policy=RetryPolicy(base_delay_seconds=0, max_delay_seconds=0),
                now=started_at + timedelta(seconds=1),
            )
        await session.rollback()

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job.id)
        persisted_run = await session.get(ChapterWorkflowRun, "workflow-transition-rollback")
        events = list(
            (
                await session.execute(
                    select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.sequence)
                )
            ).scalars()
        )

    assert persisted_job is not None
    assert persisted_job.status == "running"
    assert persisted_job.fencing_token == before_sequence
    assert persisted_job.lease_owner == "workflow-rollback-worker"
    assert persisted_run is not None
    assert persisted_run.status == "running"
    assert persisted_run.is_active is True
    assert persisted_run.row_revision == before_revision
    assert [event.event_type for event in events] == [
        "job.queued",
        "workflow.phase_changed",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_transition_identity_drift_fails_closed(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, _ = await _create_workflow_root(
            session,
            user_id=1406,
            project_id="workflow-transition-drift",
            chapter_number=1,
            run_id="workflow-transition-drift",
        )
        job.stream_id = "drifted-workflow-stream"
        await session.commit()
        job_id = job.id
        transition_at = datetime.now(timezone.utc)

        with pytest.raises(ValueError, match="身份不一致"):
            await JobService(session).claim_next(
                worker_id="workflow-drift-worker",
                lease_seconds=30,
                now=transition_at,
            )
        await session.rollback()

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job_id)
        persisted_run = await session.get(ChapterWorkflowRun, "workflow-transition-drift")
        events = list(
            (await session.execute(select(JobEvent).where(JobEvent.job_id == job_id))).scalars()
        )

    assert persisted_job is not None
    assert persisted_job.status == "queued"
    assert persisted_job.attempt == 0
    assert persisted_job.lease_owner is None
    assert persisted_run is not None
    assert persisted_run.status == "queued"
    assert persisted_run.row_revision == 0
    assert len(events) == 1
