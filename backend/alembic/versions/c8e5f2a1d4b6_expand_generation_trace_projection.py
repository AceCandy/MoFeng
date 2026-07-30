"""expand JobEvent-backed generation trace projection

Revision ID: c8e5f2a1d4b6
Revises: b7d4e2f1a9c3
Create Date: 2026-07-30 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "c8e5f2a1d4b6"
down_revision: Union[str, None] = "b7d4e2f1a9c3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chapter_generation_traces",
        sa.Column("source_run_id", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "chapter_generation_traces",
        sa.Column("source_event_cursor", sa.BigInteger(), nullable=True),
    )
    op.create_check_constraint(
        "ck_chapter_generation_trace_source_pair",
        "chapter_generation_traces",
        "(source_run_id IS NULL AND source_event_cursor IS NULL) OR "
        "(source_run_id IS NOT NULL AND source_event_cursor IS NOT NULL)",
    )
    op.create_unique_constraint(
        "uq_chapter_generation_trace_source",
        "chapter_generation_traces",
        ["source_run_id", "source_event_cursor"],
    )
    trace_projection_checkpoints = op.create_table(
        "chapter_generation_trace_projection_checkpoints",
        sa.Column("projector_name", sa.String(length=64), nullable=False),
        sa.Column(
            "last_event_cursor",
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
        sa.CheckConstraint(
            "last_event_cursor >= 0",
            name="ck_chapter_generation_trace_projection_cursor",
        ),
        sa.PrimaryKeyConstraint("projector_name"),
    )
    op.bulk_insert(
        trace_projection_checkpoints,
        [{"projector_name": "chapter_generation_trace_v1", "last_event_cursor": 0}],
    )


def downgrade() -> None:
    op.drop_table("chapter_generation_trace_projection_checkpoints")
    op.drop_constraint(
        "uq_chapter_generation_trace_source",
        "chapter_generation_traces",
        type_="unique",
    )
    op.drop_constraint(
        "ck_chapter_generation_trace_source_pair",
        "chapter_generation_traces",
        type_="check",
    )
    op.drop_column("chapter_generation_traces", "source_event_cursor")
    op.drop_column("chapter_generation_traces", "source_run_id")
