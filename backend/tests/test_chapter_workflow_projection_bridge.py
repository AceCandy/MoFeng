# AIMETA P=章节工作流投影桥测试|R=失败重放再次等待_canonical观察_stream漂移|NR=不调用外部projection算法|E=test_*|X=internal|A=integration_test|D=pytest,postgresql|S=test|RD=../app/services/README.ai
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from test_chapter_workflow_finalize import _start_claim_with_candidate

from app.models import (
    BackgroundTask,
    Chapter,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
    ChapterWorkflowCommand,
    ChapterWorkflowRun,
    JobActivity,
)
from app.schemas.chapter_workflow import (
    ChapterWorkflowCommandEnvelope,
    ChapterWorkflowState,
)
from app.schemas.job import ChapterOutboxDispatchJobPayload, ChapterProjectionJobPayload
from app.schemas.novel import ChapterGenerationStatus
from app.services.chapter_outbox_dispatcher import ChapterOutboxDispatcher
from app.services.chapter_projection_ops import (
    ChapterProjectionOpsService,
    ChapterProjectionReplayRequest,
)
from app.services.chapter_projection_runtime import (
    CurrentProjection,
    enqueue_downstream_projections,
    maybe_enqueue_reconciler,
)
from app.services.chapter_workflow_finalize import ChapterWorkflowFinalizeService
from app.services.chapter_workflow_handler import (
    ChapterWorkflowBindingAssembler,
    ChapterWorkflowProviders,
)
from app.services.chapter_workflow_projection import ChapterWorkflowProjectionService
from app.services.job_registry import SideEffectClass
from app.services.job_service import JobService
from app.services.job_worker import JobExecutionContext


