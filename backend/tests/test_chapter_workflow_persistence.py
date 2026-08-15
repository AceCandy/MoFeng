# AIMETA P=章节工作流候选事务持久化测试|R=fence_revision_回滚_并发重放_隐私|NR=不执行graph_interrupt或finalize|E=test_*|X=internal|A=integration_test|D=pytest|S=test|RD=./README.ai
from __future__ import annotations

import asyncio
from copy import deepcopy
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from test_chapter_workflow_context import _start_and_claim

from app.models import (
    BackgroundTask,
    Chapter,
    ChapterEvaluation,
    ChapterGenerationTrace,
    ChapterOutline,
    ChapterVersion,
    JobActivity,
    JobEvent,
)
from app.schemas.chapter_context import stable_digest
from app.services.chapter_workflow_activities import (
    ChapterWorkflowActivityRef,
    ChapterWorkflowCandidateInput,
    ChapterWorkflowCandidateOutput,
    ChapterWorkflowModelActivityService,
    ChapterWorkflowPlanInput,
    ChapterWorkflowPlanOutput,
    ChapterWorkflowPostReviewInput,
    ChapterWorkflowPostReviewOutput,
    ChapterWorkflowReviewInput,
    ChapterWorkflowReviewOutput,
)
from app.services.chapter_workflow_context import ChapterWorkflowContextService
from app.services.chapter_workflow_persistence import (
    ChapterWorkflowCandidatePersistenceService,
    ChapterWorkflowPersistCandidatesInput,
)
from app.services.job_registry import SideEffectClass
from app.services.job_service import LeaseLostError
from app.services.job_worker import JobExecutionContext
from app.services.novel_service import NovelService


def _ref(execution) -> ChapterWorkflowActivityRef:
    return ChapterWorkflowActivityRef(
        activity_key=execution.activity_key,
        result_hash=execution.result.result_hash,
    )


async def _build_inputs(isolated_pg, *, user_id: int, project_id: str):
    started, execution = await _start_and_claim(
        isolated_pg,
        user_id=user_id,
        project_id=project_id,
    )
    context = await ChapterWorkflowContextService(execution).execute_retrieval_activity()
    activities = ChapterWorkflowModelActivityService(execution)
    base = {
        "context_snapshot": context.result.context_snapshot,
        "context_activity_key": context.activity_key,
        "context_result_hash": context.result.result_hash,
    }

    async def plan_provider(_request, *, provider_request_key):
        assert provider_request_key
        return ChapterWorkflowPlanOutput(mission={"goal": "PRIVATE_MISSION"})

    plan_input = ChapterWorkflowPlanInput(**base)
    plan = await activities.execute_plan(plan_input, plan_provider)

    async def candidate_provider(request, *, provider_request_key):
        assert provider_request_key
        return ChapterWorkflowCandidateOutput(
            ordinal=request.ordinal,
            content=f"PRIVATE_CANDIDATE_{request.ordinal}",
            metadata={"provider": "test"},
        )

    candidates = []
    for ordinal in (1, 2):
        candidate_input = ChapterWorkflowCandidateInput(
            **base,
            upstream_refs={"plan": _ref(plan)},
            plan=plan.result.output,
            ordinal=ordinal,
        )
        candidates.append(await activities.execute_candidate(candidate_input, candidate_provider))

    async def review_provider(_request, *, provider_request_key):
        assert provider_request_key
        return ChapterWorkflowReviewOutput(
            best_ordinal=2,
            report={"summary": "PRIVATE_REVIEW"},
        )

    review_input = ChapterWorkflowReviewInput(
        **base,
        upstream_refs={
            "plan": _ref(plan),
            **{
                f"candidate:{candidate.result.output.ordinal}": _ref(candidate)
                for candidate in candidates
            },
        },
        plan=plan.result.output,
        candidates=[candidate.result.output for candidate in candidates],
    )
    review = await activities.execute_review(review_input, review_provider)

    async def post_provider(request, *, provider_request_key):
        assert provider_request_key
        return ChapterWorkflowPostReviewOutput(
            stage=request.stage,
            content="PRIVATE_REFINED_CANDIDATE_2",
            report={"fixed": "PRIVATE_FIX"},
        )

    post_input = ChapterWorkflowPostReviewInput(
        **base,
        upstream_refs={
            "candidate:2": _ref(candidates[1]),
            "review:version_review": _ref(review),
        },
        source_candidate=candidates[1].result.output,
        review=review.result.output,
        stage="consistency",
    )
    post = await activities.execute_post_review(post_input, post_provider)
    request = ChapterWorkflowPersistCandidatesInput(
        candidate_refs=[_ref(candidate) for candidate in candidates],
        review_ref=_ref(review),
        post_review_refs={2: [_ref(post)]},
    )
    return started, execution, request


