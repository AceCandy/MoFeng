# AIMETA P=章节工作流模型activity测试|R=稳定阶段key_私有结果重放_ambiguity停止|NR=不持久化候选或执行完整graph|E=test_*|X=internal|A=integration_test|D=pytest|S=test|RD=./README.ai
from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_chapter_workflow_context import _start_and_claim

from app.models import AIUsageRecord, BackgroundTask, ChapterWorkflowRun, JobActivity
from app.schemas.chapter_context import ChapterContext
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
from app.services.chapter_workflow_handler import ChapterWorkflowLLMProvidersV1
from app.services.job_registry import SideEffectClass
from app.services.job_service import AmbiguousActivityError
from app.services.llm_service import LLMService
from app.utils.ai_telemetry import AICallResult, TokenUsage


def _activity_ref(execution) -> ChapterWorkflowActivityRef:
    return ChapterWorkflowActivityRef(
        activity_key=execution.activity_key,
        result_hash=execution.result.result_hash,
    )


async def _context_and_service(isolated_pg, *, user_id: int, project_id: str):
    started, execution = await _start_and_claim(
        isolated_pg,
        user_id=user_id,
        project_id=project_id,
    )
    context = await ChapterWorkflowContextService(execution).execute_retrieval_activity()
    return (
        started,
        execution,
        context,
        ChapterWorkflowModelActivityService(execution),
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_production_llm_providers_forward_stable_provider_request_keys(
    isolated_pg,
    monkeypatch,
):
    _started, execution, context, _service = await _context_and_service(
        isolated_pg,
        user_id=4300,
        project_id="workflow-production-provider-keys",
    )
    calls: list[tuple[str, str | None]] = []
    responses = {
        "chapter_mission": '{"mission":{"goal":"推进冲突"}}',
        "chapter_writing": '{"content":"候选正文"}',
        "version_review": '{"best_ordinal":1}',
        "chapter_optimization": '{"content":"修订正文"}',
    }

    async def fake_prompt(_self, name, *, fallback=None):
        return f"prompt:{name}:{fallback or ''}"

    async def fake_detached(*, stage, provider_request_key=None, **_kwargs):
        calls.append((stage, provider_request_key))
        return AICallResult(
            value=responses[stage],
            provider_type="openai_compatible",
            model="test-model",
            model_id=None,
            stage=stage,
            usage=TokenUsage(
                input_tokens=1,
                output_tokens=1,
                total_tokens=2,
                cached_input_tokens=0,
                cache_write_input_tokens=0,
                reasoning_tokens=0,
                is_complete=True,
            ),
            cost_amount=None,
            cost_currency=None,
            cost_unknown_reason="pricing_unconfigured",
        )

    monkeypatch.setattr(ChapterWorkflowLLMProvidersV1, "_prompt", fake_prompt)
    monkeypatch.setattr(
        LLMService,
        "get_llm_response_result_detached",
        staticmethod(fake_detached),
    )
    provider = ChapterWorkflowLLMProvidersV1(execution)
    common_input = {
        "context_snapshot": context.result.context_snapshot,
        "context_activity_key": context.activity_key,
        "context_result_hash": context.result.result_hash,
    }

    plan = await provider.plan(
        ChapterWorkflowPlanInput(**common_input),
        provider_request_key="provider-key-plan",
    )
    candidate = await provider.candidate(
        ChapterWorkflowCandidateInput(
            **common_input,
            plan=plan.value,
            ordinal=1,
        ),
        provider_request_key="provider-key-candidate",
    )
    review = await provider.review(
        ChapterWorkflowReviewInput(
            **common_input,
            plan=plan.value,
            candidates=[
                candidate.value,
                ChapterWorkflowCandidateOutput(ordinal=2, content="候选正文二"),
            ],
        ),
        provider_request_key="provider-key-review",
    )
    assert isinstance(review, AICallResult)
    await provider.post_review(
        ChapterWorkflowPostReviewInput(
            **common_input,
            source_candidate=candidate.value,
            review=review.value,
            stage="consistency",
        ),
        provider_request_key="provider-key-post-review",
    )

    single_review = await provider.review(
        ChapterWorkflowReviewInput(
            **common_input,
            plan=plan.value,
            candidates=[candidate.value],
        ),
        provider_request_key="unused-single-review-key",
    )

    assert calls == [
        ("chapter_mission", "provider-key-plan"),
        ("chapter_writing", "provider-key-candidate"),
        ("version_review", "provider-key-review"),
        ("chapter_optimization", "provider-key-post-review"),
    ]
    assert single_review.best_ordinal == 1
    assert single_review.report["mode"] == "single"


@pytest.mark.asyncio(loop_scope="session")
async def test_model_activities_replay_by_stable_ordinal_and_stage_with_private_results(
    isolated_pg,
):
    started, _execution, context, service = await _context_and_service(
        isolated_pg,
        user_id=4301,
        project_id="workflow-model-activities",
    )
    calls = {"plan": 0, "candidate": 0, "review": 0, "post": 0}

    plan_input = ChapterWorkflowPlanInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
        planning_options={"directive": "PRIVATE_PLAN_DIRECTIVE"},
    )

    async def plan_provider(_request, *, provider_request_key):
        assert provider_request_key
        calls["plan"] += 1
        return AICallResult(
            value=ChapterWorkflowPlanOutput(
                mission={"goal": "PRIVATE_MISSION"},
                allowed_new_characters=["顾遥"],
            ),
            provider_type="openai_compatible",
            model="test-model",
            model_id=None,
            stage="chapter_plan",
            usage=TokenUsage(
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                cached_input_tokens=0,
                cache_write_input_tokens=0,
                reasoning_tokens=0,
                is_complete=True,
            ),
            cost_amount=None,
            cost_currency=None,
            cost_unknown_reason="pricing_unconfigured",
        )

    plan = await service.execute_plan(plan_input, plan_provider)
    assert await service.execute_plan(plan_input, plan_provider) == plan

    async def candidate_provider(request, *, provider_request_key):
        assert provider_request_key
        calls["candidate"] += 1
        return ChapterWorkflowCandidateOutput(
            ordinal=request.ordinal,
            content=f"PRIVATE_CANDIDATE_{request.ordinal}",
            metadata={"provider": "test"},
        )

    candidate_one_input = ChapterWorkflowCandidateInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
        upstream_refs={"plan": _activity_ref(plan)},
        plan=plan.result.output,
        ordinal=1,
        style_hint="冷峻",
    )
    candidate_two_input = candidate_one_input.model_copy(update={"ordinal": 2})
    candidate_one = await service.execute_candidate(
        candidate_one_input,
        candidate_provider,
    )
    candidate_two = await service.execute_candidate(
        candidate_two_input,
        candidate_provider,
    )
    assert await service.execute_candidate(candidate_one_input, candidate_provider) == candidate_one

    review_input = ChapterWorkflowReviewInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
        upstream_refs={
            "plan": _activity_ref(plan),
            "candidate:1": _activity_ref(candidate_one),
            "candidate:2": _activity_ref(candidate_two),
        },
        plan=plan.result.output,
        candidates=[candidate_one.result.output, candidate_two.result.output],
    )

    async def review_provider(_request, *, provider_request_key):
        assert provider_request_key
        calls["review"] += 1
        return ChapterWorkflowReviewOutput(
            best_ordinal=2,
            report={"summary": "PRIVATE_REVIEW"},
        )

    review = await service.execute_review(review_input, review_provider)
    assert await service.execute_review(review_input, review_provider) == review

    post_input = ChapterWorkflowPostReviewInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
        upstream_refs={
            "candidate:2": _activity_ref(candidate_two),
            "review:version_review": _activity_ref(review),
        },
        source_candidate=candidate_two.result.output,
        review=review.result.output,
        stage="consistency",
    )

    async def post_provider(request, *, provider_request_key):
        assert provider_request_key
        calls["post"] += 1
        return ChapterWorkflowPostReviewOutput(
            stage=request.stage,
            content="PRIVATE_REFINED_CONTENT",
            report={"fixed": True},
        )

    post = await service.execute_post_review(post_input, post_provider)
    assert await service.execute_post_review(post_input, post_provider) == post

    assert calls == {"plan": 1, "candidate": 2, "review": 1, "post": 1}
    assert candidate_one.activity_key != candidate_two.activity_key

    executions = [plan, candidate_one, candidate_two, review, post]
    for execution in executions:
        state_update = execution.state_update()
        assert set(state_update) == {"activity_refs", "result_refs"}
        assert "content" not in str(state_update).lower()
        assert "PRIVATE" not in str(state_update)

    async with isolated_pg.session_factory() as session:
        activities = list(
            (
                await session.execute(
                    select(JobActivity)
                    .where(
                        JobActivity.job_id == started.root_job.id,
                        JobActivity.activity_key.like("wf:%"),
                        JobActivity.activity_key.not_like("wf:freeze_context:%"),
                    )
                    .order_by(JobActivity.activity_key)
                )
            ).scalars()
        )
        usage_records = list(
            (
                await session.execute(
                    select(AIUsageRecord).where(AIUsageRecord.job_id == started.root_job.id)
                )
            ).scalars()
        )

    assert len(activities) == 5
    assert all(
        activity.side_effect_class == SideEffectClass.AMBIGUOUS_EXTERNAL.value
        for activity in activities
    )
    assert all("PRIVATE" not in str(activity.request_payload) for activity in activities)
    assert any("PRIVATE_CANDIDATE_1" in str(activity.result_payload) for activity in activities)
    assert any("PRIVATE_REFINED_CONTENT" in str(activity.result_payload) for activity in activities)
    assert len(usage_records) == 1
    assert usage_records[0].stage == "chapter_plan"
    assert usage_records[0].total_tokens == 15


