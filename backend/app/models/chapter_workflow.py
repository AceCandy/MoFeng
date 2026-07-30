# AIMETA P=持久章节工作流模型_run与command_inbox|R=编排状态_活动槽_命令幂等|NR=不拥有lease_activity_event或正文|E=ChapterWorkflowRun_ChapterWorkflowCommand|X=internal|A=ORM模型|D=sqlalchemy|S=db|RD=./README.ai
"""Persistent Chapter workflow orchestration state and command inbox."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ChapterWorkflowRun(Base):
    """One durable graph run; JobRun remains the execution authority."""

    __tablename__ = "chapter_workflow_runs"
    __table_args__ = (
        UniqueConstraint("root_job_id", name="uq_chapter_workflow_root_job"),
        CheckConstraint("chapter_number > 0", name="ck_chapter_workflow_chapter_number"),
        CheckConstraint("base_revision >= 0", name="ck_chapter_workflow_base_revision"),
        CheckConstraint(
            "workflow_version >= 1 AND state_schema_version >= 1 "
            "AND context_schema_version >= 1",
            name="ck_chapter_workflow_schema_versions",
        ),
        CheckConstraint("row_revision >= 0", name="ck_chapter_workflow_row_revision"),
        CheckConstraint(
            "progress >= 0 AND progress <= 100",
            name="ck_chapter_workflow_progress",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'retry_wait', 'waiting_for_selection', "
            "'finalizing', 'projection_pending', 'needs_attention', 'successful', "
            "'failed', 'cancelled', 'superseded')",
            name="ck_chapter_workflow_status",
        ),
        CheckConstraint(
            "((is_active AND status IN ('queued', 'running', 'retry_wait', "
            "'waiting_for_selection', 'finalizing', 'projection_pending', "
            "'needs_attention')) OR (NOT is_active AND status IN "
            "('successful', 'failed', 'cancelled', 'superseded')))",
            name="ck_chapter_workflow_active_status",
        ),
        Index(
            "uq_chapter_workflow_active",
            "project_id",
            "chapter_number",
            "base_revision",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_chapter_workflow_status",
            "status",
            "updated_at",
        ),
        Index(
            "ix_chapter_workflow_chapter",
            "chapter_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    base_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    root_job_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("background_tasks.id", ondelete="RESTRICT"),
        nullable=False,
    )
    workflow_version: Mapped[int] = mapped_column(Integer, nullable=False)
    state_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    row_revision: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    context_schema_version: Mapped[int] = mapped_column(Integer, nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    context_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    runtime_input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_id: Mapped[Optional[str]] = mapped_column(Text)
    progress: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    error_category: Mapped[Optional[str]] = mapped_column(String(64))
    public_error: Mapped[Optional[str]] = mapped_column(String(512))
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    successor_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_workflow_runs.id", ondelete="SET NULL"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChapterWorkflowCommand(Base):
    """Idempotent durable command submitted to one workflow run."""

    __tablename__ = "chapter_workflow_commands"
    __table_args__ = (
        CheckConstraint("payload_version >= 1", name="ck_chapter_workflow_command_version"),
        CheckConstraint(
            "expected_run_revision >= 0 AND expected_chapter_revision >= 0",
            name="ck_chapter_workflow_command_revisions",
        ),
        CheckConstraint(
            "type IN ('select', 'retry', 'retry_external', 'retry_projection', 'cancel')",
            name="ck_chapter_workflow_command_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'applied', 'rejected')",
            name="ck_chapter_workflow_command_status",
        ),
        Index(
            "ix_chapter_workflow_command_pending",
            "run_id",
            "status",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chapter_workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_version: Mapped[int] = mapped_column(Integer, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    actor_user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    expected_run_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_chapter_revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    expected_checkpoint_id: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    rejection_code: Mapped[Optional[str]] = mapped_column(String(64))
    result_payload: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
