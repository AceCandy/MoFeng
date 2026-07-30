# AIMETA P=PostgreSQL双驱动测试隔离|R=共享search_path_checkpoint失败清理|NR=不测试业务服务|E=test_*|X=internal|A=integration_test|D=pytest,asyncpg,psycopg,langgraph|S=test|RD=../app/README.ai
from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace
from typing import TypedDict
from uuid import uuid4

import conftest as postgres_fixtures
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph import END, START, StateGraph
from psycopg import AsyncConnection
from psycopg.conninfo import conninfo_to_dict
from psycopg.errors import UndefinedTable
from sqlalchemy import Column, Integer, MetaData, Table, text
from sqlalchemy.engine import make_url

from app.db.chapter_workflow_checkpoint_schema import (
    CHECKPOINT_MIGRATION_VERSIONS,
    CHECKPOINT_TABLES,
)
from app.db.chapter_workflow_checkpointer import (
    open_chapter_workflow_checkpointer,
    psycopg_dsn_from_sqlalchemy_url,
)

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _CheckpointProbeState(TypedDict):
    value: int


async def _increment_checkpoint_probe(
    state: _CheckpointProbeState,
) -> dict[str, int]:
    return {"value": state["value"] + 1}


def _compile_checkpoint_probe(saver: AsyncPostgresSaver):
    builder = StateGraph(_CheckpointProbeState)
    builder.add_node("increment", _increment_checkpoint_probe)
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    return builder.compile(checkpointer=saver)


async def _install_dependency_checkpoint_schema(dsn: str) -> None:
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()


async def _resource_counts(source_engine, *, schema: str) -> tuple[int, int]:
    application_name = postgres_fixtures._isolation_application_name(schema)
    async with source_engine.connect() as connection:
        schema_count = await connection.scalar(
            text("SELECT count(*) FROM pg_namespace WHERE nspname = :schema"),
            {"schema": schema},
        )
        connection_count = await connection.scalar(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE application_name = :application_name"
            ),
            {"application_name": application_name},
        )
    return int(schema_count or 0), int(connection_count or 0)


async def _database_count(source_engine, *, database_name: str) -> int:
    async with source_engine.connect() as connection:
        count = await connection.scalar(
            text("SELECT count(*) FROM pg_database WHERE datname = :database_name"),
            {"database_name": database_name},
        )
    return int(count or 0)


async def _assert_resources_released(source_engine, *, schema: str) -> None:
    for _ in range(20):
        if await _resource_counts(source_engine, schema=schema) == (0, 0):
            return
        await asyncio.sleep(0.05)
    assert await _resource_counts(source_engine, schema=schema) == (0, 0)


async def test_session_postgres_engine_uses_disposable_database(_pg_engine) -> None:
    async with _pg_engine.connect() as connection:
        database_name = await connection.scalar(text("SELECT current_database()"))

    assert isinstance(database_name, str)
    assert database_name == _pg_engine.url.database
    assert database_name.startswith("mofeng_pytest_")
    configured_url = os.environ.get("TEST_POSTGRES_URL")
    if configured_url:
        assert database_name != make_url(configured_url).database


async def test_session_postgres_cleans_database_after_setup_failure(
    _pg_engine,
    monkeypatch,
) -> None:
    database_name = "mofeng_pytest_cleanup_database"
    monkeypatch.setattr(
        postgres_fixtures,
        "uuid4",
        lambda: SimpleNamespace(hex="cleanup_database"),
    )

    def fail_metadata(_connection) -> None:
        raise RuntimeError("injected session database setup failure")

    monkeypatch.setattr(postgres_fixtures, "_create_isolated_metadata", fail_metadata)

    assert await _database_count(_pg_engine, database_name=database_name) == 0
    with pytest.raises(RuntimeError, match="injected session database setup failure"):
        async with postgres_fixtures._temporary_postgres_engine(_pg_engine.url):
            pytest.fail("setup failure must happen before yielding the database")
    assert await _database_count(_pg_engine, database_name=database_name) == 0


