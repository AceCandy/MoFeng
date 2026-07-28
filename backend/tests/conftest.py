"""pytest 全局 fixture。"""
import asyncio
import os

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401  确保所有模型注册到 Base.metadata


@pytest.fixture(autouse=True)
def _bypass_ssrf_in_integration_tests():
    """集成测试旁路 SSRF 校验（矩阵由 tests/test_ssrf.py 专门覆盖）。

    同时规避沙箱 DNS 把外部域名解析到 198.18 私有段导致的误拒。
    """
    previous = settings.allow_private_llm_endpoints
    settings.allow_private_llm_endpoints = True
    yield
    settings.allow_private_llm_endpoints = previous


@pytest.fixture(autouse=True)
def _restore_session_loop_for_marked_tests(request):
    """避免函数级 loop 测试污染后续 session loop 测试。"""
    marker = request.node.get_closest_marker("asyncio")
    if marker is None:
        return
    loop_scope = marker.kwargs.get("loop_scope") or marker.kwargs.get("scope")
    if loop_scope == "session":
        asyncio.set_event_loop(request.getfixturevalue("_session_event_loop"))


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _pg_engine():
    """session 级别启动 pgvector PG 测试容器，建表一次。

    生产用 PostgreSQL，测试也用 PostgreSQL（含 pgvector 扩展），避免跨数据库测试。
    engine 在 session event loop 内创建并复用；asyncpg connection 绑定创建它的 loop，
    因此依赖该 fixture 的测试也必须用 session loop（见各测试 marker loop_scope="session"）。
    """
    configured_url = os.environ.get("TEST_POSTGRES_URL")
    if configured_url:
        engine = create_async_engine(configured_url)
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        try:
            yield engine
        finally:
            await engine.dispose()
        return

    with PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as container:
        engine = create_async_engine(container.get_connection_url())
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(Base.metadata.create_all)
        yield engine
        await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session_factory(_pg_engine):
    """每测试一个 session 工厂，基于共享 connection + savepoint 做事务回滚隔离。

    service 内部 commit 只 release savepoint，不真提交；测试结束 rollback 外层事务，
    数据彻底清空，测试间互不污染。
    """
    async with _pg_engine.connect() as conn:
        trans = await conn.begin()
        factory = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        yield factory
        await trans.rollback()
        await conn.close()
