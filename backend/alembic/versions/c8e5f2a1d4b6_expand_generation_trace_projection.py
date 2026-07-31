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

_TRACE_PROJECTION_CHECKPOINT_TABLE = "chapter_generation_trace_projection_checkpoints"
_TRACE_PROJECTION_CHECK_NAME = "ck_chapter_generation_trace_projection_cursor"


def _normalize_sql(value: object) -> str:
    return "".join(str(value).lower().split())


def _validate_precreated_trace_projection_checkpoint_table() -> None:
    table = sa.Table(
        _TRACE_PROJECTION_CHECKPOINT_TABLE,
        sa.MetaData(),
        autoload_with=op.get_bind(),
    )
    columns = tuple(table.columns)
    checks = {
        constraint.name: constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }
    valid = (
        tuple(column.name for column in columns)
        == ("projector_name", "last_event_cursor", "updated_at")
        and isinstance(columns[0].type, sa.String)
        and columns[0].type.length == 64
        and not columns[0].nullable
        and columns[0].server_default is None
        and isinstance(columns[1].type, sa.BigInteger)
        and not columns[1].nullable
        and columns[1].server_default is not None
        and _normalize_sql(columns[1].server_default.arg) in {"0", "'0'::bigint"}
        and isinstance(columns[2].type, sa.DateTime)
        and columns[2].type.timezone is True
        and not columns[2].nullable
        and columns[2].server_default is not None
        and _normalize_sql(columns[2].server_default.arg) in {"now()", "current_timestamp"}
        and tuple(column.name for column in table.primary_key.columns) == ("projector_name",)
        and set(checks) == {_TRACE_PROJECTION_CHECK_NAME}
        and _normalize_sql(checks[_TRACE_PROJECTION_CHECK_NAME].sqltext)
        in {"last_event_cursor>=0", "(last_event_cursor>=0)"}
        and not table.foreign_keys
        and not table.indexes
        and not any(isinstance(item, sa.UniqueConstraint) for item in table.constraints)
    )
    if not valid:
        raise RuntimeError("incompatible_preexisting_generation_trace_projection_checkpoint_schema")


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError(
            "generation trace projection checkpoint reconciliation requires an online migration"
        )

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
    checkpoint_table_exists = sa.inspect(op.get_bind()).has_table(
        _TRACE_PROJECTION_CHECKPOINT_TABLE
    )
    if checkpoint_table_exists:
        _validate_precreated_trace_projection_checkpoint_table()
    else:
        op.create_table(
            _TRACE_PROJECTION_CHECKPOINT_TABLE,
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
                name=_TRACE_PROJECTION_CHECK_NAME,
            ),
            sa.PrimaryKeyConstraint("projector_name"),
        )
    op.execute(
        sa.text(
            "INSERT INTO chapter_generation_trace_projection_checkpoints "
            "(projector_name, last_event_cursor) "
            "VALUES ('chapter_generation_trace_v1', 0) "
            "ON CONFLICT (projector_name) DO NOTHING"
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "Generation trace projection checkpoints and source lineage are durable state; "
        "use the documented binary rollback floor instead of destructive downgrade."
    )
