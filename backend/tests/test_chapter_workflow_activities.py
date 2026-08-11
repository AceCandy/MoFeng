# AIMETA P=章节工作流模型activity测试|R=稳定阶段key_私有结果重放_ambiguity停止|NR=不持久化候选或执行完整graph|E=test_*|X=internal|A=integration_test|D=pytest|S=test|RD=./README.ai
from __future__ import annotations

import json
import logging
from copy import deepcopy
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from test_chapter_workflow_context import _start_and_claim

from app.models import (
    AIUsageRecord,
    BackgroundTask,
    ChapterWorkflowRun,
    JobActivity,
    SystemConfig,
)
from app.schemas.chapter_context import ChapterContext
from app.schemas.chapter_workflow import (
    ChapterWorkflowCommandEnvelope,
    ChapterWorkflowStateV1,
)
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
from app.services.chapter_workflow_handler import (
    ChapterWorkflowBindingAssemblerV1,
    ChapterWorkflowLLMProvidersV1,
)
from app.services.job_registry import SideEffectClass
from app.services.job_service import AmbiguousActivityError, JobService
from app.services.job_worker import JobExecutionContext
from app.services.llm_service import LLMService
from app.services.model_response_parser import parse_chapter_content_response
from app.utils.ai_telemetry import AICallResult, TokenUsage


def _activity_ref(execution) -> ChapterWorkflowActivityRef:
    return ChapterWorkflowActivityRef(
        activity_key=execution.activity_key,
        result_hash=execution.result.result_hash,
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('{"optimized_content":"普通正文"}', "普通正文"),
        ('```json\n{"optimized_content":"候选正文"}\n```', "候选正文"),
        (
            '{"optimized_content":"```json\\n{\\"optimized_content\\":\\"最终正文\\"}\\n```"}',
            "最终正文",
        ),
        (
            r"```json\n{\"optimized_content\":\"第一段\\n第二段\"}\n```",
            "第一段\n第二段",
        ),
        (
            r'"```json\n{\"optimized_content\":\"外层正文\"}\n```"',
            "外层正文",
        ),
        (
            r'{"optimized_content":"路径 C:\\new\\chapter，字面量 \\n"}',
            r"路径 C:\new\chapter，字面量 \n",
        ),
        (
            '```json\n{"optimized_content":"他按住"左胸"。",'
            '"optimization_notes":["保留正文引号"]}\n```',
            '他按住"左胸"。',
        ),
    ],
)
def test_content_from_response_unwraps_optimizer_payloads(raw, expected):
    content, _report = parse_chapter_content_response(raw)

    assert content == expected


@pytest.mark.parametrize(
    "raw",
    [
        r"正文包含 C:\new 与字面量 \n",
        "[注] 正文从方括号开始",
        "{旁白} 正文从花括号开始",
        '故事里写道 {"foo":"bar"}，随后继续。',
    ],
)
def test_content_from_response_preserves_plain_text(raw):
    content, _report = parse_chapter_content_response(raw)

    assert content == raw


def test_content_from_response_unwraps_deep_complete_payloads():
    raw = "最终正文"
    for _ in range(6):
        raw = json.dumps({"content": raw}, ensure_ascii=False)

    content, _report = parse_chapter_content_response(raw)

    assert content == "最终正文"


