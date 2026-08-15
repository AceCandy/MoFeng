# AIMETA P=持久任务payload契约_版本化业务参数|R=任务payload校验|NR=不含任务执行逻辑|E=ChapterOutlineJobPayload_ChapterWorkflowJobPayload_ChapterFinalizeJobPayload|X=internal|A=pydantic_contract|D=pydantic|S=none|RD=./README.ai
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .chapter_context import stable_digest
from .chapter_workflow import ChapterWorkflowRunId
from .novel import FlowConfig


class ChapterOutlineJobPayload(BaseModel):
    """章节大纲 durable job v1 的持久参数。"""

    project_id: str = Field(min_length=1, max_length=36)
    start_chapter: int = Field(ge=1)
    num_chapters: int = Field(ge=1, le=20)


class ChapterEditPostprocessJobPayload(BaseModel):
    """章节编辑后处理 durable job v1 的不可变正文引用。"""

    project_id: str = Field(min_length=1, max_length=36)
    chapter_number: int = Field(ge=1)
    selected_version_id: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    skip_vector_update: bool = False


class ChapterFinalizeJobPayload(ChapterEditPostprocessJobPayload):
    """章节确认定稿 durable job v1 的不可变正文引用。"""

    chapter_id: Optional[int] = Field(default=None, ge=1)
    chapter_revision_id: Optional[str] = Field(default=None, min_length=36, max_length=36)
    revision: Optional[int] = Field(default=None, ge=1)
    source_hash: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_generation: Optional[str] = Field(default=None, min_length=1, max_length=36)
    execution_mode: Literal["legacy", "shadow"] = "legacy"
    rollout_generation: Optional[int] = Field(default=None, ge=1)
    rollout_fencing_token: Optional[int] = Field(default=None, ge=0)
    workflow_stream_id: Optional[str] = Field(default=None, min_length=1, max_length=64)
    outbox_event_id: Optional[str] = Field(default=None, min_length=36, max_length=36)


class ChapterFinalizeOutboxPayload(BaseModel):
    """ChapterFinalizationRequested v2 的 immutable dispatch contract。"""

    job_type: Literal["chapter_finalize"]
    payload_version: Literal[2]
    project_id: str = Field(min_length=1, max_length=36)
    chapter_id: int = Field(ge=1)
    chapter_number: int = Field(ge=1)
    chapter_revision_id: str = Field(min_length=36, max_length=36)
    revision: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_generation: str = Field(min_length=1, max_length=36)
    execution_mode: Literal["active", "legacy", "shadow"]
    rollout_owner: Literal["legacy", "projection"]
    rollout_generation: int = Field(ge=1)
    rollout_fencing_token: int = Field(ge=0)
    workflow_stream_type: Literal["workflow"]
    workflow_stream_id: str = Field(min_length=1, max_length=64)
    outbox_event_id: str = Field(min_length=36, max_length=36)
    selected_version_id: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    skip_vector_update: bool = False
    dispatch_idempotency_key: str = Field(min_length=1, max_length=255)
    summary_run_id: Optional[str] = Field(default=None, min_length=36, max_length=36)
    summary_artifact_generation: Optional[str] = Field(
        default=None,
        min_length=36,
        max_length=36,
    )

    @model_validator(mode="after")
    def validate_summary_identity(self):
        has_summary_identity = (
            self.summary_run_id is not None and self.summary_artifact_generation is not None
        )
        if self.execution_mode == "legacy" and (
            self.summary_run_id is not None or self.summary_artifact_generation is not None
        ):
            raise ValueError("legacy 事件不能携带 summary projection identity")
        if self.execution_mode != "legacy" and not has_summary_identity:
            raise ValueError("projection 事件缺少 summary projection identity")
        return self


class ChapterOutboxDispatchJobPayload(BaseModel):
    """Outbox dispatcher v1 只引用不可变事件，不复制业务正文。"""

    project_id: str = Field(min_length=1, max_length=36)
    outbox_event_id: str = Field(min_length=36, max_length=36)
    event_type: Literal[
        "ChapterFinalizationRequested",
        "ChapterRevisionSuperseded",
        "ChapterTombstoned",
    ]
    event_version: Literal[2]
    payload_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ChapterProjectionJobPayload(BaseModel):
    """章节投影 durable child job v1 的 immutable revision 引用。"""

    project_id: str = Field(min_length=1, max_length=36)
    chapter_id: int = Field(ge=1)
    chapter_number: int = Field(ge=1)
    chapter_revision_id: str = Field(min_length=36, max_length=36)
    revision: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_generation: str = Field(min_length=1, max_length=36)
    projection_run_id: str = Field(min_length=36, max_length=36)
    artifact_generation: str = Field(min_length=36, max_length=36)
    workflow_stream_id: str = Field(min_length=1, max_length=64)
    outbox_event_id: str = Field(min_length=36, max_length=36)

    rollout_owner: str = Field(default="projection", min_length=1, max_length=32)
    rollout_generation: int = Field(default=1, ge=1)
    rollout_fencing_token: int = Field(default=0, ge=0)
    execution_mode: Literal["active", "shadow"] = "active"
    legacy_job_id: Optional[str] = Field(default=None, min_length=36, max_length=36)
    dependency_run_id: Optional[str] = Field(default=None, min_length=36, max_length=36)
    selected_version_id: Optional[int] = Field(default=None, ge=1)
    content_hash: Optional[str] = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    skip_vector_update: bool = False


