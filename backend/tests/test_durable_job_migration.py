from __future__ import annotations

import hashlib
import json
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import command
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
        yield source_engine.url.set(database=database_name).render_as_string(hide_password=False)
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
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT id, status, available_at, stream_type, stream_id, "
                                "event_sequence, error_category "
                                "FROM background_tasks ORDER BY id"
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                streams = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT stream_type, stream_id, last_sequence, "
                                "retained_through_cursor FROM job_event_streams "
                                "ORDER BY stream_id"
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                events = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT job_id, sequence, event_type, payload "
                                "FROM job_events ORDER BY cursor"
                            )
                        )
                    )
                    .mappings()
                    .all()
                )
                control = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT active_generation, rollout_owner "
                                "FROM job_executor_controls WHERE scope = 'default'"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )

            assert revision == "c8e5f2a1d4b6"
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
            assert [
                (event["job_id"], event["sequence"], event["event_type"]) for event in events
            ] == [
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


@pytest.mark.asyncio(loop_scope="session")
async def test_schema_convergence_migration_adds_pricing_usage_and_retention(
    _pg_engine,
) -> None:
    async with _temporary_database(_pg_engine) as database_url:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    _upgrade,
                    database_url,
                    "e7c9a1b2d3f4",
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, hashed_password, is_admin, is_active) "
                        "VALUES (7010, 'schema-convergence-user', 'secret', true, true)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO user_model_providers "
                        "(id, user_id, name, provider_type, base_url, capabilities_json, "
                        "is_enabled) VALUES "
                        "(8010, 7010, 'provider', 'openai_compatible', "
                        "'https://example.invalid', '{}'::json, true)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO user_ai_models "
                        "(id, user_id, provider_id, display_name, model_name, "
                        "capabilities_json, is_default_chat, is_default_embedding, "
                        "is_default_tts, tts_speed, is_enabled, sort_order) VALUES "
                        "(9010, 7010, 8010, 'model', 'model-v1', '{}'::json, "
                        "false, false, false, 1.0, true, 0)"
                    )
                )

            async with engine.begin() as connection:
                await connection.run_sync(_upgrade, database_url, "head")
                await connection.run_sync(_check_metadata, database_url)

            async with engine.connect() as connection:
                revision = await connection.scalar(
                    sa.text("SELECT version_num FROM alembic_version")
                )
                pricing = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT input_price_per_million, output_price_per_million, "
                                "cached_input_price_per_million, "
                                "cache_write_input_price_per_million, pricing_currency "
                                "FROM user_ai_models WHERE id = 9010"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )

                def inspect_schema(sync_connection):
                    inspector = sa.inspect(sync_connection)

                    def column_contract(table_name: str):
                        return {
                            column["name"]: (
                                str(column["type"]),
                                column["nullable"],
                                (
                                    str(column["default"])
                                    if column.get("default") is not None
                                    else None
                                ),
                            )
                            for column in inspector.get_columns(table_name)
                        }

                    def index_contract(table_name: str):
                        result = {}
                        for item in inspector.get_indexes(table_name):
                            where = item.get("dialect_options", {}).get("postgresql_where")
                            result[item["name"]] = (
                                item["column_names"],
                                item["unique"],
                                str(where) if where is not None else None,
                            )
                        return result

                    pricing_columns = {
                        column["name"]: column
                        for column in inspector.get_columns("user_ai_models")
                        if column["name"].endswith("price_per_million")
                        or column["name"] == "pricing_currency"
                    }
                    return {
                        "tables": set(inspector.get_table_names()),
                        "pricing_columns": {
                            name: (
                                getattr(column["type"], "precision", None),
                                getattr(column["type"], "scale", None),
                                getattr(column["type"], "length", None),
                                column["nullable"],
                            )
                            for name, column in pricing_columns.items()
                        },
                        "pricing_checks": {
                            item["name"]
                            for item in inspector.get_check_constraints("user_ai_models")
                        },
                        "usage_checks": {
                            item["name"]
                            for item in inspector.get_check_constraints("ai_usage_records")
                        },
                        "usage_columns": column_contract("ai_usage_records"),
                        "usage_pk": inspector.get_pk_constraint("ai_usage_records")[
                            "constrained_columns"
                        ],
                        "usage_indexes": {
                            item["name"]: item["column_names"]
                            for item in inspector.get_indexes("ai_usage_records")
                        },
                        "usage_fks": {
                            tuple(item["constrained_columns"]): (
                                item["referred_table"],
                                item.get("options", {}).get("ondelete"),
                            )
                            for item in inspector.get_foreign_keys("ai_usage_records")
                        },
                        "retention_checks": {
                            item["name"]
                            for item in inspector.get_check_constraints(
                                "chapter_projection_retention_audits"
                            )
                        },
                        "retention_columns": column_contract("chapter_projection_retention_audits"),
                        "retention_pk": inspector.get_pk_constraint(
                            "chapter_projection_retention_audits"
                        )["constrained_columns"],
                        "retention_uniques": {
                            item["name"]: item["column_names"]
                            for item in inspector.get_unique_constraints(
                                "chapter_projection_retention_audits"
                            )
                        },
                        "retention_indexes": index_contract("chapter_projection_retention_audits"),
                        "retention_fks": inspector.get_foreign_keys(
                            "chapter_projection_retention_audits"
                        ),
                    }

                schema = await connection.run_sync(inspect_schema)

            assert revision == "c8e5f2a1d4b6"
            assert set(pricing.values()) == {None}
            assert {
                "ai_usage_records",
                "chapter_projection_retention_audits",
            } <= schema["tables"]
            assert schema["pricing_columns"] == {
                "input_price_per_million": (24, 12, None, True),
                "output_price_per_million": (24, 12, None, True),
                "cached_input_price_per_million": (24, 12, None, True),
                "cache_write_input_price_per_million": (24, 12, None, True),
                "pricing_currency": (None, None, 3, True),
            }
            assert {
                "ck_user_ai_models_input_price",
                "ck_user_ai_models_output_price",
                "ck_user_ai_models_cached_input_price",
                "ck_user_ai_models_cache_write_price",
            } <= schema["pricing_checks"]
            assert schema["usage_checks"] == {
                "ck_ai_usage_cost_amount",
                "ck_ai_usage_input_tokens",
                "ck_ai_usage_output_tokens",
                "ck_ai_usage_total_tokens",
            }
            assert set(schema["usage_columns"]) == {
                "job_activity_id",
                "job_id",
                "user_id",
                "project_id",
                "provider_type",
                "model_name",
                "model_id",
                "stage",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "reasoning_tokens",
                "usage_complete",
                "cost_amount",
                "cost_currency",
                "cost_known",
                "cost_unknown_reason",
                "created_at",
            }
            assert schema["usage_columns"]["job_activity_id"][:2] == (
                "VARCHAR(36)",
                False,
            )
            assert schema["usage_columns"]["cost_amount"][:2] == (
                "NUMERIC(24, 12)",
                True,
            )
            assert schema["usage_columns"]["usage_complete"][1:] == (
                False,
                "false",
            )
            assert schema["usage_columns"]["cost_known"][1:] == (False, "false")
            assert schema["usage_columns"]["created_at"][1] is False
            assert "now()" in schema["usage_columns"]["created_at"][2]
            assert schema["usage_pk"] == ["job_activity_id"]
            assert schema["usage_indexes"] == {
                "ix_ai_usage_project_created": ["project_id", "created_at"],
                "ix_ai_usage_provider_model": ["provider_type", "model_name"],
                "ix_ai_usage_records_job_id": ["job_id"],
                "ix_ai_usage_records_user_id": ["user_id"],
            }
            assert schema["usage_fks"] == {
                ("job_activity_id",): ("job_activities", "CASCADE"),
                ("job_id",): ("background_tasks", "CASCADE"),
                ("project_id",): ("novel_projects", "SET NULL"),
                ("user_id",): ("users", "CASCADE"),
            }
            assert schema["retention_checks"] == {
                "ck_chapter_projection_retention_artifact_kind",
                "ck_chapter_projection_retention_mode",
                "ck_chapter_projection_retention_positive_identity",
                "ck_chapter_projection_retention_status",
            }
            assert set(schema["retention_columns"]) == {
                "id",
                "operator_user_id",
                "project_id",
                "chapter_id",
                "chapter_number",
                "revision",
                "artifact_generation",
                "artifact_kind",
                "projection_run_id",
                "mode",
                "status",
                "idempotency_key",
                "reason",
                "request_scope",
                "result",
                "created_at",
                "completed_at",
            }
            assert schema["retention_columns"]["id"][:2] == ("VARCHAR(36)", False)
            assert schema["retention_columns"]["request_scope"][1:] == (False, None)
            assert schema["retention_columns"]["result"][1:] == (False, None)
            assert "now()" in schema["retention_columns"]["created_at"][2]
            assert "now()" in schema["retention_columns"]["completed_at"][2]
            assert schema["retention_pk"] == ["id"]
            assert schema["retention_uniques"] == {
                "uq_chapter_projection_retention_operator_key": [
                    "operator_user_id",
                    "idempotency_key",
                ]
            }
            assert schema["retention_indexes"]["ix_chapter_projection_retention_rate"][:2] == (
                ["operator_user_id", "created_at"],
                False,
            )
            assert schema["retention_indexes"]["ix_chapter_projection_retention_target"][:2] == (
                [
                    "project_id",
                    "chapter_number",
                    "revision",
                    "artifact_generation",
                ],
                False,
            )
            assert schema["retention_indexes"]["uq_chapter_projection_retention_completed_purge"][
                :2
            ] == (
                [
                    "project_id",
                    "chapter_number",
                    "revision",
                    "artifact_generation",
                    "artifact_kind",
                ],
                True,
            )
            partial_where = schema["retention_indexes"][
                "uq_chapter_projection_retention_completed_purge"
            ][2]
            assert partial_where is not None
            assert "mode" in partial_where
            assert "purge" in partial_where
            assert "status" in partial_where
            assert "completed" in partial_where
            assert schema["retention_fks"] == []

            async with engine.begin() as connection:
                with pytest.raises(sa.exc.IntegrityError) as price_error:
                    async with connection.begin_nested():
                        await connection.execute(
                            sa.text(
                                "UPDATE user_ai_models "
                                "SET input_price_per_million = -1 WHERE id = 9010"
                            )
                        )
                assert "ck_user_ai_models_input_price" in str(price_error.value)

                await connection.execute(
                    sa.text(
                        "INSERT INTO background_tasks "
                        "(id, user_id, task_type, title, status, progress, payload, "
                        "result, error, log_entries, stream_id) VALUES "
                        "('schema-usage-job', 7010, 'chapter_projection_rag', "
                        "'usage', 'queued', 0, '{}'::json, NULL, NULL, '[]'::json, "
                        "'schema-usage-job')"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO job_activities "
                        "(id, job_id, activity_key, side_effect_class, status, "
                        "provider_request_key, attempt, fencing_token, request_payload, "
                        "started_at) VALUES "
                        "('schema-usage-activity', 'schema-usage-job', 'embedding', "
                        "'idempotent_external', 'succeeded', 'schema-provider-key', "
                        "1, 1, '{}'::json, now())"
                    )
                )
                with pytest.raises(sa.exc.IntegrityError) as usage_error:
                    async with connection.begin_nested():
                        await connection.execute(
                            sa.text(
                                "INSERT INTO ai_usage_records "
                                "(job_activity_id, job_id, user_id, provider_type, "
                                "model_name, stage, input_tokens, usage_complete, "
                                "cost_known) VALUES "
                                "('schema-usage-activity', 'schema-usage-job', 7010, "
                                "'openai_compatible', 'model-v1', 'embedding', -1, "
                                "true, false)"
                            )
                        )
                assert "ck_ai_usage_input_tokens" in str(usage_error.value)
        finally:
            await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_migration_backfills_legacy_rollout_and_enforces_checks(
    _pg_engine,
):
    async with _temporary_database(_pg_engine) as database_url:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    _upgrade,
                    database_url,
                    "d4b8f1a2c3e7",
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, hashed_password, is_admin, is_active) "
                        "VALUES (7002, 'legacy-projection-user', 'secret', false, true)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO novel_projects (id, user_id, title, status) "
                        "VALUES ('legacy-projection-project', 7002, "
                        "'旧章节投影项目', 'draft')"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO chapters "
                        "(id, project_id, chapter_number, status, generation_progress, "
                        "generation_step_index, generation_step_total, word_count) "
                        "VALUES (8101, 'legacy-projection-project', 1, 'successful', 0, 0, 0, 4)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO chapter_versions (id, chapter_id, version_label, content) "
                        "VALUES (9101, 8101, 'v1', '旧章节正文')"
                    )
                )
                await connection.execute(
                    sa.text("UPDATE chapters SET selected_version_id = 9101 WHERE id = 8101")
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO project_memories "
                        "(id, project_id, global_summary, last_updated_chapter, version) "
                        "VALUES (9201, 'legacy-projection-project', '旧全局记忆', 1, 1)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO chapter_snapshots "
                        "(id, project_id, chapter_number, chapter_summary, word_count) "
                        "VALUES (9301, 'legacy-projection-project', 1, '旧章节梳理', 4)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO foreshadowings "
                        "(id, project_id, chapter_id, chapter_number, content, type, status, is_manual) "
                        "VALUES (9401, 'legacy-projection-project', 8101, 1, "
                        "'旧伏笔', 'mystery', 'planted', false)"
                    )
                )

            async with engine.begin() as connection:
                await connection.run_sync(_upgrade, database_url, "head")
                await connection.run_sync(_check_metadata, database_url)

            async with engine.connect() as connection:
                revision = await connection.scalar(
                    sa.text("SELECT version_num FROM alembic_version")
                )
                rollout = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT id, chapter_id, project_id, owner, state, generation, "
                                "fencing_token, transition_sequence, required_observations, "
                                "successful_observations, failed_observations "
                                "FROM chapter_projection_rollouts WHERE chapter_id = 8101"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                transition = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT id, rollout_id, aggregate_id, project_id, chapter_id, "
                                "sequence, from_owner, to_owner, from_state, to_state, generation, "
                                "fencing_token, operator_user_id, reason, details "
                                "FROM chapter_projection_rollout_transitions "
                                "WHERE rollout_id = :rollout_id"
                            ),
                            {"rollout_id": rollout["id"]},
                        )
                    )
                    .mappings()
                    .one()
                )
                chapter = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT current_revision, source_hash, projection_generation "
                                "FROM chapters WHERE id = 8101"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                canonical_revision = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT id, chapter_id, revision, selected_version_id, source_hash, "
                                "source_content, lifecycle, source_generation "
                                "FROM chapter_revisions WHERE chapter_id = 8101"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                memory = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT projection_revision, projection_generation "
                                "FROM project_memories WHERE id = 9201"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                snapshot = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT chapter_revision, artifact_generation, is_active "
                                "FROM chapter_snapshots WHERE id = 9301"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                foreshadowing = (
                    (
                        await connection.execute(
                            sa.text(
                                "SELECT chapter_revision, artifact_generation, is_active "
                                "FROM foreshadowings WHERE id = 9401"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )

            assert revision == "c8e5f2a1d4b6"
            source_hash = hashlib.sha256("旧章节正文".encode()).hexdigest()
            assert chapter == {
                "current_revision": 1,
                "source_hash": source_hash,
                "projection_generation": "legacy",
            }
            assert canonical_revision == {
                "id": "15f7b768-d78c-bbba-416f-20ac76a1b242",
                "chapter_id": 8101,
                "revision": 1,
                "selected_version_id": 9101,
                "source_hash": source_hash,
                "source_content": "旧章节正文",
                "lifecycle": "successful",
                "source_generation": "legacy",
            }
            assert memory == {
                "projection_revision": 1,
                "projection_generation": "legacy",
            }
            assert snapshot == {
                "chapter_revision": 1,
                "artifact_generation": "legacy",
                "is_active": True,
            }
            assert foreshadowing == {
                "chapter_revision": 1,
                "artifact_generation": "legacy",
                "is_active": True,
            }
            assert rollout == {
                "id": "beb6efb6bbe40647dadb02f9ba1ce755",
                "chapter_id": 8101,
                "project_id": "legacy-projection-project",
                "owner": "legacy",
                "state": "legacy",
                "generation": 1,
                "fencing_token": 0,
                "transition_sequence": 1,
                "required_observations": 0,
                "successful_observations": 0,
                "failed_observations": 0,
            }
            assert transition == {
                "id": "de2859042a2ef2a77383f12fd9d1e908",
                "rollout_id": rollout["id"],
                "aggregate_id": "8101",
                "project_id": "legacy-projection-project",
                "chapter_id": 8101,
                "sequence": 1,
                "from_owner": None,
                "to_owner": "legacy",
                "from_state": None,
                "to_state": "legacy",
                "generation": 1,
                "fencing_token": 0,
                "operator_user_id": None,
                "reason": "migration legacy rollout backfill",
                "details": {},
            }

            async with engine.begin() as connection:
                with pytest.raises(sa.exc.IntegrityError) as owner_state_error:
                    async with connection.begin_nested():
                        await connection.execute(
                            sa.text(
                                "UPDATE chapter_projection_rollouts "
                                "SET owner = 'projection', state = 'legacy' "
                                "WHERE chapter_id = 8101"
                            )
                        )
                assert "ck_chapter_projection_rollout_owner_state" in str(owner_state_error.value)

                with pytest.raises(sa.exc.IntegrityError) as edge_error:
                    async with connection.begin_nested():
                        await connection.execute(
                            sa.text(
                                "UPDATE chapter_projection_rollout_transitions "
                                "SET from_owner = 'legacy', from_state = 'legacy', "
                                "to_owner = 'projection', to_state = 'projection' "
                                "WHERE rollout_id = :rollout_id"
                            ),
                            {"rollout_id": rollout["id"]},
                        )
                assert "ck_chapter_projection_transition_edge" in str(edge_error.value)
        finally:
            await engine.dispose()


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "invalid_case",
    ["missing_selected_version", "cross_chapter_selected_version"],
)
async def test_projection_migration_rejects_unbackfillable_finalized_chapters(
    _pg_engine,
    invalid_case: str,
):
    async with _temporary_database(_pg_engine) as database_url:
        engine = create_async_engine(database_url)
        try:
            async with engine.begin() as connection:
                await connection.run_sync(
                    _upgrade,
                    database_url,
                    "d4b8f1a2c3e7",
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO users "
                        "(id, username, hashed_password, is_admin, is_active) "
                        "VALUES (7003, 'invalid-projection-user', 'secret', false, true)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO novel_projects (id, user_id, title, status) "
                        "VALUES ('invalid-projection-project', 7003, "
                        "'无效章节投影项目', 'draft')"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO chapters "
                        "(id, project_id, chapter_number, status, generation_progress, "
                        "generation_step_index, generation_step_total, word_count) "
                        "VALUES (8103, 'invalid-projection-project', 2, "
                        "'waiting_for_confirm', 0, 0, 0, 4)"
                    )
                )
                await connection.execute(
                    sa.text(
                        "INSERT INTO chapter_versions (id, chapter_id, version_label, content) "
                        "VALUES (9102, 8103, 'v1', '其他章节正文')"
                    )
                )
                if invalid_case == "missing_selected_version":
                    await connection.execute(
                        sa.text(
                            "INSERT INTO chapters "
                            "(id, project_id, chapter_number, status, generation_progress, "
                            "generation_step_index, generation_step_total, word_count) "
                            "VALUES (8102, 'invalid-projection-project', 1, "
                            "'successful', 0, 0, 0, 0)"
                        )
                    )
                else:
                    await connection.execute(
                        sa.text(
                            "INSERT INTO chapters "
                            "(id, project_id, chapter_number, status, generation_progress, "
                            "generation_step_index, generation_step_total, word_count, "
                            "selected_version_id) VALUES (8104, 'invalid-projection-project', "
                            "3, 'finalizing', 0, 0, 0, 4, 9102)"
                        )
                    )

            with pytest.raises(
                sa.exc.DBAPIError,
                match="successful/finalizing chapters require a valid selected_version_id",
            ):
                async with engine.begin() as connection:
                    await connection.run_sync(_upgrade, database_url, "head")

            async with engine.connect() as connection:
                revision = await connection.scalar(
                    sa.text("SELECT version_num FROM alembic_version")
                )
                tables = await connection.run_sync(
                    lambda sync_connection: set(sa.inspect(sync_connection).get_table_names())
                )
                chapter_columns = await connection.run_sync(
                    lambda sync_connection: {
                        column["name"]
                        for column in sa.inspect(sync_connection).get_columns("chapters")
                    }
                )

            assert revision == "d4b8f1a2c3e7"
            assert "chapter_revisions" not in tables
            assert "chapter_outbox_events" not in tables
            assert "chapter_projection_runs" not in tables
            assert "current_revision" not in chapter_columns
        finally:
            await engine.dispose()