@pytest.mark.asyncio(loop_scope="session")
async def test_model_activity_provider_uncertainty_stops_run_without_automatic_replay(
    isolated_pg,
):
    started, _execution, context, service = await _context_and_service(
        isolated_pg,
        user_id=4302,
        project_id="workflow-model-ambiguous",
    )
    request = ChapterWorkflowPlanInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
    )
    calls = 0

    async def uncertain_provider(_request, *, provider_request_key):
        nonlocal calls
        assert provider_request_key
        calls += 1
        raise RuntimeError("provider response may have been delivered: SECRET_TOKEN")

    with pytest.raises(AmbiguousActivityError, match="结果未知"):
        await service.execute_plan(request, uncertain_provider)

    async with isolated_pg.session_factory() as session:
        activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key.like("wf:plan_and_direct:%"),
                )
            )
        ).scalar_one()
        job = await session.get(BackgroundTask, started.root_job.id)
        run = await session.get(ChapterWorkflowRun, started.run.id)

    assert calls == 1
    assert activity.status == "ambiguous"
    assert activity.result_payload is None
    assert job is not None and job.status == "needs_attention"
    assert run is not None and run.status == "needs_attention" and run.is_active is True
    assert "SECRET_TOKEN" not in (job.error or "")


@pytest.mark.asyncio(loop_scope="session")
async def test_model_activity_replay_rejects_tampered_private_result(isolated_pg):
    started, _execution, context, service = await _context_and_service(
        isolated_pg,
        user_id=4303,
        project_id="workflow-model-result-drift",
    )
    request = ChapterWorkflowPlanInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
    )
    calls = 0

    async def provider(_request, *, provider_request_key):
        nonlocal calls
        assert provider_request_key
        calls += 1
        return ChapterWorkflowPlanOutput(mission={"goal": "keep"})

    completed = await service.execute_plan(request, provider)
    async with isolated_pg.session_factory() as session:
        activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key == completed.activity_key,
                )
            )
        ).scalar_one()
        activity.result_payload = {
            **deepcopy(activity.result_payload),
            "result_hash": "f" * 64,
        }
        await session.commit()

    with pytest.raises(ValidationError, match="result hash"):
        await service.execute_plan(request, provider)
    assert calls == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_model_activity_rejects_unledgered_enriched_context_before_intent(
    isolated_pg,
):
    started, _execution, context, service = await _context_and_service(
        isolated_pg,
        user_id=4304,
        project_id="workflow-model-context-drift",
    )
    restored = ChapterContext.model_validate(context.result.context_snapshot)
    drifted_notes = restored.writing_notes.model_copy(
        update={"value": "UNLEDGERED_PRIVATE_CONTEXT"}
    )
    drifted = restored.with_updates(writing_notes=drifted_notes)
    request = ChapterWorkflowPlanInput(
        context_snapshot=drifted.snapshot_payload(),
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
    )

    async def provider(_request, *, provider_request_key):
        raise AssertionError(provider_request_key)

    with pytest.raises(ValueError, match="retrieval result"):
        await service.execute_plan(request, provider)

    async with isolated_pg.session_factory() as session:
        plan_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key.like("wf:plan_and_direct:%"),
                )
            )
        ).scalar_one_or_none()
    assert plan_activity is None