async def _finalized_projection_scope(isolated_pg, *, user_id: int, project_id: str):
    started, execution, request = await _start_claim_with_candidate(
        isolated_pg,
        user_id=user_id,
        project_id=project_id,
        content="projection bridge canonical content",
    )
    finalized = await ChapterWorkflowFinalizeService(execution).execute(request)
    async with isolated_pg.session_factory() as session:
        dispatcher = await session.get(BackgroundTask, finalized.result.dispatcher_job_id)
        assert dispatcher is not None
        await ChapterOutboxDispatcher(session).dispatch(
            command=ChapterOutboxDispatchJobPayload.model_validate(dispatcher.payload),
            user_id=user_id,
        )
        dispatcher.status = "succeeded"
        dispatcher.completed_at = dispatcher.updated_at
        await session.commit()
    return started, execution, request, finalized


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_projection_requeues_same_run_and_reuses_completed_activity(
    isolated_pg,
) -> None:
    started, _execution, request, finalized = await _finalized_projection_scope(
        isolated_pg,
        user_id=4801,
        project_id="workflow-projection-retry",
    )
    checkpoint_id = "checkpoint-projection-failed"
    async with isolated_pg.session_factory() as session:
        root = await session.get(BackgroundTask, started.root_job.id)
        run = await session.get(ChapterWorkflowRun, started.run.id)
        chapter = await session.get(Chapter, started.run.chapter_id)
        failed_run = (
            await session.execute(
                select(ChapterProjectionRun).where(
                    ChapterProjectionRun.chapter_revision_id
                    == finalized.result.chapter_revision_id,
                    ChapterProjectionRun.projection_name == "summary",
                )
            )
        ).scalar_one()
        failed_job = await session.get(BackgroundTask, failed_run.job_id)
        assert root is not None and run is not None and chapter is not None
        assert failed_job is not None
        failed_run_id = failed_run.id
        failed_job_id = failed_job.id
        root.status = "waiting"
        root.lease_owner = None
        root.lease_expires_at = None
        run.status = "projection_pending"
        run.node_key = "wait_for_projections"
        run.checkpoint_id = checkpoint_id
        run.progress = 90
        failed_run.status = "failed"
        failed_run.error_category = "projection_failed"
        failed_job.status = "failed"
        failed_job.error_category = "projection_failed"
        session.add(
            JobActivity(
                id=str(uuid4()),
                job_id=failed_job.id,
                activity_key="summary_generation",
                side_effect_class="ambiguous_external",
                status="succeeded",
                provider_request_key=str(uuid4()),
                attempt=1,
                fencing_token=1,
                request_payload={"revision": 1},
                result_payload={"response": "已生成的章节梳理"},
                started_at=datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    command_id = str(uuid4())
    async with isolated_pg.session_factory() as session:
        run = await session.get(ChapterWorkflowRun, started.run.id)
        chapter = await session.get(Chapter, started.run.chapter_id)
        assert run is not None and chapter is not None
        snapshot = await JobService(session).get_chapter_workflow_snapshot(
            run.id,
            user_id=run.user_id,
        )
        assert "retry_projection" in snapshot.allowed_commands
        command = await JobService(session).submit_chapter_workflow_command(
            run.id,
            actor_user_id=run.user_id,
            envelope=ChapterWorkflowCommandEnvelope(
                command_id=command_id,
                type="retry_projection",
                payload={},
                expected_run_revision=run.row_revision,
                expected_chapter_revision=chapter.current_revision,
                expected_checkpoint_id=checkpoint_id,
            ),
        )
        assert command.status == "pending"
        lease = await JobService(session).claim_next(
            worker_id="workflow-projection-retry",
            lease_seconds=60,
        )
    assert lease is not None and lease.job_id == started.root_job.id
    retry_execution = JobExecutionContext(
        lease=lease,
        side_effect_class=_execution.side_effect_class,
        session_factory=isolated_pg.session_factory,
    )
    state = ChapterWorkflowState(
        run_id=started.run.id,
        node_key="wait_for_projections",
        context_hash=started.run.context_hash,
        candidate_version_ids=request.candidate_version_ids,
        selected_version_id=request.selected_version_id,
        target_chapter_revision=finalized.result.target_chapter_revision,
    )
    binding = ChapterWorkflowBindingAssembler(
        retry_execution,
        cast(ChapterWorkflowProviders, object()),
    )
    update = await binding.apply_projection_resume(state, {"command_id": command_id})
    replay = await ChapterWorkflowProjectionService(retry_execution).retry_failed(
        state,
        command_id=command_id,
    )

    async with isolated_pg.session_factory() as session:
        replay_runs = list(
            (
                await session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.chapter_revision_id
                        == finalized.result.chapter_revision_id,
                        ChapterProjectionRun.projection_name == "summary",
                    )
                )
            ).scalars()
        )
        replay_jobs = list(
            (
                await session.execute(
                    select(BackgroundTask).where(BackgroundTask.id.in_(replay.job_ids.values()))
                )
            ).scalars()
        )
        activity_count = await session.scalar(
            select(func.count(JobActivity.id)).where(
                JobActivity.job_id == started.root_job.id,
                JobActivity.activity_key == f"wf:retry_projection:{command_id}",
            )
        )
        command = await session.get(ChapterWorkflowCommand, command_id)
        preserved_activity = await session.scalar(
            select(JobActivity).where(
                JobActivity.job_id == failed_job_id,
                JobActivity.activity_key == "summary_generation",
            )
        )

    assert update == {"last_applied_command_id": command_id}
    assert set(replay.projection_run_ids) == {"summary"}
    assert len(replay_runs) == 1
    assert len(replay_jobs) == 1
    assert replay_runs[0].id == failed_run_id
    assert replay_runs[0].status == "queued"
    assert replay_jobs[0].id == failed_job_id
    assert replay_jobs[0].status == "queued"
    assert all(job.stream_id == started.run.id for job in replay_jobs)
    assert all(job.payload["workflow_stream_id"] == started.run.id for job in replay_jobs)
    assert preserved_activity is not None
    assert preserved_activity.status == "succeeded"
    assert preserved_activity.result_payload == {"response": "已生成的章节梳理"}
    assert activity_count == 1
    assert command is not None and command.status == "pending"


