"""pytest 全局 fixture。"""

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from uuid import uuid4

import pytest
import pytest_asyncio
from psycopg import AsyncConnection
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import URL, Connection, make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.schema import CreateSchema, DropSchema
from testcontainers.postgres import PostgresContainer

import app.models  # noqa: F401  确保所有模型注册到 Base.metadata
from app.core.config import settings
from app.db.base import Base
from app.db.chapter_workflow_checkpointer import psycopg_dsn_from_sqlalchemy_url
from app.models.job import JobExecutorControl
from app.services.event_bus import shutdown_event_bus


@dataclass(frozen=True)
class IsolatedPostgres:
    """真实多连接测试使用的函数级 PostgreSQL 隔离域。"""

    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    schema: str
    checkpoint_database_url: URL
    application_name: str


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


def _create_isolated_metadata(connection: Connection) -> None:
    Base.metadata.create_all(connection, checkfirst=False)


@asynccontextmanager
async def _temporary_postgres_engine(database_url: str | URL) -> AsyncIterator[AsyncEngine]:
    """在会话级临时数据库中运行测试，避免接触配置数据库的 public 数据。"""

    source_url = make_url(database_url)
    database_name = f"mofeng_pytest_{uuid4().hex}"
    admin_engine = create_async_engine(
        source_url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    test_engine: AsyncEngine | None = None
    database_created = False
    try:
        async with admin_engine.connect() as connection:
            quoted_name = connection.dialect.identifier_preparer.quote(database_name)
            await connection.execute(text(f"CREATE DATABASE {quoted_name}"))
            database_created = True

        test_engine = create_async_engine(source_url.set(database=database_name))
        async with test_engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.run_sync(_create_isolated_metadata)
            await _seed_job_executor_control(conn)
        yield test_engine
    finally:
        try:
            if test_engine is not None:
                await test_engine.dispose()
        finally:
            try:
                if database_created:
                    async with admin_engine.connect() as connection:
                        await connection.execute(
                            text(
                                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                                "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                            ),
                            {"database_name": database_name},
                        )
                        quoted_name = connection.dialect.identifier_preparer.quote(database_name)
                        await connection.execute(text(f"DROP DATABASE IF EXISTS {quoted_name}"))
            finally:
                await admin_engine.dispose()


def _isolation_application_name(schema: str) -> str:
    return f"mofeng-test-{schema}"


def _checkpoint_database_url(
    database_url: URL,
    *,
    schema: str,
    application_name: str,
) -> URL:
    return database_url.update_query_dict(
        {
            "application_name": application_name,
            "options": f"-csearch_path={schema},public",
        }
    )


async def _validate_psycopg_search_path(
    connection: AsyncConnection,
    expected_schema: str,
) -> None:
    cursor = await connection.execute("SELECT current_schema()")
    row = await cursor.fetchone()
    if row is None or row[0] != expected_schema:
        raise RuntimeError("Psycopg 未连接到随机 PostgreSQL schema")


async def _verify_psycopg_search_path(
    database_url: URL,
    *,
    expected_schema: str,
) -> None:
    dsn = psycopg_dsn_from_sqlalchemy_url(database_url)
    async with await AsyncConnection.connect(dsn, autocommit=True) as connection:
        await _validate_psycopg_search_path(connection, expected_schema)


@asynccontextmanager
async def _isolated_postgres_scope(
    source_engine: AsyncEngine,
) -> AsyncIterator[IsolatedPostgres]:
    schema = f"test_{uuid4().hex}"
    application_name = _isolation_application_name(schema)
    checkpoint_database_url = _checkpoint_database_url(
        source_engine.url,
        schema=schema,
        application_name=application_name,
    )
    engine: AsyncEngine | None = None
    try:
        async with source_engine.begin() as conn:
            await conn.execute(CreateSchema(schema))

        search_path = f'"{schema}", public'
        engine = create_async_engine(
            source_engine.url,
            connect_args={
                "server_settings": {
                    "application_name": application_name,
                    "search_path": search_path,
                }
            },
        )
        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(_create_isolated_metadata)
            await _seed_job_executor_control(conn)
            table_count = await conn.scalar(
                text(
                    "SELECT count(*) FROM information_schema.tables " "WHERE table_schema = :schema"
                ),
                {"schema": schema},
            )
            if table_count != len(Base.metadata.tables):
                raise RuntimeError("随机 PostgreSQL schema 未完整创建测试表")
        await _verify_psycopg_search_path(
            checkpoint_database_url,
            expected_schema=schema,
        )
        yield IsolatedPostgres(
            engine=engine,
            session_factory=session_factory,
            schema=schema,
            checkpoint_database_url=checkpoint_database_url,
            application_name=application_name,
        )
    finally:
        try:
            if engine is not None:
                await engine.dispose()
        finally:
            async with source_engine.begin() as conn:
                await conn.execute(DropSchema(schema, cascade=True, if_exists=True))


@pytest.fixture(autouse=True)
def _bypass_ssrf_in_integration_tests():
    """集成测试旁路 SSRF 校验（矩阵由 tests/test_ssrf.py 专门覆盖）。

    同时规避沙箱 DNS 把外部域名解析到 198.18 私有段导致的误拒。
    """
    previous = settings.allow_private_llm_endpoints
    settings.allow_private_llm_endpoints = True
    yield
    settings.allow_private_llm_endpoints = previous


@pytest.fixture
def app_caplog(caplog):
    """让 app.* 日志在生产 logging 配置已加载时仍可被 caplog 捕获。"""
    app_logger = logging.getLogger("app")
    previous = app_logger.propagate
    app_logger.propagate = True
    try:
        yield caplog
    finally:
        app_logger.propagate = previous


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
    """基于 PostgreSQL 服务连接创建 session 级临时数据库并建表一次。

    生产用 PostgreSQL，测试也用 PostgreSQL（含 pgvector 扩展），避免跨数据库测试。
    TEST_POSTGRES_URL 只提供服务连接信息，不会直接作为测试目标数据库。
    engine 在 session event loop 内创建并复用；asyncpg connection 绑定创建它的 loop，
    因此依赖该 fixture 的测试也必须用 session loop（见各测试 marker loop_scope="session"）。
    """
    configured_url = os.environ.get("TEST_POSTGRES_URL")
    if configured_url:
        async with _temporary_postgres_engine(configured_url) as engine:
            yield engine
        return

    with PostgresContainer("pgvector/pgvector:pg16", driver="asyncpg") as container:
        async with _temporary_postgres_engine(container.get_connection_url()) as engine:
            yield engine


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

    async with _isolated_postgres_scope(_pg_engine) as isolated:
        yield isolated
