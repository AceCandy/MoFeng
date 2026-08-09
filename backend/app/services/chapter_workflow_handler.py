# AIMETA P=章节工作流生产装配|R=activity引用重建_模型provider绑定_command_marker握手_事务定稿|NR=不实现projection观察业务桥|E=build_chapter_workflow_job_handler|X=job|A=composition_root|D=langgraph,llm,sqlalchemy|S=db,net,checkpoint|RD=./README.ai
"""Production bindings and job handler for durable Chapter workflow v1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy.engine import URL

from ..models.job import JobActivity
from ..repositories.job_repository import JobRepository
from ..schemas.chapter_context import ChapterContext
from ..schemas.chapter_workflow import ChapterWorkflowStateV1
from ..schemas.job import ChapterWorkflowJobPayload
from ..utils.ai_telemetry import AICallResult
from ..utils.json_utils import remove_think_tags, unwrap_markdown_json
from .chapter_context_adapters import GenerationContextAdapter, ReviewContextAdapter
from .chapter_workflow_activities import (
    ChapterWorkflowActivityRef,
    ChapterWorkflowCandidateInput,
    ChapterWorkflowCandidateOutput,
    ChapterWorkflowModelActivityExecution,
    ChapterWorkflowModelActivityResult,
    ChapterWorkflowModelActivityService,
    ChapterWorkflowPlanInput,
    ChapterWorkflowPlanOutput,
    ChapterWorkflowPostReviewInput,
    ChapterWorkflowPostReviewOutput,
    ChapterWorkflowPostReviewStage,
    ChapterWorkflowReviewInput,
    ChapterWorkflowReviewOutput,
)
from .chapter_workflow_context import (
    ChapterWorkflowContextService,
    ChapterWorkflowRetrievalActivityResult,
)
from .chapter_workflow_finalize import (
    ChapterWorkflowFinalizeInput,
    ChapterWorkflowFinalizeService,
)
from .chapter_workflow_graph import ChapterWorkflowGraphBindingsV1
from .chapter_workflow_persistence import (
    ChapterWorkflowCandidatePersistenceService,
    ChapterWorkflowPersistCandidatesInput,
)
from .chapter_workflow_projection import ChapterWorkflowProjectionService
from .chapter_workflow_runtime import ChapterWorkflowRuntime
from .job_registry import SideEffectClass
from .job_service import ChapterWorkflowAutomaticResume, JobService
from .job_worker import JobExecutionContext, JobOutcome, JobWaitOutcome
from .llm_service import LLMService
from .prompt_service import PromptService

OutputT = TypeVar("OutputT", bound=BaseModel)
WorkflowHandler = Callable[[JobExecutionContext], Awaitable[JobOutcome | JobWaitOutcome]]


class ChapterWorkflowProvidersV1(Protocol):
    async def plan(
        self,
        request: ChapterWorkflowPlanInput,
        *,
        provider_request_key: str,
    ) -> ChapterWorkflowPlanOutput | AICallResult[ChapterWorkflowPlanOutput]: ...

    async def candidate(
        self,
        request: ChapterWorkflowCandidateInput,
        *,
        provider_request_key: str,
    ) -> ChapterWorkflowCandidateOutput | AICallResult[ChapterWorkflowCandidateOutput]: ...

    async def review(
        self,
        request: ChapterWorkflowReviewInput,
        *,
        provider_request_key: str,
    ) -> ChapterWorkflowReviewOutput | AICallResult[ChapterWorkflowReviewOutput]: ...

    async def post_review(
        self,
        request: ChapterWorkflowPostReviewInput,
        *,
        provider_request_key: str,
    ) -> ChapterWorkflowPostReviewOutput | AICallResult[ChapterWorkflowPostReviewOutput]: ...


ProviderFactory = Callable[[JobExecutionContext], ChapterWorkflowProvidersV1]


def _json_payload(raw: str) -> dict[str, Any]:
    normalized = unwrap_markdown_json(remove_think_tags(raw))
    value = json.loads(normalized)
    if not isinstance(value, dict):
        raise ValueError("模型必须返回 JSON object")
    return value


def _content_from_response(raw: str) -> tuple[str, dict[str, Any]]:
    content = remove_think_tags(raw).strip()
    report: dict[str, Any] = {}
    for _ in range(4):
        payload = None
        for candidate in (content, unwrap_markdown_json(content)):
            unescaped = (
                candidate.replace(r'\"', '"')
                .replace(r"\\r", r"\r")
                .replace(r"\\n", r"\n")
                .replace(r"\\t", r"\t")
            )
            unescaped = unescaped.removeprefix(r"\r\n").removeprefix(r"\n")
            unescaped = unescaped.removesuffix(r"\r\n").removesuffix(r"\n")
            for normalized in (candidate, unescaped):
                try:
                    payload = json.loads(normalized)
                    break
                except json.JSONDecodeError:
                    continue
            if payload is not None:
                break
        if payload is None:
            break
        if isinstance(payload, str) and payload.strip() and payload.strip() != content:
            content = payload.strip()
            continue
        if not isinstance(payload, dict):
            break
        if not report and isinstance(payload.get("report"), dict):
            report = payload["report"]
        for key in ("content", "optimized_content", "revised_content", "chapter_content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                content = value.strip()
                break
        else:
            break
    if content:
        return content, report
    raise ValueError("模型未返回有效正文")


@dataclass(frozen=True)
class ChapterWorkflowLLMProvidersV1:
    """Use the existing prompt/model routing without retaining database sessions."""

    execution: JobExecutionContext

    async def plan(
        self,
        request: ChapterWorkflowPlanInput,
        *,
        provider_request_key: str,
    ) -> AICallResult[ChapterWorkflowPlanOutput]:
        prompt = await self._prompt("chapter_plan")
        context = ChapterContext.model_validate(request.context_snapshot)
        generation = GenerationContextAdapter.to_context(context)
        user_prompt = json.dumps(
            {
                "previous_chapter": generation["previous_chapter"],
                "chapter_outline": generation["chapter_outline"],
                "introduced_characters": generation["introduced_characters"],
                "all_characters": generation["all_characters"],
                "writing_notes": generation["writing_notes"],
                "planning_options": request.planning_options,
            },
            ensure_ascii=False,
        )
        call = await LLMService.get_llm_response_result_detached(
            system_prompt=prompt,
            conversation_history=[{"role": "user", "content": user_prompt}],
            session_factory=self.execution.session_factory,
            temperature=0.3,
            user_id=self.execution.lease.user_id,
            timeout=120.0,
            stage="chapter_mission",
            provider_request_key=provider_request_key,
        )
        payload = _json_payload(call.value)
        mission_value = payload.get("mission")
        mission = mission_value if isinstance(mission_value, dict) else payload
        allowed = mission.get("allowed_new_characters")
        output = ChapterWorkflowPlanOutput(
            mission=mission,
            allowed_new_characters=(
                [str(item) for item in allowed] if isinstance(allowed, list) else []
            ),
        )
        return call.with_value(output)

    async def candidate(
        self,
        request: ChapterWorkflowCandidateInput,
        *,
        provider_request_key: str,
    ) -> AICallResult[ChapterWorkflowCandidateOutput]:
        prompt = await self._prompt("writing_v2", fallback="writing")
        context = ChapterContext.model_validate(request.context_snapshot)
        generation = GenerationContextAdapter.to_context(context)
        user_payload = {
            "writer_blueprint": generation["writer_blueprint"],
            "previous_chapter": generation["previous_chapter"],
            "chapter_outline": generation["chapter_outline"],
            "chapter_mission": request.plan.mission,
            "writing_notes": generation["writing_notes"],
            "forbidden_characters": generation["forbidden_characters"],
            "retrieval_context": {
                "rag": generation["rag_context"],
                "knowledge": generation["knowledge_context"],
            },
            "style_hint": request.style_hint,
            "generation_options": request.generation_options,
        }
        call = await LLMService.get_llm_response_result_detached(
            system_prompt=prompt,
            conversation_history=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                }
            ],
            session_factory=self.execution.session_factory,
            temperature=0.9,
            user_id=self.execution.lease.user_id,
            timeout=600.0,
            response_format=None,
            max_tokens=7000,
            stage="chapter_writing",
            provider_request_key=provider_request_key,
        )
        content, metadata = _content_from_response(call.value)
        return call.with_value(
            ChapterWorkflowCandidateOutput(
                ordinal=request.ordinal,
                content=content,
                metadata={
                    **metadata,
                    "style_hint": request.style_hint,
                    "pipeline": {"workflow": "chapter_workflow.v1"},
                },
            )
        )

    async def review(
        self,
        request: ChapterWorkflowReviewInput,
        *,
        provider_request_key: str,
    ) -> ChapterWorkflowReviewOutput | AICallResult[ChapterWorkflowReviewOutput]:
        if len(request.candidates) == 1:
            return ChapterWorkflowReviewOutput(
                best_ordinal=request.candidates[0].ordinal,
                report={"mode": "single", "final_recommendation": "采用唯一版本"},
            )
        prompt = await self._prompt("editor_review")
        context = ChapterContext.model_validate(request.context_snapshot)
        user_payload = ReviewContextAdapter.to_prompt_context(context)
        user_payload.update(
            {
                "chapter_mission": request.plan.mission,
                "candidate_versions": [
                    {"ordinal": item.ordinal, "content": item.content}
                    for item in request.candidates
                ],
            }
        )
        call = await LLMService.get_llm_response_result_detached(
            system_prompt=prompt,
            conversation_history=[
                {
                    "role": "user",
                    "content": json.dumps(user_payload, ensure_ascii=False),
                }
            ],
            session_factory=self.execution.session_factory,
            temperature=0.3,
            user_id=self.execution.lease.user_id,
            timeout=180.0,
            stage="version_review",
            provider_request_key=provider_request_key,
        )
        payload = _json_payload(call.value)
        raw_best = payload.get("best_ordinal", payload.get("best_version_index"))
        if isinstance(raw_best, bool) or not isinstance(raw_best, (int, str)):
            raise ValueError("版本评审缺少合法 best ordinal")
        best_ordinal = int(raw_best)
        if "best_ordinal" not in payload:
            best_ordinal += 1
        return call.with_value(
            ChapterWorkflowReviewOutput(
                best_ordinal=best_ordinal,
                report=payload,
            )
        )

    async def post_review(
        self,
        request: ChapterWorkflowPostReviewInput,
        *,
        provider_request_key: str,
    ) -> AICallResult[ChapterWorkflowPostReviewOutput]:
        prompt_name = (
            "optimize_recommended_version"
            if request.stage in {"review_guided_refinement", "optimizer"}
            else "evaluation"
        )
        prompt = await self._prompt(prompt_name)
        source_content = request.source_candidate.content
        if request.prior_stage_results:
            source_content = next(
                (
                    result.content
                    for result in reversed(request.prior_stage_results)
                    if result.content
                ),
                source_content,
            )
        call = await LLMService.get_llm_response_result_detached(
            system_prompt=prompt,
            conversation_history=[
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "stage": request.stage,
                            "source_content": source_content,
                            "review": request.review.report,
                            "instruction": "返回完整修订正文，并以 JSON object 表达。",
                        },
                        ensure_ascii=False,
                    ),
                }
            ],
            session_factory=self.execution.session_factory,
            temperature=0.7,
            user_id=self.execution.lease.user_id,
            timeout=600.0,
            response_format=None,
            stage="chapter_optimization",
            provider_request_key=provider_request_key,
        )
        content, report = _content_from_response(call.value)
        return call.with_value(
            ChapterWorkflowPostReviewOutput(
                stage=request.stage,
                content=content,
                report=report,
            )
        )

    async def _prompt(self, name: str, *, fallback: str | None = None) -> str:
        async with self.execution.session_factory() as session:
            service = PromptService(session)
            prompt = await service.get_prompt(name)
            if prompt is None and fallback is not None:
                prompt = await service.get_prompt(fallback)
        if not prompt:
            raise ValueError(f"缺少 workflow provider 提示词: {name}")
        return str(prompt)


class ChapterWorkflowBindingAssemblerV1:
    """Rebuild private activity inputs from durable references for each graph node."""

    def __init__(
        self,
        execution: JobExecutionContext,
        providers: ChapterWorkflowProvidersV1,
    ) -> None:
        self.execution = execution
        self.providers = providers
        self.model_activities = ChapterWorkflowModelActivityService(execution)

    def bindings(self) -> ChapterWorkflowGraphBindingsV1:
        return ChapterWorkflowGraphBindingsV1(
            freeze_context=self.freeze_context,
            plan_and_direct=self.plan_and_direct,
            generate_candidates=self.generate_candidates,
            review_candidates=self.review_candidates,
            persist_candidates=self.persist_candidates,
            apply_selection_resume=self.apply_selection_resume,
            finalize_revision=self.finalize_revision,
            apply_projection_resume=self.apply_projection_resume,
            observe_projection=self.observe_projection,
        )

    async def freeze_context(self, _state: ChapterWorkflowStateV1) -> dict[str, object]:
        result = await ChapterWorkflowContextService(self.execution).execute_retrieval_activity()
        update = result.state_update()
        return {
            "activity_refs": update["activity_refs"],
            "result_refs": update["result_refs"],
        }

    async def plan_and_direct(self, state: ChapterWorkflowStateV1) -> dict[str, object]:
        context_key, context_result = await self._context(state)
        execution = await self.model_activities.execute_plan(
            ChapterWorkflowPlanInput(
                context_snapshot=context_result.context_snapshot,
                context_activity_key=context_key,
                context_result_hash=context_result.result_hash,
                planning_options={
                    "flow_config": self._payload().runtime_inputs.flow_config.model_dump(
                        mode="json", exclude_none=True
                    )
                },
            ),
            self.providers.plan,
        )
        return cast(dict[str, object], execution.state_update())

    async def generate_candidates(self, state: ChapterWorkflowStateV1) -> dict[str, object]:
        context_key, context_result = await self._context(state)
        plan_execution = await self._model_execution(state, "plan", ChapterWorkflowPlanOutput)
        plan = cast(ChapterWorkflowPlanOutput, plan_execution.result.output)
        flow_config = self._payload().runtime_inputs.flow_config
        version_count = max(1, min(2, flow_config.versions or 1))
        style_hints = (
            "情绪更细腻，节奏更慢，多写内心戏和感官描写",
            "冲突更强，节奏更快，多写动作和对话",
        )
        updates: dict[str, dict[str, str]] = {"activity_refs": {}, "result_refs": {}}
        for ordinal in range(1, version_count + 1):
            execution = await self.model_activities.execute_candidate(
                ChapterWorkflowCandidateInput(
                    context_snapshot=context_result.context_snapshot,
                    context_activity_key=context_key,
                    context_result_hash=context_result.result_hash,
                    upstream_refs={"plan": self._ref(plan_execution)},
                    plan=plan,
                    ordinal=ordinal,
                    style_hint=style_hints[ordinal - 1],
                    generation_options=flow_config.model_dump(mode="json", exclude_none=True),
                ),
                self.providers.candidate,
            )
            self._merge_updates(updates, execution.state_update())
        return {
            "activity_refs": updates["activity_refs"],
            "result_refs": updates["result_refs"],
        }

    async def review_candidates(self, state: ChapterWorkflowStateV1) -> dict[str, object]:
        context_key, context_result = await self._context(state)
        plan_execution = await self._model_execution(state, "plan", ChapterWorkflowPlanOutput)
        plan = cast(ChapterWorkflowPlanOutput, plan_execution.result.output)
        candidates = await self._candidate_executions(state)
        candidate_outputs = [
            cast(ChapterWorkflowCandidateOutput, execution.result.output)
            for execution in candidates
        ]
        upstream_refs = {"plan": self._ref(plan_execution)}
        upstream_refs.update({execution.ref_name: self._ref(execution) for execution in candidates})
        review = await self.model_activities.execute_review(
            ChapterWorkflowReviewInput(
                context_snapshot=context_result.context_snapshot,
                context_activity_key=context_key,
                context_result_hash=context_result.result_hash,
                upstream_refs=upstream_refs,
                plan=plan,
                candidates=candidate_outputs,
            ),
            self.providers.review,
        )
        updates: dict[str, dict[str, str]] = {"activity_refs": {}, "result_refs": {}}
        self._merge_updates(updates, review.state_update())

        review_output = cast(ChapterWorkflowReviewOutput, review.result.output)
        selected = next(
            item
            for item in candidates
            if cast(ChapterWorkflowCandidateOutput, item.result.output).ordinal
            == review_output.best_ordinal
        )
        prior_results: list[ChapterWorkflowPostReviewOutput] = []
        post_refs = {
            selected.ref_name: self._ref(selected),
            review.ref_name: self._ref(review),
        }
        for stage in self._post_review_stages():
            execution = await self.model_activities.execute_post_review(
                ChapterWorkflowPostReviewInput(
                    context_snapshot=context_result.context_snapshot,
                    context_activity_key=context_key,
                    context_result_hash=context_result.result_hash,
                    upstream_refs=dict(post_refs),
                    source_candidate=cast(
                        ChapterWorkflowCandidateOutput,
                        selected.result.output,
                    ),
                    review=review_output,
                    stage=stage,
                    prior_stage_results=list(prior_results),
                ),
                self.providers.post_review,
            )
            post_output = cast(ChapterWorkflowPostReviewOutput, execution.result.output)
            prior_results.append(post_output)
            post_refs[execution.ref_name] = self._ref(execution)
            self._merge_updates(updates, execution.state_update())
        return cast(dict[str, object], updates)

    async def persist_candidates(self, state: ChapterWorkflowStateV1) -> dict[str, object]:
        candidates = await self._candidate_executions(state)
        review = await self._model_execution(
            state,
            "review:version_review",
            ChapterWorkflowReviewOutput,
        )
        post_review_refs: dict[int, list[ChapterWorkflowActivityRef]] = {}
        for ref_name in sorted(state.activity_refs):
            if not ref_name.startswith("post_review:"):
                continue
            execution = await self._model_execution(
                state,
                ref_name,
                ChapterWorkflowPostReviewOutput,
            )
            ordinal = execution.result.subject_ordinal
            if ordinal is None:
                raise ValueError("post-review activity 缺少 subject ordinal")
            post_review_refs.setdefault(ordinal, []).append(self._ref(execution))
        persisted = await ChapterWorkflowCandidatePersistenceService(self.execution).execute(
            ChapterWorkflowPersistCandidatesInput(
                candidate_refs=[self._ref(item) for item in candidates],
                review_ref=self._ref(review),
                post_review_refs=post_review_refs,
            )
        )
        update = persisted.state_update()
        return {
            "candidate_version_ids": update["candidate_version_ids"],
            "activity_refs": update["activity_refs"],
            "result_refs": update["result_refs"],
        }

    async def finalize_revision(self, state: ChapterWorkflowStateV1) -> dict[str, object]:
        if state.selected_version_id is None:
            raise ValueError("workflow finalize checkpoint 缺少选中版本")
        finalized = await ChapterWorkflowFinalizeService(self.execution).execute(
            ChapterWorkflowFinalizeInput(
                run_id=state.run_id,
                candidate_version_ids=state.candidate_version_ids,
                selected_version_id=state.selected_version_id,
            )
        )
        return finalized.state_update()

    async def _context(
        self,
        state: ChapterWorkflowStateV1,
    ) -> tuple[str, ChapterWorkflowRetrievalActivityResult]:
        ref_name = "retrieval_context"
        activity = await self._activity(state, ref_name)
        result = ChapterWorkflowRetrievalActivityResult.model_validate(activity.result_payload)
        if result.result_hash != state.result_refs.get(ref_name):
            raise ValueError("workflow retrieval checkpoint 引用已漂移")
        return activity.activity_key, result

    async def _candidate_executions(
        self,
        state: ChapterWorkflowStateV1,
    ) -> list[ChapterWorkflowModelActivityExecution]:
        names = sorted(
            (name for name in state.activity_refs if name.startswith("candidate:")),
            key=lambda name: int(name.split(":", 1)[1]),
        )
        if not names:
            raise ValueError("workflow checkpoint 缺少候选 activity refs")
        return [
            await self._model_execution(state, name, ChapterWorkflowCandidateOutput)
            for name in names
        ]

    async def _model_execution(
        self,
        state: ChapterWorkflowStateV1,
        ref_name: str,
        output_type: type[OutputT],
    ) -> ChapterWorkflowModelActivityExecution:
        activity = await self._activity(state, ref_name)
        result = ChapterWorkflowModelActivityResult.model_validate(activity.result_payload)
        if result.result_hash != state.result_refs.get(ref_name):
            raise ValueError(f"workflow model checkpoint 引用已漂移: {ref_name}")
        output_type.model_validate(result.output)
        return ChapterWorkflowModelActivityExecution(
            activity_key=activity.activity_key,
            ref_name=ref_name,
            result=result,
        )

    async def _activity(
        self,
        state: ChapterWorkflowStateV1,
        ref_name: str,
    ) -> JobActivity:
        activity_key = state.activity_refs.get(ref_name)
        result_hash = state.result_refs.get(ref_name)
        if not activity_key or not result_hash:
            raise ValueError(f"workflow checkpoint 缺少引用: {ref_name}")
        async with self.execution.session_factory() as session:
            activity = await JobRepository(session).get_activity(
                job_id=self.execution.lease.job_id,
                activity_key=activity_key,
            )
        if activity is None or activity.status != "succeeded":
            raise ValueError(f"workflow activity 不存在或未完成: {ref_name}")
        expected_side_effect = (
            SideEffectClass.IDEMPOTENT_EXTERNAL.value
            if ref_name == "retrieval_context"
            else SideEffectClass.AMBIGUOUS_EXTERNAL.value
        )
        if activity.side_effect_class != expected_side_effect:
            raise ValueError(f"workflow activity side effect class 不匹配: {ref_name}")
        return activity

    def _post_review_stages(self) -> tuple[ChapterWorkflowPostReviewStage, ...]:
        flow = self._payload().runtime_inputs.flow_config
        stages: list[ChapterWorkflowPostReviewStage] = ["review_guided_refinement"]
        if flow.preset == "enhanced":
            stages.append("enhanced_review")
        if flow.enable_consistency:
            stages.append("consistency")
        if flow.enable_optimizer:
            stages.append("optimizer")
        if flow.enable_enrichment:
            stages.append("enrichment")
        return tuple(stages)

    def _payload(self) -> ChapterWorkflowJobPayload:
        return ChapterWorkflowJobPayload.model_validate(self.execution.lease.payload)

    @staticmethod
    def _ref(
        execution: ChapterWorkflowModelActivityExecution,
    ) -> ChapterWorkflowActivityRef:
        return ChapterWorkflowActivityRef(
            activity_key=execution.activity_key,
            result_hash=execution.result.result_hash,
        )

    @staticmethod
    def _merge_updates(
        target: dict[str, dict[str, str]],
        update: dict[str, dict[str, str]],
    ) -> None:
        target["activity_refs"].update(update["activity_refs"])
        target["result_refs"].update(update["result_refs"])

    @staticmethod
    async def apply_selection_resume(
        _state: ChapterWorkflowStateV1,
        resume_value: object,
    ) -> dict[str, object]:
        if not isinstance(resume_value, dict):
            raise ValueError("select resume payload 必须为 object")
        command_id = resume_value.get("command_id")
        selected_version_id = resume_value.get("selected_version_id")
        if not isinstance(command_id, str) or not isinstance(selected_version_id, int):
            raise ValueError("select resume payload 缺少 command 或 version identity")
        return {
            "selected_version_id": selected_version_id,
            "last_applied_command_id": command_id,
        }

    async def apply_projection_resume(
        self,
        state: ChapterWorkflowStateV1,
        resume_value: object,
    ) -> dict[str, object]:
        if not isinstance(resume_value, dict):
            raise ValueError("projection resume payload 必须是 object")
        if set(resume_value) == {"command_id"}:
            command_id = resume_value["command_id"]
            if not isinstance(command_id, str):
                raise ValueError("projection resume command identity 无效")
            await ChapterWorkflowProjectionService(self.execution).retry_failed(
                state,
                command_id=command_id,
            )
            return {"last_applied_command_id": command_id}
        if set(resume_value) == {"reason", "target_chapter_revision"}:
            target_revision = resume_value["target_chapter_revision"]
            if (
                resume_value["reason"] != "projection_completed"
                or isinstance(target_revision, bool)
                or not isinstance(target_revision, int)
                or target_revision != state.target_chapter_revision
            ):
                raise ValueError("projection automatic resume identity 无效")
            return {}
        raise ValueError("projection resume payload shape 无效")

    async def observe_projection(
        self,
        state: ChapterWorkflowStateV1,
    ) -> dict[str, object]:
        await ChapterWorkflowProjectionService(self.execution).observe_completed(state)
        return {}


def build_chapter_workflow_production_bindings(
    execution: JobExecutionContext,
    *,
    provider_factory: ProviderFactory = ChapterWorkflowLLMProvidersV1,
) -> ChapterWorkflowGraphBindingsV1:
    providers = provider_factory(execution)
    return ChapterWorkflowBindingAssemblerV1(execution, providers).bindings()


def build_chapter_workflow_job_handler(
    database_url: str | URL,
    *,
    provider_factory: ProviderFactory = ChapterWorkflowLLMProvidersV1,
) -> WorkflowHandler:
    async def handle(context: JobExecutionContext) -> JobOutcome | JobWaitOutcome:
        async with context.session_factory() as session:
            pending = await JobService(session).prepare_chapter_workflow_resume(context.lease)
        runtime = ChapterWorkflowRuntime(
            context,
            database_url=database_url,
            bindings=build_chapter_workflow_production_bindings(
                context,
                provider_factory=provider_factory,
            ),
        )
        if pending is None:
            return await runtime.execute()
        if isinstance(pending, ChapterWorkflowAutomaticResume):
            return await runtime.execute(resume_value=pending.resume_value)

        async def apply_checkpointed(command_id: str, checkpoint_id: str) -> None:
            async with context.session_factory() as session:
                await JobService(session).apply_checkpointed_workflow_command(
                    context.lease,
                    command_id=command_id,
                    marker_checkpoint_id=checkpoint_id,
                )

        return await runtime.execute(
            resume_value=pending.resume_value,
            command_id=pending.command_id,
            expected_checkpoint_id=pending.expected_checkpoint_id,
            on_command_checkpointed=apply_checkpointed,
        )

    return handle


__all__ = [
    "ChapterWorkflowBindingAssemblerV1",
    "ChapterWorkflowLLMProvidersV1",
    "ChapterWorkflowProvidersV1",
    "ProviderFactory",
    "build_chapter_workflow_job_handler",
    "build_chapter_workflow_production_bindings",
]