@pytest.mark.asyncio(loop_scope="session")
async def test_ambiguous_projection_activity_can_retry_same_remote_leaf(isolated_pg) -> None:
    started, _execution, _request, finalized = await _finalized_projection_scope(
        isolated_pg,
        user_id=4804,
        project_id="workflow-projection-ambiguous-retry",
    )
    checkpoint_id = "checkpoint-projection-ambiguous"
    request_payload = {
        "project_id": started.run.project_id,
        "chapter_id": started.run.chapter_id,
        "revision": finalized.result.target_chapter_revision,
        "source_hash": finalized.result.source_hash,
    }
    async with isolated_pg.session_factory() as session:
        root = await session.get(BackgroundTask, started.root_job.id)
        run = await session.get(ChapterWorkflowRun, started.run.id)
        chapter = await session.get(Chapter, started.run.chapter_id)
        projection_run = await session.scalar(
            select(ChapterProjectionRun).where(
                ChapterProjectionRun.chapter_revision_id == finalized.result.chapter_revision_id,
                ChapterProjectionRun.projection_name == "summary",
            )
        )
        assert root is not None and run is not None and chapter is not None
        assert projection_run is not None and projection_run.job_id is not None
        projection_job = await session.get(BackgroundTask, projection_run.job_id)
        assert projection_job is not None
        root.status = "waiting"
        root.lease_owner = None
        root.lease_expires_at = None
        run.status = "projection_pending"
        run.node_key = "wait_for_projections"
        run.checkpoint_id = checkpoint_id
        run.progress = 90
        projection_run.status = "needs_attention"
        projection_job.status = "needs_attention"
        projection_job.error_category = "ambiguous_external_result"
        projection_job.payload = {
            **projection_job.payload,
            "revision": finalized.result.target_chapter_revision + 1,
        }
        original = JobActivity(
            id=str(uuid4()),
            job_id=projection_job.id,
            activity_key="summary_generation",
            side_effect_class="ambiguous_external",
            status="ambiguous",
            provider_request_key=str(uuid4()),
            attempt=1,
            fencing_token=1,
            request_payload=request_payload,
            started_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(original)
        await session.commit()
        projection_job_id = projection_job.id

    invalid_command_id = str(uuid4())
    async with isolated_pg.session_factory() as session:
        snapshot = await JobService(session).get_chapter_workflow_snapshot(
            started.run.id,
            user_id=started.run.user_id,
        )
        with pytest.raises(ValueError, match="ambiguous projection activity 身份无效"):
            await JobService(session).submit_chapter_workflow_command(
                started.run.id,
                actor_user_id=started.run.user_id,
                envelope=ChapterWorkflowCommandEnvelope(
                    command_id=invalid_command_id,
                    type="retry_external",
                    payload={
                        "activity_key": "summary_generation",
                        "acknowledge_possible_duplicate": True,
                    },
                    expected_run_revision=snapshot.row_revision,
                    expected_chapter_revision=snapshot.current_chapter_revision,
                    expected_checkpoint_id=snapshot.checkpoint_id,
                ),
            )
        await session.rollback()

    async with isolated_pg.session_factory() as session:
        projection_job = await session.get(BackgroundTask, projection_job_id)
        assert projection_job is not None
        projection_job.payload = {
            **projection_job.payload,
            "revision": finalized.result.target_chapter_revision,
        }
        await session.commit()

    command_id = str(uuid4())
    async with isolated_pg.session_factory() as session:
        snapshot = await JobService(session).get_chapter_workflow_snapshot(
            started.run.id,
            user_id=started.run.user_id,
        )
        assert "retry_external" in snapshot.allowed_commands
        assert snapshot.retry_activity_key == "summary_generation"
        command = await JobService(session).submit_chapter_workflow_command(
            started.run.id,
            actor_user_id=started.run.user_id,
            envelope=ChapterWorkflowCommandEnvelope(
                command_id=command_id,
                type="retry_external",
                payload={
                    "activity_key": "summary_generation",
                    "acknowledge_possible_duplicate": True,
                },
                expected_run_revision=snapshot.row_revision,
                expected_chapter_revision=snapshot.current_chapter_revision,
                expected_checkpoint_id=snapshot.checkpoint_id,
            ),
        )
        assert command.status == "applied"
        projection_job = await session.get(BackgroundTask, projection_job_id)
        projection_run = await session.scalar(
            select(ChapterProjectionRun).where(ChapterProjectionRun.job_id == projection_job_id)
        )
        manual = await session.scalar(
            select(JobActivity).where(
                JobActivity.job_id == projection_job_id,
                JobActivity.activity_key == f"manual_retry:{command_id}",
            )
        )
        assert projection_job is not None and projection_job.status == "queued"
        assert projection_run is not None and projection_run.status == "queued"
        assert manual is not None and manual.status == "manual_retry_pending"
        replayed = await JobService(session).apply_ambiguous_activity_command(command_id)
        assert replayed.status == "applied"
        lease = await JobService(session).claim_next(
            worker_id="workflow-projection-ambiguous-retry",
            lease_seconds=60,
        )

    assert lease is not None and lease.job_id == projection_job_id
    execution = JobExecutionContext(
        lease=lease,
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        session_factory=isolated_pg.session_factory,
    )
    resumed = await execution.begin_activity(
        "summary_generation",
        request_payload=request_payload,
    )
    assert resumed.should_execute is True
    assert resumed.activity_key == f"manual_retry:{command_id}"


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_retry_lock_queue_has_no_reverse_root_edge(isolated_pg) -> None:
    started, _execution, request, finalized = await _finalized_projection_scope(
        isolated_pg,
        user_id=4803,
        project_id="workflow-projection-lock-order",
    )
    checkpoint_id = "checkpoint-projection-lock-order"
    async with isolated_pg.session_factory() as session:
        root = await session.get(BackgroundTask, started.root_job.id)
        run = await session.get(ChapterWorkflowRun, started.run.id)
        chapter = await session.get(Chapter, started.run.chapter_id)
        failed_run = (
            await session.execute(
                select(ChapterProjectionRun).where(
                    ChapterProjectionRun.chapter_revision_id
                    == finalized.result.chapter_revision_id,
                    ChapterProjectionRun.projection_name == "summary",
                )
            )
        ).scalar_one()
        failed_job = await session.get(BackgroundTask, failed_run.job_id)
        assert root is not None and run is not None and chapter is not None
        assert failed_job is not None
        root.status = "waiting"
        root.lease_owner = None
        root.lease_expires_at = None
        run.status = "projection_pending"
        run.node_key = "wait_for_projections"
        run.checkpoint_id = checkpoint_id
        run.progress = 90
        failed_run.status = "failed"
        failed_run.error_category = "projection_failed"
        failed_job.status = "failed"
        failed_job.error_category = "projection_failed"
        await session.commit()

    command_id = str(uuid4())
    async with isolated_pg.session_factory() as session:
        run = await session.get(ChapterWorkflowRun, started.run.id)
        chapter = await session.get(Chapter, started.run.chapter_id)
        assert run is not None and chapter is not None
        await JobService(session).submit_chapter_workflow_command(
            run.id,
            actor_user_id=run.user_id,
            envelope=ChapterWorkflowCommandEnvelope(
                command_id=command_id,
                type="retry_projection",
                payload={},
                expected_run_revision=run.row_revision,
                expected_chapter_revision=chapter.current_revision,
                expected_checkpoint_id=checkpoint_id,
            ),
        )
        lease = await JobService(session).claim_next(
            worker_id="workflow-projection-lock-order",
            lease_seconds=60,
        )
    assert lease is not None and lease.job_id == started.root_job.id

    state = ChapterWorkflowState(
        run_id=started.run.id,
        node_key="wait_for_projections",
        context_hash=started.run.context_hash,
        candidate_version_ids=request.candidate_version_ids,
        selected_version_id=request.selected_version_id,
        target_chapter_revision=finalized.result.target_chapter_revision,
    )
    retry_pids: list[int] = []
    retry_session_opened = asyncio.Event()

    @asynccontextmanager
    async def recording_session():
        async with isolated_pg.session_factory() as session:
            pid = await session.scalar(select(func.pg_backend_pid()))
            assert pid is not None
            retry_pids.append(pid)
            retry_session_opened.set()
            yield session

    retry_execution = JobExecutionContext(
        lease=lease,
        side_effect_class=_execution.side_effect_class,
        session_factory=recording_session,
    )
    scope_request = ChapterProjectionReplayRequest(
        project_id=started.run.project_id,
        chapter_id=started.run.chapter_id,
        revision=finalized.result.target_chapter_revision,
        projection_name="summary",
        idempotency_key=f"lock-order:{command_id}",
        reason="lock order test",
        outbox_event_id=finalized.result.outbox_event_id,
    )

    async def wait_until_blocked(waiter_pid: int, blocker_pid: int) -> None:
        async with isolated_pg.session_factory() as observer:
            for _ in range(100):
                blocking_pids = await observer.scalar(select(func.pg_blocking_pids(waiter_pid)))
                if blocker_pid in (blocking_pids or []):
                    return
                await asyncio.sleep(0.01)
        raise AssertionError(f"backend {waiter_pid} 未按预期等待 {blocker_pid}")

    async def lock_root_after_retry(pid_ready: asyncio.Future[int]) -> None:
        async with isolated_pg.session_factory() as follower:
            follower_pid = await follower.scalar(select(func.pg_backend_pid()))
            assert follower_pid is not None
            pid_ready.set_result(follower_pid)
            await follower.execute(
                select(BackgroundTask)
                .where(BackgroundTask.id == started.root_job.id)
                .with_for_update()
            )
            await follower.commit()

    async def lock_run_after_retry(pid_ready: asyncio.Future[int]) -> None:
        async with isolated_pg.session_factory() as follower:
            follower_pid = await follower.scalar(select(func.pg_backend_pid()))
            assert follower_pid is not None
            pid_ready.set_result(follower_pid)
            await follower.execute(
                select(ChapterWorkflowRun)
                .where(ChapterWorkflowRun.id == started.run.id)
                .with_for_update()
            )
            await follower.commit()

    retry_task: asyncio.Task | None = None
    root_follower_task: asyncio.Task | None = None
    run_follower_task: asyncio.Task | None = None
    async with (
        isolated_pg.session_factory() as projection_blocker,
        isolated_pg.session_factory() as run_blocker,
    ):
        projection_blocker_pid = await projection_blocker.scalar(select(func.pg_backend_pid()))
        run_blocker_pid = await run_blocker.scalar(select(func.pg_backend_pid()))
        assert projection_blocker_pid is not None and run_blocker_pid is not None
        await ChapterProjectionOpsService(projection_blocker)._load_scope(
            scope_request, for_update=True
        )
        await run_blocker.execute(
            select(ChapterWorkflowRun)
            .where(ChapterWorkflowRun.id == started.run.id)
            .with_for_update()
        )
        try:
            retry_task = asyncio.create_task(
                ChapterWorkflowProjectionService(retry_execution).retry_failed(
                    state,
                    command_id=command_id,
                )
            )
            await asyncio.wait_for(retry_session_opened.wait(), timeout=3)
            retry_pid = retry_pids[0]
            await asyncio.wait_for(
                wait_until_blocked(retry_pid, run_blocker_pid),
                timeout=3,
            )

            root_follower_pid_ready = asyncio.Future[int]()
            root_follower_task = asyncio.create_task(lock_root_after_retry(root_follower_pid_ready))
            root_follower_pid = await asyncio.wait_for(root_follower_pid_ready, timeout=3)
            await asyncio.wait_for(
                wait_until_blocked(root_follower_pid, retry_pid),
                timeout=3,
            )

            await run_blocker.commit()
            await asyncio.wait_for(
                wait_until_blocked(retry_pid, projection_blocker_pid),
                timeout=3,
            )

            run_follower_pid_ready = asyncio.Future[int]()
            run_follower_task = asyncio.create_task(lock_run_after_retry(run_follower_pid_ready))
            run_follower_pid = await asyncio.wait_for(run_follower_pid_ready, timeout=3)
            await asyncio.wait_for(
                wait_until_blocked(run_follower_pid, retry_pid),
                timeout=3,
            )

            await projection_blocker.commit()
            replay = await asyncio.wait_for(retry_task, timeout=5)
            await asyncio.wait_for(root_follower_task, timeout=5)
            await asyncio.wait_for(run_follower_task, timeout=5)
        finally:
            await run_blocker.rollback()
            await projection_blocker.rollback()
            for task in (retry_task, root_follower_task, run_follower_task):
                if task is not None and not task.done():
                    task.cancel()
            await asyncio.gather(
                *(
                    task
                    for task in (retry_task, root_follower_task, run_follower_task)
                    if task is not None
                ),
                return_exceptions=True,
            )

    async with isolated_pg.session_factory() as session:
        replay_runs = list(
            (
                await session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.chapter_revision_id
                        == finalized.result.chapter_revision_id,
                        ChapterProjectionRun.projection_name == "summary",
                    )
                )
            ).scalars()
        )
        replay_jobs = list(
            (
                await session.execute(
                    select(BackgroundTask).where(BackgroundTask.id.in_(replay.job_ids.values()))
                )
            ).scalars()
        )

    assert set(replay.projection_run_ids) == {"summary"}
    assert len(replay_runs) == 1
    assert len(replay_jobs) == 1
    assert replay_runs[0].status == "queued"
    assert replay_jobs[0].status == "queued"
    assert replay_jobs[0].stream_id == started.run.id
    assert replay_jobs[0].payload["workflow_stream_id"] == started.run.id


