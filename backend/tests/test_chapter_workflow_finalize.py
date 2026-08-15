# AIMETA P=章节工作流事务定稿测试|R=原子canonical写入_replay_回滚_隐私|NR=不观察projection完成|E=test_*|X=internal|A=integration_test|D=pytest,postgresql|S=test|RD=../app/services/README.ai
from __future__ import annotations

import json
from typing import cast

import pytest
from sqlalchemy import func, select
from test_chapter_workflow_start import _seed_project

from app.models import (
    BackgroundTask,
    Chapter,
    ChapterOutboxEvent,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
    ChapterVersion,
    JobActivity,
)
from app.schemas.chapter_context import stable_digest
from app.schemas.chapter_workflow import ChapterWorkflowState
from app.schemas.job import ChapterOutboxDispatchJobPayload, ChapterProjectionJobPayload
from app.schemas.novel import ChapterGenerationStatus
from app.services.chapter_finalize_service import ChapterFinalizeSubmissionService
from app.services.chapter_outbox_dispatcher import ChapterOutboxDispatcher
from app.services.chapter_projection_runtime import (
    CurrentProjection,
    enqueue_downstream_projections,
    maybe_enqueue_reconciler,
)
from app.services.chapter_workflow_finalize import (
    ChapterWorkflowFinalizeInput,
    ChapterWorkflowFinalizeService,
)
from app.services.chapter_workflow_handler import (
    ChapterWorkflowBindingAssembler,
    ChapterWorkflowProviders,
)
from app.services.chapter_workflow_start import ChapterWorkflowStartService
from app.services.job_registry import SideEffectClass
from app.services.job_service import JobService
from app.services.job_worker import JobExecutionContext


