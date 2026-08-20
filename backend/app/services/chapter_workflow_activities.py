# AIMETA P=章节工作流模型activity|R=plan_候选ordinal_review_stage私有结果重放|NR=不持久化候选或推进graph_checkpoint|E=ChapterWorkflowModelActivityService|X=internal|A=domain_service|D=pydantic,sqlalchemy|S=db,net|RD=./README.ai
"""Typed model activities for the durable Chapter workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, TypeVar, cast, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..repositories.job_repository import JobRepository
from ..schemas.chapter_context import ChapterContext, stable_digest
from ..schemas.job import (
    ChapterWorkflowJobPayload,
    validate_chapter_workflow_job_payload,
)
from ..utils.ai_telemetry import AICallResult
from .chapter_word_count_settings import count_chapter_words
from .chapter_workflow_context import ChapterWorkflowRetrievalActivityResult
from .job_public_projection import sanitize_public_text
from .job_registry import SideEffectClass
from .job_service import LeaseLostError
from .job_worker import JobExecutionContext
from .llm_service import get_llm_failure_diagnostic

logger = logging.getLogger(__name__)

ChapterWorkflowPostReviewStage = Literal[
    "review_guided_refinement",
    "enhanced_review",
    "self_critique",
    "reader_simulator",
    "consistency",
    "optimizer",
    "enrichment",
    "compression",
]
ChapterWorkflowModelStage = Literal[
    "plan_and_direct",
    "generate_candidate",
    "version_review",
    "review_guided_refinement",
    "enhanced_review",
    "self_critique",
    "reader_simulator",
    "consistency",
    "optimizer",
    "enrichment",
    "compression",
]

_STAGE_PUBLIC_NAMES = {
    "plan_and_direct": "章节规划",
    "generate_candidate": "生成候选正文",
    "version_review": "候选版本评审",
    "review_guided_refinement": "按评审修订正文",
    "enhanced_review": "增强正文",
    "self_critique": "自我审校",
    "reader_simulator": "读者模拟",
    "consistency": "修复一致性",
    "optimizer": "优化正文",
    "enrichment": "扩写正文",
    "compression": "压缩正文",
}


def _public_model_identity(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = " ".join(value.split()).strip()
    lowered = normalized.lower()
    if (
        not normalized
        or "://" in normalized
        or lowered.startswith(("bearer ", "sk-"))
    ):
        return None
    return normalized[:128]


def _ambiguous_public_message(stage: ChapterWorkflowModelStage, exc: Exception) -> str:
    diagnostic = get_llm_failure_diagnostic(exc)
    if not diagnostic:
        return f"章节工作流 {stage} 外部调用结果未知，需要人工确认"

    provider = _public_model_identity(diagnostic.get("provider"))
    model = _public_model_identity(diagnostic.get("model"))
    target = ""
    if provider:
        target = f"供应商 {provider}"
    if model:
        target = f"{target} 的模型 {model}" if target else f"模型 {model}"

    reason = diagnostic.get("reason")
    reason_text = reason if isinstance(reason, str) and reason else "AI 服务调用失败"
    status_code = diagnostic.get("status_code")
    if isinstance(status_code, int):
        reason_text = f"{reason_text}（HTTP {status_code}）"

    stage_name = _STAGE_PUBLIC_NAMES.get(stage, stage)
    target_text = f"{target} " if target else ""
    recovery_text = (
        "本次结果未保存，请重试当前节点"
        if reason_text.startswith("模型")
        else "未获得可确认的结果，请确认后重试当前节点"
    )
    return sanitize_public_text(
        f"{stage_name}调用{target_text}失败：{reason_text}。{recovery_text}",
    )


class ChapterWorkflowActivityRef(BaseModel):
    """一个已持久化私有 activity result 的内容寻址引用。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    activity_key: str = Field(min_length=1, max_length=128)
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class _PrivateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    context_snapshot: dict[str, Any]
    context_activity_key: str = Field(min_length=1, max_length=128)
    context_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    upstream_refs: dict[str, ChapterWorkflowActivityRef] = Field(
        default_factory=dict,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_context_snapshot(self):
        ChapterContext.model_validate(self.context_snapshot)
        return self


class ChapterWorkflowPlanInput(_PrivateInput):
    """私有规划输入；完整内容只在 handler 内存中传给 provider。"""

    planning_options: dict[str, Any] = Field(default_factory=dict)


class ChapterWorkflowPlanOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["plan"] = "plan"
    mission: dict[str, Any]
    allowed_new_characters: list[str] = Field(default_factory=list, max_length=100)


class ChapterWorkflowCandidateInput(_PrivateInput):
    """一个候选 ordinal 的完整私有 provider 输入。"""

    plan: ChapterWorkflowPlanOutput
    ordinal: int = Field(ge=1, le=100)
    style_hint: str | None = Field(default=None, max_length=2000)
    generation_options: dict[str, Any] = Field(default_factory=dict)
    target_word_count: int = Field(default=3000, ge=2200)
    minimum_word_count: int = Field(default=2200, ge=2200)
    maximum_word_count: int = Field(default=3300, ge=2200)

    @model_validator(mode="after")
    def validate_word_count_contract(self):
        if not (
            self.minimum_word_count
            <= self.target_word_count
            <= self.maximum_word_count
        ):
            raise ValueError("candidate 字数上下限与目标不一致")
        return self


class ChapterWorkflowCandidateOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["candidate"] = "candidate"
    ordinal: int = Field(ge=1, le=100)
    content: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChapterWorkflowReviewInput(_PrivateInput):
    """版本评审输入；候选正文不进入 activity request metadata。"""

    plan: ChapterWorkflowPlanOutput
    candidates: list[ChapterWorkflowCandidateOutput] = Field(
        min_length=1,
        max_length=100,
    )

    @model_validator(mode="after")
    def validate_candidate_ordinals(self):
        ordinals = [candidate.ordinal for candidate in self.candidates]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("候选 ordinal 不可重复")
        return self


class ChapterWorkflowReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["review"] = "review"
    best_ordinal: int = Field(ge=1, le=100)
    report: dict[str, Any]

    def to_evaluation_payload(self) -> dict[str, Any]:
        """转换为写作台评审面板使用的结构，并保留原始评审报告。"""
        evaluation: dict[str, dict[str, Any]] = {}
        raw_reviews = self.report.get("version_reviews")
        if isinstance(raw_reviews, list):
            for raw_review in raw_reviews:
                if not isinstance(raw_review, dict):
                    continue
                version_number = raw_review.get("version_number")
                if not isinstance(version_number, int) or not 1 <= version_number <= 100:
                    continue
                pros = raw_review.get("pros")
                cons = raw_review.get("cons")
                scores = raw_review.get("scores")
                overall_review = raw_review.get("overall_review")
                evaluation[f"version{version_number}"] = {
                    "pros": [item for item in pros if isinstance(item, str)]
                    if isinstance(pros, list)
                    else [],
                    "cons": [item for item in cons if isinstance(item, str)]
                    if isinstance(cons, list)
                    else [],
                    "overall_review": overall_review
                    if isinstance(overall_review, str)
                    else "",
                    "scores": scores if isinstance(scores, dict) else {},
                }

        reason = ""
        for key in ("final_recommendation", "overall_evaluation", "summary"):
            value = self.report.get(key)
            if isinstance(value, str) and value.strip():
                reason = value.strip()
                break
        return {
            "best_choice": self.best_ordinal,
            "reason_for_choice": reason,
            "evaluation": evaluation,
            "report": self.report,
        }


class ChapterWorkflowPostReviewInput(_PrivateInput):
    """一个稳定 post-review stage 的私有输入。"""

    source_candidate: ChapterWorkflowCandidateOutput
    review: ChapterWorkflowReviewOutput
    stage: ChapterWorkflowPostReviewStage
    prior_stage_results: list["ChapterWorkflowPostReviewOutput"] = Field(
        default_factory=list,
        max_length=20,
    )
    target_word_count: int = Field(default=3000, ge=2200)
    minimum_word_count: int = Field(default=2200, ge=2200)
    maximum_word_count: int = Field(default=3300, ge=2200)

    @model_validator(mode="after")
    def validate_prior_stages(self):
        stages = [result.stage for result in self.prior_stage_results]
        if len(stages) != len(set(stages)):
            raise ValueError("post-review 前序 stage 不可重复")
        if self.stage in stages:
            raise ValueError("post-review 当前 stage 不可出现在前序结果中")
        if not (
            self.minimum_word_count
            <= self.target_word_count
            <= self.maximum_word_count
        ):
            raise ValueError("post-review 字数上下限与目标不一致")
        return self


class ChapterWorkflowPostReviewOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["post_review"] = "post_review"
    stage: ChapterWorkflowPostReviewStage
    content: str | None = None
    report: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_nonempty_result(self):
        if self.content is None and not self.report:
            raise ValueError("post-review 结果必须包含正文或报告")
        return self


ChapterWorkflowModelOutput = (
    ChapterWorkflowPlanOutput
    | ChapterWorkflowCandidateOutput
    | ChapterWorkflowReviewOutput
    | ChapterWorkflowPostReviewOutput
)


class ChapterWorkflowModelActivityResult(BaseModel):
    """私有 activity 结果；Graph 只能复制 result_hash 与 activity key。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    stage: ChapterWorkflowModelStage
    subject_ordinal: int | None = Field(default=None, ge=1, le=100)
    upstream_result_hashes: dict[str, str] = Field(default_factory=dict, max_length=100)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output: ChapterWorkflowModelOutput
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    ai_telemetry: dict[str, Any] | None = None
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_addresses(self):
        if self.stage == "generate_candidate" or self.stage in get_args(
            ChapterWorkflowPostReviewStage
        ):
            if self.subject_ordinal is None:
                raise ValueError("candidate/post-review result 缺少 subject ordinal")
        elif self.subject_ordinal is not None:
            raise ValueError("非候选模型结果不可携带 subject ordinal")
        if isinstance(self.output, ChapterWorkflowCandidateOutput):
            if self.output.ordinal != self.subject_ordinal:
                raise ValueError("candidate result subject ordinal 与输出不一致")
        output_payload = self.output.model_dump(mode="json")
        if self.output_hash != stable_digest(output_payload):
            raise ValueError("model activity output hash 与结果不一致")
        expected_result_hash = stable_digest(self.model_dump(mode="json", exclude={"result_hash"}))
        if self.result_hash != expected_result_hash:
            raise ValueError("model activity result hash 与结果不一致")
        return self


@dataclass(frozen=True)
class ChapterWorkflowModelActivityExecution:
    """私有结果及其引用型 checkpoint 更新。"""

    activity_key: str
    ref_name: str
    result: ChapterWorkflowModelActivityResult

    def state_update(self) -> dict[str, dict[str, str]]:
        return {
            "activity_refs": {self.ref_name: self.activity_key},
            "result_refs": {self.ref_name: self.result.result_hash},
        }


InputT = TypeVar("InputT", bound=_PrivateInput)
OutputT = TypeVar("OutputT", bound=BaseModel)
ModelProvider = Callable[..., Awaitable[OutputT | AICallResult[OutputT]]]


class ChapterWorkflowModelActivityService:
    """Execute model-backed stages through stable ambiguous activity intents."""

    def __init__(self, execution: JobExecutionContext) -> None:
        self.execution = execution

    async def execute_plan(
        self,
        request: ChapterWorkflowPlanInput,
        provider: ModelProvider[ChapterWorkflowPlanOutput],
        *,
        node_key: Literal["plan_chapter"] = "plan_chapter",
    ) -> ChapterWorkflowModelActivityExecution:
        return await self._execute(
            node_key=node_key,
            stage="plan_and_direct",
            ref_name="plan",
            request=request,
            output_type=ChapterWorkflowPlanOutput,
            provider=provider,
        )

    async def execute_candidate(
        self,
        request: ChapterWorkflowCandidateInput,
        provider: ModelProvider[ChapterWorkflowCandidateOutput],
        *,
        node_key: Literal[
            "generate_candidate_1",
            "generate_candidate_2",
        ] = "generate_candidate_1",
    ) -> ChapterWorkflowModelActivityExecution:
        execution = await self._execute(
            node_key=node_key,
            stage="generate_candidate",
            ref_name=f"candidate:{request.ordinal}",
            request=request,
            output_type=ChapterWorkflowCandidateOutput,
            provider=provider,
        )
        output = cast(ChapterWorkflowCandidateOutput, execution.result.output)
        if output.ordinal != request.ordinal:
            raise ValueError("candidate activity ordinal 与请求不一致")
        return execution

    async def execute_review(
        self,
        request: ChapterWorkflowReviewInput,
        provider: ModelProvider[ChapterWorkflowReviewOutput],
        *,
        node_key: Literal["review_candidates"] = "review_candidates",
    ) -> ChapterWorkflowModelActivityExecution:
        execution = await self._execute(
            node_key=node_key,
            stage="version_review",
            ref_name="review:version_review",
            request=request,
            output_type=ChapterWorkflowReviewOutput,
            provider=provider,
        )
        output = cast(ChapterWorkflowReviewOutput, execution.result.output)
        if output.best_ordinal not in {candidate.ordinal for candidate in request.candidates}:
            raise ValueError("review best ordinal 不在候选集合中")
        return execution

    async def execute_post_review(
        self,
        request: ChapterWorkflowPostReviewInput,
        provider: ModelProvider[ChapterWorkflowPostReviewOutput],
        *,
        node_key: Literal[
            "refine_candidate",
            "enhance_content",
            "repair_consistency",
            "optimize_style",
            "enrich_content",
            "compress_candidate",
        ] = "refine_candidate",
        ref_name: str | None = None,
    ) -> ChapterWorkflowModelActivityExecution:
        execution = await self._execute(
            node_key=node_key,
            stage=request.stage,
            ref_name=ref_name or f"post_review:{request.stage}",
            request=request,
            output_type=ChapterWorkflowPostReviewOutput,
            provider=provider,
        )
        output = cast(ChapterWorkflowPostReviewOutput, execution.result.output)
        if output.stage != request.stage:
            raise ValueError("post-review stage 与请求不一致")
        return execution

    async def _execute(
        self,
        *,
        node_key: Literal[
            "plan_chapter",
            "generate_candidate_1",
            "generate_candidate_2",
            "review_candidates",
            "refine_candidate",
            "enhance_content",
            "repair_consistency",
            "optimize_style",
            "enrich_content",
            "compress_candidate",
        ],
        stage: ChapterWorkflowModelStage,
        ref_name: str,
        request: InputT,
        output_type: type[OutputT],
        provider: ModelProvider[OutputT],
    ) -> ChapterWorkflowModelActivityExecution:
        payload = await self._load_root_payload(request)
        input_hash = stable_digest(request.model_dump(mode="json"))
        canonical_request = {
            "schema_version": 1,
            "workflow_version": payload.workflow_version,
            "state_schema_version": payload.state_schema_version,
            "run_id": payload.run_id,
            "node_key": node_key,
            "stage": stage,
            "input_hash": input_hash,
        }
        activity_key = f"wf:{node_key}:{stable_digest(canonical_request)}"
        activity = await self.execution.begin_activity(
            activity_key,
            side_effect_class=SideEffectClass.AMBIGUOUS_EXTERNAL,
            request_payload=canonical_request,
        )
        execution_activity_key = activity.activity_key
        if not activity.should_execute:
            result = ChapterWorkflowModelActivityResult.model_validate(activity.result)
            self._validate_replay(
                result,
                stage=stage,
                input_hash=input_hash,
                output_type=output_type,
            )
            return ChapterWorkflowModelActivityExecution(
                activity_key=execution_activity_key,
                ref_name=ref_name,
                result=result,
            )

        failure_phase = "provider"
        try:
            provider_result = await provider(
                request,
                provider_request_key=activity.provider_request_key,
            )
            failure_phase = "response_validation"
            ai_call = provider_result if isinstance(provider_result, AICallResult) else None
            output_value = ai_call.value if ai_call is not None else provider_result
            output = output_type.model_validate(output_value)
            self._validate_output(request=request, output=output)
            result_payload = {
                "schema_version": 1,
                "stage": stage,
                "subject_ordinal": self._subject_ordinal(request),
                "upstream_result_hashes": {
                    name: ref.result_hash for name, ref in sorted(request.upstream_refs.items())
                },
                "input_hash": input_hash,
                "output": output.model_dump(mode="json"),
                "output_hash": stable_digest(output.model_dump(mode="json")),
                "ai_telemetry": ai_call.telemetry_dict() if ai_call is not None else None,
            }
            result_payload["result_hash"] = stable_digest(result_payload)
            result = ChapterWorkflowModelActivityResult.model_validate(result_payload)
        except LeaseLostError:
            raise
        except Exception as exc:
            logger.error(
                "Chapter workflow model activity result uncertain: "
                "stage=%s failure_phase=%s activity_key=%s input_hash=%s error_type=%s",
                stage,
                failure_phase,
                execution_activity_key,
                input_hash,
                type(exc).__name__,
            )
            await self.execution.mark_activity_ambiguous(
                execution_activity_key,
                provider_request_key=activity.provider_request_key,
                public_message=_ambiguous_public_message(stage, exc),
            )
            raise AssertionError("mark_activity_ambiguous 必须终止当前执行")

        await self.execution.complete_activity(
            execution_activity_key,
            provider_request_key=activity.provider_request_key,
            result=result.model_dump(mode="json"),
            ai_call=ai_call,
        )
        return ChapterWorkflowModelActivityExecution(
            activity_key=execution_activity_key,
            ref_name=ref_name,
            result=result,
        )

    async def _load_root_payload(
        self,
        request: _PrivateInput,
    ) -> ChapterWorkflowJobPayload:
        lease = self.execution.lease
        if lease.job_type != "chapter_workflow":
            raise ValueError("workflow root job 类型或版本不匹配")
        payload = validate_chapter_workflow_job_payload(
            lease.payload_version,
            lease.payload,
        )
        context = ChapterContext.model_validate(request.context_snapshot)
        async with self.execution.session_factory() as session:
            run = await ChapterWorkflowRepository(session).get_user_run(
                payload.run_id,
                user_id=lease.user_id,
            )
            retrieval_activity = await JobRepository(session).get_activity(
                job_id=lease.job_id,
                activity_key=request.context_activity_key,
            )
            if run is None:
                raise ValueError("workflow run 不存在")
            frozen_identity = (
                run.root_job_id == lease.job_id
                and run.project_id == payload.project_id == lease.project_id
                and run.chapter_id == payload.chapter_id
                and run.chapter_number == payload.chapter_number
                and run.base_revision == payload.base_revision
                and run.workflow_version == payload.workflow_version
                and run.state_schema_version == payload.state_schema_version
                and run.context_schema_version == payload.context_schema_version
                and run.context_hash == payload.context_hash
                and run.runtime_input_hash == payload.runtime_input_hash
                and context.project_id == payload.project_id
                and context.chapter_number == payload.chapter_number
            )
            if not frozen_identity:
                raise ValueError("workflow model activity 与冻结身份不一致")
            retrieval_node_key = (
                retrieval_activity.request_payload.get("node_key")
                if retrieval_activity is not None
                and isinstance(retrieval_activity.request_payload, dict)
                else None
            )
            if (
                retrieval_activity is None
                or retrieval_activity.status != "succeeded"
                or retrieval_activity.side_effect_class != SideEffectClass.IDEMPOTENT_EXTERNAL.value
                or retrieval_node_key != "retrieve_context"
                or not retrieval_activity.activity_key.startswith(f"wf:{retrieval_node_key}:")
            ):
                raise ValueError("workflow retrieval activity 不存在或未完成")
            retrieval_payload = retrieval_activity.result_payload
            await self._validate_upstream_results(
                session=session,
                job_id=lease.job_id,
                request=request,
            )
        retrieval_result = ChapterWorkflowRetrievalActivityResult.model_validate(retrieval_payload)
        if (
            retrieval_result.base_context_hash != payload.context_hash
            or retrieval_result.result_hash != request.context_result_hash
            or retrieval_result.context_hash != context.input_hash
            or retrieval_result.context_snapshot != request.context_snapshot
        ):
            raise ValueError("workflow model activity 与 retrieval result 不一致")
        return payload

    @staticmethod
    def _subject_ordinal(request: _PrivateInput) -> int | None:
        if isinstance(request, ChapterWorkflowCandidateInput):
            return request.ordinal
        if isinstance(request, ChapterWorkflowPostReviewInput):
            return request.source_candidate.ordinal
        return None

    @staticmethod
    async def _validate_upstream_results(
        *,
        session: AsyncSession,
        job_id: str,
        request: _PrivateInput,
    ) -> None:
        expected_outputs = ChapterWorkflowModelActivityService._expected_upstream_outputs(request)
        if set(request.upstream_refs) != set(expected_outputs):
            raise ValueError("workflow model activity 上游引用集合不一致")
        repository = JobRepository(session)
        for ref_name, expected_output in expected_outputs.items():
            ref = request.upstream_refs[ref_name]
            activity = await repository.get_activity(
                job_id=job_id,
                activity_key=ref.activity_key,
            )
            if (
                activity is None
                or activity.status != "succeeded"
                or activity.side_effect_class != SideEffectClass.AMBIGUOUS_EXTERNAL.value
            ):
                raise ValueError("workflow model activity 上游结果不存在或未完成")
            result = ChapterWorkflowModelActivityResult.model_validate(activity.result_payload)
            if (
                result.stage != ChapterWorkflowModelActivityService._stage_for_ref_name(ref_name)
                or result.result_hash != ref.result_hash
                or result.output.model_dump(mode="json") != expected_output.model_dump(mode="json")
            ):
                raise ValueError("workflow model activity 上游结果不一致")

    @staticmethod
    def _expected_upstream_outputs(
        request: _PrivateInput,
    ) -> dict[str, BaseModel]:
        if isinstance(request, ChapterWorkflowPlanInput):
            return {}
        if isinstance(request, ChapterWorkflowCandidateInput):
            return {"plan": request.plan}
        if isinstance(request, ChapterWorkflowReviewInput):
            return {
                "plan": request.plan,
                **{f"candidate:{candidate.ordinal}": candidate for candidate in request.candidates},
            }
        if isinstance(request, ChapterWorkflowPostReviewInput):
            return {
                f"candidate:{request.source_candidate.ordinal}": request.source_candidate,
                "review:version_review": request.review,
                **{f"post_review:{result.stage}": result for result in request.prior_stage_results},
            }
        raise TypeError("不支持的 workflow model activity input")

    @staticmethod
    def _stage_for_ref_name(ref_name: str) -> ChapterWorkflowModelStage:
        if ref_name == "plan":
            return "plan_and_direct"
        if ref_name.startswith("candidate:"):
            return "generate_candidate"
        if ref_name == "review:version_review":
            return "version_review"
        if ref_name.startswith("post_review:"):
            return cast(
                ChapterWorkflowModelStage,
                ref_name.removeprefix("post_review:"),
            )
        raise ValueError("不支持的 workflow model activity 上游引用")

    @staticmethod
    def _validate_replay(
        result: ChapterWorkflowModelActivityResult,
        *,
        stage: ChapterWorkflowModelStage,
        input_hash: str,
        output_type: type[OutputT],
    ) -> None:
        if result.stage != stage or result.input_hash != input_hash:
            raise ValueError("model activity replay identity 不一致")
        output_type.model_validate(result.output)

    @staticmethod
    def _validate_output(*, request: _PrivateInput, output: BaseModel) -> None:
        if (
            isinstance(request, ChapterWorkflowCandidateInput)
            and isinstance(output, ChapterWorkflowCandidateOutput)
            and output.ordinal != request.ordinal
        ):
            raise ValueError("candidate activity ordinal 与请求不一致")
        if isinstance(request, ChapterWorkflowReviewInput) and isinstance(
            output,
            ChapterWorkflowReviewOutput,
        ):
            ordinals = {candidate.ordinal for candidate in request.candidates}
            if output.best_ordinal not in ordinals:
                raise ValueError("review best ordinal 不在候选集合中")
        if (
            isinstance(request, ChapterWorkflowPostReviewInput)
            and isinstance(output, ChapterWorkflowPostReviewOutput)
            and output.stage != request.stage
        ):
            raise ValueError("post-review stage 与请求不一致")
        if (
            isinstance(request, ChapterWorkflowPostReviewInput)
            and request.stage == "compression"
            and isinstance(output, ChapterWorkflowPostReviewOutput)
        ):
            word_count = count_chapter_words(output.content or "")
            if not request.minimum_word_count <= word_count <= request.maximum_word_count:
                raise ValueError("压缩正文未满足冻结字数合同")
