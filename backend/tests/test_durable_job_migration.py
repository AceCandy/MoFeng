from __future__ import annotations

from contextlib import asynccontextmanager
import json
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.migration import build_alembic_config


@asynccontextmanager
async def _temporary_database(source_engine):
    database_name = f"mofeng_job_{uuid4().hex}"
    admin_engine = create_async_engine(
        source_engine.url.set(database="postgres"),
        isolation_level="AUTOCOMMIT",
    )
    try:
        async with admin_engine.connect() as connection:
            quoted_name = connection.dialect.identifier_preparer.quote(database_name)
            await connection.execute(sa.text(f"CREATE DATABASE {quoted_name}"))
        yield source_engine.url.set(database=database_name).render_as_string(
            hide_password=False
        )
    finally:
        async with admin_engine.connect() as connection:
            await connection.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            quoted_name = connection.dialect.identifier_preparer.quote(database_name)
            await connection.execute(sa.text(f"DROP DATABASE IF EXISTS {quoted_name}"))
        await admin_engine.dispose()


def _upgrade(connection, database_url: str, revision: str) -> None:
    config = build_alembic_config(database_url)
    config.attributes["connection"] = connection
    command.upgrade(config, revision)


def _check_metadata(connection, database_url: str) -> None:
    config = build_alembic_config(database_url)
    config.attributes["connection"] = connection
    command.check(config)


@pytest.mark.asyncio(loop_scope="session")
async def test_durable_job_migration_backfills_legacy_rows_without_private_payload(
    _pg_engine,
):
    async with _temporary_database(_pg_engine) as database_url:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    _upgrade,
                    database_url,
                    "9c2f47a1d8e6",
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, hashed_password, is_admin, is_active) "
                        "VALUES (7001, 'legacy-job-user', 'secret', false, true)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO background_tasks "
                        "(id, user_id, task_type, title, status, progress, payload, result, "
                        "error, log_entries) VALUES "
                        "('legacy-queued', 7001, 'legacy-test', '旧排队任务', 'queued', 0, "
                        "CAST(:payload AS json), NULL, NULL, '[]'::json), "
                        "('legacy-running', 7001, 'legacy-test', '旧运行任务', 'running', 25, "
                        "CAST(:payload AS json), CAST(:result AS json), NULL, '[]'::json)"
                    ),
                    {
                        "payload": json.dumps({"prompt": "private prompt"}),
                        "result": json.dumps({"content": "private result"}),
                    },
                )

            async with engine.begin() as connection:
                await connection.run_sync(_upgrade, database_url, "head")
                await connection.run_sync(_check_metadata, database_url)

            async with engine.connect() as connection:
                revision = await connection.scalar(
                    sa.text("SELECT version_num FROM alembic_version")
                )
                tasks = (
                    await connection.execute(
                        sa.text(
                            "SELECT id, status, available_at, stream_type, stream_id, "
                            "event_sequence, error_category "
                            "FROM background_tasks ORDER BY id"
                        )
                    )
                ).mappings().all()
                streams = (
                    await connection.execute(
                        sa.text(
                            "SELECT stream_type, stream_id, last_sequence, "
                            "retained_through_cursor FROM job_event_streams "
                            "ORDER BY stream_id"
                        )
                    )
                ).mappings().all()
                events = (
                    await connection.execute(
                        sa.text(
                            "SELECT job_id, sequence, event_type, payload "
                            "FROM job_events ORDER BY cursor"
                        )
                    )
                ).mappings().all()
                control = (
                    await connection.execute(
                        sa.text(
                            "SELECT active_generation, rollout_owner "
                            "FROM job_executor_controls WHERE scope = 'default'"
                        )
                    )
                ).mappings().one()

            assert revision == "d4b8f1a2c3e7"
            assert [(task["id"], task["status"]) for task in tasks] == [
                ("legacy-queued", "queued"),
                ("legacy-running", "needs_attention"),
            ]
            assert all(task["available_at"] is not None for task in tasks)
            assert [(task["stream_type"], task["stream_id"]) for task in tasks] == [
                ("job", "legacy-queued"),
                ("job", "legacy-running"),
            ]
            assert all(task["event_sequence"] == 1 for task in tasks)
            assert [
                (
                    stream["stream_type"],
                    stream["stream_id"],
                    stream["last_sequence"],
                    stream["retained_through_cursor"],
                )
                for stream in streams
            ] == [
                ("job", "legacy-queued", 1, 0),
                ("job", "legacy-running", 1, 0),
            ]
            assert tasks[1]["error_category"] == "legacy_running_state_ambiguous"
            assert [(event["job_id"], event["sequence"], event["event_type"]) for event in events] == [
                ("legacy-queued", 1, "job.legacy_imported"),
                ("legacy-running", 1, "job.legacy_imported"),
            ]
            for event in events:
                projection = event["payload"]["task"]
                assert "payload" not in projection
                assert "result" not in projection
                assert projection["stream_type"] == "job"
                assert projection["stream_id"] == event["job_id"]
            assert events[1]["payload"]["task"]["status"] == "failed"
            assert control == {
                "active_generation": 1,
                "rollout_owner": "durable-job-migration",
            }
        finally:
            await engine.dispose()
