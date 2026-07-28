"""expand replayable chapter projections

Revision ID: e7c9a1b2d3f4
Revises: d4b8f1a2c3e7
Create Date: 2026-07-28 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7c9a1b2d3f4"
down_revision: Union[str, None] = "d4b8f1a2c3e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column("current_revision", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column("chapters", sa.Column("source_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "chapters",
        sa.Column(
            "required_projection_snapshot",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
    )
    op.add_column(
        "chapters",
        sa.Column("projection_generation", sa.String(length=36), nullable=True),
    )
    op.add_column(
        "chapters",
        sa.Column("tombstone_revision", sa.BigInteger(), server_default="0", nullable=False),
    )

    op.create_table(
        "chapter_revisions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("selected_version_id", sa.BigInteger(), nullable=True),
        sa.Column("legacy_job_id", sa.String(length=36), nullable=True),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("source_content", sa.Text(), nullable=False),
        sa.Column(
            "projection_context",
            sa.JSON(),
            server_default=sa.text("'{}'::json"),
            nullable=False,
        ),
        sa.Column("lifecycle", sa.String(length=32), server_default="finalizing", nullable=False),
        sa.Column(
            "required_projections",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column(
            "skipped_projections",
            sa.JSON(),
            server_default=sa.text("'[]'::json"),
            nullable=False,
        ),
        sa.Column("source_generation", sa.String(length=36), nullable=False),
        sa.Column("superseded_by_revision", sa.BigInteger(), nullable=True),
        sa.Column("tombstoned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("revision > 0", name="ck_chapter_revisions_positive_revision"),
        sa.CheckConstraint(
            "lifecycle IN ('finalizing', 'shadow_ready', 'shadow_mismatch', "
            "'successful', 'superseded', 'tombstone', 'tombstoned')",
            name="ck_chapter_revisions_lifecycle",
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["selected_version_id"],
            ["chapter_versions.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["legacy_job_id"],
            ["background_tasks.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "chapter_id",
            "revision",
            name="uq_chapter_revisions_chapter_revision",
        ),
        sa.UniqueConstraint(
            "project_id",
            "chapter_number",
            "revision",
            name="uq_chapter_revisions_project_number_revision",
        ),
    )
    op.create_index(
        "ix_chapter_revisions_project_created",
        "chapter_revisions",
        ["project_id", "created_at"],
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM chapters
                    LEFT JOIN chapter_versions
                      ON chapter_versions.id = chapters.selected_version_id
                    WHERE chapters.status IN ('successful', 'finalizing')
                      AND (
                          chapters.selected_version_id IS NULL
                          OR chapter_versions.id IS NULL
                          OR chapter_versions.chapter_id <> chapters.id
                      )
                ) THEN
                    RAISE EXCEPTION
                        'cannot backfill replayable chapter revisions: successful/finalizing chapters require a valid selected_version_id'
                        USING ERRCODE = 'check_violation';
                END IF;
            END $$;
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO chapter_revisions (
                id,
                chapter_id,
                project_id,
                chapter_number,
                revision,
                selected_version_id,
                source_hash,
                source_content,
                projection_context,
                lifecycle,
                required_projections,
                skipped_projections,
                source_generation
            )
            SELECT
                substr(md5('chapter-revision:legacy:' || chapters.id::text), 1, 8)
                    || '-' || substr(md5('chapter-revision:legacy:' || chapters.id::text), 9, 4)
                    || '-' || substr(md5('chapter-revision:legacy:' || chapters.id::text), 13, 4)
                    || '-' || substr(md5('chapter-revision:legacy:' || chapters.id::text), 17, 4)
                    || '-' || substr(md5('chapter-revision:legacy:' || chapters.id::text), 21, 12),
                chapters.id,
                chapters.project_id,
                chapters.chapter_number,
                1,
                chapter_versions.id,
                encode(
                    sha256(convert_to(COALESCE(chapter_versions.content, ''), 'UTF8')),
                    'hex'
                ),
                COALESCE(chapter_versions.content, ''),
                '{}'::json,
                CASE
                    WHEN chapters.status = 'successful' THEN 'successful'
                    ELSE 'finalizing'
                END,
                '[]'::json,
                '[]'::json,
                'legacy'
            FROM chapters
            JOIN chapter_versions
              ON chapter_versions.id = chapters.selected_version_id
             AND chapter_versions.chapter_id = chapters.id
            ON CONFLICT (chapter_id, revision) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE chapters
            SET
                current_revision = 1,
                source_hash = encode(
                    sha256(convert_to(COALESCE(chapter_versions.content, ''), 'UTF8')),
                    'hex'
                ),
                projection_generation = 'legacy'
            FROM chapter_versions
            WHERE chapter_versions.id = chapters.selected_version_id
              AND chapter_versions.chapter_id = chapters.id
            """
        )
    )

    op.create_table(
        "chapter_outbox_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("aggregate_type", sa.String(length=32), server_default="chapter", nullable=False),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("event_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("payload_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("workflow_stream_type", sa.String(length=32), nullable=True),
        sa.Column("workflow_stream_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("revision > 0", name="ck_chapter_outbox_positive_revision"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_chapter_outbox_idempotency"),
        sa.UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "revision",
            "event_type",
            name="uq_chapter_outbox_aggregate_revision_type",
        ),
    )
    op.create_index(
        "ix_chapter_outbox_project_created",
        "chapter_outbox_events",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_chapter_outbox_event_created",
        "chapter_outbox_events",
        ["event_type", "created_at"],
    )

    op.create_table(
        "chapter_projection_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("chapter_revision_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("projection_name", sa.String(length=32), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column("dependency_run_id", sa.String(length=36), nullable=True),
        sa.Column("replay_of_run_id", sa.String(length=36), nullable=True),
        sa.Column("job_id", sa.String(length=36), nullable=True),
        sa.Column("artifact_generation", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="queued", nullable=False),
        sa.Column("required", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("checkpoint", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error_category", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["chapter_revision_id"],
            ["chapter_revisions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["dependency_run_id"],
            ["chapter_projection_runs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["replay_of_run_id"],
            ["chapter_projection_runs.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["job_id"], ["background_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_chapter_projection_job"),
        sa.CheckConstraint(
            "projection_name IN ('summary', 'memory', 'rag', 'foreshadowing', "
            "'trace', 'reconcile', 'tombstone')",
            name="ck_chapter_projection_run_name",
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'retry_wait', 'succeeded', 'failed', "
            "'skipped', 'stale', 'needs_attention', 'dead_letter')",
            name="ck_chapter_projection_run_status",
        ),
        sa.UniqueConstraint(
            "chapter_revision_id",
            "projection_name",
            "artifact_generation",
            name="uq_chapter_projection_revision_name_generation",
        ),
    )
    op.create_index(
        "uq_chapter_projection_active",
        "chapter_projection_runs",
        ["chapter_id", "revision", "projection_name"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_chapter_projection_status",
        "chapter_projection_runs",
        ["project_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_chapter_projection_revision",
        "chapter_projection_runs",
        ["chapter_id", "revision", "projection_name"],
    )

    op.create_table(
        "chapter_projection_rollouts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("chapter_id", sa.BigInteger(), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=False),
        sa.Column("owner", sa.String(length=32), server_default="projection", nullable=False),
        sa.Column("state", sa.String(length=32), server_default="projection", nullable=False),
        sa.Column("generation", sa.Integer(), server_default="1", nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("transition_sequence", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("shadow_digest", sa.String(length=64), nullable=True),
        sa.Column("shadow_diff", sa.JSON(), nullable=True),
        sa.Column("observation_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observation_deadline_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("required_observations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("successful_observations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_observations", sa.Integer(), server_default="0", nullable=False),
        sa.Column("last_observed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cutover_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_manifest", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "generation >= 1",
            name="ck_chapter_projection_rollout_generation",
        ),
        sa.CheckConstraint(
            "fencing_token >= 0",
            name="ck_chapter_projection_rollout_fencing_token",
        ),
        sa.CheckConstraint(
            "transition_sequence >= 0",
            name="ck_chapter_projection_rollout_transition_sequence",
        ),
        sa.CheckConstraint(
            "required_observations >= 0 AND successful_observations >= 0 "
            "AND failed_observations >= 0",
            name="ck_chapter_projection_rollout_observation_counts",
        ),
        sa.CheckConstraint(
            "owner IN ('legacy', 'projection')",
            name="ck_chapter_projection_rollout_owner",
        ),
        sa.CheckConstraint(
            "state IN ('legacy', 'shadow', 'draining', 'projection')",
            name="ck_chapter_projection_rollout_state",
        ),
        sa.CheckConstraint(
            "((owner = 'legacy' AND state IN ('legacy', 'shadow', 'draining')) "
            "OR (owner = 'projection' AND state = 'projection'))",
            name="ck_chapter_projection_rollout_owner_state",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chapter_id", name="uq_chapter_projection_rollout_chapter"),
    )
    op.create_index(
        "ix_chapter_projection_rollout_owner",
        "chapter_projection_rollouts",
        ["owner", "state"],
    )
    op.create_index(
        "ix_chapter_projection_rollout_observation",
        "chapter_projection_rollouts",
        ["state", "observation_deadline_at"],
    )

    op.create_table(
        "chapter_projection_rollout_transitions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rollout_id", sa.String(length=36), nullable=True),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("sequence", sa.BigInteger(), nullable=False),
        sa.Column("from_owner", sa.String(length=32), nullable=True),
        sa.Column("to_owner", sa.String(length=32), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.BigInteger(), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "sequence > 0",
            name="ck_chapter_projection_transition_sequence",
        ),
        sa.CheckConstraint(
            "generation >= 1",
            name="ck_chapter_projection_transition_generation",
        ),
        sa.CheckConstraint(
            "fencing_token >= 0",
            name="ck_chapter_projection_transition_fencing_token",
        ),
        sa.CheckConstraint(
            "(from_owner IS NULL OR from_owner IN ('legacy', 'projection')) "
            "AND to_owner IN ('legacy', 'projection')",
            name="ck_chapter_projection_transition_owner",
        ),
        sa.CheckConstraint(
            "(from_state IS NULL OR from_state IN "
            "('legacy', 'shadow', 'draining', 'projection')) "
            "AND to_state IN ('legacy', 'shadow', 'draining', 'projection')",
            name="ck_chapter_projection_transition_state",
        ),
        sa.CheckConstraint(
            "((from_owner IS NULL AND from_state IS NULL) OR "
            "(from_owner = 'legacy' AND from_state IN ('legacy', 'shadow', 'draining')) OR "
            "(from_owner = 'projection' AND from_state = 'projection')) AND "
            "((to_owner = 'legacy' AND to_state IN ('legacy', 'shadow', 'draining')) OR "
            "(to_owner = 'projection' AND to_state = 'projection'))",
            name="ck_chapter_projection_transition_owner_state",
        ),
        sa.CheckConstraint(
            "((from_state IS NULL AND to_state IN ('legacy', 'projection')) OR "
            "(from_state = 'legacy' AND to_state = 'shadow') OR "
            "(from_state = 'shadow' AND to_state = 'draining') OR "
            "(from_state = 'draining' AND to_state IN ('shadow', 'projection')) OR "
            "(from_state = 'projection' AND to_state = 'legacy'))",
            name="ck_chapter_projection_transition_edge",
        ),
        sa.ForeignKeyConstraint(
            ["rollout_id"],
            ["chapter_projection_rollouts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rollout_id",
            "sequence",
            name="uq_chapter_projection_rollout_transition_sequence",
        ),
    )
    op.create_index(
        "ix_chapter_projection_rollout_transition_created",
        "chapter_projection_rollout_transitions",
        ["rollout_id", "created_at"],
    )
    op.create_index(
        "ix_chapter_projection_rollout_transition_aggregate",
        "chapter_projection_rollout_transitions",
        ["project_id", "chapter_id", "created_at"],
    )

    op.execute(
        sa.text(
            """
            INSERT INTO chapter_projection_rollouts (
                id,
                chapter_id,
                project_id,
                owner,
                state,
                generation,
                fencing_token,
                transition_sequence,
                required_observations,
                successful_observations,
                failed_observations,
                updated_at
            )
            SELECT
                md5('chapter-projection-rollout:' || chapters.id::text),
                chapters.id,
                chapters.project_id,
                'legacy',
                'legacy',
                1,
                0,
                1,
                0,
                0,
                0,
                now()
            FROM chapters
            ON CONFLICT (chapter_id) DO NOTHING
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO chapter_projection_rollout_transitions (
                id,
                rollout_id,
                aggregate_id,
                project_id,
                chapter_id,
                sequence,
                from_owner,
                to_owner,
                from_state,
                to_state,
                generation,
                fencing_token,
                operator_user_id,
                reason,
                details,
                created_at
            )
            SELECT
                md5('chapter-projection-rollout-transition:' || chapters.id::text),
                rollouts.id,
                chapters.id::text,
                chapters.project_id,
                chapters.id,
                1,
                NULL,
                'legacy',
                NULL,
                'legacy',
                1,
                0,
                NULL,
                'migration legacy rollout backfill',
                CAST('{}' AS json),
                now()
            FROM chapter_projection_rollouts AS rollouts
            JOIN chapters ON chapters.id = rollouts.chapter_id
            WHERE rollouts.owner = 'legacy'
              AND rollouts.state = 'legacy'
              AND NOT EXISTS (
                  SELECT 1
                  FROM chapter_projection_rollout_transitions AS transitions
                  WHERE transitions.rollout_id = rollouts.id
                    AND transitions.sequence = 1
              )
            """
        )
    )

    op.create_table(
        "chapter_projection_shadow_observations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("rollout_id", sa.String(length=36), nullable=True),
        sa.Column("aggregate_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("projection_run_id", sa.String(length=36), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("rollout_generation", sa.Integer(), nullable=False),
        sa.Column("sample_key", sa.String(length=255), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("digest", sa.String(length=64), nullable=False),
        sa.Column("diff", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revision > 0",
            name="ck_chapter_projection_observation_revision",
        ),
        sa.CheckConstraint(
            "rollout_generation >= 1",
            name="ck_chapter_projection_observation_generation",
        ),
        sa.CheckConstraint(
            "outcome IN ('match', 'mismatch')",
            name="ck_chapter_projection_observation_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["rollout_id"],
            ["chapter_projection_rollouts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["projection_run_id"],
            ["chapter_projection_runs.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rollout_id",
            "sample_key",
            name="uq_chapter_projection_shadow_observation_sample",
        ),
    )
    op.create_index(
        "ix_chapter_projection_shadow_observation_created",
        "chapter_projection_shadow_observations",
        ["rollout_id", "created_at"],
    )
    op.create_index(
        "ix_chapter_projection_shadow_observation_outcome",
        "chapter_projection_shadow_observations",
        ["rollout_id", "outcome", "created_at"],
    )

    op.create_table(
        "chapter_projection_replay_audits",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.String(length=36), nullable=True),
        sa.Column("chapter_id", sa.BigInteger(), nullable=True),
        sa.Column("revision", sa.BigInteger(), nullable=False),
        sa.Column("projection_name", sa.String(length=32), nullable=True),
        sa.Column("mode", sa.String(length=16), nullable=False),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="accepted", nullable=False),
        sa.Column("request_scope", sa.JSON(), server_default=sa.text("'{}'::json"), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "projection_name IS NULL OR projection_name IN "
            "('summary', 'memory', 'rag', 'foreshadowing', 'trace', 'reconcile')",
            name="ck_chapter_projection_replay_name",
        ),
        sa.CheckConstraint(
            "mode IN ('dry_run', 'replay')",
            name="ck_chapter_projection_replay_mode",
        ),
        sa.CheckConstraint(
            "status IN ('accepted', 'completed', 'rejected')",
            name="ck_chapter_projection_replay_status",
        ),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["novel_projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapters.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operator_user_id",
            "idempotency_key",
            name="uq_chapter_projection_replay_operator_key",
        ),
    )
    op.create_index(
        "ix_chapter_projection_replay_rate",
        "chapter_projection_replay_audits",
        ["operator_user_id", "created_at"],
    )
    op.create_index(
        "ix_chapter_projection_replay_project",
        "chapter_projection_replay_audits",
        ["project_id", "chapter_id", "revision"],
    )

    for table_name in ("rag_chunks", "rag_summaries"):
        op.alter_column(
            table_name,
            "id",
            existing_type=sa.String(length=128),
            type_=sa.String(length=192),
            existing_nullable=False,
        )
        op.add_column(
            table_name,
            sa.Column("source_revision", sa.BigInteger(), server_default="0", nullable=False),
        )
        op.add_column(
            table_name,
            sa.Column(
                "artifact_generation",
                sa.String(length=36),
                server_default="legacy",
                nullable=False,
            ),
        )
        op.add_column(
            table_name,
            sa.Column("projection_run_id", sa.String(length=36), nullable=True),
        )
        op.add_column(
            table_name,
            sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        )
        op.create_foreign_key(
            f"fk_{table_name}_projection_run_id",
            table_name,
            "chapter_projection_runs",
            ["projection_run_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index(
            f"ix_{table_name}_active",
            table_name,
            ["project_id", "chapter_number", "is_active"],
        )
        op.create_index(
            f"ix_{table_name}_generation",
            table_name,
            ["project_id", "chapter_number", "artifact_generation"],
        )

    op.add_column(
        "project_memories",
        sa.Column("projection_revision", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "project_memories",
        sa.Column("projection_generation", sa.String(length=36), nullable=True),
    )

    for table_name in ("chapter_snapshots", "character_states", "foreshadowings"):
        revision_column = "chapter_revision"
        op.add_column(
            table_name,
            sa.Column(revision_column, sa.BigInteger(), server_default="0", nullable=False),
        )
        op.add_column(
            table_name,
            sa.Column(
                "artifact_generation",
                sa.String(length=36),
                server_default="legacy",
                nullable=False,
            ),
        )
        op.add_column(
            table_name,
            sa.Column("projection_run_id", sa.String(length=36), nullable=True),
        )
        op.create_foreign_key(
            f"fk_{table_name}_projection_run_id",
            table_name,
            "chapter_projection_runs",
            ["projection_run_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.add_column(
        "chapter_snapshots",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.create_index(
        "ix_chapter_snapshots_projection",
        "chapter_snapshots",
        ["project_id", "chapter_number", "chapter_revision", "is_active"],
    )
    op.add_column(
        "character_states",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "foreshadowings",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.drop_constraint(
        "foreshadowings_chapter_id_fkey",
        "foreshadowings",
        type_="foreignkey",
    )
    op.alter_column(
        "foreshadowings",
        "chapter_id",
        existing_type=sa.BigInteger(),
        nullable=True,
    )
    op.create_foreign_key(
        "fk_foreshadowings_chapter_id",
        "foreshadowings",
        "chapters",
        ["chapter_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "foreshadowing_status_history",
        sa.Column("chapter_revision", sa.BigInteger(), server_default="0", nullable=False),
    )
    op.add_column(
        "foreshadowing_status_history",
        sa.Column(
            "artifact_generation",
            sa.String(length=36),
            server_default="legacy",
            nullable=False,
        ),
    )
    op.add_column(
        "foreshadowing_status_history",
        sa.Column("projection_run_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_foreshadowing_status_history_projection_run_id",
        "foreshadowing_status_history",
        "chapter_projection_runs",
        ["projection_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    for table_name, revision_column in (
        ("rag_chunks", "source_revision"),
        ("rag_summaries", "source_revision"),
        ("chapter_snapshots", "chapter_revision"),
        ("character_states", "chapter_revision"),
        ("foreshadowings", "chapter_revision"),
    ):
        op.execute(
            sa.text(
                f"""
                UPDATE {table_name} AS artifact
                SET
                    {revision_column} = chapters.current_revision,
                    artifact_generation = 'legacy'
                FROM chapters
                WHERE artifact.project_id = chapters.project_id
                  AND artifact.chapter_number = chapters.chapter_number
                  AND chapters.current_revision > 0
                """
            )
        )
    op.execute(
        sa.text(
            """
            UPDATE project_memories AS memory
            SET
                projection_revision = chapters.current_revision,
                projection_generation = 'legacy'
            FROM chapters
            WHERE memory.project_id = chapters.project_id
              AND memory.last_updated_chapter = chapters.chapter_number
              AND chapters.current_revision > 0
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE foreshadowing_status_history AS history
            SET
                chapter_revision = chapters.current_revision,
                artifact_generation = 'legacy'
            FROM foreshadowings, chapters
            WHERE history.foreshadowing_id = foreshadowings.id
              AND chapters.project_id = foreshadowings.project_id
              AND chapters.chapter_number = history.chapter_number
              AND chapters.current_revision > 0
            """
        )
    )


def downgrade() -> None:
    raise RuntimeError(
        "Replayable chapter revisions and outbox events are audit data; "
        "use the documented binary rollback floor instead of destructive downgrade."
    )
