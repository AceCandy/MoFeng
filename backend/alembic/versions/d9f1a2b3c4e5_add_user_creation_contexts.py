"""add per-user project creation contexts

Revision ID: d9f1a2b3c4e5
Revises: c8e5f2a1d4b6
Create Date: 2026-08-24 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "d9f1a2b3c4e5"
down_revision: Union[str, None] = "c8e5f2a1d4b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CREATION_CONTEXT_TABLE = "user_creation_contexts"
_CREATION_CONTEXT_CHECKS = {
    "ck_user_creation_context_surface": {
        "surfaceisnullorsurfacein('inspiration','archive','writing')",
        "surfaceisnullor(surface::text=any(array['inspiration'::charactervarying,"
        "'archive'::charactervarying,'writing'::charactervarying]::text[]))",
    },
    "ck_user_creation_context_chapter_number": {
        "chapter_numberisnullorchapter_number>=1",
    },
    "ck_user_creation_context_desk_section": {
        "desk_sectionisnullordesk_sectionin('content','versions','evaluation')",
        "desk_sectionisnullor(desk_section::text=any(array['content'::charactervarying,"
        "'versions'::charactervarying,'evaluation'::charactervarying]::text[]))",
    },
    "ck_user_creation_context_inspiration_turn": {
        "inspiration_turnisnullorinspiration_turn>=0",
    },
}


def _normalize_sql(value: object) -> str:
    return "".join(str(value).lower().split())


def _validate_precreated_creation_context_table() -> None:
    table = sa.Table(
        _CREATION_CONTEXT_TABLE,
        sa.MetaData(),
        autoload_with=op.get_bind(),
    )
    columns = tuple(table.columns)
    checks = {
        constraint.name: constraint
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }
    foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            tuple(element.target_fullname for element in constraint.elements),
            constraint.ondelete,
        )
        for constraint in table.foreign_key_constraints
    }
    indexes = {
        (index.name, index.unique, tuple(column.name for column in index.columns))
        for index in table.indexes
    }
    valid = (
        tuple(column.name for column in columns)
        == (
            "user_id",
            "project_id",
            "surface",
            "chapter_number",
            "desk_section",
            "inspiration_draft",
            "inspiration_turn",
            "updated_at",
        )
        and isinstance(columns[0].type, sa.Integer)
        and not columns[0].nullable
        and columns[0].server_default is None
        and isinstance(columns[1].type, sa.String)
        and columns[1].type.length == 36
        and not columns[1].nullable
        and columns[1].server_default is None
        and isinstance(columns[2].type, sa.String)
        and columns[2].type.length == 16
        and columns[2].nullable
        and columns[2].server_default is None
        and isinstance(columns[3].type, sa.Integer)
        and columns[3].nullable
        and columns[3].server_default is None
        and isinstance(columns[4].type, sa.String)
        and columns[4].type.length == 16
        and columns[4].nullable
        and columns[4].server_default is None
        and isinstance(columns[5].type, sa.Text)
        and columns[5].nullable
        and columns[5].server_default is None
        and isinstance(columns[6].type, sa.Integer)
        and columns[6].nullable
        and columns[6].server_default is None
        and isinstance(columns[7].type, sa.DateTime)
        and columns[7].type.timezone is True
        and not columns[7].nullable
        and columns[7].server_default is not None
        and _normalize_sql(columns[7].server_default.arg) in {"now()", "current_timestamp"}
        and tuple(column.name for column in table.primary_key.columns) == ("user_id", "project_id")
        and set(checks) == set(_CREATION_CONTEXT_CHECKS)
        and all(
            _normalize_sql(checks[name].sqltext) in accepted_sql
            for name, accepted_sql in _CREATION_CONTEXT_CHECKS.items()
        )
        and foreign_keys
        == {
            (("project_id",), ("novel_projects.id",), "CASCADE"),
            (("user_id",), ("users.id",), "CASCADE"),
        }
        and indexes
        == {
            (
                "ix_user_creation_contexts_recent",
                False,
                ("user_id", "updated_at"),
            )
        }
        and not any(isinstance(constraint, sa.UniqueConstraint) for constraint in table.constraints)
    )
    if not valid:
        raise RuntimeError("incompatible_preexisting_user_creation_context_schema")


def upgrade() -> None:
    if op.get_context().as_sql:
        raise RuntimeError("creation context reconciliation requires an online migration")

    if sa.inspect(op.get_bind()).has_table(_CREATION_CONTEXT_TABLE):
        _validate_precreated_creation_context_table()
    else:
        op.create_table(
            _CREATION_CONTEXT_TABLE,
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.String(length=36), nullable=False),
            sa.Column("surface", sa.String(length=16), nullable=True),
            sa.Column("chapter_number", sa.Integer(), nullable=True),
            sa.Column("desk_section", sa.String(length=16), nullable=True),
            sa.Column("inspiration_draft", sa.Text(), nullable=True),
            sa.Column("inspiration_turn", sa.Integer(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.CheckConstraint(
                "surface IS NULL OR surface IN ('inspiration', 'archive', 'writing')",
                name="ck_user_creation_context_surface",
            ),
            sa.CheckConstraint(
                "chapter_number IS NULL OR chapter_number >= 1",
                name="ck_user_creation_context_chapter_number",
            ),
            sa.CheckConstraint(
                "desk_section IS NULL OR desk_section IN ('content', 'versions', 'evaluation')",
                name="ck_user_creation_context_desk_section",
            ),
            sa.CheckConstraint(
                "inspiration_turn IS NULL OR inspiration_turn >= 0",
                name="ck_user_creation_context_inspiration_turn",
            ),
            sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("user_id", "project_id"),
        )
        op.create_index(
            "ix_user_creation_contexts_recent",
            _CREATION_CONTEXT_TABLE,
            ["user_id", "updated_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("ix_user_creation_contexts_recent", table_name="user_creation_contexts")
    op.drop_table("user_creation_contexts")
