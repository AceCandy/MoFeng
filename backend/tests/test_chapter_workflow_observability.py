# AIMETA P=章节工作流可观测性测试|R=有界聚合_checkpoint_lag_稳定告警|NR=不测试外部指标系统|E=test_*|X=internal|A=integration_test|D=pytest,postgresql|S=test|RD=../app/README.ai
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.models import BackgroundTask, ChapterWorkflowRun, JobEvent, NovelProject
from app.models.user import User
from app.schemas.chapter_workflow import ChapterWorkflowStateV1
from app.services.chapter_workflow_observability import (
    ChapterWorkflowObservabilityService,
)
from app.services.chapter_workflow_reconciler import ChapterWorkflowReconcileCandidate
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


async def _create_workflow(
    session,
    *,
    ordinal: int,
    now: datetime,
    status: str,
    node_key: str,
    job_status: str,
    checkpoint_id: str | None,
    age_seconds: int,
) -> tuple[BackgroundTask, ChapterWorkflowRun]:
    run_id = str(uuid4())
    project_id = str(uuid4())
    user = User(username=f"workflow-metrics-{ordinal}-{run_id}", hashed_password="secret")
    session.add(user)
    await session.flush()
    session.add(
        NovelProject(
            id=project_id,
            user_id=user.id,
            title=f"Workflow metrics {ordinal}",
            initial_prompt="private prompt",
        )
    )
    await session.commit()
    job = await JobService(session).enqueue_job(
        user_id=user.id,
        project_id=project_id,
        job_type="chapter_workflow",
        title="Durable Chapter workflow",
        payload={"private_token": "must-not-appear"},
        idempotency_key=f"workflow:{run_id}",
        stream_type="workflow",
        stream_id=run_id,
    )
    job.status = job_status
    job.updated_at = now - timedelta(seconds=age_seconds)
    run = ChapterWorkflowRun(
        id=run_id,
        user_id=user.id,
        project_id=project_id,
        chapter_number=ordinal,
        base_revision=0,
        root_job_id=job.id,
        workflow_version=1,
        state_schema_version=1,
        context_schema_version=1,
        context_snapshot={"private_token": "must-not-appear"},
        context_hash="a" * 64,
        runtime_input_hash="b" * 64,
        status=status,
        node_key=node_key,
        checkpoint_id=checkpoint_id,
        is_active=True,
        created_at=now - timedelta(seconds=age_seconds + 100),
        updated_at=now - timedelta(seconds=age_seconds),
    )
    session.add(run)
    await session.commit()
    return job, run


def _state(run: ChapterWorkflowRun) -> ChapterWorkflowStateV1:
    return ChapterWorkflowStateV1(
        run_id=run.id,
        node_key=run.node_key,
        context_hash=run.context_hash,
    )


