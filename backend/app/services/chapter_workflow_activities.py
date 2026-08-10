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
from ..schemas.job import ChapterWorkflowJobPayload
from ..utils.ai_telemetry import AICallResult
from .chapter_workflow_context import ChapterWorkflowRetrievalActivityResult
from .job_registry import SideEffectClass
from .job_service import LeaseLostError
from .job_worker import JobExecutionContext

logger = logging.getLogger(__name__)

ChapterWorkflowPostReviewStage = Literal[
    "review_guided_refinement",
    "enhanced_review",
    "self_critique",
    "reader_simulator",
    "consistency",
    "optimizer",
    "enrichment",
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
]


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


class ChapterWorkflowPostReviewInput(_PrivateInput):
    """一个稳定 post-review stage 的私有输入。"""

    source_candidate: ChapterWorkflowCandidateOutput
    review: ChapterWorkflowReviewOutput
    stage: ChapterWorkflowPostReviewStage
    prior_stage_results: list["ChapterWorkflowPostReviewOutput"] = Field(
        default_factory=list,
        max_length=20,
    )

    @model_validator(mode="after")
    def validate_prior_stages(self):
        stages = [result.stage for result in self.prior_stage_results]
        if len(stages) != len(set(stages)):
            raise ValueError("post-review 前序 stage 不可重复")
        if self.stage in stages:
            raise ValueError("post-review 当前 stage 不可出现在前序结果中")
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
    ) -> ChapterWorkflowModelActivityExecution:
        return await self._execute(
            node_key="plan_and_direct",
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
    ) -> ChapterWorkflowModelActivityExecution:
        execution = await self._execute(
            node_key="generate_candidates",
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
    ) -> ChapterWorkflowModelActivityExecution:
        execution = await self._execute(
            node_key="review_candidates",
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
    ) -> ChapterWorkflowModelActivityExecution:
        execution = await self._execute(
            node_key="review_candidates",
            stage=request.stage,
            ref_name=f"post_review:{request.stage}",
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
            "plan_and_direct",
            "generate_candidates",
            "review_candidates",
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
                public_message=(f"章节工作流 {stage} 外部调用结果未知，需要人工确认"),
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
        if lease.job_type != "chapter_workflow" or lease.payload_version != 1:
            raise ValueError("workflow root job 类型或版本不匹配")
        payload = ChapterWorkflowJobPayload.model_validate(lease.payload)
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
            if (
                retrieval_activity is None
                or retrieval_activity.status != "succeeded"
                or retrieval_activity.side_effect_class != SideEffectClass.IDEMPOTENT_EXTERNAL.value
                or not retrieval_activity.activity_key.startswith("wf:freeze_context:")
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
