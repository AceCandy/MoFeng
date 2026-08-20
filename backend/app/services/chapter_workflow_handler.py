# AIMETA P=章节工作流生产装配|R=activity引用重建_模型provider绑定_command_marker握手_事务定稿|NR=不实现projection观察业务桥|E=build_chapter_workflow_job_handler|X=job|A=composition_root|D=langgraph,llm,sqlalchemy|S=db,net,checkpoint|RD=./README.ai
"""Production bindings and job handler for durable Chapter workflow v1."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Protocol, TypeVar, cast

from pydantic import BaseModel
from sqlalchemy.engine import URL

from ..models.job import JobActivity
from ..repositories.job_repository import JobRepository
from ..schemas.chapter_context import ChapterContext, stable_digest
from ..schemas.chapter_workflow import ChapterWorkflowState
from ..schemas.job import (
    ChapterWorkflowJobPayload,
    validate_chapter_workflow_job_payload,
)
from ..utils.ai_telemetry import AICallResult
from ..utils.json_utils import (
    remove_think_tags,
    unwrap_markdown_json,
)
from .chapter_context_adapters import GenerationContextAdapter, ReviewContextAdapter
from .chapter_word_count_settings import (
    build_word_count_requirement_text,
    count_chapter_words,
)
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
from .chapter_workflow_graph import (
    ChapterWorkflowGraphBindings,
)
from .chapter_workflow_persistence import (
    ChapterWorkflowCandidatePersistenceService,
    ChapterWorkflowPersistCandidatesInput,
)
from .chapter_workflow_projection import ChapterWorkflowProjectionService
from .chapter_workflow_runtime import ChapterWorkflowRuntime
from .job_registry import SideEffectClass
from .job_service import ChapterWorkflowAutomaticResume, JobService
from .job_worker import JobExecutionContext, JobOutcome, JobWaitOutcome
from .llm_service import LLMService, set_llm_failure_diagnostic
from .model_response_parser import parse_chapter_content_response
from .prompt_service import PromptService

OutputT = TypeVar("OutputT", bound=BaseModel)
WorkflowHandler = Callable[[JobExecutionContext], Awaitable[JobOutcome | JobWaitOutcome]]


class ChapterWorkflowProviders(Protocol):
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


ProviderFactory = Callable[[JobExecutionContext], ChapterWorkflowProviders]


def _json_payload(raw: str) -> dict[str, Any]:
    normalized = unwrap_markdown_json(remove_think_tags(raw))
    value = json.loads(normalized)
    if not isinstance(value, dict):
        raise ValueError("模型必须返回 JSON object")
    return value


_REVISION_STAGE_INSTRUCTIONS: dict[ChapterWorkflowPostReviewStage, str] = {
    "review_guided_refinement": "根据评审意见修订完整正文，保留已经成立的优点。",
    "enhanced_review": "增强场景、动作、情绪和关键细节，不改变核心剧情、人物关系和时间顺序。",
    "self_critique": "审校并修复正文中的明显问题，不改变核心剧情。",
    "reader_simulator": "从读者体验出发优化信息清晰度、节奏和阅读吸引力。",
    "consistency": "修复人物、设定、时间线和前后文一致性问题，不改变核心剧情。",
    "optimizer": "优化语言、节奏和可读性，保留原文风格和关键信息。",
    "enrichment": "在不改变主线、人物关系、时间顺序和结尾钩子的前提下扩写必要细节。",
    "compression": "压缩正文并保留核心剧情、人物关系和关键信息。",
}


@dataclass(frozen=True)
class ChapterWorkflowLLMProviders:
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
            "word_count": {
                "target": request.target_word_count,
                "minimum": request.minimum_word_count,
                "maximum": request.maximum_word_count,
                "requirement": build_word_count_requirement_text(
                    request.target_word_count
                ),
            },
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
        content, metadata = parse_chapter_content_response(call.value)
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
        best_field = next(
            (
                field
                for field in ("best_ordinal", "best_version_number", "best_version_index")
                if field in payload
            ),
            None,
        )
        raw_best = payload.get(best_field) if best_field else None
        if isinstance(raw_best, bool) or not isinstance(raw_best, (int, str)):
            raise ValueError("版本评审缺少合法 best ordinal")
        try:
            best_ordinal = int(raw_best)
        except ValueError as exc:
            raise ValueError("版本评审缺少合法 best ordinal") from exc
        if best_field == "best_version_index":
            best_ordinal += 1
        if best_ordinal not in {candidate.ordinal for candidate in request.candidates}:
            raise ValueError("版本评审推荐 ordinal 不在候选集合中")
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
            "chapter_compression"
            if request.stage == "compression"
            else "optimize_recommended_version"
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
        user_payload = (
            {
                "target_word_count": request.target_word_count,
                "maximum_word_count": request.maximum_word_count,
                "current_word_count": count_chapter_words(source_content),
                "content": source_content,
            }
            if request.stage == "compression"
            else {
                "source_content": source_content,
                "review_summary": " ".join(
                    (
                        _REVISION_STAGE_INSTRUCTIONS[request.stage],
                        build_word_count_requirement_text(request.target_word_count),
                    )
                ),
                "version_number": request.source_candidate.ordinal,
                "version_review": request.review.report,
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
            temperature=0.3 if request.stage == "compression" else 0.7,
            user_id=self.execution.lease.user_id,
            timeout=600.0,
            response_format=None,
            stage="chapter_optimization",
            provider_request_key=provider_request_key,
        )
        try:
            content, report = parse_chapter_content_response(call.value)
        except ValueError as exc:
            reason = {
                "模型返回的结构化正文无法解析": "模型返回不完整，未能提取章节正文",
                "模型返回的结构化正文缺少有效正文": (
                    "模型只返回了说明信息，没有返回章节正文"
                ),
                "模型返回的结构化正文存在循环包装": (
                    "模型返回内容异常，未能提取章节正文"
                ),
                "模型未返回有效正文": "模型没有返回可用的章节正文",
            }.get(str(exc), "模型返回内容无法识别为完整章节正文")
            set_llm_failure_diagnostic(
                exc,
                provider=call.provider_name or call.provider_type,
                model=call.model,
                status_code=None,
                reason=reason,
            )
            raise
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


class _ChapterWorkflowBindingAssemblerBase:
    """Rebuild private activity inputs from durable references for each graph node."""

    def __init__(
        self,
        execution: JobExecutionContext,
        providers: ChapterWorkflowProviders,
    ) -> None:
        self.execution = execution
        self.providers = providers
        self.model_activities = ChapterWorkflowModelActivityService(execution)

    async def finalize_revision(
        self,
        state: ChapterWorkflowState,
    ) -> dict[str, object]:
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
        state: ChapterWorkflowState,
    ) -> tuple[str, ChapterWorkflowRetrievalActivityResult]:
        ref_name = "retrieval_context"
        activity = await self._activity(state, ref_name)
        result = ChapterWorkflowRetrievalActivityResult.model_validate(activity.result_payload)
        if result.result_hash != state.result_refs.get(ref_name):
            raise ValueError("workflow retrieval checkpoint 引用已漂移")
        return activity.activity_key, result

    async def _candidate_executions(
        self,
        state: ChapterWorkflowState,
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
        state: ChapterWorkflowState,
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
        state: ChapterWorkflowState,
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

    def _payload(self) -> ChapterWorkflowJobPayload:
        return validate_chapter_workflow_job_payload(
            self.execution.lease.payload_version,
            self.execution.lease.payload,
        )

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
        _state: ChapterWorkflowState,
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
        state: ChapterWorkflowState,
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

    async def reconcile_projections(
        self,
        state: ChapterWorkflowState,
    ) -> dict[str, object]:
        await ChapterWorkflowProjectionService(self.execution).observe_completed(state)
        return {}


class ChapterWorkflowBindingAssembler(_ChapterWorkflowBindingAssemblerBase):
    """将每个真实产物边界绑定到独立 durable activity。"""

    _STAGE_REFS: tuple[tuple[str, ChapterWorkflowPostReviewStage], ...] = (
        ("refine_candidate", "review_guided_refinement"),
        ("enhance_content", "enhanced_review"),
        ("repair_consistency", "consistency"),
        ("optimize_style", "optimizer"),
        ("enrich_content", "enrichment"),
        ("compress_candidate", "compression"),
    )

    def bindings(self) -> ChapterWorkflowGraphBindings:
        return ChapterWorkflowGraphBindings(
            freeze_base_context=self.freeze_base_context,
            retrieve_context=self.retrieve_context,
            plan_chapter=self.plan_chapter,
            generate_candidate_1=self.generate_candidate_1,
            generate_candidate_2=self.generate_candidate_2,
            review_candidates=self.review_candidates,
            refine_candidate=self.refine_candidate,
            enhance_content=self.enhance_content,
            repair_consistency=self.repair_consistency,
            optimize_style=self.optimize_style,
            enrich_content=self.enrich_content,
            compress_candidate=self.compress_candidate,
            persist_drafts=self.persist_drafts,
            apply_selection_resume=self.apply_selection_resume,
            finalize_revision=self.finalize_revision,
            apply_projection_resume=self.apply_projection_resume,
            reconcile_projections=self.reconcile_projections,
        )

    async def freeze_base_context(
        self,
        state: ChapterWorkflowState,
    ) -> dict[str, object]:
        payload = self._payload()
        if state.context_hash != payload.context_hash:
            raise ValueError("base context checkpoint 与冻结 payload 不一致")
        request_payload = {
            "schema_version": 1,
            "workflow_version": payload.workflow_version,
            "state_schema_version": payload.state_schema_version,
            "run_id": payload.run_id,
            "node_key": "freeze_base_context",
            "context_hash": payload.context_hash,
        }
        activity_key = f"wf:freeze_base_context:{stable_digest(request_payload)}"
        activity = await self.execution.begin_activity(
            activity_key,
            side_effect_class=SideEffectClass.TRANSACTIONAL,
            request_payload=request_payload,
        )
        if activity.should_execute:
            result_payload = {
                "schema_version": 1,
                "context_hash": payload.context_hash,
            }
            result_payload["result_hash"] = stable_digest(result_payload)
            completed = await self.execution.complete_activity(
                activity_key,
                provider_request_key=activity.provider_request_key,
                result=result_payload,
            )
            result = completed.result_payload
        else:
            result = activity.result
        if (
            not isinstance(result, dict)
            or result.get("context_hash") != payload.context_hash
            or result.get("result_hash")
            != stable_digest({key: value for key, value in result.items() if key != "result_hash"})
        ):
            raise ValueError("base context activity result 无效")
        return {
            "activity_refs": {"base_context": activity_key},
            "result_refs": {"base_context": str(result["result_hash"])},
        }

    async def retrieve_context(
        self,
        _state: ChapterWorkflowState,
    ) -> dict[str, object]:
        result = await ChapterWorkflowContextService(
            self.execution
        ).execute_retrieval_activity(node_key="retrieve_context")
        update = result.state_update()
        return {
            "activity_refs": update["activity_refs"],
            "result_refs": update["result_refs"],
        }

    async def plan_chapter(self, state: ChapterWorkflowState) -> dict[str, object]:
        context_key, context_result = await self._context(state)
        execution = await self.model_activities.execute_plan(
            ChapterWorkflowPlanInput(
                context_snapshot=context_result.context_snapshot,
                context_activity_key=context_key,
                context_result_hash=context_result.result_hash,
                planning_options={
                    "flow_config": self._payload().runtime_inputs.flow_config.model_dump(
                        mode="json",
                        exclude_none=True,
                    )
                },
            ),
            self.providers.plan,
            node_key="plan_chapter",
        )
        return cast(dict[str, object], execution.state_update())

    async def generate_candidate_1(
        self,
        state: ChapterWorkflowState,
    ) -> dict[str, object]:
        return await self._generate_candidate(state, ordinal=1)

    async def generate_candidate_2(
        self,
        state: ChapterWorkflowState,
    ) -> dict[str, object]:
        return await self._generate_candidate(state, ordinal=2)

    async def _generate_candidate(
        self,
        state: ChapterWorkflowState,
        *,
        ordinal: Literal[1, 2],
    ) -> dict[str, object]:
        context_key, context_result = await self._context(state)
        plan_execution = await self._model_execution(
            state,
            "plan",
            ChapterWorkflowPlanOutput,
        )
        runtime_inputs = self._payload().runtime_inputs
        flow_config = runtime_inputs.flow_config
        style_hints = (
            "情绪更细腻，节奏更慢，多写内心戏和感官描写",
            "冲突更强，节奏更快，多写动作和对话",
        )
        node_key: Literal["generate_candidate_1", "generate_candidate_2"] = (
            "generate_candidate_1" if ordinal == 1 else "generate_candidate_2"
        )
        execution = await self.model_activities.execute_candidate(
            ChapterWorkflowCandidateInput(
                context_snapshot=context_result.context_snapshot,
                context_activity_key=context_key,
                context_result_hash=context_result.result_hash,
                upstream_refs={"plan": self._ref(plan_execution)},
                plan=cast(ChapterWorkflowPlanOutput, plan_execution.result.output),
                ordinal=ordinal,
                style_hint=style_hints[ordinal - 1],
                generation_options=flow_config.model_dump(mode="json", exclude_none=True),
                target_word_count=runtime_inputs.target_word_count,
                minimum_word_count=runtime_inputs.minimum_word_count,
                maximum_word_count=runtime_inputs.maximum_word_count,
            ),
            self.providers.candidate,
            node_key=node_key,
        )
        return cast(dict[str, object], execution.state_update())

    async def review_candidates(
        self,
        state: ChapterWorkflowState,
    ) -> dict[str, object]:
        context_key, context_result = await self._context(state)
        plan_execution = await self._model_execution(
            state,
            "plan",
            ChapterWorkflowPlanOutput,
        )
        candidates = await self._candidate_executions(state)
        execution = await self.model_activities.execute_review(
            ChapterWorkflowReviewInput(
                context_snapshot=context_result.context_snapshot,
                context_activity_key=context_key,
                context_result_hash=context_result.result_hash,
                upstream_refs={
                    "plan": self._ref(plan_execution),
                    **{item.ref_name: self._ref(item) for item in candidates},
                },
                plan=cast(ChapterWorkflowPlanOutput, plan_execution.result.output),
                candidates=[
                    cast(ChapterWorkflowCandidateOutput, item.result.output)
                    for item in candidates
                ],
            ),
            self.providers.review,
        )
        return cast(dict[str, object], execution.state_update())

    async def refine_candidate(self, state: ChapterWorkflowState) -> dict[str, object]:
        return await self._execute_stage(
            state,
            node_key="refine_candidate",
            stage="review_guided_refinement",
        )

    async def enhance_content(self, state: ChapterWorkflowState) -> dict[str, object]:
        return await self._execute_stage(
            state,
            node_key="enhance_content",
            stage="enhanced_review",
        )

    async def repair_consistency(
        self,
        state: ChapterWorkflowState,
    ) -> dict[str, object]:
        return await self._execute_stage(
            state,
            node_key="repair_consistency",
            stage="consistency",
        )

    async def optimize_style(self, state: ChapterWorkflowState) -> dict[str, object]:
        return await self._execute_stage(
            state,
            node_key="optimize_style",
            stage="optimizer",
        )

    async def enrich_content(self, state: ChapterWorkflowState) -> dict[str, object]:
        return await self._execute_stage(
            state,
            node_key="enrich_content",
            stage="enrichment",
        )

    async def compress_candidate(self, state: ChapterWorkflowState) -> dict[str, object]:
        runtime_inputs = self._payload().runtime_inputs
        content = await self._recommended_content(state, before_node="compress_candidate")
        word_count = count_chapter_words(content)
        if word_count <= runtime_inputs.maximum_word_count:
            return {"skipped_stages": {"compress_candidate": "within_word_limit"}}
        return await self._execute_stage(
            state,
            node_key="compress_candidate",
            stage="compression",
        )

    async def _recommended_content(
        self,
        state: ChapterWorkflowState,
        *,
        before_node: str,
    ) -> str:
        candidates = await self._candidate_executions(state)
        review = await self._model_execution(
            state,
            "review:version_review",
            ChapterWorkflowReviewOutput,
        )
        review_output = cast(ChapterWorkflowReviewOutput, review.result.output)
        selected = next(
            item
            for item in candidates
            if cast(ChapterWorkflowCandidateOutput, item.result.output).ordinal
            == review_output.best_ordinal
        )
        content = cast(ChapterWorkflowCandidateOutput, selected.result.output).content
        for prior_node, prior_stage in self._STAGE_REFS:
            if prior_node == before_node:
                break
            ref_name = f"post_review:{prior_stage}"
            if ref_name not in state.activity_refs:
                continue
            execution = await self._model_execution(
                state,
                ref_name,
                ChapterWorkflowPostReviewOutput,
            )
            output = cast(ChapterWorkflowPostReviewOutput, execution.result.output)
            if output.content:
                content = output.content
        return content

    async def _execute_stage(
        self,
        state: ChapterWorkflowState,
        *,
        node_key: str,
        stage: ChapterWorkflowPostReviewStage,
    ) -> dict[str, object]:
        context_key, context_result = await self._context(state)
        candidates = await self._candidate_executions(state)
        review = await self._model_execution(
            state,
            "review:version_review",
            ChapterWorkflowReviewOutput,
        )
        review_output = cast(ChapterWorkflowReviewOutput, review.result.output)
        selected = next(
            item
            for item in candidates
            if cast(ChapterWorkflowCandidateOutput, item.result.output).ordinal
            == review_output.best_ordinal
        )
        prior_executions = []
        for prior_node, prior_stage in self._STAGE_REFS:
            if prior_node == node_key:
                break
            ref_name = f"post_review:{prior_stage}"
            if ref_name in state.activity_refs:
                prior_executions.append(
                    await self._model_execution(
                        state,
                        ref_name,
                        ChapterWorkflowPostReviewOutput,
                    )
                )
        runtime_inputs = self._payload().runtime_inputs
        execution = await self.model_activities.execute_post_review(
            ChapterWorkflowPostReviewInput(
                context_snapshot=context_result.context_snapshot,
                context_activity_key=context_key,
                context_result_hash=context_result.result_hash,
                upstream_refs={
                    selected.ref_name: self._ref(selected),
                    review.ref_name: self._ref(review),
                    **{item.ref_name: self._ref(item) for item in prior_executions},
                },
                source_candidate=cast(
                    ChapterWorkflowCandidateOutput,
                    selected.result.output,
                ),
                review=review_output,
                stage=stage,
                prior_stage_results=[
                    cast(ChapterWorkflowPostReviewOutput, item.result.output)
                    for item in prior_executions
                ],
                target_word_count=runtime_inputs.target_word_count,
                minimum_word_count=runtime_inputs.minimum_word_count,
                maximum_word_count=runtime_inputs.maximum_word_count,
            ),
            self.providers.post_review,
            node_key=cast(Any, node_key),
            ref_name=f"post_review:{stage}",
        )
        return cast(dict[str, object], execution.state_update())

    async def persist_drafts(self, state: ChapterWorkflowState) -> dict[str, object]:
        candidates = await self._candidate_executions(state)
        review = await self._model_execution(
            state,
            "review:version_review",
            ChapterWorkflowReviewOutput,
        )
        review_output = cast(ChapterWorkflowReviewOutput, review.result.output)
        post_refs: list[ChapterWorkflowActivityRef] = []
        for _node_key, stage in self._STAGE_REFS:
            ref_name = f"post_review:{stage}"
            if ref_name in state.activity_refs:
                execution = await self._model_execution(
                    state,
                    ref_name,
                    ChapterWorkflowPostReviewOutput,
                )
                post_refs.append(self._ref(execution))
        persisted = await ChapterWorkflowCandidatePersistenceService(self.execution).execute(
            ChapterWorkflowPersistCandidatesInput(
                candidate_refs=[self._ref(item) for item in candidates],
                review_ref=self._ref(review),
                post_review_refs={review_output.best_ordinal: post_refs},
            )
        )
        update = persisted.state_update()
        return {
            "candidate_version_ids": update["candidate_version_ids"],
            "activity_refs": update["activity_refs"],
            "result_refs": update["result_refs"],
        }

def build_chapter_workflow_production_bindings(
    execution: JobExecutionContext,
    *,
    provider_factory: ProviderFactory = ChapterWorkflowLLMProviders,
) -> ChapterWorkflowGraphBindings:
    providers = provider_factory(execution)
    return ChapterWorkflowBindingAssembler(execution, providers).bindings()


def build_chapter_workflow_job_handler(
    database_url: str | URL,
    *,
    provider_factory: ProviderFactory = ChapterWorkflowLLMProviders,
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
    "ChapterWorkflowBindingAssembler",
    "ChapterWorkflowLLMProviders",
    "ChapterWorkflowProviders",
    "ProviderFactory",
    "build_chapter_workflow_job_handler",
    "build_chapter_workflow_production_bindings",
]
