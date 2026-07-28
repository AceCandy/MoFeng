"""add database bootstrap ledgers

Revision ID: 9c2f47a1d8e6
Revises: 17a89f18291c
Create Date: 2026-07-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9c2f47a1d8e6"
down_revision: Union[str, None] = "17a89f18291c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "database_bootstrap_versions",
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("minimum_binary_version", sa.Integer(), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("version"),
    )
    op.create_table(
        "legacy_database_adoptions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schema_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("adopted_revision", sa.String(length=64), nullable=False),
        sa.Column("operator", sa.String(length=128), nullable=False),
        sa.Column("backup_confirmed", sa.Boolean(), nullable=False),
        sa.Column("result", sa.String(length=32), nullable=False),
        sa.Column(
            "adopted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_legacy_database_adoptions_schema_fingerprint"),
        "legacy_database_adoptions",
        ["schema_fingerprint"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_legacy_database_adoptions_schema_fingerprint"),
        table_name="legacy_database_adoptions",
    )
    op.drop_table("legacy_database_adoptions")
    op.drop_table("database_bootstrap_versions")
