# AIMETA P=章节工作流模糊外部调用命令测试|R=审计重试_取消_幂等_禁止自动重放|NR=不覆盖HTTP接收或checkpoint握手|E=test_*|X=internal|A=integration_test|D=pytest|S=test|RD=./README.ai
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.models import (
    BackgroundTask,
    Chapter,
    ChapterWorkflowCommand,
    ChapterWorkflowRun,
    JobActivity,
    JobEvent,
    NovelProject,
)
from app.models.user import User
from app.repositories.chapter_workflow_repository import ChapterWorkflowRepository
from app.schemas.chapter_workflow import ChapterWorkflowCommandEnvelope
from app.services.chapter_workflow_transition import ChapterWorkflowTransition
from app.services.job_registry import SideEffectClass
from app.services.job_service import (
    ChapterWorkflowCommandRejectedError,
    JobService,
)


async def _create_ambiguous_workflow(
    session,
    *,
    user_id: int,
    project_id: str,
    run_id: str,
) -> tuple[BackgroundTask, ChapterWorkflowRun, JobActivity]:
    session.add(User(id=user_id, username=f"command-{user_id}", hashed_password="secret"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="Workflow command",
            initial_prompt="test",
        )
    )
    chapter = Chapter(project_id=project_id, chapter_number=1)
    session.add(chapter)
    await session.commit()

    service = JobService(session)
    job = await service.enqueue_job(
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
        base_revision=chapter.current_revision,
        root_job_id=job.id,
        workflow_version=1,
        state_schema_version=1,
        context_schema_version=1,
        context_snapshot={},
        context_hash="a" * 64,
        runtime_input_hash="b" * 64,
        status="queued",
        node_key="generate_candidates",
        checkpoint_id="checkpoint-before-provider",
    )
    session.add(run)
    await session.commit()

    started_at = datetime.now(timezone.utc)
    lease = await service.claim_next(
        worker_id=f"worker-{user_id}",
        lease_seconds=30,
        now=started_at,
    )
    assert lease is not None
    execution = await service.begin_activity(
        lease,
        activity_key="wf:generate_candidates:input-hash",
        side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
        request_payload={
            "schema_version": 1,
            "workflow_version": 1,
            "state_schema_version": 1,
            "run_id": run_id,
            "node_key": "generate_candidates",
            "stage": "candidate",
            "input_hash": "c" * 64,
        },
        now=started_at,
    )
    await service.mark_activity_ambiguous(
        lease,
        activity_key="wf:generate_candidates:input-hash",
        provider_request_key=execution.provider_request_key,
        public_message="provider 结果未知",
        now=started_at + timedelta(seconds=1),
    )
    activity = (
        await session.execute(
            select(JobActivity).where(
                JobActivity.job_id == job.id,
                JobActivity.activity_key == "wf:generate_candidates:input-hash",
            )
        )
    ).scalar_one()
    return job, run, activity


def _command(
    *,
    command_id: str,
    run: ChapterWorkflowRun,
    actor_user_id: int,
    command_type: str,
    payload: dict,
) -> ChapterWorkflowCommand:
    return ChapterWorkflowCommand(
        id=command_id,
        run_id=run.id,
        type=command_type,
        payload_version=1,
        payload=payload,
        actor_user_id=actor_user_id,
        expected_run_revision=run.row_revision,
        expected_chapter_revision=run.base_revision,
        expected_checkpoint_id=run.checkpoint_id,
        status="pending",
    )


def _activity_snapshot(activity: JobActivity) -> tuple[object, ...]:
    return (
        activity.id,
        activity.activity_key,
        activity.side_effect_class,
        activity.status,
        activity.provider_request_key,
        activity.attempt,
        activity.fencing_token,
        activity.request_payload,
        activity.result_payload,
        activity.error_category,
        activity.started_at,
        activity.completed_at,
        activity.updated_at,
    )


