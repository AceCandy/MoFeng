# AIMETA P=后台任务Schema_任务状态与日志响应|R=任务列表_任务详情|NR=不含任务提交请求|E=BackgroundTaskResponse|X=http|A=response|D=pydantic|S=none|RD=./README.ai
from datetime import datetime
from typing import Any, ClassVar, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


PublicTaskStatus = Literal["queued", "running", "succeeded", "failed"]


class BackgroundTaskLogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str


class BackgroundTaskResponse(BaseModel):
    _PUBLIC_STATUS_BY_INTERNAL_STATUS: ClassVar[dict[str, PublicTaskStatus]] = {
        "queued": "queued",
        "retry_wait": "queued",
        "running": "running",
        "succeeded": "succeeded",
        "failed": "failed",
        "dead_letter": "failed",
        "needs_attention": "failed",
        "cancelled": "failed",
    }

    id: str
    user_id: int
    project_id: Optional[str] = None
    stream_type: Optional[str] = None
    stream_id: Optional[str] = None
    task_type: str
    title: str
    status: PublicTaskStatus
    progress: int
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    log_entries: List[BackgroundTaskLogEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def public_status(cls, status: str) -> PublicTaskStatus:
        """将内部 durable job 状态收敛到旧前端可识别的四态。"""

        try:
            return cls._PUBLIC_STATUS_BY_INTERNAL_STATUS[status]
        except KeyError as exc:
            raise ValueError(f"未知后台任务状态: {status}") from exc

    @field_validator("status", mode="before")
    @classmethod
    def map_public_status(cls, status: object) -> PublicTaskStatus:
        if not isinstance(status, str):
            raise ValueError("后台任务状态必须是字符串")
        return cls.public_status(status)


class BackgroundTaskSnapshotResponse(BaseModel):
    """同一数据库快照中的任务列表与可续传游标。"""

    tasks: List[BackgroundTaskResponse]
    snapshot_revision: str
    resume_cursor: int
    stream_type: Optional[str] = None
    stream_id: Optional[str] = None


class BackgroundTaskEventResponse(BaseModel):
    """SSE 中一条可按任务 ID upsert 的 durable 事件。"""

    cursor: int
    event_type: str
    task: BackgroundTaskResponse


class BackgroundTaskCursorResetResponse(BaseModel):
    """游标已越过保留窗口，客户端必须重新获取 snapshot。"""

    reason: Literal["cursor_expired"] = "cursor_expired"
    retained_through_cursor: int