@pytest.mark.asyncio(loop_scope="session")
async def test_persist_drafts_is_atomic_private_and_replayable(isolated_pg):
    started, execution, request = await _build_inputs(
        isolated_pg,
        user_id=4401,
        project_id="workflow-persist-candidates",
    )
    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
        assert chapter is not None
        selected = ChapterVersion(
            chapter_id=chapter.id,
            version_label="current",
            content="CURRENT_CANONICAL_CONTENT",
        )
        session.add(selected)
        await session.flush()
        chapter.selected_version_id = selected.id
        session.add(
            ChapterEvaluation(
                chapter_id=chapter.id,
                version_id=selected.id,
                decision="legacy_review",
                feedback="CURRENT_CANONICAL_REVIEW",
            )
        )
        await session.commit()
        selected_id = selected.id

    service = ChapterWorkflowCandidatePersistenceService(execution)
    first = await service.execute(request)
    replay = await service.execute(request)

    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
        versions = list(
            (
                await session.execute(
                    select(ChapterVersion)
                    .where(ChapterVersion.chapter_id == started.run.chapter_id)
                    .order_by(ChapterVersion.id)
                )
            ).scalars()
        )
        evaluations = list(
            (
                await session.execute(
                    select(ChapterEvaluation).where(
                        ChapterEvaluation.chapter_id == started.run.chapter_id
                    )
                )
            ).scalars()
        )
        activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key == first.activity_key,
                )
            )
        ).scalar_one()
        events = list(
            (
                await session.execute(
                    select(JobEvent).where(JobEvent.job_id == started.root_job.id)
                )
            ).scalars()
        )

    assert replay == first
    candidate_versions = [
        version for version in versions if version.id in first.result.candidate_version_ids
    ]
    assert [version.id for version in candidate_versions] == (first.result.candidate_version_ids)
    assert [version.content for version in candidate_versions] == [
        "PRIVATE_CANDIDATE_1",
        "PRIVATE_REFINED_CANDIDATE_2",
    ]
    assert chapter is not None and chapter.status == "waiting_for_confirm"
    assert chapter.selected_version_id == selected_id
    assert next(version for version in versions if version.id == selected_id).content == (
        "CURRENT_CANONICAL_CONTENT"
    )
    assert len(evaluations) == 2
    assert any(
        evaluation.version_id == selected_id and evaluation.decision == "legacy_review"
        for evaluation in evaluations
    )
    assert any(
        evaluation.version_id == candidate_versions[1].id and evaluation.decision == "ai_review"
        for evaluation in evaluations
    )
    assert activity.side_effect_class == SideEffectClass.TRANSACTIONAL.value
    assert "PRIVATE" not in str(activity.request_payload)
    assert "PRIVATE" not in str(activity.result_payload)
    assert all("PRIVATE" not in str(event.payload) for event in events)
    assert first.state_update() == {
        "node_key": "wait_for_selection",
        "candidate_version_ids": first.result.candidate_version_ids,
        "activity_refs": {"persist_drafts": first.activity_key},
        "result_refs": {"persist_drafts": first.result.result_hash},
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_durable_best_version_is_the_only_public_confirmation_candidate(isolated_pg):
    started, execution, request = await _build_inputs(
        isolated_pg,
        user_id=4410,
        project_id="workflow-best-confirmation",
    )

    persisted = await ChapterWorkflowCandidatePersistenceService(execution).execute(request)

    async with isolated_pg.session_factory() as session:
        result = await session.execute(
            select(Chapter)
            .options(
                selectinload(Chapter.versions),
                selectinload(Chapter.evaluations),
            )
            .where(Chapter.id == started.run.chapter_id)
        )
        chapter = result.scalars().one()
        outline = await session.scalar(
            select(ChapterOutline).where(
                ChapterOutline.project_id == started.run.project_id,
                ChapterOutline.chapter_number == started.run.chapter_number,
            )
        )
        schema = NovelService(session)._build_chapter_schema_from_entities(
            chapter_number=started.run.chapter_number,
            outline=outline,
            chapter=chapter,
        )

        candidate_versions = [
            version
            for version in chapter.versions
            if version.id in persisted.result.candidate_version_ids
        ]
        assert [version.metadata["ai_review"]["is_best"] for version in candidate_versions] == [
            False,
            True,
        ]
        assert schema.versions == ["PRIVATE_CANDIDATE_1", "PRIVATE_REFINED_CANDIDATE_2"]
        assert schema.version_selections is not None
        assert [(item.id, item.content) for item in schema.version_selections] == [
            (candidate_versions[1].id, "PRIVATE_REFINED_CANDIDATE_2")
        ]
        assert any(
            evaluation.version_id == candidate_versions[1].id
            and evaluation.decision == "ai_review"
            for evaluation in chapter.evaluations
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_persist_drafts_rolls_back_domain_rows_with_activity(isolated_pg):
    started, execution, request = await _build_inputs(
        isolated_pg,
        user_id=4402,
        project_id="workflow-persist-rollback",
    )

    class FailingPersistenceService(ChapterWorkflowCandidatePersistenceService):
        async def _write_candidates(self, **kwargs):
            await super()._write_candidates(**kwargs)
            raise RuntimeError("injected persistence failure")

    with pytest.raises(RuntimeError, match="injected persistence failure"):
        await FailingPersistenceService(execution).execute(request)

    async with isolated_pg.session_factory() as session:
        version_count = await session.scalar(
            select(func.count(ChapterVersion.id)).where(
                ChapterVersion.chapter_id == started.run.chapter_id
            )
        )
        persist_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key.like("wf:persist_drafts:%"),
                )
            )
        ).scalar_one()
    assert version_count == 0
    assert persist_activity.status == "started"
    assert persist_activity.result_payload is None

    completed = await ChapterWorkflowCandidatePersistenceService(execution).execute(request)
    assert len(completed.result.candidate_version_ids) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_persist_drafts_rejects_revision_drift_before_intent(isolated_pg):
    started, execution, request = await _build_inputs(
        isolated_pg,
        user_id=4403,
        project_id="workflow-persist-revision-drift",
    )
    async with isolated_pg.session_factory() as session:
        chapter = await session.get(Chapter, started.run.chapter_id)
        assert chapter is not None
        chapter.current_revision += 1
        await session.commit()

    with pytest.raises(ValueError, match="revision 已漂移"):
        await ChapterWorkflowCandidatePersistenceService(execution).execute(request)

    async with isolated_pg.session_factory() as session:
        persist_count = await session.scalar(
            select(func.count(JobActivity.id)).where(
                JobActivity.job_id == started.root_job.id,
                JobActivity.activity_key.like("wf:persist_drafts:%"),
            )
        )
    assert persist_count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_persist_drafts_rejects_cross_wired_review_before_intent(isolated_pg):
    started, execution, request = await _build_inputs(
        isolated_pg,
        user_id=4406,
        project_id="workflow-persist-provenance-drift",
    )
    assert request.review_ref is not None
    async with isolated_pg.session_factory() as session:
        review_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key == request.review_ref.activity_key,
                )
            )
        ).scalar_one()
        payload = deepcopy(review_activity.result_payload)
        payload["upstream_result_hashes"]["candidate:2"] = "f" * 64
        payload["result_hash"] = stable_digest(
            {key: value for key, value in payload.items() if key != "result_hash"}
        )
        review_activity.result_payload = payload
        await session.commit()

    cross_wired = request.model_copy(
        update={
            "review_ref": ChapterWorkflowActivityRef(
                activity_key=request.review_ref.activity_key,
                result_hash=payload["result_hash"],
            )
        }
    )
    with pytest.raises(ValueError, match="未绑定当前候选集合"):
        await ChapterWorkflowCandidatePersistenceService(execution).execute(cross_wired)

    async with isolated_pg.session_factory() as session:
        persist_count = await session.scalar(
            select(func.count(JobActivity.id)).where(
                JobActivity.job_id == started.root_job.id,
                JobActivity.activity_key.like("wf:persist_drafts:%"),
            )
        )
    assert persist_count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_persist_drafts_concurrent_replay_writes_one_version_set(isolated_pg):
    started, execution, request = await _build_inputs(
        isolated_pg,
        user_id=4404,
        project_id="workflow-persist-concurrent",
    )
    second_execution = JobExecutionContext(
        lease=execution.lease,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        session_factory=isolated_pg.session_factory,
    )
    first, second = await asyncio.gather(
        ChapterWorkflowCandidatePersistenceService(execution).execute(request),
        ChapterWorkflowCandidatePersistenceService(second_execution).execute(request),
    )

    async with isolated_pg.session_factory() as session:
        versions = list(
            (
                await session.execute(
                    select(ChapterVersion).where(
                        ChapterVersion.chapter_id == started.run.chapter_id
                    )
                )
            ).scalars()
        )
    assert first == second
    assert len(versions) == 2
    assert sorted(version.id for version in versions) == sorted(first.result.candidate_version_ids)