class ChapterTombstoneJobPayload(BaseModel):
    """精确清理旧 revision/generation 的 durable job v1 参数。"""

    project_id: str = Field(min_length=1, max_length=36)
    chapter_id: int = Field(ge=1)
    chapter_number: int = Field(ge=1)
    chapter_revision_id: str = Field(min_length=36, max_length=36)
    tombstone_revision: int = Field(ge=1)
    source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_generation: str = Field(min_length=36, max_length=36)
    projection_run_id: str = Field(min_length=36, max_length=36)
    artifact_generation: str = Field(min_length=36, max_length=36)
    target_revision: int = Field(ge=0)
    target_generation: str = Field(min_length=1, max_length=36)
    target_artifact_generations: dict[str, str] = Field(default_factory=dict)
    event_type: Literal["ChapterRevisionSuperseded", "ChapterTombstoned"]
    reason: str = Field(min_length=1, max_length=255)
    workflow_stream_id: str = Field(min_length=1, max_length=64)
    outbox_event_id: str = Field(min_length=36, max_length=36)

    @field_validator("target_artifact_generations")
    @classmethod
    def validate_target_artifact_generations(
        cls,
        value: dict[str, str],
    ) -> dict[str, str]:
        allowed = {"summary", "memory", "rag", "foreshadowing", "trace", "reconcile"}
        if not set(value).issubset(allowed):
            raise ValueError("target_artifact_generations 包含未知投影")
        if any(not generation or len(generation) > 36 for generation in value.values()):
            raise ValueError("target artifact generation 长度必须为 1 到 36")
        return value


class ChapterWorkflowRetrievalInputs(BaseModel):
    """retrieve_context activity 使用的规范化检索输入。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    enabled: bool
    mode: Literal["simple", "two_stage"]
    query_text: str = Field(max_length=2000)
    pov_character: Optional[str] = Field(default=None, max_length=255)


class ChapterWorkflowRuntimeInputs(BaseModel):
    """root job 内冻结的规范化请求；retrieval 仍由后续 activity 执行。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    project_id: str = Field(min_length=1, max_length=36)
    chapter_number: int = Field(ge=1)
    writing_notes: Optional[str] = None
    flow_config: FlowConfig = Field(default_factory=FlowConfig)
    retrieval_inputs: ChapterWorkflowRetrievalInputs
    target_word_count: int = Field(default=3000, ge=2200)
    minimum_word_count: int = Field(default=2200, ge=2200)
    maximum_word_count: int = Field(default=3300, ge=2200)

    @model_validator(mode="after")
    def validate_word_count_contract(self) -> "ChapterWorkflowRuntimeInputs":
        if not (
            self.minimum_word_count
            <= self.target_word_count
            <= self.maximum_word_count
        ):
            raise ValueError("workflow 字数上下限与目标不一致")
        return self


class ChapterWorkflowJobPayload(BaseModel):
    """durable Chapter workflow root job 的冻结启动参数。"""

    model_config = ConfigDict(extra="forbid")

    run_id: ChapterWorkflowRunId
    project_id: str = Field(min_length=1, max_length=36)
    chapter_id: int = Field(ge=1)
    chapter_number: int = Field(ge=1)
    base_revision: int = Field(ge=0)
    workflow_version: Literal[1] = 1
    state_schema_version: Literal[1] = 1
    context_schema_version: Literal[1] = 1
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    runtime_inputs: ChapterWorkflowRuntimeInputs

    @model_validator(mode="after")
    def validate_frozen_runtime_identity(self):
        if (
            self.runtime_inputs.project_id != self.project_id
            or self.runtime_inputs.chapter_number != self.chapter_number
        ):
            raise ValueError("workflow runtime input 身份与 root payload 不一致")
        expected_hash = stable_digest(self.runtime_inputs.model_dump(mode="json"))
        if self.runtime_input_hash != expected_hash:
            raise ValueError("workflow runtime input hash 与冻结 payload 不一致")
        return self
    candidate_count: int = Field(default=1, ge=1, le=2)
    optional_stages: dict[
        Literal[
            "enhance_content",
            "repair_consistency",
            "optimize_style",
            "enrich_content",
        ],
        bool,
    ] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_graph_options(self) -> "ChapterWorkflowJobPayload":
        flow = self.runtime_inputs.flow_config
        expected_count = max(1, min(2, flow.versions or 1))
        expected_optional = resolve_chapter_workflow_optional_stages(flow)
        enabled_optional = {
            key: enabled for key, enabled in self.optional_stages.items() if enabled
        }
        if self.candidate_count != expected_count or enabled_optional != expected_optional:
            raise ValueError("graph options 与冻结 flow config 不一致")
        return self


def resolve_chapter_workflow_optional_stages(flow: FlowConfig) -> dict[str, bool]:
    """把 preset 与显式覆盖归一为唯一的可选节点集合。"""

    ultimate = flow.preset == "ultimate"
    return {
        key: True
        for key, enabled in {
            "enhance_content": flow.preset in {"enhanced", "ultimate"},
            "repair_consistency": (
                ultimate if flow.enable_consistency is None else flow.enable_consistency
            ),
            "optimize_style": (
                ultimate if flow.enable_optimizer is None else flow.enable_optimizer
            ),
            "enrich_content": (
                ultimate if flow.enable_enrichment is None else flow.enable_enrichment
            ),
        }.items()
        if enabled
    }


def validate_chapter_workflow_job_payload(
    payload_version: int,
    payload: object,
) -> ChapterWorkflowJobPayload:
    """按 root Job payload version 精确解析，未知版本禁止回退。"""

    if payload_version == 1:
        return ChapterWorkflowJobPayload.model_validate(payload)
    raise ValueError(f"不支持的 Chapter workflow payload version: {payload_version}")