async def test_checkpoint_dependency_smoke_shares_schema_between_drivers(isolated_pg) -> None:
    probe_metadata = MetaData(schema=isolated_pg.schema)
    probe_table = Table(
        "mofeng_driver_isolation_probe",
        probe_metadata,
        Column("value", Integer, nullable=False),
    )
    async with isolated_pg.engine.begin() as connection:
        database_and_schema = (
            await connection.execute(text("SELECT current_database(), current_schema()"))
        ).one()
        assert database_and_schema == (
            isolated_pg.engine.url.database,
            isolated_pg.schema,
        )
        await connection.run_sync(probe_metadata.create_all)
        await connection.execute(probe_table.insert().values(value=7))

    dsn = psycopg_dsn_from_sqlalchemy_url(isolated_pg.checkpoint_database_url)
    params = conninfo_to_dict(dsn)
    assert params["dbname"] == isolated_pg.engine.url.database
    assert params["application_name"] == isolated_pg.application_name
    assert params["options"] == f"-csearch_path={isolated_pg.schema},public"

    async with await AsyncConnection.connect(dsn, autocommit=True) as connection:
        identity_cursor = await connection.execute("SELECT current_database(), current_schema()")
        value_cursor = await connection.execute("SELECT value FROM mofeng_driver_isolation_probe")
        assert await identity_cursor.fetchone() == (
            isolated_pg.engine.url.database,
            isolated_pg.schema,
        )
        assert await value_cursor.fetchone() == (7,)

    await _install_dependency_checkpoint_schema(dsn)
    async with isolated_pg.engine.connect() as connection:
        schema_tables = set(
            await connection.scalars(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = :schema"
                ),
                {"schema": isolated_pg.schema},
            )
        )
        public_tables = set(
            await connection.scalars(
                text(
                    "SELECT table_name FROM information_schema.tables "
                    "WHERE table_schema = 'public'"
                )
            )
        )
        migration_versions = tuple(
            await connection.scalars(text("SELECT v FROM checkpoint_migrations ORDER BY v"))
        )
    assert CHECKPOINT_TABLES.issubset(schema_tables)
    assert CHECKPOINT_TABLES.isdisjoint(public_tables)
    assert migration_versions == CHECKPOINT_MIGRATION_VERSIONS

    config = {"configurable": {"thread_id": str(uuid4())}}
    async with open_chapter_workflow_checkpointer(isolated_pg.checkpoint_database_url) as saver:
        graph = _compile_checkpoint_probe(saver)
        assert await graph.ainvoke({"value": 1}, config) == {"value": 2}
        assert await saver.aget_tuple(config) is not None


@pytest.mark.parametrize("failure_point", ("metadata", "seed", "psycopg"))
async def test_isolated_postgres_cleans_schema_and_connections_after_setup_failure(
    _pg_engine,
    monkeypatch,
    failure_point,
) -> None:
    schema = f"test_cleanup_{failure_point}"
    monkeypatch.setattr(
        postgres_fixtures,
        "uuid4",
        lambda: SimpleNamespace(hex=f"cleanup_{failure_point}"),
    )

    if failure_point == "metadata":

        def fail_metadata(_connection) -> None:
            raise RuntimeError("injected isolation setup failure")

        monkeypatch.setattr(postgres_fixtures, "_create_isolated_metadata", fail_metadata)
    elif failure_point == "seed":

        async def fail_seed(_connection) -> None:
            raise RuntimeError("injected isolation setup failure")

        monkeypatch.setattr(postgres_fixtures, "_seed_job_executor_control", fail_seed)
    else:

        async def fail_psycopg_validation(_connection, _expected_schema) -> None:
            raise RuntimeError("injected isolation setup failure")

        monkeypatch.setattr(
            postgres_fixtures,
            "_validate_psycopg_search_path",
            fail_psycopg_validation,
        )

    await _assert_resources_released(_pg_engine, schema=schema)
    with pytest.raises(RuntimeError, match="injected isolation setup failure"):
        async with postgres_fixtures._isolated_postgres_scope(_pg_engine):
            pytest.fail("setup failure must happen before yielding the isolation scope")
    await _assert_resources_released(_pg_engine, schema=schema)


async def test_checkpoint_dependency_smoke_cleans_after_write_failure(
    _pg_engine,
    monkeypatch,
) -> None:
    schema = "test_cleanup_checkpoint_write"
    monkeypatch.setattr(
        postgres_fixtures,
        "uuid4",
        lambda: SimpleNamespace(hex="cleanup_checkpoint_write"),
    )

    await _assert_resources_released(_pg_engine, schema=schema)
    with pytest.raises(UndefinedTable):
        async with postgres_fixtures._isolated_postgres_scope(_pg_engine) as isolated:
            dsn = psycopg_dsn_from_sqlalchemy_url(isolated.checkpoint_database_url)
            await _install_dependency_checkpoint_schema(dsn)
            async with isolated.engine.begin() as connection:
                await connection.execute(text("DROP TABLE checkpoints"))
            async with open_chapter_workflow_checkpointer(
                isolated.checkpoint_database_url
            ) as saver:
                graph = _compile_checkpoint_probe(saver)
                await graph.ainvoke(
                    {"value": 1},
                    {"configurable": {"thread_id": "checkpoint-write-failure"}},
                )
    await _assert_resources_released(_pg_engine, schema=schema)