@pytest.mark.parametrize(
    "raw",
    [
        '```json\n{"optimized_content":"未闭合正文',
        '```json\n{"optimized_content":"完整正文"}',
        '{"optimized_content":"未闭合正文',
        '以下是结果：\n{"optimized_content":"未闭合正文',
        '以下是结果：\n{"optimized_content":"完整正文"}',
        '说明\n```json\n{"optimized_content":"完整正文"}\n```\n尾注',
        '{optimized_content: "未闭合正文"',
        '{"optimization_notes":["缺少正文字段"]}',
    ],
)
def test_content_from_response_rejects_invalid_structured_payload(raw):
    with pytest.raises(ValueError, match="结构化"):
        parse_chapter_content_response(raw)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("# 版本一\n正文", "正文"),
        ("## 版本 2\r\n正文", "正文"),
        ("### 版本三：\n正文", "正文"),
        ("普通正文\n# 版本一", "普通正文\n# 版本一"),
        ("# 第一章\n正文", "# 第一章\n正文"),
    ],
)
def test_content_from_response_removes_only_leading_version_heading(raw, expected):
    content, _report = parse_chapter_content_response(raw)

    assert content == expected


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
async def test_configured_version_count_drives_two_candidate_activities(isolated_pg):
    async with isolated_pg.session_factory() as session:
        session.add(
            SystemConfig(
                key="writer.chapter_versions",
                value="2",
                description="章节候选版本数量",
            )
        )
        await session.commit()

    started, execution = await _start_and_claim(
        isolated_pg,
        user_id=4301,
        project_id="workflow-configured-candidate-count",
    )
    candidate_ordinals: list[int] = []

    class Providers:
        async def plan(self, _request, *, provider_request_key):
            assert provider_request_key
            return ChapterWorkflowPlanOutput(mission={"goal": "推进冲突"})

        async def candidate(self, request, *, provider_request_key):
            assert provider_request_key
            candidate_ordinals.append(request.ordinal)
            return ChapterWorkflowCandidateOutput(
                ordinal=request.ordinal,
                content=f"候选正文 {request.ordinal}",
            )

    assembler = ChapterWorkflowBindingAssemblerV1(execution, Providers())
    state = ChapterWorkflowStateV1.initial(
        run_id=started.run.id,
        context_hash=started.run.context_hash,
    )
    context_update = await assembler.freeze_context(state)
    state = state.model_copy(
        update={
            **context_update,
            "node_key": "plan_and_direct",
        }
    )
    plan_update = await assembler.plan_and_direct(state)
    state = state.model_copy(
        update={
            "node_key": "generate_candidates",
            "activity_refs": {
                **state.activity_refs,
                **plan_update["activity_refs"],
            },
            "result_refs": {
                **state.result_refs,
                **plan_update["result_refs"],
            },
        }
    )

    candidate_update = await assembler.generate_candidates(state)

    assert candidate_ordinals == [1, 2]
    assert set(candidate_update["activity_refs"]) == {"candidate:1", "candidate:2"}


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
    app_caplog: pytest.LogCaptureFixture,
):
    app_caplog.set_level(logging.ERROR, logger="app.services.chapter_workflow_activities")
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
    assert "failure_phase=provider" in app_caplog.text
    assert "stage=plan_and_direct" in app_caplog.text
    assert "error_type=RuntimeError" in app_caplog.text
    assert "SECRET_TOKEN" not in app_caplog.text


@pytest.mark.asyncio(loop_scope="session")
async def test_retry_external_requeues_and_retries_only_ambiguous_review_activity(isolated_pg):
    started, _execution, context, service = await _context_and_service(
        isolated_pg,
        user_id=4307,
        project_id="workflow-model-manual-retry",
    )
    calls = {"plan": 0, "candidate": 0, "review": 0}
    plan_input = ChapterWorkflowPlanInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
    )

    async def plan_provider(_request, *, provider_request_key):
        assert provider_request_key
        calls["plan"] += 1
        return ChapterWorkflowPlanOutput(mission={"goal": "continue"})

    plan = await service.execute_plan(plan_input, plan_provider)
    candidate_input = ChapterWorkflowCandidateInput(
        context_snapshot=context.result.context_snapshot,
        context_activity_key=context.activity_key,
        context_result_hash=context.result.result_hash,
        upstream_refs={"plan": _activity_ref(plan)},
        plan=plan.result.output,
        ordinal=1,
    )

    async def candidate_provider(request, *, provider_request_key):
        assert provider_request_key
        calls["candidate"] += 1
        return ChapterWorkflowCandidateOutput(ordinal=request.ordinal, content="candidate")

    candidate_one = await service.execute_candidate(candidate_input, candidate_provider)
    candidate_two_input = candidate_input.model_copy(update={"ordinal": 2})
    candidate_two = await service.execute_candidate(candidate_two_input, candidate_provider)
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
        if calls["review"] == 1:
            raise RuntimeError("provider result uncertain")
        return ChapterWorkflowReviewOutput(best_ordinal=1, report={"summary": "accepted"})

    with pytest.raises(AmbiguousActivityError, match="结果未知"):
        await service.execute_review(review_input, review_provider)

    async with isolated_pg.session_factory() as session:
        original = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key.like("wf:review_candidates:%"),
                )
            )
        ).scalar_one()
        run = await session.get(ChapterWorkflowRun, started.run.id)
        assert run is not None and run.checkpoint_id is None
        command = await JobService(session).submit_chapter_workflow_command(
            run.id,
            actor_user_id=run.user_id,
            envelope=ChapterWorkflowCommandEnvelope(
                command_id=str(uuid4()),
                type="retry_external",
                payload={
                    "activity_key": original.activity_key,
                    "acknowledge_possible_duplicate": True,
                },
                expected_run_revision=run.row_revision,
                expected_chapter_revision=run.base_revision,
                expected_checkpoint_id=None,
            ),
        )
        assert command.status == "applied"
        manual_activity_key = command.result_payload["activity_key"]
        retry_lease = await JobService(session).claim_next(
            worker_id="workflow-model-manual-retry-worker",
            lease_seconds=60,
        )

    assert retry_lease is not None
    retry_execution = JobExecutionContext(
        lease=retry_lease,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        session_factory=isolated_pg.session_factory,
    )
    retry_service = ChapterWorkflowModelActivityService(retry_execution)
    assert await retry_service.execute_plan(plan_input, plan_provider) == plan
    assert (
        await retry_service.execute_candidate(candidate_input, candidate_provider) == candidate_one
    )
    assert (
        await retry_service.execute_candidate(candidate_two_input, candidate_provider)
        == candidate_two
    )
    retried = await retry_service.execute_review(review_input, review_provider)
    assert await retry_service.execute_review(review_input, review_provider) == retried

    async with isolated_pg.session_factory() as session:
        persisted_original = await session.get(JobActivity, original.id)
        manual_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key == manual_activity_key,
                )
            )
        ).scalar_one()

    assert calls == {"plan": 1, "candidate": 2, "review": 2}
    assert retried.activity_key == manual_activity_key
    assert persisted_original is not None and persisted_original.status == "ambiguous"
    assert manual_activity.status == "succeeded"
    assert manual_activity.result_payload == retried.result.model_dump(mode="json")


