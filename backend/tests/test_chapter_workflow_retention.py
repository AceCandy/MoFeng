# AIMETA P=章节工作流终态保留测试|R=保护矩阵_payload清理_checkpoint幂等|NR=不测试生产定时调度|E=test_*|X=internal|A=integration_test|D=pytest,postgresql|S=test|RD=../app/README.ai
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import JSON, cast, func, literal, null, select, update
from sqlalchemy.dialects.postgresql import JSONB

from app.models import (
    AIUsageRecord,
    BackgroundTask,
    Chapter,
    ChapterOutboxEvent,
    ChapterProjectionRetentionAudit,
    ChapterWorkflowCommand,
    ChapterWorkflowRun,
    JobActivity,
    JobEvent,
    NovelProject,
)
from app.models.user import User
from app.repositories.chapter_workflow_repository import ChapterWorkflowRepository
from app.schemas.chapter_workflow import ChapterWorkflowStateV1
from app.services.chapter_workflow_reconciler import ChapterWorkflowReconcileCandidate
from app.services.chapter_workflow_retention import ChapterWorkflowRetentionService
from app.services.job_service import ChapterWorkflowCheckpointEvidence, JobService

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _CheckpointReader:
    def __init__(self, evidence: dict[str, ChapterWorkflowCheckpointEvidence]) -> None:
        self.evidence = evidence

    async def read(
        self,
        candidates: list[ChapterWorkflowReconcileCandidate],
    ) -> dict[str, ChapterWorkflowCheckpointEvidence]:
        return {candidate.run_id: self.evidence[candidate.run_id] for candidate in candidates}


class _CheckpointCleaner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    async def delete_threads(self, run_ids) -> None:
        self.calls.append(tuple(run_ids))


class _FailOnceCheckpointCleaner(_CheckpointCleaner):
    async def delete_threads(self, run_ids) -> None:
        await super().delete_threads(run_ids)
        if len(self.calls) == 1:
            raise RuntimeError("checkpoint delete unavailable")


class _FailAfterFirstThreadCleaner(_CheckpointCleaner):
    def __init__(self) -> None:
        super().__init__()
        self.deleted: set[str] = set()
        self.failed = False

    async def delete_threads(self, run_ids) -> None:
        await super().delete_threads(run_ids)
        for run_id in run_ids:
            if self.deleted and not self.failed:
                self.failed = True
                raise RuntimeError("checkpoint batch delete interrupted")
            self.deleted.add(run_id)


async def _create_workflow(
    session,
    *,
    ordinal: int,
    run_id: str | None = None,
) -> tuple[BackgroundTask, ChapterWorkflowRun, Chapter]:
    run_id = run_id or str(uuid4())
    project_id = str(uuid4())
    user = User(username=f"retention-{ordinal}-{run_id}", hashed_password="secret")
    session.add(user)
    await session.flush()
    session.add(
        NovelProject(
            id=project_id,
            user_id=user.id,
            title=f"Workflow retention {ordinal}",
            initial_prompt="private prompt",
        )
    )
    chapter = Chapter(project_id=project_id, chapter_number=ordinal)
    session.add(chapter)
    await session.commit()
    job = await JobService(session).enqueue_job(
        user_id=user.id,
        project_id=project_id,
        job_type="chapter_workflow",
        title="Durable Chapter workflow",
        payload={"private": "root payload retained"},
        idempotency_key=f"workflow:{run_id}",
        stream_type="workflow",
        stream_id=run_id,
    )
    run = ChapterWorkflowRun(
        id=run_id,
        user_id=user.id,
        project_id=project_id,
        chapter_id=chapter.id,
        chapter_number=ordinal,
        base_revision=0,
        root_job_id=job.id,
        workflow_version=1,
        state_schema_version=1,
        context_schema_version=1,
        context_snapshot={"private": "frozen context retained"},
        context_hash="a" * 64,
        runtime_input_hash="b" * 64,
        status="queued",
        node_key="freeze_context",
    )
    session.add(run)
    await session.commit()
    return job, run, chapter


def _terminalize(
    job: BackgroundTask,
    run: ChapterWorkflowRun,
    *,
    completed_at: datetime,
    checkpoint_id: str,
) -> None:
    job.status = "failed"
    job.completed_at = completed_at
    run.status = "failed"
    run.node_key = "failed"
    run.is_active = False
    run.completed_at = completed_at
    run.checkpoint_id = checkpoint_id


def _state(run: ChapterWorkflowRun, *, target_revision: int | None) -> ChapterWorkflowStateV1:
    return ChapterWorkflowStateV1(
        run_id=run.id,
        node_key="observe_projection",
        context_hash=run.context_hash,
        target_chapter_revision=target_revision,
    )