@pytest.mark.asyncio(loop_scope="session")
async def test_candidate_activity_rejects_unledgered_plan_before_intent(isolated_pg):
    started, _execution, context, service = await _context_and_service(
        isolated_pg,
        user_id=4305,
        project_id="workflow-model-plan-drift",
    )

    async def plan_provider(_request, *, provider_request_key):
        assert provider_request_key
        return ChapterWorkflowPlanOutput(mission={"goal": "ledgered"})

    plan_input = ChapterWorkflowPlanInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
    )
    plan = await service.execute_plan(plan_input, plan_provider)
    drifted_plan = plan.result.output.model_copy(
        update={"mission": {"goal": "UNLEDGERED_PRIVATE_PLAN"}}
    )
    candidate_input = ChapterWorkflowCandidateInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
        upstream_refs={"plan": _activity_ref(plan)},
        plan=drifted_plan,
        ordinal=1,
    )

    async def candidate_provider(_request, *, provider_request_key):
        raise AssertionError(provider_request_key)

    with pytest.raises(ValueError, match="上游结果"):
        await service.execute_candidate(candidate_input, candidate_provider)

    async with isolated_pg.session_factory() as session:
        candidate_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key.like("wf:generate_candidates:%"),
                )
            )
        ).scalar_one_or_none()
    assert candidate_activity is None