@pytest.mark.parametrize("manual_status", ["started", "ambiguous"])
@pytest.mark.asyncio(loop_scope="session")
async def test_retry_external_does_not_replay_uncertain_manual_activity(
    isolated_pg,
    manual_status,
):
    user_id = 4308 if manual_status == "started" else 4309
    started, _execution, context, service = await _context_and_service(
        isolated_pg,
        user_id=user_id,
        project_id=f"workflow-model-manual-{manual_status}",
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
        raise RuntimeError("provider result uncertain")

    with pytest.raises(AmbiguousActivityError, match="结果未知"):
        await service.execute_plan(request, uncertain_provider)

    async with isolated_pg.session_factory() as session:
        original = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key.like("wf:plan_and_direct:%"),
                )
            )
        ).scalar_one()
        run = await session.get(ChapterWorkflowRun, started.run.id)
        assert run is not None and run.checkpoint_id is None
        command = await JobService(session).submit_chapter_workflow_command(
            run.id,
            actor_user_id=run.user_id,
            envelope=ChapterWorkflowCommandEnvelope(
                command_id=str(uuid4()),
                type="retry_external",
                payload={
                    "activity_key": original.activity_key,
                    "acknowledge_possible_duplicate": True,
                },
                expected_run_revision=run.row_revision,
                expected_chapter_revision=run.base_revision,
                expected_checkpoint_id=None,
            ),
        )
        manual_activity_key = command.result_payload["activity_key"]
        retry_lease = await JobService(session).claim_next(
            worker_id=f"workflow-model-manual-{manual_status}-worker",
            lease_seconds=60,
        )
        manual_activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == started.root_job.id,
                    JobActivity.activity_key == manual_activity_key,
                )
            )
        ).scalar_one()
        manual_activity.status = manual_status
        await session.commit()

    assert retry_lease is not None
    retry_execution = JobExecutionContext(
        lease=retry_lease,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        session_factory=isolated_pg.session_factory,
    )
    retry_service = ChapterWorkflowModelActivityService(retry_execution)
    with pytest.raises(AmbiguousActivityError, match="禁止自动重放"):
        await retry_service.execute_plan(request, uncertain_provider)

    async with isolated_pg.session_factory() as session:
        persisted_manual = await session.scalar(
            select(JobActivity).where(
                JobActivity.job_id == started.root_job.id,
                JobActivity.activity_key == manual_activity_key,
            )
        )

    assert calls == 1
    assert persisted_manual is not None and persisted_manual.status == manual_status


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
