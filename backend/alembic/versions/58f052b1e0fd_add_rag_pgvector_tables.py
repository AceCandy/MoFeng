"""add rag pgvector tables

Revision ID: 58f052b1e0fd
Revises: 6e85c84f9541
Create Date: 2026-07-19 17:10:05.793859

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = '58f052b1e0fd'
down_revision: Union[str, None] = '6e85c84f9541'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 启用 pgvector 扩展（需数据库超级用户权限）
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        'rag_chunks',
        sa.Column('id', sa.String(length=128), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('chapter_title', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_rag_chunks_project', 'rag_chunks', ['project_id', 'chapter_number'])

    op.create_table(
        'rag_summaries',
        sa.Column('id', sa.String(length=128), nullable=False),
        sa.Column('project_id', sa.String(length=64), nullable=False),
        sa.Column('chapter_number', sa.Integer(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=False),
        sa.Column('embedding', Vector(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_rag_summaries_project', 'rag_summaries', ['project_id', 'chapter_number'])


def downgrade() -> None:
    op.drop_index('idx_rag_summaries_project', table_name='rag_summaries')
    op.drop_table('rag_summaries')
    op.drop_index('idx_rag_chunks_project', table_name='rag_chunks')
    op.drop_table('rag_chunks')
    # 不主动 DROP EXTENSION vector，避免影响其他可能依赖该扩展的用途
