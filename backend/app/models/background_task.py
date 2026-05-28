# AIMETA P=后台任务模型_用户可见任务日志|R=后台任务状态_进度_日志|NR=不含任务执行逻辑|E=BackgroundTask|X=db|A=任务记录|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class BackgroundTask(Base):
    """用户可见的后台任务记录，用于前端轮询任务状态和日志。"""

    __tablename__ = "background_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[Optional[dict]] = mapped_column(JSON)
    result: Mapped[Optional[dict]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    log_entries: Mapped[list[dict]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
