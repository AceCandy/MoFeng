"""expand AI usage pricing and projection retention audit

Revision ID: f2a6c9d4e8b1
Revises: e7c9a1b2d3f4
Create Date: 2026-07-28 20:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a6c9d4e8b1"
down_revision: Union[str, None] = "e7c9a1b2d3f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for column_name in (
        "input_price_per_million",
        "output_price_per_million",
        "cached_input_price_per_million",
        "cache_write_input_price_per_million",
    ):
        op.add_column(
            "user_ai_models",
            sa.Column(column_name, sa.Numeric(precision=24, scale=12), nullable=True),
        )
    op.add_column(
        "user_ai_models",
        sa.Column("pricing_currency", sa.String(length=3), nullable=True),
    )
    op.create_check_constraint(
        "ck_user_ai_models_input_price",
        "user_ai_models",
        "input_price_per_million IS NULL OR input_price_per_million >= 0",
    )
    op.create_check_constraint(
        "ck_user_ai_models_output_price",
        "user_ai_models",
        "output_price_per_million IS NULL OR output_price_per_million >= 0",
    )
    op.create_check_constraint(
        "ck_user_ai_models_cached_input_price",
        "user_ai_models",
        "cached_input_price_per_million IS NULL OR cached_input_price_per_million >= 0",
    )
    op.create_check_constraint(
        "ck_user_ai_models_cache_write_price",
        "user_ai_models",
        "cache_write_input_price_per_million IS NULL OR "
        "cache_write_input_price_per_million >= 0",
    )

    op.create_table(
        "ai_usage_records",
        sa.Column("job_activity_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("provider_type", sa.String(length=32), nullable=False),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("model_id", sa.Integer(), nullable=True),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("output_tokens", sa.BigInteger(), nullable=True),
        sa.Column("total_tokens", sa.BigInteger(), nullable=True),
        sa.Column("cached_input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("cache_write_input_tokens", sa.BigInteger(), nullable=True),
        sa.Column("reasoning_tokens", sa.BigInteger(), nullable=True),
        sa.Column(
            "usage_complete",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("cost_amount", sa.Numeric(precision=24, scale=12), nullable=True),
        sa.Column("cost_currency", sa.String(length=3), nullable=True),
        sa.Column(
            "cost_known",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("cost_unknown_reason", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "input_tokens IS NULL OR input_tokens >= 0",
            name="ck_ai_usage_input_tokens",
        ),
        sa.CheckConstraint(
            "output_tokens IS NULL OR output_tokens >= 0",
            name="ck_ai_usage_output_tokens",
        ),
        sa.CheckConstraint(
            "total_tokens IS NULL OR total_tokens >= 0",
            name="ck_ai_usage_total_tokens",
        ),
        sa.CheckConstraint(
            "cost_amount IS NULL OR cost_amount >= 0",
            name="ck_ai_usage_cost_amount",
        ),
        sa.ForeignKeyConstraint(
            ["job_activity_id"],
            ["job_activities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["background_tasks.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["project_id"],
            ["novel_projects.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("job_activity_id"),
    )
    op.create_index(
        "ix_ai_usage_records_job_id",
        "ai_usage_records",
        ["job_id"],
    )
    op.create_index(
        "ix_ai_usage_records_user_id",
        "ai_usage_records",
        ["user_id"],
    )
    op.create_index(
        "ix_ai_usage_project_created",
        "ai_usage_records",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_ai_usage_provider_model",
        "ai_usage_records",
        ["provider_type", "model_name"],
    )

    op.create_table(
        "chapter_projection_retention_audits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("artifact_generation", sa.String(length=36), nullable=False),
        sa.Column("artifact_kind", sa.String(length=32), nullable=False),
        sa.Column("projection_run_id", sa.String(length=36), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=160), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("request_scope", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chapter_number > 0 AND revision > 0",
            name="ck_chapter_projection_retention_positive_identity",
        ),
        sa.CheckConstraint(
            "artifact_kind IN ('rag', 'foreshadowing')",
            name="ck_chapter_projection_retention_artifact_kind",
        ),
        sa.CheckConstraint(
            "mode IN ('preview', 'purge')",
            name="ck_chapter_projection_retention_mode",
        ),
        sa.CheckConstraint(
            "status IN ('completed', 'rejected')",
            name="ck_chapter_projection_retention_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operator_user_id",
            "idempotency_key",
            name="uq_chapter_projection_retention_operator_key",
        ),
    )
    op.create_index(
        "ix_chapter_projection_retention_rate",
        "chapter_projection_retention_audits",
        ["operator_user_id", "created_at"],
    )
    op.create_index(
        "ix_chapter_projection_retention_target",
        "chapter_projection_retention_audits",
        ["project_id", "chapter_number", "revision", "artifact_generation"],
    )
    op.create_index(
        "uq_chapter_projection_retention_completed_purge",
        "chapter_projection_retention_audits",
        [
            "project_id",
            "chapter_number",
            "revision",
            "artifact_generation",
            "artifact_kind",
        ],
        unique=True,
        postgresql_where=sa.text("mode = 'purge' AND status = 'completed'"),
    )


def downgrade() -> None:
    raise RuntimeError(
        "AI usage and projection retention rows are audit data; "
        "use the documented binary rollback floor instead of destructive downgrade."
    )
