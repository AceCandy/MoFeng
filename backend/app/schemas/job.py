# AIMETA P=持久任务payload契约_版本化业务参数|R=任务payload校验|NR=不含任务执行逻辑|E=ChapterOutlineJobPayload_ChapterGenerationJobPayload_ChapterFinalizeJobPayload|X=internal|A=pydantic_contract|D=pydantic|S=none|RD=./README.ai
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

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
            self.summary_run_id is not None
            and self.summary_artifact_generation is not None
        )
        if self.execution_mode == "legacy" and (
            self.summary_run_id is not None
            or self.summary_artifact_generation is not None
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


class ChapterGenerationJobPayload(BaseModel):
    """章节 LangGraph 生成 durable job v1 的持久参数。"""

    project_id: str = Field(min_length=1, max_length=36)
    chapter_number: int = Field(ge=1)
    writing_notes: Optional[str] = None
    flow_config: FlowConfig = Field(default_factory=FlowConfig)
    from_node_key: Optional[str] = None