async def _create_waiting_workflow(
    session,
    *,
    user_id: int,
    project_id: str,
) -> tuple[BackgroundTask, ChapterWorkflowRun, Chapter]:
    run_id = str(uuid4())
    session.add(User(id=user_id, username=f"waiting-command-{user_id}", hashed_password="secret"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="Waiting workflow command",
            initial_prompt="test",
        )
    )
    chapter = Chapter(project_id=project_id, chapter_number=1)
    session.add(chapter)
    await session.commit()

    service = JobService(session)
    job = await service.enqueue_job(
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
        base_revision=chapter.current_revision,
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

    lease = await service.claim_next(
        worker_id=f"waiting-worker-{user_id}",
        lease_seconds=30,
        now=datetime.now(timezone.utc),
    )
    assert lease is not None
    job = await service.wait_for_resume(
        lease,
        workflow_transition=ChapterWorkflowTransition(
            status="waiting_for_selection",
            node_key="waiting_for_selection",
            checkpoint_id="checkpoint-selection",
            progress=60,
        ),
    )
    await session.refresh(run)
    await session.refresh(chapter)
    return job, run, chapter


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_select_command_is_idempotent_and_requeues_waiting_root(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, run, chapter = await _create_waiting_workflow(
            session,
            user_id=1710,
            project_id="command-submit-project",
        )
        envelope = ChapterWorkflowCommandEnvelope(
            command_id=str(uuid4()),
            type="select",
            payload={"selected_version_id": 101},
            expected_run_revision=run.row_revision,
            expected_chapter_revision=chapter.current_revision,
            expected_checkpoint_id=run.checkpoint_id,
        )
        job_id = job.id
        run_id = run.id
        expected_run_revision = run.row_revision

    async with session_factory() as first_session, session_factory() as replay_session:
        first, replay = await asyncio.gather(
            JobService(first_session).submit_chapter_workflow_command(
                run_id,
                actor_user_id=1710,
                envelope=envelope,
            ),
            JobService(replay_session).submit_chapter_workflow_command(
                run_id,
                actor_user_id=1710,
                envelope=envelope,
            ),
        )
        assert first.id == replay.id == envelope.command_id
        assert first.status == replay.status == "pending"

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job_id)
        persisted_run = await session.get(ChapterWorkflowRun, run_id)
        commands = list((await session.execute(select(ChapterWorkflowCommand))).scalars())
        events = list(
            (
                await session.execute(
                    select(JobEvent).where(JobEvent.job_id == job_id).order_by(JobEvent.sequence)
                )
            ).scalars()
        )

    assert persisted_job is not None and persisted_job.status == "queued"
    assert persisted_job.lease_owner is None
    assert persisted_job.lease_expires_at is None
    assert persisted_job.heartbeat_at is None
    assert persisted_run is not None and persisted_run.status == "queued"
    assert persisted_run.node_key == "waiting_for_selection"
    assert persisted_run.row_revision == expected_run_revision + 1
    assert len(commands) == 1
    accepted = [event for event in events if event.event_type == "workflow.command.accepted"]
    assert len(accepted) == 1
    assert accepted[0].payload["workflow"]["command"] == {
        "id": envelope.command_id,
        "type": "select",
        "status": "pending",
    }
    assert [event.event_type for event in events][-2:] == [
        "workflow.phase_changed",
        "workflow.command.accepted",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_distinct_commands_accept_only_one_expected_revision(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        _, run, chapter = await _create_waiting_workflow(
            session,
            user_id=1712,
            project_id="command-concurrent-stale-project",
        )
        common = {
            "type": "select",
            "payload": {"selected_version_id": 101},
            "expected_run_revision": run.row_revision,
            "expected_chapter_revision": chapter.current_revision,
            "expected_checkpoint_id": run.checkpoint_id,
        }
        first_envelope = ChapterWorkflowCommandEnvelope(
            command_id=str(uuid4()),
            **common,
        )
        second_envelope = ChapterWorkflowCommandEnvelope(
            command_id=str(uuid4()),
            **common,
        )
        run_id = run.id
        job_id = run.root_job_id

    async def submit(envelope: ChapterWorkflowCommandEnvelope) -> str:
        async with session_factory() as session:
            try:
                command = await JobService(session).submit_chapter_workflow_command(
                    run_id,
                    actor_user_id=1712,
                    envelope=envelope,
                )
            except ChapterWorkflowCommandRejectedError as error:
                return error.reason_code
            return command.status

    results = await asyncio.gather(submit(first_envelope), submit(second_envelope))
    assert sorted(results) == ["pending", "stale_run_revision"]

    async with session_factory() as session:
        commands = list(
            (
                await session.execute(
                    select(ChapterWorkflowCommand).where(ChapterWorkflowCommand.run_id == run_id)
                )
            ).scalars()
        )
        command_events = list(
            (
                await session.execute(
                    select(JobEvent).where(
                        JobEvent.job_id == job_id,
                        JobEvent.event_type.in_(
                            {
                                "workflow.command.accepted",
                                "workflow.command.rejected",
                            }
                        ),
                    )
                )
            ).scalars()
        )

    assert sorted(command.status for command in commands) == ["pending", "rejected"]
    assert sorted(event.event_type for event in command_events) == [
        "workflow.command.accepted",
        "workflow.command.rejected",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_submit_stale_command_persists_one_rejection_without_requeue(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, run, chapter = await _create_waiting_workflow(
            session,
            user_id=1711,
            project_id="command-stale-project",
        )
        envelope = ChapterWorkflowCommandEnvelope(
            command_id=str(uuid4()),
            type="select",
            payload={"selected_version_id": 101},
            expected_run_revision=run.row_revision,
            expected_chapter_revision=chapter.current_revision,
            expected_checkpoint_id="stale-checkpoint",
        )
        job_id = job.id
        run_id = run.id

        for _ in range(2):
            with pytest.raises(ChapterWorkflowCommandRejectedError) as error:
                await JobService(session).submit_chapter_workflow_command(
                    run_id,
                    actor_user_id=1711,
                    envelope=envelope,
                )
            assert error.value.reason_code == "stale_checkpoint"

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job_id)
        command = await session.get(ChapterWorkflowCommand, envelope.command_id)
        rejected_events = list(
            (
                await session.execute(
                    select(JobEvent).where(
                        JobEvent.job_id == job_id,
                        JobEvent.event_type == "workflow.command.rejected",
                    )
                )
            ).scalars()
        )

    assert persisted_job is not None and persisted_job.status == "waiting"
    assert command is not None and command.status == "rejected"
    assert command.rejection_code == "stale_checkpoint"
    assert len(rejected_events) == 1
    assert rejected_events[0].payload["workflow"]["command"]["rejection_code"] == (
        "stale_checkpoint"
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_external_rejects_stale_chapter_revision_without_mutating_run(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, run, original = await _create_ambiguous_workflow(
            session,
            user_id=1719,
            project_id="command-stale-chapter-project",
            run_id="command-stale-chapter-run",
        )
        expected_run_revision = run.row_revision
        expected_chapter_revision = run.base_revision
        expected_checkpoint_id = run.checkpoint_id
        job_id = job.id
        run_id = run.id
        chapter_id = run.chapter_id
        activity_id = original.id
        activity_key = original.activity_key

    async with session_factory() as session:
        chapter = await session.get(Chapter, chapter_id)
        assert chapter is not None
        chapter.current_revision += 1
        await session.commit()

    envelope = ChapterWorkflowCommandEnvelope(
        command_id=str(uuid4()),
        type="retry_external",
        payload={
            "activity_key": activity_key,
            "acknowledge_possible_duplicate": True,
        },
        expected_run_revision=expected_run_revision,
        expected_chapter_revision=expected_chapter_revision,
        expected_checkpoint_id=expected_checkpoint_id,
    )
    async with session_factory() as session:
        with pytest.raises(ChapterWorkflowCommandRejectedError) as error:
            await JobService(session).submit_chapter_workflow_command(
                run_id,
                actor_user_id=1719,
                envelope=envelope,
            )
        assert error.value.reason_code == "stale_chapter_revision"

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job_id)
        persisted_run = await session.get(ChapterWorkflowRun, run_id)
        persisted_activity = await session.get(JobActivity, activity_id)
        persisted_command = await session.get(ChapterWorkflowCommand, envelope.command_id)
        activity_count = await session.scalar(
            select(func.count()).select_from(JobActivity).where(JobActivity.job_id == job_id)
        )

    assert persisted_job is not None and persisted_job.status == "needs_attention"
    assert persisted_run is not None and persisted_run.row_revision == expected_run_revision
    assert persisted_run.status == "needs_attention"
    assert persisted_activity is not None and persisted_activity.status == "ambiguous"
    assert persisted_command is not None and persisted_command.status == "rejected"
    assert persisted_command.rejection_code == "stale_chapter_revision"
    assert activity_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_external_requires_ack_and_uses_persisted_actor(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        _, run, original = await _create_ambiguous_workflow(
            session,
            user_id=1701,
            project_id="command-reject-project",
            run_id="command-reject-run",
        )
        session.add(User(id=1702, username="wrong-command-actor", hashed_password="secret"))
        await session.commit()
        missing_ack = _command(
            command_id="command-missing-ack",
            run=run,
            actor_user_id=1701,
            command_type="retry_external",
            payload={"activity_key": original.activity_key},
        )
        wrong_actor = _command(
            command_id="command-wrong-actor",
            run=run,
            actor_user_id=1702,
            command_type="retry_external",
            payload={
                "activity_key": original.activity_key,
                "acknowledge_possible_duplicate": True,
            },
        )
        payload_actor = _command(
            command_id="command-payload-actor",
            run=run,
            actor_user_id=1701,
            command_type="retry_external",
            payload={
                "activity_key": original.activity_key,
                "acknowledge_possible_duplicate": True,
                "actor_user_id": 1701,
            },
        )
        session.add_all([missing_ack, wrong_actor, payload_actor])
        await session.commit()
        original_before = _activity_snapshot(original)

        with pytest.raises(ChapterWorkflowCommandRejectedError) as missing_ack_error:
            await JobService(session).apply_ambiguous_activity_command(missing_ack.id)
        assert missing_ack_error.value.reason_code == "possible_duplicate_ack_required"

        with pytest.raises(ChapterWorkflowCommandRejectedError) as actor_error:
            await JobService(session).apply_ambiguous_activity_command(wrong_actor.id)
        assert actor_error.value.reason_code == "actor_mismatch"

        with pytest.raises(ChapterWorkflowCommandRejectedError) as payload_actor_error:
            await JobService(session).apply_ambiguous_activity_command(payload_actor.id)
        assert payload_actor_error.value.reason_code == "invalid_command_payload"

    async with session_factory() as session:
        rejected = [
            await session.get(ChapterWorkflowCommand, "command-missing-ack"),
            await session.get(ChapterWorkflowCommand, "command-wrong-actor"),
            await session.get(ChapterWorkflowCommand, "command-payload-actor"),
        ]
        persisted_original = await session.get(JobActivity, original.id)
        activity_count = await session.scalar(select(func.count()).select_from(JobActivity))

    assert [command.status for command in rejected] == ["rejected", "rejected", "rejected"]
    assert [command.rejection_code for command in rejected] == [
        "possible_duplicate_ack_required",
        "actor_mismatch",
        "invalid_command_payload",
    ]
    assert persisted_original is not None
    assert _activity_snapshot(persisted_original) == original_before
    assert activity_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_external_rejects_noncanonical_provider_request_payload(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, run, original = await _create_ambiguous_workflow(
            session,
            user_id=1713,
            project_id="command-private-payload-project",
            run_id="command-private-payload-run",
        )
        original.request_payload = {
            **original.request_payload,
            "prompt": "不应复制的私有正文",
        }
        command = _command(
            command_id="command-private-payload-retry",
            run=run,
            actor_user_id=1713,
            command_type="retry_external",
            payload={
                "activity_key": original.activity_key,
                "acknowledge_possible_duplicate": True,
            },
        )
        session.add(command)
        await session.commit()

        with pytest.raises(ChapterWorkflowCommandRejectedError) as error:
            await JobService(session).apply_ambiguous_activity_command(command.id)
        assert error.value.reason_code == "invalid_ambiguous_activity_request"

    async with session_factory() as session:
        persisted = await session.get(ChapterWorkflowCommand, command.id)
        activity_count = await session.scalar(
            select(func.count()).select_from(JobActivity).where(JobActivity.job_id == job.id)
        )
        rejected_events = await session.scalar(
            select(func.count())
            .select_from(JobEvent)
            .where(
                JobEvent.job_id == job.id,
                JobEvent.event_type == "workflow.command.rejected",
            )
        )

    assert persisted is not None and persisted.status == "rejected"
    assert activity_count == 1
    assert rejected_events == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_external_derives_one_manual_intent_and_replay_is_idempotent(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, run, original = await _create_ambiguous_workflow(
            session,
            user_id=1703,
            project_id="command-retry-project",
            run_id="command-retry-run",
        )
        command = _command(
            command_id="command-retry-external",
            run=run,
            actor_user_id=1703,
            command_type="retry_external",
            payload={
                "activity_key": original.activity_key,
                "acknowledge_possible_duplicate": True,
            },
        )
        session.add(command)
        await session.commit()
        original_before = _activity_snapshot(original)
        command_id = command.id

    async with session_factory() as session_a, session_factory() as session_b:
        await session_a.get(BackgroundTask, job.id)
        await session_b.get(BackgroundTask, job.id)
        first, concurrent = await asyncio.gather(
            JobService(session_a).apply_ambiguous_activity_command(command_id),
            JobService(session_b).apply_ambiguous_activity_command(command_id),
        )
        first_result = dict(first.result_payload or {})
        concurrent_result = dict(concurrent.result_payload or {})
    assert concurrent_result == first_result

    async with session_factory() as session:
        replayed = await JobService(session).apply_ambiguous_activity_command(command_id)
        persisted_job = await session.get(BackgroundTask, job.id)
        persisted_run = await session.get(ChapterWorkflowRun, run.id)
        persisted_original = await session.get(JobActivity, original.id)
        activities = list(
            (
                await session.execute(
                    select(JobActivity)
                    .where(JobActivity.job_id == job.id)
                    .order_by(JobActivity.activity_key)
                )
            ).scalars()
        )
        events = list(
            (
                await session.execute(
                    select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.sequence)
                )
            ).scalars()
        )

    assert replayed.status == "applied"
    assert replayed.result_payload == first_result
    assert persisted_job is not None and persisted_job.status == "queued"
    assert persisted_job.lease_owner is None
    assert persisted_run is not None and persisted_run.status == "queued"
    assert persisted_run.is_active is True
    assert persisted_original is not None
    assert _activity_snapshot(persisted_original) == original_before
    assert len(activities) == 2
    manual_intent = next(activity for activity in activities if activity.id != original.id)
    assert manual_intent.activity_key == first_result["activity_key"]
    assert manual_intent.provider_request_key == first_result["provider_request_key"]
    assert manual_intent.status == "manual_retry_pending"
    assert manual_intent.side_effect_class == "ambiguous_external"
    assert manual_intent.request_payload["manual_retry_command_id"] == command_id
    assert manual_intent.request_payload["logical_step_key"] == original.activity_key
    assert manual_intent.request_payload["replaces_activity"]["id"] == original.id
    assert [event.event_type for event in events][-2:] == [
        "workflow.phase_changed",
        "workflow.command.applied",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_only_command_derived_manual_intent_can_restart_ambiguous_provider(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, run, original = await _create_ambiguous_workflow(
            session,
            user_id=1704,
            project_id="command-execute-project",
            run_id="command-execute-run",
        )
        command = _command(
            command_id="command-execute-external",
            run=run,
            actor_user_id=1704,
            command_type="retry_external",
            payload={
                "activity_key": original.activity_key,
                "acknowledge_possible_duplicate": True,
            },
        )
        session.add(command)
        await session.commit()
        applied = await JobService(session).apply_ambiguous_activity_command(command.id)
        manual_activity_key = applied.result_payload["activity_key"]
        manual_intent = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == job.id,
                    JobActivity.activity_key == manual_activity_key,
                )
            )
        ).scalar_one()
        manual_request = dict(manual_intent.request_payload)
        lease = await JobService(session).claim_next(
            worker_id="manual-retry-worker",
            lease_seconds=30,
            now=datetime.now(timezone.utc),
        )
        assert lease is not None

        provider_execution_grants = 0
        execution = await JobService(session).begin_activity(
            lease,
            activity_key=manual_activity_key,
            side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
            request_payload=manual_request,
        )
        if execution.should_execute:
            provider_execution_grants += 1
        assert provider_execution_grants == 1

    async with session_factory() as session:
        reclaimed = await JobService(session).claim_next(
            worker_id="ordinary-reclaim-worker",
            lease_seconds=30,
            now=lease.lease_expires_at + timedelta(seconds=1),
        )
        persisted_original = await session.get(JobActivity, original.id)
        persisted_job = await session.get(BackgroundTask, job.id)
        persisted_run = await session.get(ChapterWorkflowRun, run.id)
        persisted_manual = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == job.id,
                    JobActivity.activity_key == manual_activity_key,
                )
            )
        ).scalar_one()

    assert reclaimed is None
    assert provider_execution_grants == 1
    assert persisted_original is not None and persisted_original.status == "ambiguous"
    assert persisted_manual.status == "started"
    assert persisted_job is not None and persisted_job.status == "needs_attention"
    assert persisted_job.lease_owner is None
    assert persisted_run is not None and persisted_run.status == "needs_attention"
    assert persisted_run.is_active is True

    async with session_factory() as session:
        session.add(
            ChapterWorkflowCommand(
                id="command-requeue-without-new-intent",
                run_id=run.id,
                type="retry",
                payload_version=1,
                payload={"activity_key": original.activity_key},
                actor_user_id=1704,
                expected_run_revision=run.row_revision,
                expected_chapter_revision=run.base_revision,
                expected_checkpoint_id=run.checkpoint_id,
                status="pending",
            )
        )
        await session.commit()
        with pytest.raises(ChapterWorkflowCommandRejectedError):
            await JobService(session).apply_ambiguous_activity_command(
                "command-requeue-without-new-intent"
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_pending_command_lock_refreshes_cached_payload(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as setup_session:
        _, run, original = await _create_ambiguous_workflow(
            setup_session,
            user_id=1706,
            project_id="command-lock-refresh-project",
            run_id="command-lock-refresh-run",
        )
        command = _command(
            command_id="command-lock-refresh",
            run=run,
            actor_user_id=1706,
            command_type="retry_external",
            payload={
                "activity_key": original.activity_key,
                "acknowledge_possible_duplicate": True,
            },
        )
        setup_session.add(command)
        await setup_session.commit()

    async with session_factory() as stale_session, session_factory() as writer_session:
        cached = await stale_session.get(ChapterWorkflowCommand, command.id)
        assert cached is not None
        assert "audit_marker" not in cached.payload

        current = await writer_session.get(ChapterWorkflowCommand, command.id)
        assert current is not None
        current.payload = {**current.payload, "audit_marker": "latest"}
        await writer_session.commit()

        locked = await ChapterWorkflowRepository(stale_session).list_pending_commands_for_update(
            run.id
        )

        assert len(locked) == 1
        assert locked[0] is cached
        assert locked[0].payload["audit_marker"] == "latest"


@pytest.mark.asyncio(loop_scope="session")
async def test_ambiguous_cancel_is_terminal_without_new_intent_or_provider_call(isolated_pg):
    session_factory = isolated_pg.session_factory

    async with session_factory() as session:
        job, run, original = await _create_ambiguous_workflow(
            session,
            user_id=1705,
            project_id="command-cancel-project",
            run_id="command-cancel-run",
        )
        command = _command(
            command_id="command-cancel-ambiguous",
            run=run,
            actor_user_id=1705,
            command_type="cancel",
            payload={"activity_key": original.activity_key},
        )
        session.add(command)
        await session.commit()
        original_before = _activity_snapshot(original)

        applied = await JobService(session).apply_ambiguous_activity_command(command.id)
        replayed = await JobService(session).apply_ambiguous_activity_command(command.id)
        assert replayed.result_payload == applied.result_payload

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job.id)
        persisted_run = await session.get(ChapterWorkflowRun, run.id)
        persisted_original = await session.get(JobActivity, original.id)
        activities = await session.scalar(
            select(func.count()).select_from(JobActivity).where(JobActivity.job_id == job.id)
        )
        events = list(
            (
                await session.execute(
                    select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.sequence)
                )
            ).scalars()
        )

    assert persisted_job is not None and persisted_job.status == "cancelled"
    assert persisted_job.lease_owner is None
    assert persisted_run is not None and persisted_run.status == "cancelled"
    assert persisted_run.is_active is False
    assert persisted_original is not None
    assert _activity_snapshot(persisted_original) == original_before
    assert activities == 1
    assert [event.event_type for event in events].count("workflow.completed") == 1


@pytest.mark.parametrize(
    ("command_type", "payload"),
    [
        ("select", {}),
        ("select", {"selected_version_id": True}),
        ("retry", {"activity_key": "forbidden"}),
        ("retry_external", {"activity_key": "wf:generate_candidates:hash"}),
        ("retry_projection", {"retry": True}),
        ("cancel", {"provider_result": {"forged": True}}),
    ],
)
def test_command_envelope_rejects_noncanonical_payload(command_type, payload):
    with pytest.raises(ValidationError):
        ChapterWorkflowCommandEnvelope(
            command_id=str(uuid4()),
            type=command_type,
            payload=payload,
            expected_run_revision=0,
            expected_chapter_revision=0,
            expected_checkpoint_id="checkpoint",
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_waiting_cancel_command_is_applied_atomically(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        job, run, chapter = await _create_waiting_workflow(
            session,
            user_id=1714,
            project_id="command-waiting-cancel-project",
        )
        command = await JobService(session).submit_chapter_workflow_command(
            run.id,
            actor_user_id=1714,
            envelope=ChapterWorkflowCommandEnvelope(
                command_id=str(uuid4()),
                type="cancel",
                payload={},
                expected_run_revision=run.row_revision,
                expected_chapter_revision=chapter.current_revision,
                expected_checkpoint_id=run.checkpoint_id,
            ),
        )
        await session.refresh(job)
        await session.refresh(run)
        events = list(
            (
                await session.execute(
                    select(JobEvent).where(JobEvent.job_id == job.id).order_by(JobEvent.sequence)
                )
            ).scalars()
        )

    assert command.status == "applied"
    assert command.result_payload == {
        "command_id": command.id,
        "status": "applied",
        "cancelled_job_id": job.id,
        "cancel_pending": False,
    }
    assert job.status == "cancelled"
    assert run.status == "cancelled"
    assert run.is_active is False
    assert [event.event_type for event in events][-3:] == [
        "workflow.command.accepted",
        "workflow.completed",
        "workflow.command.applied",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_running_cancel_command_requires_current_fence_to_finish(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        job, run, chapter = await _create_waiting_workflow(
            session,
            user_id=1715,
            project_id="command-running-cancel-project",
        )
        await JobService(session).resume_waiting(
            job.id,
            expected_fencing_token=job.fencing_token,
            workflow_transition=ChapterWorkflowTransition(
                status="queued",
                node_key=run.node_key,
                checkpoint_id=run.checkpoint_id,
                progress=run.progress,
            ),
        )
        lease = await JobService(session).claim_next(
            worker_id="command-running-cancel-worker",
            lease_seconds=30,
        )
        assert lease is not None
        await session.refresh(run)
        command = await JobService(session).submit_chapter_workflow_command(
            run.id,
            actor_user_id=1715,
            envelope=ChapterWorkflowCommandEnvelope(
                command_id=str(uuid4()),
                type="cancel",
                payload={},
                expected_run_revision=run.row_revision,
                expected_chapter_revision=chapter.current_revision,
                expected_checkpoint_id=run.checkpoint_id,
            ),
        )
        await session.refresh(job)
        await session.refresh(run)

        assert command.status == "applied"
        assert command.result_payload["cancel_pending"] is True
        assert job.status == "running"
        assert job.cancel_requested_at is not None
        assert run.status == "running"
        assert run.is_active is True

        heartbeat = await JobService(session).heartbeat(lease, lease_seconds=30)
        assert heartbeat.cancel_requested is True
        await JobService(session).mark_cancelled(lease)
        await session.refresh(run)

    assert run.status == "cancelled"
    assert run.is_active is False


@pytest.mark.asyncio(loop_scope="session")
async def test_determinate_retry_reuses_run_and_concurrent_replay_returns_same_target(
    isolated_pg,
):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        job, run, chapter = await _create_waiting_workflow(
            session,
            user_id=1716,
            project_id="command-terminal-retry-project",
        )
        await JobService(session).resume_waiting(
            job.id,
            expected_fencing_token=job.fencing_token,
            workflow_transition=ChapterWorkflowTransition(
                status="queued",
                node_key=run.node_key,
                checkpoint_id=run.checkpoint_id,
                progress=run.progress,
            ),
        )
        lease = await JobService(session).claim_next(
            worker_id="command-terminal-retry-worker",
            lease_seconds=30,
        )
        assert lease is not None
        await JobService(session).record_failure(
            lease,
            error_category="determinate_failure",
            public_message="节点返回了确定失败",
            retryable=False,
        )
        await session.refresh(run)
        expected_revision = run.row_revision
        common = {
            "type": "retry",
            "payload": {},
            "expected_run_revision": expected_revision,
            "expected_chapter_revision": chapter.current_revision,
            "expected_checkpoint_id": run.checkpoint_id,
        }
        run_id = run.id
        first_envelope = ChapterWorkflowCommandEnvelope(
            command_id=str(uuid4()),
            **common,
        )
        second_envelope = ChapterWorkflowCommandEnvelope(
            command_id=str(uuid4()),
            **common,
        )

    async def submit(envelope):
        async with session_factory() as session:
            return await JobService(session).submit_chapter_workflow_command(
                run_id,
                actor_user_id=1716,
                envelope=envelope,
            )

    first, second = await asyncio.gather(submit(first_envelope), submit(second_envelope))
    assert first.status == second.status == "applied"
    assert first.result_payload["retry_run_id"] == run_id
    assert second.result_payload["retry_run_id"] == run_id

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job.id)
        persisted_run = await session.get(ChapterWorkflowRun, run_id)
        run_count = await session.scalar(select(func.count()).select_from(ChapterWorkflowRun))
        job_count = await session.scalar(
            select(func.count())
            .select_from(BackgroundTask)
            .where(BackgroundTask.task_type == "chapter_workflow")
        )

    assert persisted_job is not None and persisted_job.status == "queued"
    assert persisted_run is not None and persisted_run.status == "queued"
    assert persisted_run.is_active is True
    assert persisted_run.checkpoint_id == "checkpoint-selection"
    assert persisted_run.row_revision == expected_revision + 1
    assert run_count == 1
    assert job_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_workflow_snapshot_exposes_only_fact_backed_commands(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        _, waiting_run, _ = await _create_waiting_workflow(
            session,
            user_id=1717,
            project_id="command-snapshot-waiting-project",
        )
        waiting_snapshot = await JobService(session).get_chapter_workflow_snapshot(
            waiting_run.id,
            user_id=1717,
        )

    assert waiting_snapshot.allowed_commands == ["select", "cancel"]
    assert waiting_snapshot.status == "waiting_for_selection"
    assert waiting_snapshot.checkpoint_id == "checkpoint-selection"
    assert waiting_snapshot.current_chapter_revision == 0
    assert waiting_snapshot.resume_cursor > 0

    async with session_factory() as session:
        _, ambiguous_run, _ = await _create_ambiguous_workflow(
            session,
            user_id=1718,
            project_id="command-snapshot-ambiguous-project",
            run_id=str(uuid4()),
        )
        ambiguous_snapshot = await JobService(session).get_chapter_workflow_snapshot(
            ambiguous_run.id,
            user_id=1718,
        )

    assert ambiguous_snapshot.allowed_commands == ["retry_external", "cancel"]
    assert ambiguous_snapshot.status == "needs_attention"


@pytest.mark.asyncio(loop_scope="session")
async def test_noncanonical_ambiguous_snapshot_allows_only_cancel_and_rejects_retry(isolated_pg):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        workflow_run_id = str(uuid4())
        job, run, original = await _create_ambiguous_workflow(
            session,
            user_id=1720,
            project_id="command-noncanonical-project",
            run_id=workflow_run_id,
        )
        original.request_payload = {
            **original.request_payload,
            "prompt": "private provider input",
        }
        await session.commit()
        snapshot = await JobService(session).get_chapter_workflow_snapshot(
            run.id,
            user_id=1720,
        )
        expected_run_revision = run.row_revision
        expected_chapter_revision = run.base_revision
        expected_checkpoint_id = run.checkpoint_id
        job_id = job.id
        run_id = run.id

    assert snapshot.allowed_commands == ["cancel"]
    assert "retry" not in snapshot.allowed_commands
    assert "retry_external" not in snapshot.allowed_commands

    envelope = ChapterWorkflowCommandEnvelope(
        command_id=str(uuid4()),
        type="retry",
        payload={},
        expected_run_revision=expected_run_revision,
        expected_chapter_revision=expected_chapter_revision,
        expected_checkpoint_id=expected_checkpoint_id,
    )
    async with session_factory() as session:
        with pytest.raises(ChapterWorkflowCommandRejectedError) as error:
            await JobService(session).submit_chapter_workflow_command(
                run_id,
                actor_user_id=1720,
                envelope=envelope,
            )
        assert error.value.reason_code == "command_not_allowed_in_current_state"

    async with session_factory() as session:
        persisted_job = await session.get(BackgroundTask, job_id)
        persisted_run = await session.get(ChapterWorkflowRun, run_id)
        activity_count = await session.scalar(
            select(func.count()).select_from(JobActivity).where(JobActivity.job_id == job_id)
        )

    assert persisted_job is not None and persisted_job.status == "needs_attention"
    assert persisted_run is not None and persisted_run.status == "needs_attention"
    assert persisted_run.row_revision == expected_run_revision
    assert activity_count == 1
