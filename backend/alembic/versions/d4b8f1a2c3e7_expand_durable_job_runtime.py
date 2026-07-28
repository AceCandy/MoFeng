"""expand durable job runtime and event log

Revision ID: d4b8f1a2c3e7
Revises: 9c2f47a1d8e6
Create Date: 2026-07-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4b8f1a2c3e7"
down_revision: Union[str, None] = "9c2f47a1d8e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "background_tasks",
        "status",
        existing_type=sa.String(length=32),
        server_default="queued",
        existing_nullable=False,
    )
    op.alter_column(
        "background_tasks",
        "progress",
        existing_type=sa.Integer(),
        server_default="0",
        existing_nullable=False,
    )
    op.add_column(
        "background_tasks",
        sa.Column("payload_version", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "background_tasks",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )
    op.add_column(
        "background_tasks",
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "background_tasks",
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "background_tasks",
        sa.Column("lease_owner", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column("fencing_token", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "background_tasks",
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column("dead_lettered_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column("error_category", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column("executor_generation", sa.Integer(), server_default="1", nullable=False),
    )
    op.add_column(
        "background_tasks",
        sa.Column("stream_type", sa.String(length=32), server_default="job", nullable=False),
    )
    op.add_column(
        "background_tasks",
        sa.Column("stream_id", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "background_tasks",
        sa.Column("event_sequence", sa.BigInteger(), server_default="0", nullable=False),
    )

    op.execute(
        "UPDATE background_tasks "
        "SET available_at = created_at "
        "WHERE available_at IS NULL"
    )
    op.execute("UPDATE background_tasks SET stream_id = id WHERE stream_id IS NULL")
    op.execute(
        "UPDATE background_tasks "
        "SET status = 'needs_attention', "
        "error_category = 'legacy_running_state_ambiguous', "
        "error = COALESCE(error, '升级前运行中的任务结果未知，需要人工确认'), "
        "completed_at = COALESCE(completed_at, now()) "
        "WHERE status = 'running'"
    )
    op.execute(
        "UPDATE background_tasks "
        "SET status = 'needs_attention', "
        "error_category = 'legacy_unknown_status', "
        "error = COALESCE(error, '升级前任务状态无法识别，需要人工确认'), "
        "completed_at = COALESCE(completed_at, now()) "
        "WHERE status NOT IN ('queued', 'succeeded', 'failed', 'needs_attention')"
    )
    op.alter_column("background_tasks", "available_at", nullable=False)
    op.alter_column("background_tasks", "stream_id", nullable=False)

    op.create_index(
        "uq_background_tasks_idempotency",
        "background_tasks",
        ["user_id", "task_type", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "ix_background_tasks_claim",
        "background_tasks",
        ["executor_generation", "status", "available_at"],
        unique=False,
    )
    op.create_index(
        "ix_background_tasks_lease_expires_at",
        "background_tasks",
        ["lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "ix_background_tasks_stream_created",
        "background_tasks",
        ["stream_type", "stream_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "job_event_streams",
        sa.Column("stream_type", sa.String(length=32), nullable=False),
        sa.Column("stream_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("last_sequence", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "retained_through_cursor",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "last_sequence >= 0",
            name="ck_job_event_stream_sequence",
        ),
        sa.CheckConstraint(
            "retained_through_cursor >= 0",
            name="ck_job_event_stream_retention_cursor",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("stream_type", "stream_id"),
    )
    op.create_index(
        "ix_job_event_streams_user",
        "job_event_streams",
        ["user_id", "stream_type", "stream_id"],
        unique=False,
    )

    op.create_table(
        "job_events",
        sa.Column("cursor", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("stream_type", sa.String(length=32), nullable=False),
        sa.Column("stream_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["background_tasks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("cursor"),
        sa.UniqueConstraint(
            "stream_type",
            "stream_id",
            "sequence",
            name="uq_job_events_stream_sequence",
        ),
    )
    op.create_index("ix_job_events_job_id", "job_events", ["job_id"], unique=False)
    op.create_index("ix_job_events_event_type", "job_events", ["event_type"], unique=False)
    op.create_index(
        "ix_job_events_user_cursor",
        "job_events",
        ["user_id", "cursor"],
        unique=False,
    )
    op.create_index(
        "ix_job_events_stream_cursor",
        "job_events",
        ["stream_type", "stream_id", "cursor"],
        unique=False,
    )

    op.create_table(
        "job_event_retentions",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "retained_through_cursor",
            sa.BigInteger(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "job_activities",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("activity_key", sa.String(length=128), nullable=False),
        sa.Column("side_effect_class", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("provider_request_key", sa.String(length=128), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["job_id"], ["background_tasks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "activity_key", name="uq_job_activities_job_key"),
        sa.UniqueConstraint("provider_request_key", name="uq_job_activities_provider_request_key"),
    )
    op.create_index("ix_job_activities_job_id", "job_activities", ["job_id"], unique=False)
    op.create_index("ix_job_activities_status", "job_activities", ["status"], unique=False)

    op.create_table(
        "job_executor_controls",
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("active_generation", sa.Integer(), nullable=False),
        sa.Column("rollout_owner", sa.String(length=128), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "fencing_token >= 0",
            name="ck_job_executor_control_fencing",
        ),
        sa.CheckConstraint(
            "active_generation >= 1",
            name="ck_job_executor_control_generation",
        ),
        sa.PrimaryKeyConstraint("scope"),
    )
    op.execute(
        "INSERT INTO job_executor_controls "
        "(scope, active_generation, rollout_owner, fencing_token) "
        "VALUES ('default', 1, 'durable-job-migration', 0)"
    )

    op.create_table(
        "job_worker_heartbeats",
        sa.Column("worker_id", sa.String(length=128), nullable=False),
        sa.Column("executor_generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("worker_id"),
    )
    op.create_index(
        "ix_job_worker_heartbeats_generation_state",
        "job_worker_heartbeats",
        ["executor_generation", "state"],
        unique=False,
    )
    op.create_index(
        "ix_job_worker_heartbeats_heartbeat",
        "job_worker_heartbeats",
        ["heartbeat_at"],
        unique=False,
    )

    op.execute(
        """
        INSERT INTO job_event_streams (
            stream_type,
            stream_id,
            user_id,
            project_id,
            last_sequence,
            retained_through_cursor,
            created_at,
            updated_at
        )
        SELECT
            stream_type,
            stream_id,
            user_id,
            project_id,
            1,
            0,
            created_at,
            updated_at
        FROM background_tasks
        """
    )

    op.execute(
        """
        INSERT INTO job_events (
            job_id,
            user_id,
            project_id,
            stream_type,
            stream_id,
            sequence,
            event_type,
            payload,
            created_at
        )
        SELECT
            id,
            user_id,
            project_id,
            stream_type,
            stream_id,
            1,
            'job.legacy_imported',
            json_build_object(
                'task',
                json_build_object(
                    'id', id,
                    'user_id', user_id,
                    'project_id', project_id,
                    'stream_type', stream_type,
                    'stream_id', stream_id,
                    'task_type', task_type,
                    'title', title,
                    'status', CASE
                        WHEN status = 'retry_wait' THEN 'queued'
                        WHEN status IN ('dead_letter', 'needs_attention', 'cancelled') THEN 'failed'
                        ELSE status
                    END,
                    'progress', progress,
                    'error', error,
                    'log_entries', COALESCE(log_entries, '[]'::json),
                    'created_at', created_at,
                    'updated_at', updated_at,
                    'started_at', started_at,
                    'completed_at', completed_at
                )
            ),
            updated_at
        FROM background_tasks
        ORDER BY created_at, id
        """
    )
    op.execute("UPDATE background_tasks SET event_sequence = 1")


def downgrade() -> None:
    raise RuntimeError(
        "durable job migration contains audit and activity data; deploy older code instead of dropping it"
    )