async def test_retention_scrubs_private_payload_and_preserves_audit(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    async with isolated_pg.session_factory() as session:
        job, run, chapter = await _create_workflow(session, ordinal=1)
        _terminalize(job, run, completed_at=old, checkpoint_id="checkpoint-old")
        chapter.current_revision = 2
        command = ChapterWorkflowCommand(
            id=str(uuid4()),
            run_id=run.id,
            type="select",
            payload_version=1,
            payload={"private": "command payload"},
            actor_user_id=run.user_id,
            expected_run_revision=0,
            expected_chapter_revision=0,
            expected_checkpoint_id="checkpoint-old",
            status="applied",
            result_payload={"private": "command result"},
            applied_at=old,
        )
        activity = JobActivity(
            id=str(uuid4()),
            job_id=job.id,
            activity_key="wf:generate_candidates:hash",
            side_effect_class="ambiguous_external",
            status="succeeded",
            provider_request_key=str(uuid4()),
            attempt=1,
            fencing_token=1,
            request_payload={"private": "activity request"},
            result_payload={"private": "activity result"},
            started_at=old,
            completed_at=old,
        )
        usage = AIUsageRecord(
            job_activity_id=activity.id,
            job_id=job.id,
            user_id=run.user_id,
            project_id=run.project_id,
            provider_type="openai",
            model_name="audit-model",
            stage="generate_candidates",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            usage_complete=True,
            cost_amount=Decimal("0.123"),
            cost_currency="USD",
            cost_known=True,
        )
        outbox = ChapterOutboxEvent(
            id=str(uuid4()),
            aggregate_type="chapter",
            aggregate_id=str(chapter.id),
            chapter_id=chapter.id,
            project_id=run.project_id,
            revision=1,
            event_type="ChapterFinalizationRequested",
            event_version=1,
            payload={"audit": "retained"},
            payload_fingerprint="c" * 64,
            idempotency_key=f"retention-outbox:{run.id}",
            workflow_stream_type="workflow",
            workflow_stream_id=run.id,
        )
        projection_audit = ChapterProjectionRetentionAudit(
            id=str(uuid4()),
            operator_user_id=run.user_id,
            project_id=run.project_id,
            chapter_id=chapter.id,
            chapter_number=chapter.chapter_number,
            revision=1,
            artifact_generation=str(uuid4()),
            artifact_kind="rag",
            mode="preview",
            status="completed",
            idempotency_key=f"retention-audit:{run.id}",
            reason="retention preservation test",
            request_scope={"audit": "retained"},
            result={"candidate_rows": 1},
        )
        session.add_all([command, activity, outbox, projection_audit])
        await session.flush()
        session.add(usage)
        await session.commit()
        event_count_before = await session.scalar(
            select(func.count(JobEvent.cursor)).where(
                JobEvent.stream_type == "workflow",
                JobEvent.stream_id == run.id,
            )
        )

        cleaner = _CheckpointCleaner()
        service = ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=_CheckpointReader(
                {
                    run.id: ChapterWorkflowCheckpointEvidence(
                        checkpoint_id="checkpoint-old",
                        state=_state(run, target_revision=1),
                    )
                }
            ),
            checkpoint_cleaner=cleaner,
        )
        result = await service.cleanup(before=now - timedelta(days=30))
        second = await service.cleanup(before=now - timedelta(days=30))

        retained_run = await session.get(ChapterWorkflowRun, run.id)
        retained_job = await session.get(BackgroundTask, job.id)
        retained_command = await session.get(ChapterWorkflowCommand, command.id)
        retained_activity = await session.get(JobActivity, activity.id)
        retained_usage = await session.get(AIUsageRecord, activity.id)
        retained_outbox = await session.get(ChapterOutboxEvent, outbox.id)
        retained_projection_audit = await session.get(
            ChapterProjectionRetentionAudit,
            projection_audit.id,
        )
        event_count_after = await session.scalar(
            select(func.count(JobEvent.cursor)).where(
                JobEvent.stream_type == "workflow",
                JobEvent.stream_id == run.id,
            )
        )

    assert result.scanned == 1
    assert result.cleaned_runs == 1
    assert result.deleted_threads == 1
    assert result.scrubbed_commands == 1
    assert result.scrubbed_activities == 1
    assert cleaner.calls == [(run.id,)]
    assert second.scanned == 0
    assert second.cleaned_runs == 0
    assert retained_run is not None
    assert retained_run.status == "failed"
    assert retained_run.checkpoint_id is None
    assert retained_run.context_snapshot == {"private": "frozen context retained"}
    assert retained_job is not None and retained_job.payload == {"private": "root payload retained"}
    assert retained_command is not None
    assert retained_command.type == "select"
    assert retained_command.status == "applied"
    assert retained_command.actor_user_id == run.user_id
    assert retained_command.payload == {}
    assert retained_command.result_payload is None
    assert retained_activity is not None
    assert retained_activity.activity_key == "wf:generate_candidates:hash"
    assert retained_activity.status == "succeeded"
    assert retained_activity.request_payload == {}
    assert retained_activity.result_payload is None
    assert retained_usage is not None
    assert retained_usage.total_tokens == 30
    assert retained_usage.cost_amount == Decimal("0.123000000000")
    assert retained_usage.cost_currency == "USD"
    assert retained_outbox is not None
    assert retained_outbox.workflow_stream_id == run.id
    assert retained_projection_audit is not None
    assert retained_projection_audit.result == {"candidate_rows": 1}
    assert event_count_before is not None and event_count_before > 0
    assert event_count_after == event_count_before