@pytest.mark.asyncio(loop_scope="session")
async def test_persist_drafts_rejects_stale_fence_and_ignores_trace(isolated_pg):
    started, execution, request = await _build_inputs(
        isolated_pg,
        user_id=4405,
        project_id="workflow-persist-stale-fence",
    )
    async with isolated_pg.session_factory() as session:
        job = await session.get(BackgroundTask, started.root_job.id)
        assert job is not None
        trace_count_before = await session.scalar(
            select(func.count(ChapterGenerationTrace.id)).where(
                ChapterGenerationTrace.source_run_id == started.run.id
            )
        )
        job.fencing_token += 1
        await session.commit()

    with pytest.raises(LeaseLostError):
        await ChapterWorkflowCandidatePersistenceService(execution).execute(request)

    async with isolated_pg.session_factory() as session:
        assert await session.scalar(select(func.count(ChapterVersion.id))) == 0
        trace_count_after = await session.scalar(
            select(func.count(ChapterGenerationTrace.id)).where(
                ChapterGenerationTrace.source_run_id == started.run.id
            )
        )

    assert trace_count_after == trace_count_before

    source = Path("app/services/chapter_workflow_persistence.py").read_text(encoding="utf-8")
    assert "clear_from_node" not in source
    assert "generation_trace" not in source.lower()
