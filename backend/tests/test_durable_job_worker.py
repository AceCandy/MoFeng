import asyncio
import json
import multiprocessing
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from test_chapter_workflow_start import _seed_project

from app.models import ChapterOutline, ChapterWorkflowRun, JobEvent, NovelBlueprint, NovelProject
from app.models.job import JobActivity, JobWorkerHeartbeat
from app.models.user import User
from app.services.chapter_workflow_start import ChapterWorkflowStartService
from app.services.chapter_workflow_transition import ChapterWorkflowTransition
from app.services.job_handlers import build_job_handler_registry
from app.services.job_registry import JobHandlerRegistry, SideEffectClass
from app.services.job_service import JobService
from app.services.job_worker import JobOutcome, JobWaitOutcome, JobWorker
from app.services.llm_service import LLMService
from app.services.prompt_service import PromptService


def _run_process_worker(
    database_url: str,
    schema: str,
    worker_id: str,
    handler_delay: float,
) -> None:
    """在独立进程中 claim 并执行单个测试 job。"""

    async def run() -> None:
        engine = create_async_engine(
            database_url,
            connect_args={"server_settings": {"search_path": f'"{schema}", public'}},
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        registry = JobHandlerRegistry()

        async def handler(_context):
            await asyncio.sleep(handler_delay)
            return JobOutcome(result={"worker_id": worker_id})

        registry.register(
            job_type="process-crash-test",
            payload_version=1,
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            handler=handler,
        )
        worker = JobWorker(
            session_factory=session_factory,
            registry=registry,
            worker_id=worker_id,
            lease_seconds=1,
            heartbeat_interval_seconds=0.1,
            poll_interval_seconds=0.05,
        )
        try:
            await worker.run_once()
        finally:
            await engine.dispose()

    asyncio.run(run())


async def _wait_for_job_state(
    session_factory,
    job_id: str,
    *,
    status: str,
    lease_owner: str | None,
    timeout: float = 10,
):
    """等待跨进程提交的 job 状态变为可见。"""

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        async with session_factory() as session:
            job = await JobService(session).get_job(job_id)
            if job is not None and job.status == status and job.lease_owner == lease_owner:
                return job
        await asyncio.sleep(0.05)
    raise AssertionError(f"job 未在 {timeout} 秒内进入 {status} 状态")


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_dispatches_versioned_handler_and_dead_letters_unknown_version(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=11, username="worker-writer", hashed_password="secret"))
        await session.commit()
        service = JobService(session)
        supported = await service.enqueue_job(
            user_id=11,
            job_type="test-handler",
            title="已注册 handler",
            payload={"value": 7},
            payload_version=1,
            idempotency_key="handler-v1",
        )
        unsupported = await service.enqueue_job(
            user_id=11,
            job_type="test-handler",
            title="未知 payload 版本",
            payload={"value": 8},
            payload_version=2,
            idempotency_key="handler-v2",
        )

    registry = JobHandlerRegistry()

    async def handler(context):
        return JobOutcome(result={"value": context.lease.payload["value"] * 2})

    registry.register(
        job_type="test-handler",
        payload_version=1,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        handler=handler,
    )
    worker = JobWorker(
        session_factory=db_session_factory,
        registry=registry,
        worker_id="test-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )

    assert await worker.run_once() is True
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        supported_result = await JobService(session).get_job(supported.id)
        unsupported_result = await JobService(session).get_job(unsupported.id)

    assert supported_result is not None
    assert supported_result.status == "succeeded"
    assert supported_result.result == {"value": 14}
    assert unsupported_result is not None
    assert unsupported_result.status == "dead_letter"
    assert unsupported_result.error_category == "unknown_payload_version"


@pytest.mark.asyncio(loop_scope="session")
async def test_execution_context_allows_per_activity_side_effect_class_and_outcome_writer(
    db_session_factory,
):
    async with db_session_factory() as session:
        session.add(User(id=1100, username="mixed-activity-writer", hashed_password="secret"))
        await session.commit()
        job = await JobService(session).enqueue_job(
            user_id=1100,
            job_type="mixed-activity-handler",
            title="Mixed activity handler",
            idempotency_key="mixed-activity-handler",
        )

    outcome_writes: list[str] = []
    registry = JobHandlerRegistry()

    async def handler(context):
        intent = await context.begin_activity(
            "persist-result",
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            request_payload={"job_id": context.lease.job_id},
        )

        async def outcome_writer(_session) -> None:
            outcome_writes.append(context.lease.job_id)

        await context.complete_activity(
            "persist-result",
            provider_request_key=intent.provider_request_key,
            result={"persisted": True},
            outcome_writer=outcome_writer,
        )
        return JobOutcome(result={"done": True})

    registry.register(
        job_type="mixed-activity-handler",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handler,
    )
    worker = JobWorker(
        session_factory=db_session_factory,
        registry=registry,
        worker_id="mixed-activity-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        refreshed = await JobService(session).get_job(job.id)
        activity = (
            await session.execute(select(JobActivity).where(JobActivity.job_id == job.id))
        ).scalar_one()

    assert refreshed is not None
    assert refreshed.status == "succeeded"
    assert activity.side_effect_class == SideEffectClass.TRANSACTIONAL.value
    assert activity.status == "succeeded"
    assert outcome_writes == [job.id]


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_wait_outcome_releases_workflow_lease_without_marking_success(
    isolated_pg,
):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        await _seed_project(
            session,
            user_id=1102,
            project_id="workflow-worker-wait-project",
        )
        started = await ChapterWorkflowStartService(session).start(
            user_id=1102,
            project_id="workflow-worker-wait-project",
            chapter_number=1,
        )

    outcome_writes: list[str] = []
    registry = JobHandlerRegistry()

    async def handler(context):
        async def outcome_writer(_session) -> None:
            outcome_writes.append(context.lease.job_id)

        return JobWaitOutcome(
            workflow_transition=ChapterWorkflowTransition(
                status="waiting_for_selection",
                node_key="wait_for_selection",
                checkpoint_id="checkpoint-selection",
                progress=60,
            ),
            outcome_writer=outcome_writer,
        )

    registry.register(
        job_type="chapter_workflow",
        payload_version=1,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        handler=handler,
    )
    worker = JobWorker(
        session_factory=session_factory,
        registry=registry,
        worker_id="workflow-wait-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )

    assert await worker.run_once() is True

    async with session_factory() as session:
        job = await JobService(session).get_job(started.root_job.id)
        run = await session.get(ChapterWorkflowRun, started.run.id)
        event_types = list(
            (
                await session.execute(
                    select(JobEvent.event_type)
                    .where(JobEvent.stream_id == started.run.id)
                    .order_by(JobEvent.sequence)
                )
            ).scalars()
        )
        unclaimed = await JobService(session).claim_next(
            worker_id="workflow-wait-worker-b",
            lease_seconds=30,
        )

    assert job is not None
    assert job.status == "waiting"
    assert job.lease_owner is None
    assert job.lease_expires_at is None
    assert job.heartbeat_at is None
    assert job.result is None
    assert run is not None
    assert run.status == "waiting_for_selection"
    assert run.node_key == "wait_for_selection"
    assert run.checkpoint_id == "checkpoint-selection"
    assert run.progress == 60
    assert run.is_active is True
    assert outcome_writes == [started.root_job.id]
    assert event_types[-2:] == ["workflow.phase_changed", "workflow.waiting"]
    assert "workflow.completed" not in event_types
    assert unclaimed is None


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_cancels_running_handler_after_durable_cancel_request(isolated_pg):
    session_factory = isolated_pg.session_factory
    handler_started = asyncio.Event()
    keep_running = asyncio.Event()

    async with session_factory() as session:
        session.add(User(id=1101, username="worker-cancel", hashed_password="secret"))
        await session.commit()
        job = await JobService(session).enqueue_job(
            user_id=1101,
            job_type="blocking-handler",
            title="等待取消",
            idempotency_key="worker-cancel-running",
        )

    registry = JobHandlerRegistry()

    async def handler(_context):
        handler_started.set()
        await keep_running.wait()
        return JobOutcome(result={"unexpected": True})

    registry.register(
        job_type="blocking-handler",
        payload_version=1,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        handler=handler,
    )
    worker = JobWorker(
        session_factory=session_factory,
        registry=registry,
        worker_id="cancel-worker",
        lease_seconds=5,
        heartbeat_interval_seconds=0.02,
    )

    try:
        run_task = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(handler_started.wait(), timeout=2)
        async with session_factory() as session:
            await JobService(session).request_cancel(job.id, user_id=1101)
        assert await asyncio.wait_for(run_task, timeout=2) is True

        async with session_factory() as session:
            refreshed = await JobService(session).get_job(job.id)
        assert refreshed is not None
        assert refreshed.status == "cancelled"
        assert refreshed.result is None
    finally:
        keep_running.set()
        async with session_factory() as session:
            await session.execute(delete(User).where(User.id == 1101))
            await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_run_forever_records_lifecycle_and_stops_cleanly(isolated_pg):
    session_factory = isolated_pg.session_factory
    stop_event = asyncio.Event()
    worker = JobWorker(
        session_factory=session_factory,
        registry=JobHandlerRegistry(),
        worker_id="lifecycle-worker",
        lease_seconds=5,
        heartbeat_interval_seconds=0.02,
        worker_heartbeat_interval_seconds=0.02,
        poll_interval_seconds=0.02,
    )

    run_task = asyncio.create_task(worker.run_forever(stop_event))
    await asyncio.sleep(0.08)
    stop_event.set()
    await asyncio.wait_for(run_task, timeout=2)

    async with session_factory() as session:
        heartbeat = await session.get(JobWorkerHeartbeat, "lifecycle-worker")
        assert heartbeat is not None
        assert heartbeat.state == "stopped"
        assert heartbeat.stopped_at is not None
        assert heartbeat.heartbeat_at >= heartbeat.started_at
        await session.delete(heartbeat)
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_process_crash_is_reclaimed_after_lease_expiry(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        user = User(
            username=f"worker-process-crash-{uuid4().hex}",
            hashed_password="secret",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        user_id = user.id
        job = await JobService(session).enqueue_job(
            user_id=user_id,
            job_type="process-crash-test",
            title="真实进程崩溃恢复",
            idempotency_key="process-crash-recovery",
        )

    database_url = isolated_pg.engine.url.render_as_string(hide_password=False)
    process_context = multiprocessing.get_context("spawn")
    first_process = process_context.Process(
        target=_run_process_worker,
        args=(database_url, isolated_pg.schema, "process-worker-a", 60.0),
    )
    second_process = None
    try:
        first_process.start()
        running = await _wait_for_job_state(
            session_factory,
            job.id,
            status="running",
            lease_owner="process-worker-a",
        )

        first_process.terminate()
        await asyncio.to_thread(first_process.join, 10)
        assert not first_process.is_alive()
        assert first_process.exitcode != 0

        lease_expires_at = running.lease_expires_at
        assert lease_expires_at is not None
        wait_seconds = (lease_expires_at - datetime.now(timezone.utc)).total_seconds() + 0.2
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)

        second_process = process_context.Process(
            target=_run_process_worker,
            args=(database_url, isolated_pg.schema, "process-worker-b", 0.0),
        )
        second_process.start()
        await asyncio.to_thread(second_process.join, 10)
        assert not second_process.is_alive()
        assert second_process.exitcode == 0

        completed = await _wait_for_job_state(
            session_factory,
            job.id,
            status="succeeded",
            lease_owner=None,
        )
        async with session_factory() as session:
            events = await JobService(session).list_events(user_id=user_id, after_cursor=0)

        assert completed.attempt == 2
        assert completed.fencing_token == 2
        assert completed.result == {"worker_id": "process-worker-b"}
        assert [event.event_type for event in events] == [
            "job.queued",
            "job.started",
            "job.reclaimed",
            "job.succeeded",
        ]
    finally:
        for process in (first_process, second_process):
            if process is None:
                continue
            if process.is_alive():
                process.terminate()
                await asyncio.to_thread(process.join, 10)
            process.close()
        async with session_factory() as session:
            await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_worker_run_forever_propagates_lifecycle_heartbeat_failure(
    isolated_pg,
    monkeypatch,
):
    session_factory = isolated_pg.session_factory
    stop_event = asyncio.Event()

    async def fail_heartbeat_worker(self, *, worker_id, executor_generation, now=None):
        raise RuntimeError("worker heartbeat unavailable")

    monkeypatch.setattr(JobService, "heartbeat_worker", fail_heartbeat_worker)
    worker = JobWorker(
        session_factory=session_factory,
        registry=JobHandlerRegistry(),
        worker_id="failing-lifecycle-worker",
        lease_seconds=5,
        heartbeat_interval_seconds=0.02,
        worker_heartbeat_interval_seconds=0.02,
        poll_interval_seconds=0.02,
    )

    with pytest.raises(RuntimeError, match="worker heartbeat unavailable"):
        await asyncio.wait_for(worker.run_forever(stop_event), timeout=2)

    assert stop_event.is_set()
    async with session_factory() as session:
        heartbeat = await session.get(JobWorkerHeartbeat, "failing-lifecycle-worker")
        assert heartbeat is not None
        assert heartbeat.state == "stopped"
        await session.delete(heartbeat)
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_outline_handler_commits_outlines_with_job_success(
    db_session_factory,
    monkeypatch,
):
    async with db_session_factory() as session:
        session.add(User(id=1201, username="outline-worker", hashed_password="secret"))
        session.add(
            NovelProject(
                id="outline-project",
                user_id=1201,
                title="大纲项目",
                initial_prompt="测试",
            )
        )
        session.add(NovelBlueprint(project_id="outline-project", title="大纲项目"))
        await session.commit()
        job = await JobService(session).enqueue_job(
            user_id=1201,
            project_id="outline-project",
            job_type="chapter_outline",
            title="生成后续章节大纲",
            payload={
                "project_id": "outline-project",
                "start_chapter": 1,
                "num_chapters": 1,
            },
        )

    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="生成大纲"))
    llm_response = json.dumps(
        {
            "chapters": [
                {
                    "chapter_number": 1,
                    "title": "第一章",
                    "summary": "主角发现异常。",
                    "goals": "打破平静。",
                    "highlights": ["异象"],
                    "character_states": {"主角": "警觉"},
                }
            ]
        },
        ensure_ascii=False,
    )
    llm_call = AsyncMock(return_value=llm_response)
    monkeypatch.setattr(LLMService, "get_llm_response_detached", llm_call)
    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="outline-handler-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        refreshed = await JobService(session).get_job(job.id)
        outline = (
            await session.execute(
                select(ChapterOutline).where(
                    ChapterOutline.project_id == "outline-project",
                    ChapterOutline.chapter_number == 1,
                )
            )
        ).scalar_one()
        activity = (
            await session.execute(select(JobActivity).where(JobActivity.job_id == job.id))
        ).scalar_one()

    assert refreshed is not None
    assert refreshed.status == "succeeded"
    assert refreshed.result == {
        "project_id": "outline-project",
        "start_chapter": 1,
        "num_chapters": 1,
        "outline_count": 1,
    }
    assert outline.goals == "打破平静。"
    assert outline.highlights == ["异象"]
    assert activity.status == "succeeded"
    llm_call.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="session")
async def test_outline_handler_marks_unknown_llm_result_for_attention(
    db_session_factory,
    monkeypatch,
):
    async with db_session_factory() as session:
        session.add(User(id=1202, username="outline-ambiguous", hashed_password="secret"))
        session.add(
            NovelProject(
                id="ambiguous-outline-project",
                user_id=1202,
                title="异常大纲项目",
                initial_prompt="测试",
            )
        )
        session.add(NovelBlueprint(project_id="ambiguous-outline-project", title="异常大纲项目"))
        await session.commit()
        job = await JobService(session).enqueue_job(
            user_id=1202,
            project_id="ambiguous-outline-project",
            job_type="chapter_outline",
            title="生成异常大纲",
            payload={
                "project_id": "ambiguous-outline-project",
                "start_chapter": 1,
                "num_chapters": 1,
            },
        )

    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="生成大纲"))
    monkeypatch.setattr(
        LLMService,
        "get_llm_response_detached",
        AsyncMock(side_effect=RuntimeError("provider response lost")),
    )
    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="outline-ambiguous-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        refreshed = await JobService(session).get_job(job.id)
        activity = (
            await session.execute(select(JobActivity).where(JobActivity.job_id == job.id))
        ).scalar_one()

    assert refreshed is not None
    assert refreshed.status == "needs_attention"
    assert refreshed.dead_lettered_at is None
    assert activity.status == "ambiguous"
