# AIMETA P=章节工作流持久状态与HTTP契约|R=checkpoint校验_start_snapshot_command响应|NR=不含正文_prompt_运行时对象|E=ChapterWorkflowStateV1_ChapterWorkflowSnapshot|X=http,internal|A=pydantic_contract|D=pydantic|S=none|RD=./README.ai
"""Serializable state and HTTP contracts for durable Chapter workflows."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Optional
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from .novel import FlowConfig

CHAPTER_WORKFLOW_VERSION_V1 = 1
CHAPTER_WORKFLOW_STATE_SCHEMA_VERSION_V1 = 1
CHAPTER_WORKFLOW_CONTEXT_SCHEMA_VERSION_V1 = 1

ChapterWorkflowNodeKeyV1 = Literal[
    "freeze_context",
    "plan_and_direct",
    "generate_candidates",
    "review_candidates",
    "persist_candidates",
    "waiting_for_selection",
    "finalize_revision",
    "projection_pending",
    "observe_projection",
    "successful",
]
ChapterWorkflowSnapshotNodeKeyV1 = (
    ChapterWorkflowNodeKeyV1
    | Literal[
        "failed",
        "cancelled",
        "superseded",
    ]
)
ChapterWorkflowRunStatus = Literal[
    "queued",
    "running",
    "retry_wait",
    "waiting_for_selection",
    "finalizing",
    "projection_pending",
    "needs_attention",
    "successful",
    "failed",
    "cancelled",
    "superseded",
]
ChapterWorkflowRootJobStatus = Literal[
    "queued",
    "running",
    "retry_wait",
    "waiting",
    "succeeded",
    "failed",
    "dead_letter",
    "needs_attention",
    "cancelled",
]
CHAPTER_WORKFLOW_NODE_KEYS_V1: tuple[ChapterWorkflowNodeKeyV1, ...] = (
    "freeze_context",
    "plan_and_direct",
    "generate_candidates",
    "review_candidates",
    "persist_candidates",
    "waiting_for_selection",
    "finalize_revision",
    "projection_pending",
    "observe_projection",
    "successful",
)

ReferenceKey = Annotated[str, Field(min_length=1, max_length=255)]
ReferenceValue = Annotated[str, Field(min_length=1, max_length=255)]
ChapterVersionId = Annotated[int, Field(ge=1)]
ChapterWorkflowCommandType = Literal[
    "select",
    "retry",
    "retry_external",
    "retry_projection",
    "cancel",
]
ChapterWorkflowCommandStatus = Literal["pending", "applied", "rejected"]


def validate_chapter_workflow_run_id(value: str) -> str:
    """拒绝不能稳定映射为 thread/stream identity 的非规范 UUID。"""

    try:
        parsed = UUID(value)
    except ValueError as error:
        raise ValueError("run_id 必须是规范 UUID") from error
    if str(parsed) != value:
        raise ValueError("run_id 必须是规范 UUID")
    return value


ChapterWorkflowRunId = Annotated[
    str,
    Field(min_length=36, max_length=36),
    AfterValidator(validate_chapter_workflow_run_id),
]


class ChapterWorkflowStateV1(BaseModel):
    """Graph V1 checkpoint；只持久化身份、hash、marker 与结果引用。"""

    model_config = ConfigDict(extra="forbid")

    workflow_version: Literal[1] = 1
    state_schema_version: Literal[1] = 1
    run_id: ChapterWorkflowRunId
    node_key: ChapterWorkflowNodeKeyV1
    context_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    activity_refs: dict[ReferenceKey, ReferenceValue] = Field(
        default_factory=dict,
        max_length=100,
    )
    result_refs: dict[ReferenceKey, ReferenceValue] = Field(
        default_factory=dict,
        max_length=100,
    )
    candidate_version_ids: list[ChapterVersionId] = Field(
        default_factory=list,
        max_length=100,
    )
    selected_version_id: Optional[int] = Field(default=None, ge=1)
    last_applied_command_id: Optional[str] = Field(
        default=None,
        min_length=36,
        max_length=36,
    )
    target_chapter_revision: Optional[int] = Field(default=None, ge=1)
    error_category: Optional[str] = Field(default=None, min_length=1, max_length=64)

    @classmethod
    def initial(cls, *, run_id: str, context_hash: str) -> "ChapterWorkflowStateV1":
        """从 durable run 身份构造首个 freeze_context checkpoint。"""

        return cls(
            run_id=run_id,
            node_key="freeze_context",
            context_hash=context_hash,
        )


class ChapterWorkflowCommandEnvelope(BaseModel):
    """客户端生成的幂等 command 身份与并发前置条件。"""

    model_config = ConfigDict(extra="forbid")

    command_id: ChapterWorkflowRunId
    type: ChapterWorkflowCommandType
    payload_version: Literal[1] = 1
    payload: dict[str, Any] = Field(default_factory=dict, max_length=16)
    expected_run_revision: int = Field(ge=0)
    expected_chapter_revision: int = Field(ge=0)
    expected_checkpoint_id: str = Field(min_length=1, max_length=512)

    @model_validator(mode="after")
    def validate_command_payload(self) -> "ChapterWorkflowCommandEnvelope":
        payload = self.payload
        if self.type == "select":
            selected_version_id = payload.get("selected_version_id")
            if (
                set(payload) != {"selected_version_id"}
                or isinstance(selected_version_id, bool)
                or not isinstance(selected_version_id, int)
                or selected_version_id < 1
            ):
                raise ValueError("select command payload 无效")
        elif self.type in {"retry", "retry_projection"}:
            if payload:
                raise ValueError(f"{self.type} command payload 必须为空")
        elif self.type == "retry_external":
            if set(payload) != {"activity_key", "acknowledge_possible_duplicate"}:
                raise ValueError("retry_external command payload 无效")
            self._validate_activity_key(payload.get("activity_key"))
            if payload.get("acknowledge_possible_duplicate") is not True:
                raise ValueError("retry_external 必须确认可能重复调用")
        else:
            if set(payload) not in (set(), {"activity_key"}):
                raise ValueError("cancel command payload 无效")
            if "activity_key" in payload:
                self._validate_activity_key(payload.get("activity_key"))
        return self

    @staticmethod
    def _validate_activity_key(value: object) -> None:
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise ValueError("activity_key 必须为 1 到 128 个字符")


class ChapterWorkflowSnapshot(BaseModel):
    """供 command/API 复用的当前 run、Chapter 与事件游标快照。"""

    model_config = ConfigDict(extra="forbid")

    run_id: ChapterWorkflowRunId
    root_job_id: ChapterWorkflowRunId
    project_id: str = Field(min_length=1, max_length=36)
    chapter_id: int = Field(ge=1)
    chapter_number: int = Field(ge=1)
    base_revision: int = Field(ge=0)
    current_chapter_revision: int = Field(ge=0)
    workflow_version: Literal[1]
    state_schema_version: Literal[1]
    context_schema_version: Literal[1]
    status: ChapterWorkflowRunStatus
    root_job_status: ChapterWorkflowRootJobStatus
    node_key: ChapterWorkflowSnapshotNodeKeyV1
    checkpoint_id: Optional[str] = Field(default=None, max_length=512)
    progress: int = Field(ge=0, le=100)
    row_revision: int = Field(ge=0)
    is_active: bool
    successor_run_id: Optional[ChapterWorkflowRunId] = None
    error_category: Optional[str] = Field(default=None, max_length=64)
    public_error: Optional[str] = Field(default=None, max_length=512)
    allowed_commands: list[ChapterWorkflowCommandType]
    retry_activity_key: Optional[str] = Field(max_length=128)
    resume_cursor: int = Field(ge=0)


class ChapterWorkflowStartRequest(BaseModel):
    """创建或复用当前章节 active workflow 的公开输入。"""

    model_config = ConfigDict(extra="forbid")

    project_id: str = Field(min_length=1, max_length=36)
    chapter_number: int = Field(ge=1)
    writing_notes: Optional[str] = None
    flow_config: FlowConfig = Field(default_factory=FlowConfig)


class ChapterWorkflowConnection(BaseModel):
    """可恢复的公开 workflow 快照与 opaque durable event stream 地址。"""

    model_config = ConfigDict(extra="forbid")

    snapshot: ChapterWorkflowSnapshot
    events_url: str = Field(min_length=1, max_length=2_048)


class ChapterWorkflowStartResponse(ChapterWorkflowConnection):
    """start 结果在可恢复连接之外标识本次是否创建 run。"""

    created: bool


class ChapterWorkflowCommandResponse(BaseModel):
    """已持久化 command 的公开状态与提交后的当前快照。"""

    model_config = ConfigDict(extra="forbid")

    command_id: ChapterWorkflowRunId
    type: ChapterWorkflowCommandType
    status: ChapterWorkflowCommandStatus
    snapshot: ChapterWorkflowSnapshot


class ChapterWorkflowCommandConflictDetail(BaseModel):
    """409 冲突携带稳定原因和同事务事实之后读取的当前快照。"""

    model_config = ConfigDict(extra="forbid")

    reason_code: str = Field(min_length=1, max_length=64)
    current_snapshot: ChapterWorkflowSnapshot


class ChapterWorkflowCommandConflictResponse(BaseModel):
    """FastAPI 默认 error envelope 中的 typed 409 detail。"""

    model_config = ConfigDict(extra="forbid")

    detail: ChapterWorkflowCommandConflictDetail
