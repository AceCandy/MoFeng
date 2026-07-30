"""expand durable Chapter workflow and LangGraph checkpoint schema

Revision ID: b7d4e2f1a9c3
Revises: f2a6c9d4e8b1
Create Date: 2026-07-29 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "b7d4e2f1a9c3"
down_revision: Union[str, None] = "f2a6c9d4e8b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chapter_workflow_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("base_revision", sa.BigInteger(), nullable=False),
        sa.Column("root_job_id", sa.String(length=36), nullable=False),
        sa.Column("workflow_version", sa.Integer(), nullable=False),
        sa.Column("state_schema_version", sa.Integer(), nullable=False),
        sa.Column("row_revision", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("context_schema_version", sa.Integer(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("context_hash", sa.String(length=64), nullable=False),
        sa.Column("runtime_input_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("node_key", sa.String(length=64), nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=True),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("public_error", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("successor_run_id", sa.String(length=36), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("chapter_number > 0", name="ck_chapter_workflow_chapter_number"),
        sa.CheckConstraint("base_revision >= 0", name="ck_chapter_workflow_base_revision"),
        sa.CheckConstraint(
            "workflow_version >= 1 AND state_schema_version >= 1 AND context_schema_version >= 1",
            name="ck_chapter_workflow_schema_versions",
        ),
        sa.CheckConstraint("row_revision >= 0", name="ck_chapter_workflow_row_revision"),
        sa.CheckConstraint(
            "progress >= 0 AND progress <= 100", name="ck_chapter_workflow_progress"
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'retry_wait', 'waiting_for_selection', "
            "'finalizing', 'projection_pending', 'needs_attention', 'successful', "
            "'failed', 'cancelled', 'superseded')",
            name="ck_chapter_workflow_status",
        ),
        sa.CheckConstraint(
            "((is_active AND status IN ('queued', 'running', 'retry_wait', "
            "'waiting_for_selection', 'finalizing', 'projection_pending', "
            "'needs_attention')) OR (NOT is_active AND status IN "
            "('successful', 'failed', 'cancelled', 'superseded')))",
            name="ck_chapter_workflow_active_status",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["root_job_id"], ["background_tasks.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["successor_run_id"], ["chapter_workflow_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("root_job_id", name="uq_chapter_workflow_root_job"),
    )
    op.create_index(
        "uq_chapter_workflow_active",
        "chapter_workflow_runs",
        ["project_id", "chapter_number", "base_revision"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index("ix_chapter_workflow_status", "chapter_workflow_runs", ["status", "updated_at"])
    op.create_index(
        "ix_chapter_workflow_chapter", "chapter_workflow_runs", ["chapter_id", "created_at"]
    )

    op.create_table(
        "chapter_workflow_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("payload_version", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), nullable=False),
        sa.Column("expected_run_revision", sa.BigInteger(), nullable=False),
        sa.Column("expected_chapter_revision", sa.BigInteger(), nullable=False),
        sa.Column("expected_checkpoint_id", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("rejection_code", sa.String(length=64), nullable=True),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("payload_version >= 1", name="ck_chapter_workflow_command_version"),
        sa.CheckConstraint(
            "expected_run_revision >= 0 AND expected_chapter_revision >= 0",
            name="ck_chapter_workflow_command_revisions",
        ),
        sa.CheckConstraint(
            "type IN ('select', 'retry', 'retry_external', 'retry_projection', 'cancel')",
            name="ck_chapter_workflow_command_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'applied', 'rejected')",
            name="ck_chapter_workflow_command_status",
        ),
        sa.ForeignKeyConstraint(["run_id"], ["chapter_workflow_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chapter_workflow_command_pending",
        "chapter_workflow_commands",
        ["run_id", "status", "created_at"],
    )

    checkpoint_migrations = op.create_table(
        "checkpoint_migrations",
        sa.Column("v", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("v"),
    )
    op.create_table(
        "checkpoints",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("parent_checkpoint_id", sa.Text(), nullable=True),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("checkpoint", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id"),
    )
    op.create_table(
        "checkpoint_blobs",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), server_default="", nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("blob", postgresql.BYTEA(), nullable=True),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "channel", "version"),
    )
    op.create_table(
        "checkpoint_writes",
        sa.Column("thread_id", sa.Text(), nullable=False),
        sa.Column("checkpoint_ns", sa.Text(), server_default="", nullable=False),
        sa.Column("checkpoint_id", sa.Text(), nullable=False),
        sa.Column("task_id", sa.Text(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=True),
        sa.Column("blob", postgresql.BYTEA(), nullable=False),
        sa.Column("task_path", sa.Text(), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_ns", "checkpoint_id", "task_id", "idx"),
    )
    op.create_index("checkpoints_thread_id_idx", "checkpoints", ["thread_id"])
    op.create_index("checkpoint_blobs_thread_id_idx", "checkpoint_blobs", ["thread_id"])
    op.create_index("checkpoint_writes_thread_id_idx", "checkpoint_writes", ["thread_id"])
    op.bulk_insert(checkpoint_migrations, [{"v": version} for version in range(10)])


def downgrade() -> None:
    raise RuntimeError(
        "Chapter workflow history and checkpoints are durable state; "
        "use the documented binary rollback floor instead of destructive downgrade."
    )