async def test_retention_protects_current_pending_successor_active_and_recent(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    evidence: dict[str, ChapterWorkflowCheckpointEvidence] = {}
    protected: list[ChapterWorkflowRun] = []
    async with isolated_pg.session_factory() as session:
        _current_job, current_run, current_chapter = await _create_workflow(session, ordinal=1)
        _terminalize(_current_job, current_run, completed_at=old, checkpoint_id="current")
        current_chapter.current_revision = 1
        evidence[current_run.id] = ChapterWorkflowCheckpointEvidence(
            checkpoint_id="current",
            state=_state(current_run, target_revision=1),
        )
        protected.append(current_run)

        unavailable_job, unavailable_run, _ = await _create_workflow(session, ordinal=7)
        _terminalize(
            unavailable_job,
            unavailable_run,
            completed_at=old,
            checkpoint_id="unavailable",
        )
        evidence[unavailable_run.id] = ChapterWorkflowCheckpointEvidence(
            checkpoint_id=None,
            state=None,
            reason_code="checkpoint_read_unavailable",
        )
        protected.append(unavailable_run)

        pending_job, pending_run, _ = await _create_workflow(session, ordinal=2)
        _terminalize(pending_job, pending_run, completed_at=old, checkpoint_id="pending")
        session.add(
            ChapterWorkflowCommand(
                id=str(uuid4()),
                run_id=pending_run.id,
                type="cancel",
                payload_version=1,
                payload={"private": True},
                actor_user_id=pending_run.user_id,
                expected_run_revision=0,
                expected_chapter_revision=0,
                expected_checkpoint_id="pending",
                status="pending",
            )
        )
        protected.append(pending_run)

        successor_job, successor_run, _ = await _create_workflow(session, ordinal=3)
        _terminalize(successor_job, successor_run, completed_at=old, checkpoint_id="successor")
        successor_target_job, successor_target, _ = await _create_workflow(session, ordinal=4)
        successor_run.successor_run_id = successor_target.id
        protected.append(successor_run)

        active_job, active_run, _ = await _create_workflow(session, ordinal=5)
        active_job.status = "needs_attention"
        active_run.status = "needs_attention"
        active_run.node_key = "generate_candidates"
        active_run.checkpoint_id = "attention"
        protected.append(active_run)

        recent_job, recent_run, _ = await _create_workflow(session, ordinal=6)
        _terminalize(
            recent_job,
            recent_run,
            completed_at=now - timedelta(days=2),
            checkpoint_id="recent",
        )
        protected.append(recent_run)
        await session.commit()

        cleaner = _CheckpointCleaner()
        result = await ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=_CheckpointReader(evidence),
            checkpoint_cleaner=cleaner,
        ).cleanup(before=now - timedelta(days=30))
        checkpoint_ids = {
            run.id: (await session.get(ChapterWorkflowRun, run.id)).checkpoint_id
            for run in protected
        }

    assert result.scanned == 2
    assert result.cleaned_runs == 0
    assert result.protected_current_revision == 1
    assert result.checkpoint_unavailable == 1
    assert cleaner.calls == []
    assert checkpoint_ids == {
        current_run.id: "current",
        pending_run.id: "pending",
        successor_run.id: "successor",
        active_run.id: "attention",
        recent_run.id: "recent",
        unavailable_run.id: "unavailable",
    }


