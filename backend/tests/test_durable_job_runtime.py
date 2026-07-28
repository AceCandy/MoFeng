import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.models import BackgroundTask, JobExecutorControl, NovelProject
from app.models.user import User
from app.services.job_registry import SideEffectClass
from app.services.job_service import (
    ExecutorGenerationInactiveError,
    HeartbeatResult,
    JobService,
    LeaseLostError,
    RetryPolicy,
)


@pytest.mark.asyncio(loop_scope="session")
async def test_duplicate_idempotency_key_returns_one_job_and_one_queued_event(db_session_factory):
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试"))
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
async def test_concurrent_claim_and_fencing_reject_stale_worker(_pg_engine):
    session_factory = async_sessionmaker(_pg_engine, expire_on_commit=False)

    async with session_factory() as session:
        session.add(User(id=1001, username="claim-writer", hashed_password="secret"))
        session.add(NovelProject(id="claim-project", user_id=1001, title="测试项目", initial_prompt="测试"))
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

        async with session_factory() as session:
            with pytest.raises(LeaseLostError):
                await JobService(session).mark_succeeded(
                    first_lease,
                    result={"winner": first_lease.worker_id},
                    now=now + timedelta(seconds=32),
                )

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
        assert await service.claim_next(
            worker_id="worker-b",
            lease_seconds=30,
            now=started_at + timedelta(seconds=10),
        ) is None

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
        assert await service.claim_next(
            worker_id="worker-c",
            lease_seconds=30,
            now=started_at + timedelta(minutes=10),
        ) is None
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

        assert await service.claim_next(
            worker_id="worker-b",
            lease_seconds=30,
            now=claimed_at + timedelta(seconds=6),
        ) is None

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

        assert await service.claim_next(
            worker_id="worker-b",
            lease_seconds=30,
            now=claimed_at + timedelta(seconds=6),
        ) is None

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
        )

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

        lease = await service.claim_next(
            worker_id="new-worker",
            lease_seconds=30,
            executor_generation=2,
        )
        assert lease is not None
        assert lease.job_id == waiting.id
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
async def test_idempotent_external_activity_reuses_provider_key_after_lease_loss(db_session_factory):
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

        queued.created_at = checked_at - timedelta(seconds=30)
        queued.available_at = queued.created_at
        retrying.status = "retry_wait"
        retrying.created_at = checked_at - timedelta(seconds=50)
        retrying.available_at = checked_at + timedelta(seconds=10)
        expired.status = "running"
        expired.created_at = checked_at - timedelta(seconds=20)
        expired.lease_owner = "dead-worker"
        expired.lease_expires_at = checked_at - timedelta(seconds=1)
        await session.commit()

        metrics = await service.get_runtime_metrics(now=checked_at)

        assert queued.status == "queued"
        assert metrics.status_counts == {
            "queued": 1,
            "retry_wait": 1,
            "running": 1,
        }
        assert metrics.queue_depth == 2
        assert metrics.oldest_queued_age_seconds == 50
        assert metrics.expired_leases == 1
        assert metrics.latest_event_cursor > 0
        assert metrics.retained_event_count == 3
        assert metrics.retention_users == 0