@pytest.mark.asyncio(loop_scope="session")
async def test_observer_accepts_only_successful_canonical_projection_lineage(
    isolated_pg,
) -> None:
    started, execution, request, finalized = await _finalized_projection_scope(
        isolated_pg,
        user_id=4802,
        project_id="workflow-projection-observe",
    )
    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
        run = await session.get(ChapterWorkflowRun, started.run.id)
        revision = await session.get(ChapterRevision, finalized.result.chapter_revision_id)
        assert chapter is not None and run is not None and revision is not None
        run.status = "running"
        run.node_key = "wait_for_projections"
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
                    ChapterProjectionRollout.chapter_id == chapter.id
                )
            )
        ).scalar_one()
        assert summary_job is not None
        summary_run.status = "succeeded"
        summary_run.is_active = True
        summary_job.status = "succeeded"
        summary_payload = ChapterProjectionJobPayload.model_validate(summary_job.payload)
        current = CurrentProjection(chapter, revision, summary_run, rollout, None)
        downstream = await enqueue_downstream_projections(
            session,
            payload=summary_payload,
            current=current,
            user_id=started.run.user_id,
        )
        for projection_run in downstream:
            if not projection_run.required:
                continue
            projection_run.status = "succeeded"
            projection_run.is_active = True
            projection_job = await session.get(BackgroundTask, projection_run.job_id)
            assert projection_job is not None
            projection_job.status = "succeeded"
        reconcile_run = await maybe_enqueue_reconciler(
            session,
            payload=summary_payload,
            current=current,
            user_id=started.run.user_id,
        )
        assert reconcile_run is not None and reconcile_run.job_id is not None
        reconcile_job = await session.get(BackgroundTask, reconcile_run.job_id)
        assert reconcile_job is not None
        reconcile_run.status = "succeeded"
        reconcile_run.is_active = True
        reconcile_job.status = "succeeded"
        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        revision.lifecycle = "successful"
        await session.commit()

    state = ChapterWorkflowState(
        run_id=started.run.id,
        node_key="reconcile_projections",
        context_hash=started.run.context_hash,
        candidate_version_ids=request.candidate_version_ids,
        selected_version_id=request.selected_version_id,
        target_chapter_revision=finalized.result.target_chapter_revision,
    )
    service = ChapterWorkflowProjectionService(execution)
    await service.observe_completed(state)

    async with isolated_pg.session_factory() as session:
        run = await session.get(ChapterWorkflowRun, started.run.id)
        assert run is not None
        run.status = "needs_attention"
        await session.commit()

    with pytest.raises(ValueError, match="observation identity 不一致"):
        await service.observe_completed(state)

    async with isolated_pg.session_factory() as session:
        run = await session.get(ChapterWorkflowRun, started.run.id)
        drifted_job = (
            await session.execute(
                select(BackgroundTask).where(BackgroundTask.id == reconcile_run.job_id)
            )
        ).scalar_one()
        assert run is not None
        run.status = "running"
        drifted_job.stream_id = str(uuid4())
        await session.commit()

    with pytest.raises(ValueError, match="stream 已漂移"):
        await service.observe_completed(state)

    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
    assert chapter is not None
    assert chapter.status == ChapterGenerationStatus.SUCCESSFUL.value