async def _start_claim_with_candidate(
    isolated_pg,
    *,
    user_id: int,
    project_id: str,
    content: str,
):
    session_factory = isolated_pg.session_factory
    async with session_factory() as session:
        await _seed_project(session, user_id=user_id, project_id=project_id)
        started = await ChapterWorkflowStartService(session).start(
            user_id=user_id,
            project_id=project_id,
            chapter_number=1,
            flow_config={"preset": "basic", "enable_rag": False},
        )
        chapter = await session.get(Chapter, started.run.chapter_id)
        assert chapter is not None
        version = ChapterVersion(
            chapter_id=chapter.id,
            version_label="v1",
            content=content,
            metadata={
                "_chapter_workflow": {
                    "run_id": started.run.id,
                    "ordinal": 1,
                    "content_hash": stable_digest(content),
                }
            },
        )
        session.add(version)
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        await session.commit()
        await session.refresh(version)
        lease = await JobService(session).claim_next(
            worker_id=f"finalize-{user_id}",
            lease_seconds=60,
        )
    assert lease is not None
    execution = JobExecutionContext(
        lease=lease,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        session_factory=session_factory,
    )
    request = ChapterWorkflowFinalizeInput(
        run_id=started.run.id,
        candidate_version_ids=[version.id],
        selected_version_id=version.id,
    )
    return started, execution, request


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_activity_atomically_writes_canonical_lineage_and_replays(
    isolated_pg,
):
    content = "workflow canonical 正文"
    started, execution, request = await _start_claim_with_candidate(
        isolated_pg,
        user_id=4701,
        project_id="workflow-finalize-success",
        content=content,
    )
    service = ChapterWorkflowFinalizeService(execution)

    first = await service.execute(request)
    replay = await service.execute(request)
    binding_replay = await ChapterWorkflowBindingAssembler(
        execution,
        cast(ChapterWorkflowProviders, object()),
    ).finalize_revision(
        ChapterWorkflowState(
            run_id=started.run.id,
            node_key="finalize_revision",
            context_hash=started.run.context_hash,
            candidate_version_ids=request.candidate_version_ids,
            selected_version_id=request.selected_version_id,
        )
    )

    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
        revision = (
            await session.execute(
                select(ChapterRevision).where(ChapterRevision.chapter_id == started.run.chapter_id)
            )
        ).scalar_one()
        outbox = (
            await session.execute(
                select(ChapterOutboxEvent).where(
                    ChapterOutboxEvent.chapter_id == started.run.chapter_id
                )
            )
        ).scalar_one()
        dispatcher = await session.get(BackgroundTask, first.result.dispatcher_job_id)
        activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key == first.activity_key,
                )
            )
        ).scalar_one()
        revision_count = await session.scalar(
            select(func.count(ChapterRevision.id)).where(
                ChapterRevision.chapter_id == started.run.chapter_id
            )
        )
        outbox_count = await session.scalar(
            select(func.count(ChapterOutboxEvent.id)).where(
                ChapterOutboxEvent.chapter_id == started.run.chapter_id
            )
        )

    assert replay == first
    assert binding_replay == first.state_update()
    assert chapter is not None
    assert chapter.current_revision == first.result.target_chapter_revision == 1
    assert chapter.selected_version_id == request.selected_version_id
    assert chapter.source_hash == stable_digest(content)
    assert revision.selected_version_id == request.selected_version_id
    assert revision.source_content == content
    assert outbox.workflow_stream_id == started.run.id
    assert outbox.payload["workflow_stream_id"] == started.run.id
    assert dispatcher is not None and dispatcher.stream_id == started.run.id
    assert activity.status == "succeeded"
    assert activity.side_effect_class == SideEffectClass.TRANSACTIONAL.value
    assert revision_count == 1
    assert outbox_count == 1
    assert first.state_update() == {
        "target_chapter_revision": 1,
        "activity_refs": {"finalize_revision": first.activity_key},
        "result_refs": {"finalize_revision": first.result.result_hash},
    }
    assert content not in json.dumps(activity.request_payload, ensure_ascii=False)
    assert content not in json.dumps(activity.result_payload, ensure_ascii=False)
    assert content not in json.dumps(first.state_update(), ensure_ascii=False)


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_activity_rolls_back_domain_writes_when_apply_fails(
    isolated_pg,
    monkeypatch,
):
    started, execution, request = await _start_claim_with_candidate(
        isolated_pg,
        user_id=4702,
        project_id="workflow-finalize-rollback",
        content="rollback canonical 正文",
    )
    original_apply = ChapterFinalizeSubmissionService.apply

    async def fail_after_apply(self, prepared, *, workflow_stream_id=None):
        await original_apply(
            self,
            prepared,
            workflow_stream_id=workflow_stream_id,
        )
        raise RuntimeError("injected finalize failure")

    monkeypatch.setattr(ChapterFinalizeSubmissionService, "apply", fail_after_apply)

    with pytest.raises(RuntimeError, match="injected finalize failure"):
        await ChapterWorkflowFinalizeService(execution).execute(request)

    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
        activity = (
            await session.execute(
                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
            )
        ).scalar_one()
        revision_count = await session.scalar(
            select(func.count(ChapterRevision.id)).where(
                ChapterRevision.chapter_id == started.run.chapter_id
            )
        )
        outbox_count = await session.scalar(
            select(func.count(ChapterOutboxEvent.id)).where(
                ChapterOutboxEvent.chapter_id == started.run.chapter_id
            )
        )
        dispatcher_count = await session.scalar(
            select(func.count(BackgroundTask.id)).where(
                BackgroundTask.task_type == "chapter_outbox_dispatch"
            )
        )

    assert chapter is not None
    assert chapter.current_revision == 0
    assert chapter.status == ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
    assert chapter.selected_version_id is None
    assert activity.status == "started"
    assert activity.result_payload is None
    assert revision_count == 0
    assert outbox_count == 0
    assert dispatcher_count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_activity_rechecks_revision_after_intent_commit(
    isolated_pg,
    monkeypatch,
):
    started, execution, request = await _start_claim_with_candidate(
        isolated_pg,
        user_id=4703,
        project_id="workflow-finalize-revision-drift",
        content="revision drift 正文",
    )
    original_begin = execution.begin_activity

    async def begin_then_drift(*args, **kwargs):
        activity = await original_begin(*args, **kwargs)
        async with isolated_pg.session_factory() as session:
            chapter = await session.get(Chapter, started.run.chapter_id)
            assert chapter is not None
            chapter.current_revision = 1
            await session.commit()
        return activity

    monkeypatch.setattr(execution, "begin_activity", begin_then_drift)

    with pytest.raises(ValueError, match="revision 已漂移"):
        await ChapterWorkflowFinalizeService(execution).execute(request)

    async with isolated_pg.session_factory() as session:
        activity = (
            await session.execute(
                select(JobActivity).where(JobActivity.job_id == started.root_job.id)
            )
        ).scalar_one()
        revision_count = await session.scalar(select(func.count(ChapterRevision.id)))
        outbox_count = await session.scalar(select(func.count(ChapterOutboxEvent.id)))
        dispatcher_count = await session.scalar(
            select(func.count(BackgroundTask.id)).where(
                BackgroundTask.task_type == "chapter_outbox_dispatch"
            )
        )

    assert activity.status == "started"
    assert activity.result_payload is None
    assert revision_count == 0
    assert outbox_count == 0
    assert dispatcher_count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_projection_jobs_keep_workflow_stream_until_reconciler(
    isolated_pg,
):
    started, execution, request = await _start_claim_with_candidate(
        isolated_pg,
        user_id=4704,
        project_id="workflow-finalize-lineage",
        content="projection lineage 正文",
    )
    finalized = await ChapterWorkflowFinalizeService(execution).execute(request)

    async with isolated_pg.session_factory() as session:
        dispatcher_job = await session.get(
            BackgroundTask,
            finalized.result.dispatcher_job_id,
        )
        assert dispatcher_job is not None
        await ChapterOutboxDispatcher(session).dispatch(
            command=ChapterOutboxDispatchJobPayload.model_validate(dispatcher_job.payload),
            user_id=4704,
        )
        await session.commit()

    async with isolated_pg.session_factory() as session:
        summary_job = (
            await session.execute(
                select(BackgroundTask).where(
                    BackgroundTask.project_id == started.run.project_id,
                    BackgroundTask.task_type == "chapter_finalize",
                    BackgroundTask.payload_version == 2,
                )
            )
        ).scalar_one()
        summary_run = (
            await session.execute(
                select(ChapterProjectionRun).where(ChapterProjectionRun.job_id == summary_job.id)
            )
        ).scalar_one()
        chapter = await session.get(Chapter, started.run.chapter_id)
        revision = await session.get(
            ChapterRevision,
            finalized.result.chapter_revision_id,
        )
        rollout = (
            await session.execute(
                select(ChapterProjectionRollout).where(
                    ChapterProjectionRollout.chapter_id == started.run.chapter_id
                )
            )
        ).scalar_one()
        assert chapter is not None and revision is not None
        summary_run.status = "succeeded"
        summary_run.is_active = True
        summary_payload = ChapterProjectionJobPayload.model_validate(summary_job.payload)
        current = CurrentProjection(chapter, revision, summary_run, rollout, None)
        downstream = await enqueue_downstream_projections(
            session,
            payload=summary_payload,
            current=current,
            user_id=4704,
        )
        for run in downstream:
            if run.required:
                run.status = "succeeded"
                run.is_active = True
        reconciler = await maybe_enqueue_reconciler(
            session,
            payload=summary_payload,
            current=current,
            user_id=4704,
        )
        assert reconciler is not None and reconciler.job_id is not None
        await session.commit()

    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
        jobs = list(
            (
                await session.execute(
                    select(BackgroundTask).where(
                        BackgroundTask.project_id == started.run.project_id,
                        BackgroundTask.task_type.in_(
                            (
                                "chapter_outbox_dispatch",
                                "chapter_finalize",
                                "chapter_projection_memory",
                                "chapter_projection_rag",
                                "chapter_projection_foreshadowing",
                                "chapter_projection_trace",
                                "chapter_projection_reconcile",
                            )
                        ),
                    )
                )
            ).scalars()
        )

    assert chapter is not None
    assert chapter.status == ChapterGenerationStatus.FINALIZING.value
    assert {job.task_type for job in jobs} >= {
        "chapter_outbox_dispatch",
        "chapter_finalize",
        "chapter_projection_memory",
        "chapter_projection_foreshadowing",
        "chapter_projection_trace",
        "chapter_projection_reconcile",
    }
    assert all(job.stream_type == "workflow" for job in jobs)
    assert all(job.stream_id == started.run.id for job in jobs)
    assert all(
        job.payload.get("workflow_stream_id") == started.run.id
        for job in jobs
        if job.task_type != "chapter_outbox_dispatch"
    )
