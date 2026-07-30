# AIMETA P=章节工作流canonical_context_activity|R=冻结检索输入_私有快照_activity重放|NR=不写run基础身份或graph_checkpoint|E=ChapterWorkflowContextService|X=internal|A=domain_service|D=sqlalchemy,pydantic|S=db,net|RD=./README.ai
"""Durable retrieval activity for the versioned Chapter workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..schemas.chapter_context import ChapterContext, ContextFallback, stable_digest
from ..schemas.job import (
    ChapterWorkflowJobPayload,
    ChapterWorkflowRetrievalInputs,
)
from ..schemas.novel import FlowConfig
from .chapter_context_resolver import ChapterContextResolver
from .job_registry import SideEffectClass
from .job_service import LeaseLostError
from .job_worker import JobExecutionContext, RetryableJobError

RETRIEVAL_ACTIVITY_REF = "retrieval_context"


class ChapterWorkflowRetrievalActivityResult(BaseModel):
    """私有 activity 结果；完整快照不得复制到 Graph checkpoint。"""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    base_context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    context_snapshot: dict[str, Any]
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    retrieval_source_revision: str = Field(min_length=1)
    retrieval_fallback: Optional[ContextFallback] = None
    retrieval_snapshot_id: str = Field(min_length=1)
    result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_content_addresses(self):
        context = ChapterContext.model_validate(self.context_snapshot)
        if context.input_hash != self.context_hash:
            raise ValueError("retrieval activity context hash 与快照不一致")
        expected_result_hash = stable_digest(self.model_dump(mode="json", exclude={"result_hash"}))
        if self.result_hash != expected_result_hash:
            raise ValueError("retrieval activity result hash 与结果不一致")
        return self


@dataclass(frozen=True)
class ChapterWorkflowContextResult:
    """运行时可用的 enriched context 及 checkpoint 引用更新。"""

    activity_key: str
    result: ChapterWorkflowRetrievalActivityResult

    def state_update(self) -> dict[str, Any]:
        return {
            "node_key": "plan_and_direct",
            "context_hash": self.result.context_hash,
            "activity_refs": {RETRIEVAL_ACTIVITY_REF: self.activity_key},
            "result_refs": {
                RETRIEVAL_ACTIVITY_REF: self.result.result_hash,
            },
        }


def build_chapter_workflow_retrieval_inputs(
    *,
    context: ChapterContext,
    flow_config: FlowConfig,
    resolver: ChapterContextResolver,
) -> ChapterWorkflowRetrievalInputs:
    """按 legacy pipeline 的 preset/override 顺序冻结有效检索配置。"""

    enabled = True
    mode = "two_stage" if flow_config.preset in {"enhanced", "ultimate"} else "simple"
    if flow_config.enable_rag is not None:
        enabled = flow_config.enable_rag
    if flow_config.rag_mode:
        mode = flow_config.rag_mode

    outline = context.outline.value
    query = "\n".join(
        part
        for part in (
            outline.get("title"),
            outline.get("summary"),
            context.writing_notes.value,
        )
        if part
    )
    mission = context.chapter_mission.value
    return ChapterWorkflowRetrievalInputs(
        enabled=enabled,
        mode=mode,
        query_text=resolver.normalize_rag_query(query),
        pov_character=mission.get("pov") or mission.get("pov_character"),
    )


class ChapterWorkflowContextService:
    """Validate the base freeze and execute/replay its retrieval activity."""

    def __init__(
        self,
        execution: JobExecutionContext,
        *,
        resolver_factory: Callable[[AsyncSession], ChapterContextResolver] = (
            ChapterContextResolver
        ),
    ) -> None:
        self.execution = execution
        self.resolver_factory = resolver_factory

    async def execute_retrieval_activity(self) -> ChapterWorkflowContextResult:
        payload, base_context = await self._load_base_context()
        request_payload = {
            "workflow_version": payload.workflow_version,
            "state_schema_version": payload.state_schema_version,
            "context_schema_version": payload.context_schema_version,
            "run_id": payload.run_id,
            "base_context_hash": payload.context_hash,
            "retrieval_inputs": payload.runtime_inputs.retrieval_inputs.model_dump(mode="json"),
        }
        activity_key = f"wf:freeze_context:{stable_digest(request_payload)}"
        activity = await self.execution.begin_activity(
            activity_key,
            # Retrieval providers are read-only; replay does not need an
            # external mutation idempotency key beyond the durable intent.
            side_effect_class=SideEffectClass.IDEMPOTENT_EXTERNAL,
            request_payload=request_payload,
        )
        if not activity.should_execute:
            return ChapterWorkflowContextResult(
                activity_key=activity_key,
                result=ChapterWorkflowRetrievalActivityResult.model_validate(activity.result),
            )

        try:
            inputs = payload.runtime_inputs.retrieval_inputs
            async with self.execution.session_factory() as session:
                resolver = self.resolver_factory(session)
                enriched = await resolver.with_retrieval(
                    base_context,
                    user_id=self.execution.lease.user_id,
                    enabled=inputs.enabled,
                    query_text=inputs.query_text,
                    mode=inputs.mode,
                    pov_character=inputs.pov_character,
                )
            result_payload = {
                "schema_version": 1,
                "base_context_hash": payload.context_hash,
                "context_snapshot": enriched.snapshot_payload(),
                "context_hash": enriched.input_hash,
                "retrieval_source_revision": enriched.rag.source_revision,
                "retrieval_fallback": (
                    enriched.rag.fallback.value if enriched.rag.fallback else None
                ),
                "retrieval_snapshot_id": enriched.rag.value.retrieval_snapshot_id,
            }
            result_payload["result_hash"] = stable_digest(result_payload)
            result = ChapterWorkflowRetrievalActivityResult.model_validate(result_payload)
            await self.execution.complete_activity(
                activity_key,
                provider_request_key=activity.provider_request_key,
                result=result.model_dump(mode="json"),
            )
        except LeaseLostError:
            raise
        except Exception as error:
            await self.execution.mark_activity_failed(
                activity_key,
                provider_request_key=activity.provider_request_key,
                error_category="chapter_context_retrieval_failed",
                retryable=True,
            )
            raise RetryableJobError(
                "chapter_context_retrieval_failed",
                "章节检索上下文构建失败，请稍后重试",
            ) from error

        return ChapterWorkflowContextResult(activity_key=activity_key, result=result)

    async def _load_base_context(
        self,
    ) -> tuple[ChapterWorkflowJobPayload, ChapterContext]:
        lease = self.execution.lease
        if lease.job_type != "chapter_workflow" or lease.payload_version != 1:
            raise ValueError("workflow root job 类型或版本不匹配")
        payload = ChapterWorkflowJobPayload.model_validate(lease.payload)
        async with self.execution.session_factory() as session:
            run = await ChapterWorkflowRepository(session).get_user_run(
                payload.run_id,
                user_id=lease.user_id,
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
            )
            if not frozen_identity:
                raise ValueError("workflow run 与 root job 冻结身份不一致")
            base_context = ChapterContext.model_validate(run.context_snapshot)

        if (
            base_context.input_hash != payload.context_hash
            or base_context.project_id != payload.project_id
            or base_context.chapter_number != payload.chapter_number
        ):
            raise ValueError("workflow base context 与冻结身份不一致")
        return payload, base_context
