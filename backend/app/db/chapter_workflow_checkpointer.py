# AIMETA P=章节工作流PostgreSQL_checkpointer连接|R=结构化DSN派生_连接生命周期|NR=不建表_不迁移_不调用setup|E=open_chapter_workflow_checkpointer|X=internal|A=resource_factory|D=sqlalchemy,psycopg,langgraph|S=db|RD=./README.ai
"""Runtime connection boundary for the Alembic-owned checkpoint schema."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from sqlalchemy.engine import URL, make_url

from ..core.config import settings


def psycopg_dsn_from_sqlalchemy_url(database_url: str | URL) -> str:
    """保留结构化连接字段，仅将 SQLAlchemy async driver 切换为 Psycopg。"""

    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise ValueError("Chapter workflow checkpointer 仅支持 PostgreSQL")
    if not url.database:
        raise ValueError("Chapter workflow checkpointer 缺少 PostgreSQL database")
    return str(url.set(drivername="postgresql").render_as_string(hide_password=False))


@asynccontextmanager
async def open_chapter_workflow_checkpointer(
    database_url: str | URL | None = None,
) -> AsyncIterator[AsyncPostgresSaver]:
    """打开并关闭 runtime saver；checkpoint schema 必须已由 Alembic 安装。"""

    dsn = psycopg_dsn_from_sqlalchemy_url(database_url or settings.sqlalchemy_database_uri)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        yield saver
