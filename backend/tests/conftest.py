"""pytest 全局 fixture。"""
import asyncio
from dataclasses import dataclass
import os
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateSchema, DropSchema
from testcontainers.postgres import PostgresContainer

from app.core.config import settings
from app.db.base import Base
import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.models.job import JobExecutorControl
from app.services.event_bus import shutdown_event_bus


@dataclass(frozen=True)
class IsolatedPostgres:
    """真实多连接测试使用的函数级 PostgreSQL 隔离域。"""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    schema: str


async def _seed_job_executor_control(conn) -> None:
    await conn.execute(
        insert(JobExecutorControl)
        .values(
            scope="default",
            active_generation=1,
            rollout_owner="test-suite",
            fencing_token=0,
        )
        .on_conflict_do_nothing(index_elements=["scope"])
    )


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
            await _seed_job_executor_control(conn)
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
            await _seed_job_executor_control(conn)
        yield engine
        await engine.dispose()


@pytest_asyncio.fixture(scope="session", autouse=True, loop_scope="session")
async def _close_event_bus_before_session_loop_stops():
    yield
    await shutdown_event_bus()


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


@pytest_asyncio.fixture(loop_scope="session")
async def isolated_pg(_pg_engine):
    """为需要真实 commit/并发连接的测试创建随机 schema。"""

    schema = f"test_{uuid4().hex}"
    engine: AsyncEngine | None = None
    try:
        async with _pg_engine.begin() as conn:
            await conn.execute(CreateSchema(schema))

        search_path = f'"{schema}", public'
        engine = create_async_engine(
            _pg_engine.url,
            connect_args={"server_settings": {"search_path": search_path}},
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all, checkfirst=False)
            await _seed_job_executor_control(conn)
            table_count = await conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables "
                    "WHERE table_schema = :schema"
                ),
                {"schema": schema},
            )
            if table_count != len(Base.metadata.tables):
                raise RuntimeError("随机 PostgreSQL schema 未完整创建测试表")
        yield IsolatedPostgres(
            engine=engine,
            session_factory=session_factory,
            schema=schema,
        )
    finally:
        try:
            if engine is not None:
                await engine.dispose()
        finally:
            async with _pg_engine.begin() as conn:
                await conn.execute(DropSchema(schema, cascade=True, if_exists=True))
