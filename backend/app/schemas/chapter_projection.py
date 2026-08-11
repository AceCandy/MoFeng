# AIMETA P=章节投影管理传输契约_重放与rollout|R=请求响应白名单_类型边界|NR=不含数据库或业务逻辑|E=ChapterProjectionOperationRequest_ChapterProjectionRolloutResponse|X=http|A=schema|D=pydantic|S=none|RD=./README.ai
"""管理员章节投影运维操作的白名单传输契约。"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

ProjectionName = Literal[
    "summary",
    "memory",
    "rag",
    "foreshadowing",
    "trace",
    "reconcile",
]
RetentionArtifactKind = Literal["rag", "foreshadowing"]
RolloutOwner = Literal["legacy", "projection"]
RolloutState = Literal["legacy", "shadow", "draining", "projection"]


class ChapterProjectionOperationRequest(BaseModel):
    project_id: str = Field(min_length=36, max_length=36)
    chapter_id: int = Field(ge=1)
    revision: int = Field(ge=1)
    projection_name: ProjectionName
    idempotency_key: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=3, max_length=255)
    outbox_event_id: Optional[str] = Field(default=None, min_length=36, max_length=36)


class ChapterProjectionOperationResponse(BaseModel):
    mode: Literal["dry_run", "replay"]
    status: Literal["eligible", "rejected", "queued"]
    idempotency_key: str
    project_id: str
    chapter_id: int
    chapter_number: int
    revision: int
    current_revision: int
    projection_name: ProjectionName
    reason_code: Optional[str] = None
    run_status_counts: dict[str, int] = Field(default_factory=dict)
    active_projections: list[str] = Field(default_factory=list)
    projection_run_id: Optional[str] = None
    job_id: Optional[str] = None


class ChapterProjectionRetentionRequest(BaseModel):
    project_id: str = Field(min_length=36, max_length=36)
    chapter_number: int = Field(ge=1)
    revision: int = Field(ge=1)
    artifact_generation: str = Field(min_length=1, max_length=36)
    artifact_kind: RetentionArtifactKind
    idempotency_key: str = Field(min_length=1, max_length=160)
    reason: str = Field(min_length=3, max_length=255)
    max_rows: int = Field(default=500, ge=1, le=500)


class ChapterProjectionRetentionResponse(BaseModel):
    mode: Literal["preview", "purge"]
    status: Literal["eligible", "completed", "rejected"]
    idempotency_key: str
    audit_id: str
    project_id: str
    chapter_id: Optional[int] = None
    chapter_number: int
    revision: int
    artifact_generation: str
    artifact_kind: RetentionArtifactKind
    reason_code: Optional[str] = None
    candidate_rows: dict[str, int] = Field(default_factory=dict)
    deleted_rows: dict[str, int] = Field(default_factory=dict)


class ChapterProjectionRolloutMutationRequest(BaseModel):
    project_id: str = Field(min_length=36, max_length=36)
    chapter_id: int = Field(ge=1)
    expected_generation: int = Field(ge=1)
    expected_fencing_token: int = Field(ge=0)
    reason: str = Field(min_length=3, max_length=255)


class ChapterProjectionEnterShadowRequest(ChapterProjectionRolloutMutationRequest):
    observation_seconds: int = Field(default=0, ge=0, le=2_592_000)
    required_observations: int = Field(default=1, ge=1, le=10_000)


class ChapterProjectionRolloutResponse(BaseModel):
    project_id: str
    chapter_id: int
    owner: RolloutOwner
    state: RolloutState
    generation: int
    fencing_token: int
    transition_sequence: int
    observation_started_at: Optional[datetime] = None
    observation_deadline_at: Optional[datetime] = None
    required_observations: int
    successful_observations: int
    failed_observations: int
    last_observed_at: Optional[datetime] = None
    shadow_digest: Optional[str] = None
    shadow_diff: Optional[dict] = None
    cutover_at: Optional[datetime] = None
    rollback_at: Optional[datetime] = None
    gate_ready: bool = False
    gate_reasons: list[str] = Field(default_factory=list)


__all__ = [
    "ChapterProjectionEnterShadowRequest",
    "ChapterProjectionOperationRequest",
    "ChapterProjectionOperationResponse",
    "ChapterProjectionRetentionRequest",
    "ChapterProjectionRetentionResponse",
    "ChapterProjectionRolloutMutationRequest",
    "ChapterProjectionRolloutResponse",
    "ProjectionName",
    "RetentionArtifactKind",
    "RolloutOwner",
    "RolloutState",
]
