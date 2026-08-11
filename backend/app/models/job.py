# AIMETA P=持久任务事件模型_追加式审计流|R=任务事件游标_流内顺序|NR=不含状态流转逻辑|E=JobEvent|X=db|A=事件记录|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class JobEventStream(Base):
    """用户可见事件流的所有权与并发 sequence 水位。"""

    __tablename__ = "job_event_streams"
    __table_args__ = (
        CheckConstraint("last_sequence >= 0", name="ck_job_event_stream_sequence"),
        CheckConstraint(
            "retained_through_cursor >= 0",
            name="ck_job_event_stream_retention_cursor",
        ),
        Index("ix_job_event_streams_user", "user_id", "stream_type", "stream_id"),
    )

    stream_type: Mapped[str] = mapped_column(String(32), primary_key=True)
    stream_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_sequence: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    retained_through_cursor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobEvent(Base):
    """任务状态机的追加式事件；cursor 全局递增，sequence 在 stream 内递增。"""

    __tablename__ = "job_events"
    __table_args__ = (
        UniqueConstraint(
            "stream_type", "stream_id", "sequence", name="uq_job_events_stream_sequence"
        ),
        Index("ix_job_events_user_cursor", "user_id", "cursor"),
        Index("ix_job_events_stream_cursor", "stream_type", "stream_id", "cursor"),
    )

    cursor: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    job_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("background_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    stream_type: Mapped[str] = mapped_column(String(32), nullable=False)
    stream_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JobEventRetention(Base):
    """记录每个用户已清理到的事件游标，供 SSE 判断是否必须重建快照。"""

    __tablename__ = "job_event_retentions"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    retained_through_cursor: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobActivity(Base):
    """外部副作用的 durable intent/result，以 activity_key 保证单一记录。"""

    __tablename__ = "job_activities"
    __table_args__ = (
        UniqueConstraint("job_id", "activity_key", name="uq_job_activities_job_key"),
        Index("ix_job_activities_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    job_id: Mapped[str] = mapped_column(
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    activity_key: Mapped[str] = mapped_column(String(128), nullable=False)
    side_effect_class: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    provider_request_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    attempt: Mapped[int] = mapped_column(nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    request_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    result_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    error_category: Mapped[Optional[str]] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AIUsageRecord(Base):
    """与 durable activity 1:1 的供应商中立 token/cost 审计。"""

    __tablename__ = "ai_usage_records"
    __table_args__ = (
        CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_usage_input_tokens",
        ),
        CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_usage_output_tokens",
        ),
        CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_ai_usage_total_tokens",
        ),
        CheckConstraint(
            "cost_amount IS NULL OR cost_amount >= 0",
            name="ck_ai_usage_cost_amount",
        ),
        Index("ix_ai_usage_project_created", "project_id", "created_at"),
        Index("ix_ai_usage_provider_model", "provider_type", "model_name"),
    )

    job_activity_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("job_activities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("background_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_type: Mapped[str] = mapped_column(String(32), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_id: Mapped[Optional[int]] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    input_tokens: Mapped[Optional[int]] = mapped_column(BigInteger)
    output_tokens: Mapped[Optional[int]] = mapped_column(BigInteger)
    total_tokens: Mapped[Optional[int]] = mapped_column(BigInteger)
    cached_input_tokens: Mapped[Optional[int]] = mapped_column(BigInteger)
    cache_write_input_tokens: Mapped[Optional[int]] = mapped_column(BigInteger)
    reasoning_tokens: Mapped[Optional[int]] = mapped_column(BigInteger)
    usage_complete: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    cost_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(24, 12))
    cost_currency: Mapped[Optional[str]] = mapped_column(String(3))
    cost_known: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    cost_unknown_reason: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class JobExecutorControl(Base):
    """durable worker 集群的当前 rollout generation 与切代 owner。"""

    __tablename__ = "job_executor_controls"
    __table_args__ = (
        CheckConstraint("active_generation >= 1", name="ck_job_executor_control_generation"),
        CheckConstraint("fencing_token >= 0", name="ck_job_executor_control_fencing"),
    )

    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    active_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    rollout_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    fencing_token: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class JobWorkerHeartbeat(Base):
    """独立 worker 进程的可观测生命周期；不参与任务结果 fencing。"""

    __tablename__ = "job_worker_heartbeats"
    __table_args__ = (
        Index(
            "ix_job_worker_heartbeats_generation_state",
            "executor_generation",
            "state",
        ),
        Index("ix_job_worker_heartbeats_heartbeat", "heartbeat_at"),
    )

    worker_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    executor_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    heartbeat_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