async def test_workflow_metrics_are_bounded_and_alert_on_durable_lag(isolated_pg) -> None:
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    async with isolated_pg.session_factory() as session:
        waiting_job, waiting_run = await _create_workflow(
            session,
            ordinal=1,
            now=now,
            status="waiting_for_selection",
            node_key="waiting_for_selection",
            job_status="waiting",
            checkpoint_id="checkpoint-old",
            age_seconds=120,
        )
        _projection_job, projection_run = await _create_workflow(
            session,
            ordinal=2,
            now=now,
            status="projection_pending",
            node_key="projection_pending",
            job_status="waiting",
            checkpoint_id="checkpoint-projection",
            age_seconds=600,
        )
        _attention_job, attention_run = await _create_workflow(
            session,
            ordinal=3,
            now=now,
            status="needs_attention",
            node_key="generate_candidates",
            job_status="needs_attention",
            checkpoint_id="checkpoint-attention",
            age_seconds=300,
        )
        _queued_job, _queued_run = await _create_workflow(
            session,
            ordinal=4,
            now=now,
            status="queued",
            node_key="freeze_context",
            job_status="queued",
            checkpoint_id=None,
            age_seconds=30,
        )
        _mismatch_job, mismatch_run = await _create_workflow(
            session,
            ordinal=5,
            now=now,
            status="projection_pending",
            node_key="projection_pending",
            job_status="queued",
            checkpoint_id="checkpoint-mismatch",
            age_seconds=45,
        )
        session.add_all(
            [
                JobEvent(
                    job_id=projection_run.root_job_id,
                    user_id=projection_run.user_id,
                    project_id=projection_run.project_id,
                    stream_type="workflow",
                    stream_id=projection_run.id,
                    sequence=2,
                    event_type="workflow.waiting",
                    payload={
                        "workflow": {
                            "run_id": projection_run.id,
                            "status": "waiting_for_selection",
                        }
                    },
                    created_at=now - timedelta(seconds=1200),
                ),
                JobEvent(
                    job_id=projection_run.root_job_id,
                    user_id=projection_run.user_id,
                    project_id=projection_run.project_id,
                    stream_type="workflow",
                    stream_id=projection_run.id,
                    sequence=3,
                    event_type="workflow.waiting",
                    payload={
                        "workflow": {
                            "run_id": projection_run.id,
                            "status": "projection_pending",
                        }
                    },
                    created_at=now - timedelta(seconds=900),
                ),
                JobEvent(
                    job_id=waiting_job.id,
                    user_id=waiting_job.user_id,
                    project_id=waiting_job.project_id,
                    stream_type="workflow",
                    stream_id=waiting_run.id,
                    sequence=2,
                    event_type="workflow.waiting",
                    payload={
                        "workflow": {
                            "run_id": waiting_run.id,
                            "status": "waiting_for_selection",
                        }
                    },
                    created_at=now - timedelta(seconds=90),
                ),
                JobEvent(
                    job_id=waiting_job.id,
                    user_id=waiting_job.user_id,
                    project_id=waiting_job.project_id,
                    stream_type="workflow",
                    stream_id=waiting_run.id,
                    sequence=3,
                    event_type="workflow.command.rejected",
                    payload={
                        "workflow": {
                            "command": {
                                "type": "select",
                                "rejection_code": "stale_checkpoint",
                            }
                        }
                    },
                    created_at=now - timedelta(seconds=30),
                ),
                JobEvent(
                    job_id=waiting_job.id,
                    user_id=waiting_job.user_id,
                    project_id=waiting_job.project_id,
                    stream_type="workflow",
                    stream_id=waiting_run.id,
                    sequence=4,
                    event_type="workflow.command.rejected",
                    payload={
                        "workflow": {
                            "command": {
                                "type": "must-not-appear",
                                "rejection_code": "must-not-appear",
                            }
                        }
                    },
                    created_at=now - timedelta(seconds=20),
                ),
                JobEvent(
                    job_id=waiting_job.id,
                    user_id=waiting_job.user_id,
                    project_id=waiting_job.project_id,
                    stream_type="workflow",
                    stream_id=waiting_run.id,
                    sequence=5,
                    event_type="workflow.reconciled",
                    payload={"workflow": {"reason_code": "projection_completed"}},
                    created_at=now - timedelta(seconds=10),
                ),
                JobEvent(
                    job_id=waiting_job.id,
                    user_id=waiting_job.user_id,
                    project_id=waiting_job.project_id,
                    stream_type="workflow",
                    stream_id=waiting_run.id,
                    sequence=6,
                    event_type="workflow.reconciled",
                    payload={"workflow": {"reason_code": "must-not-appear"}},
                    created_at=now - timedelta(seconds=5),
                ),
                JobEvent(
                    job_id=waiting_job.id,
                    user_id=waiting_job.user_id,
                    project_id=waiting_job.project_id,
                    stream_type="workflow",
                    stream_id=waiting_run.id,
                    sequence=7,
                    event_type="workflow.command.rejected",
                    payload={},
                    created_at=now - timedelta(seconds=3600),
                ),
                JobEvent(
                    job_id=waiting_job.id,
                    user_id=waiting_job.user_id,
                    project_id=waiting_job.project_id,
                    stream_type="workflow",
                    stream_id=waiting_run.id,
                    sequence=8,
                    event_type="workflow.reconciled",
                    payload={},
                    created_at=now - timedelta(seconds=3600),
                ),
            ]
        )
        await session.commit()

        reader = _CheckpointReader(
            {
                waiting_run.id: ChapterWorkflowCheckpointEvidence(
                    checkpoint_id="checkpoint-new",
                    state=_state(waiting_run),
                ),
                projection_run.id: ChapterWorkflowCheckpointEvidence(
                    checkpoint_id="checkpoint-projection",
                    state=_state(projection_run),
                ),
                attention_run.id: ChapterWorkflowCheckpointEvidence(
                    checkpoint_id=None,
                    state=None,
                    reason_code="checkpoint_read_unavailable",
                ),
                mismatch_run.id: ChapterWorkflowCheckpointEvidence(
                    checkpoint_id="checkpoint-mismatch",
                    state=_state(mismatch_run),
                ),
            }
        )
        metrics = await ChapterWorkflowObservabilityService(
            session,
            checkpoint_reader=reader,
        ).get_runtime_metrics(
            now=now,
            waiting_alert_after_seconds=60,
            projection_alert_after_seconds=60,
        )

    assert metrics.status_counts == {
        "needs_attention": 1,
        "projection_pending": 2,
        "queued": 1,
        "waiting_for_selection": 1,
    }
    assert metrics.active_runs == 5
    assert metrics.waiting_runs == 2
    assert metrics.oldest_waiting_duration_seconds == 900.0
    assert metrics.command_rejections == 3
    assert metrics.command_rejection_type_counts == {"select": 1, "unknown": 2}
    assert metrics.command_rejection_reason_counts == {
        "stale_checkpoint": 1,
        "unknown": 2,
    }
    assert metrics.needs_attention == 1
    assert metrics.oldest_needs_attention_age_seconds == 300.0
    assert metrics.checkpoint_runs_observed == 4
    assert metrics.checkpoint_lag == 2
    assert metrics.checkpoint_problem_counts == {
        "checkpoint_drift": 1,
        "checkpoint_read_unavailable": 1,
    }
    assert metrics.projection_lag == 1
    assert metrics.oldest_projection_lag_seconds == 900.0
    assert metrics.reconciler_fix_counts == {"projection_completed": 1, "unknown": 2}
    assert metrics.alerts == (
        "chapter_workflow_checkpoint_lag",
        "chapter_workflow_checkpoint_unavailable",
        "chapter_workflow_command_rejected",
        "chapter_workflow_needs_attention",
        "chapter_workflow_projection_lag",
        "chapter_workflow_reconciler_repairs",
        "chapter_workflow_waiting_stuck",
    )
    assert "must-not-appear" not in repr(metrics)


async def test_workflow_metrics_validate_windows_without_querying(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        service = ChapterWorkflowObservabilityService(
            session,
            checkpoint_reader=_CheckpointReader({}),
        )
        with pytest.raises(ValueError, match="window_seconds"):
            await service.get_runtime_metrics(window_seconds=0)
        with pytest.raises(ValueError, match="alert threshold"):
            await service.get_runtime_metrics(waiting_alert_after_seconds=0)
