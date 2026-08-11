# AIMETA P=后台任务模型_用户可见任务日志|R=后台任务状态_进度_日志|NR=不含任务执行逻辑|E=BackgroundTask|X=db|A=任务记录|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class BackgroundTask(Base):
    """Durable job current row，同时保持旧后台任务查询契约。"""

    __tablename__ = "background_tasks"
    __table_args__ = (
        Index(
            "uq_background_tasks_idempotency",
            "user_id",
            "task_type",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
        Index(
            "ix_background_tasks_claim",
            "executor_generation",
            "status",
            "available_at",
        ),
        Index(
            "ix_background_tasks_stream_created",
            "stream_type",
            "stream_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
        index=True,
    )
    progress: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    error: Mapped[Optional[str]] = mapped_column(Text)
    log_entries: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    payload_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255))
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default="3"
    )
    lease_owner: Mapped[Optional[str]] = mapped_column(String(128))
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), index=True
    )
    heartbeat_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    fencing_token: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    cancel_requested_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    dead_lettered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_category: Mapped[Optional[str]] = mapped_column(String(64))
    executor_generation: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )
    stream_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="job", server_default="job"
    )
    stream_id: Mapped[str] = mapped_column(String(64), nullable=False)
    event_sequence: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


JobRun = BackgroundTask