async def test_retention_resumes_after_checkpoint_delete_failure(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    async with isolated_pg.session_factory() as session:
        job, run, _chapter = await _create_workflow(session, ordinal=1)
        _terminalize(job, run, completed_at=old, checkpoint_id="checkpoint-old")
        command = ChapterWorkflowCommand(
            id=str(uuid4()),
            run_id=run.id,
            type="cancel",
            payload_version=1,
            payload={"private": True},
            actor_user_id=run.user_id,
            expected_run_revision=0,
            expected_chapter_revision=0,
            expected_checkpoint_id="checkpoint-old",
            status="rejected",
            rejection_code="stale_checkpoint",
            result_payload={"private": True},
        )
        session.add(command)
        await session.commit()
        cleaner = _FailOnceCheckpointCleaner()
        service = ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=_CheckpointReader(
                {
                    run.id: ChapterWorkflowCheckpointEvidence(
                        checkpoint_id="checkpoint-old",
                        state=_state(run, target_revision=None),
                    )
                }
            ),
            checkpoint_cleaner=cleaner,
        )

        with pytest.raises(RuntimeError, match="delete unavailable"):
            await service.cleanup(before=now - timedelta(days=30))
        await session.refresh(run)
        await session.refresh(command)
        assert run.checkpoint_id == "__retention_pending__"
        assert command.payload == {}
        assert command.result_payload is None

        result = await service.cleanup(before=now - timedelta(days=30))
        await session.refresh(run)

    assert result.cleaned_runs == 1
    assert result.deleted_threads == 1
    assert result.scrubbed_commands == 0
    assert cleaner.calls == [(run.id,), (run.id,)]
    assert run.checkpoint_id is None


async def test_retention_pages_past_protected_prefix(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    protected_id = "00000000-0000-0000-0000-000000000001"
    eligible_id = "ffffffff-ffff-ffff-ffff-ffffffffffff"
    async with isolated_pg.session_factory() as session:
        protected_job, protected_run, protected_chapter = await _create_workflow(
            session,
            ordinal=1,
            run_id=protected_id,
        )
        _terminalize(
            protected_job,
            protected_run,
            completed_at=old,
            checkpoint_id="protected-checkpoint",
        )
        protected_chapter.current_revision = 1

        eligible_job, eligible_run, eligible_chapter = await _create_workflow(
            session,
            ordinal=2,
            run_id=eligible_id,
        )
        _terminalize(
            eligible_job,
            eligible_run,
            completed_at=old,
            checkpoint_id="eligible-checkpoint",
        )
        eligible_chapter.current_revision = 2
        await session.commit()

        cleaner = _CheckpointCleaner()
        result = await ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=_CheckpointReader(
                {
                    protected_id: ChapterWorkflowCheckpointEvidence(
                        checkpoint_id="protected-checkpoint",
                        state=_state(protected_run, target_revision=1),
                    ),
                    eligible_id: ChapterWorkflowCheckpointEvidence(
                        checkpoint_id="eligible-checkpoint",
                        state=_state(eligible_run, target_revision=1),
                    ),
                }
            ),
            checkpoint_cleaner=cleaner,
        ).cleanup(before=now - timedelta(days=30), limit=1)
        await session.refresh(protected_run)
        await session.refresh(eligible_run)

    assert result.scanned == 2
    assert result.cleaned_runs == 1
    assert result.protected_current_revision == 1
    assert protected_run.checkpoint_id == "protected-checkpoint"
    assert eligible_run.checkpoint_id is None
    assert cleaner.calls == [(eligible_id,)]


async def test_retention_protects_current_revision_without_checkpoint(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    async with isolated_pg.session_factory() as session:
        job, run, chapter = await _create_workflow(session, ordinal=1)
        _terminalize(job, run, completed_at=old, checkpoint_id="discarded-checkpoint")
        run.checkpoint_id = None
        chapter.current_revision = 1
        command = ChapterWorkflowCommand(
            id=str(uuid4()),
            run_id=run.id,
            type="cancel",
            payload_version=1,
            payload={"private": "must remain"},
            actor_user_id=run.user_id,
            expected_run_revision=0,
            expected_chapter_revision=1,
            expected_checkpoint_id="discarded-checkpoint",
            status="rejected",
            rejection_code="stale_checkpoint",
        )
        session.add(command)
        await session.commit()

        cleaner = _CheckpointCleaner()
        result = await ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=_CheckpointReader({}),
            checkpoint_cleaner=cleaner,
        ).cleanup(before=now - timedelta(days=30))
        await session.refresh(command)

    assert result.scanned == 1
    assert result.cleaned_runs == 0
    assert result.protected_current_revision == 1
    assert command.payload == {"private": "must remain"}
    assert cleaner.calls == []


