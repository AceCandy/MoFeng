# AIMETA P=后台任务Schema_任务状态与日志响应|R=任务列表_任务详情|NR=不含任务提交请求|E=BackgroundTaskResponse|X=http|A=response|D=pydantic|S=none|RD=./README.ai
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class BackgroundTaskLogEntry(BaseModel):
    timestamp: datetime
    level: str
    message: str


class BackgroundTaskResponse(BaseModel):
    id: str
    user_id: int
    project_id: Optional[str] = None
    task_type: str
    title: str
    status: str
    progress: int
    payload: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    log_entries: List[BackgroundTaskLogEntry] = []
    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