async def test_retention_recovers_after_partial_checkpoint_batch_delete(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    run_ids = (
        "10000000-0000-0000-0000-000000000001",
        "20000000-0000-0000-0000-000000000002",
    )
    async with isolated_pg.session_factory() as session:
        workflows = []
        evidence = {}
        for ordinal, run_id in enumerate(run_ids, start=1):
            job, run, chapter = await _create_workflow(
                session,
                ordinal=ordinal,
                run_id=run_id,
            )
            _terminalize(job, run, completed_at=old, checkpoint_id=f"checkpoint-{ordinal}")
            chapter.current_revision = 2
            workflows.append(run)
            evidence[run.id] = ChapterWorkflowCheckpointEvidence(
                checkpoint_id=f"checkpoint-{ordinal}",
                state=_state(run, target_revision=1),
            )
        await session.commit()

        cleaner = _FailAfterFirstThreadCleaner()
        service = ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=_CheckpointReader(evidence),
            checkpoint_cleaner=cleaner,
        )
        with pytest.raises(RuntimeError, match="batch delete interrupted"):
            await service.cleanup(before=now - timedelta(days=30), limit=2)
        for run in workflows:
            await session.refresh(run)
            assert run.checkpoint_id == "__retention_pending__"

        result = await service.cleanup(before=now - timedelta(days=30), limit=2)
        for run in workflows:
            await session.refresh(run)

    assert result.cleaned_runs == 2
    assert result.deleted_threads == 2
    assert cleaner.calls == [run_ids, run_ids]
    assert cleaner.deleted == set(run_ids)
    assert all(run.checkpoint_id is None for run in workflows)


async def test_retention_candidate_query_distinguishes_json_empty_states(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    old = now - timedelta(days=60)
    stored_values = {
        "sql_null": null(),
        "json_null": JSON.NULL,
        "empty_object": {},
    }
    run_ids: dict[str, str] = {}
    command_ids: dict[str, str] = {}

    async with isolated_pg.session_factory() as session:
        for ordinal, (label, stored_value) in enumerate(stored_values.items(), start=1):
            job, run, chapter = await _create_workflow(session, ordinal=ordinal)
            _terminalize(job, run, completed_at=old, checkpoint_id="discarded-checkpoint")
            run.checkpoint_id = None
            chapter.current_revision = 2
            command = ChapterWorkflowCommand(
                id=str(uuid4()),
                run_id=run.id,
                type="cancel",
                payload_version=1,
                payload={},
                actor_user_id=run.user_id,
                expected_run_revision=0,
                expected_chapter_revision=0,
                expected_checkpoint_id="discarded-checkpoint",
                status="rejected",
                rejection_code="stale_checkpoint",
                result_payload=None,
            )
            session.add(command)
            await session.flush()
            await session.execute(
                update(ChapterWorkflowCommand)
                .where(ChapterWorkflowCommand.id == command.id)
                .values(result_payload=stored_value)
                .execution_options(synchronize_session=False)
            )
            run_ids[label] = run.id
            command_ids[label] = command.id
        await session.commit()

        result_json = cast(ChapterWorkflowCommand.result_payload, JSONB)
        json_null = cast(literal("null"), JSONB)
        empty_object = cast(literal("{}"), JSONB)
        rows = (
            await session.execute(
                select(
                    ChapterWorkflowCommand.id,
                    ChapterWorkflowCommand.result_payload.is_(None).label("is_sql_null"),
                    (result_json == json_null).label("is_json_null"),
                    (result_json == empty_object).label("is_empty_object"),
                ).where(ChapterWorkflowCommand.id.in_(command_ids.values()))
            )
        ).all()
        storage_states = {
            row.id: (row.is_sql_null, row.is_json_null, row.is_empty_object) for row in rows
        }
        candidates = await ChapterWorkflowRepository(session).list_retention_candidates(
            before=now - timedelta(days=30),
            after_run_id=None,
            limit=10,
        )

    assert storage_states == {
        command_ids["sql_null"]: (True, None, None),
        command_ids["json_null"]: (False, True, False),
        command_ids["empty_object"]: (False, False, True),
    }
    assert [candidate.id for candidate in candidates] == [run_ids["empty_object"]]


async def test_retention_validates_inputs_without_querying(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        service = ChapterWorkflowRetentionService(
            session,
            checkpoint_reader=_CheckpointReader({}),
            checkpoint_cleaner=_CheckpointCleaner(),
        )
        with pytest.raises(ValueError, match="时区"):
            await service.cleanup(before=datetime(2026, 7, 30), limit=1)
        with pytest.raises(ValueError, match="limit"):
            await service.cleanup(before=datetime.now(timezone.utc), limit=0)
