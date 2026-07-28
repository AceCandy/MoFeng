# AIMETA P=可重放章节投影模型_修订_outbox_run_rollout_审计|R=数据库实体与不变量|NR=不执行任务或业务事务|E=ChapterRevision_ChapterProjectionRun_ChapterProjectionRollout|X=internal|A=ORM模型|D=sqlalchemy|S=db|RD=./README.ai
"""Durable, replayable projections derived from immutable chapter revisions."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class ChapterRevision(Base):
    """Immutable canonical input captured by a chapter command."""

    __tablename__ = "chapter_revisions"
    __table_args__ = (
        UniqueConstraint("chapter_id", "revision", name="uq_chapter_revisions_chapter_revision"),
        UniqueConstraint(
            "project_id",
            "chapter_number",
            "revision",
            name="uq_chapter_revisions_project_number_revision",
        ),
        CheckConstraint("revision > 0", name="ck_chapter_revisions_positive_revision"),
        CheckConstraint(
            "lifecycle IN ('finalizing', 'shadow_ready', 'shadow_mismatch', "
            "'successful', 'superseded', 'tombstone', 'tombstoned')",
            name="ck_chapter_revisions_lifecycle",
        ),
        Index("ix_chapter_revisions_project_created", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chapter_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    selected_version_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapter_versions.id", ondelete="SET NULL"),
    )
    legacy_job_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("background_tasks.id", ondelete="SET NULL"),
    )
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_content: Mapped[str] = mapped_column(Text, nullable=False)
    projection_context: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    lifecycle: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="finalizing",
        server_default="finalizing",
    )
    required_projections: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    skipped_projections: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        server_default=text("'[]'::json"),
    )
    source_generation: Mapped[str] = mapped_column(String(36), nullable=False)
    superseded_by_revision: Mapped[Optional[int]] = mapped_column(BigInteger)
    tombstoned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChapterOutboxEvent(Base):
    """Append-only aggregate fact used to rebuild projection jobs."""

    __tablename__ = "chapter_outbox_events"
    __table_args__ = (
        UniqueConstraint(
            "aggregate_type",
            "aggregate_id",
            "revision",
            "event_type",
            name="uq_chapter_outbox_aggregate_revision_type",
        ),
        UniqueConstraint("idempotency_key", name="uq_chapter_outbox_idempotency"),
        CheckConstraint("revision > 0", name="ck_chapter_outbox_positive_revision"),
        Index("ix_chapter_outbox_project_created", "project_id", "created_at"),
        Index("ix_chapter_outbox_event_created", "event_type", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    aggregate_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="chapter",
        server_default="chapter",
    )
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    chapter_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    event_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    payload_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    workflow_stream_type: Mapped[Optional[str]] = mapped_column(String(32))
    workflow_stream_id: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChapterProjectionRun(Base):
    """Domain outcome for one typed JobRun; it does not own leases or retries."""

    __tablename__ = "chapter_projection_runs"
    __table_args__ = (
        UniqueConstraint(
            "chapter_revision_id",
            "projection_name",
            "artifact_generation",
            name="uq_chapter_projection_revision_name_generation",
        ),
        UniqueConstraint("job_id", name="uq_chapter_projection_job"),
        CheckConstraint(
            "projection_name IN ('summary', 'memory', 'rag', 'foreshadowing', "
            "'trace', 'reconcile', 'tombstone')",
            name="ck_chapter_projection_run_name",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'retry_wait', 'succeeded', 'failed', "
            "'skipped', 'stale', 'needs_attention', 'dead_letter')",
            name="ck_chapter_projection_run_status",
        ),
        Index(
            "uq_chapter_projection_active",
            "chapter_id",
            "revision",
            "projection_name",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_chapter_projection_status",
            "project_id",
            "status",
            "updated_at",
        ),
        Index(
            "ix_chapter_projection_revision",
            "chapter_id",
            "revision",
            "projection_name",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chapter_revision_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chapter_revisions.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    projection_name: Mapped[str] = mapped_column(String(32), nullable=False)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    dependency_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_projection_runs.id", ondelete="SET NULL"),
    )
    replay_of_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_projection_runs.id", ondelete="SET NULL"),
    )
    job_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("background_tasks.id", ondelete="SET NULL"),
    )
    artifact_generation: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="queued",
        server_default="queued",
    )
    required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )
    checkpoint: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    error_category: Mapped[Optional[str]] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChapterProjectionRollout(Base):
    """Per-chapter owner and generation fence for shadow/cutover/rollback."""

    __tablename__ = "chapter_projection_rollouts"
    __table_args__ = (
        UniqueConstraint("chapter_id", name="uq_chapter_projection_rollout_chapter"),
        Index("ix_chapter_projection_rollout_owner", "owner", "state"),
        Index(
            "ix_chapter_projection_rollout_observation",
            "state",
            "observation_deadline_at",
        ),
        CheckConstraint("generation >= 1", name="ck_chapter_projection_rollout_generation"),
        CheckConstraint(
            "fencing_token >= 0",
            name="ck_chapter_projection_rollout_fencing_token",
        ),
        CheckConstraint(
            "transition_sequence >= 0",
            name="ck_chapter_projection_rollout_transition_sequence",
        ),
        CheckConstraint(
            "required_observations >= 0 AND successful_observations >= 0 "
            "AND failed_observations >= 0",
            name="ck_chapter_projection_rollout_observation_counts",
        ),
        CheckConstraint(
            "owner IN ('legacy', 'projection')",
            name="ck_chapter_projection_rollout_owner",
        ),
        CheckConstraint(
            "state IN ('legacy', 'shadow', 'draining', 'projection')",
            name="ck_chapter_projection_rollout_state",
        ),
        CheckConstraint(
            "((owner = 'legacy' AND state IN ('legacy', 'shadow', 'draining')) "
            "OR (owner = 'projection' AND state = 'projection'))",
            name="ck_chapter_projection_rollout_owner_state",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    chapter_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    owner: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="projection",
        server_default="projection",
    )
    state: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="projection",
        server_default="projection",
    )
    generation: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
    )
    fencing_token: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    transition_sequence: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )
    shadow_digest: Mapped[Optional[str]] = mapped_column(String(64))
    shadow_diff: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    observation_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    observation_deadline_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    required_observations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    successful_observations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    failed_observations: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    last_observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    cutover_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rollback_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rollback_manifest: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ChapterProjectionRolloutTransition(Base):
    """Append-only owner/state/fence transition audit."""

    __tablename__ = "chapter_projection_rollout_transitions"
    __table_args__ = (
        UniqueConstraint(
            "rollout_id",
            "sequence",
            name="uq_chapter_projection_rollout_transition_sequence",
        ),
        Index(
            "ix_chapter_projection_rollout_transition_created",
            "rollout_id",
            "created_at",
        ),
        Index(
            "ix_chapter_projection_rollout_transition_aggregate",
            "project_id",
            "chapter_id",
            "created_at",
        ),
        CheckConstraint("sequence > 0", name="ck_chapter_projection_transition_sequence"),
        CheckConstraint("generation >= 1", name="ck_chapter_projection_transition_generation"),
        CheckConstraint(
            "fencing_token >= 0",
            name="ck_chapter_projection_transition_fencing_token",
        ),
        CheckConstraint(
            "(from_owner IS NULL OR from_owner IN ('legacy', 'projection')) "
            "AND to_owner IN ('legacy', 'projection')",
            name="ck_chapter_projection_transition_owner",
        ),
        CheckConstraint(
            "(from_state IS NULL OR from_state IN "
            "('legacy', 'shadow', 'draining', 'projection')) "
            "AND to_state IN ('legacy', 'shadow', 'draining', 'projection')",
            name="ck_chapter_projection_transition_state",
        ),
        CheckConstraint(
            "((from_owner IS NULL AND from_state IS NULL) OR "
            "(from_owner = 'legacy' AND from_state IN ('legacy', 'shadow', 'draining')) OR "
            "(from_owner = 'projection' AND from_state = 'projection')) AND "
            "((to_owner = 'legacy' AND to_state IN ('legacy', 'shadow', 'draining')) OR "
            "(to_owner = 'projection' AND to_state = 'projection'))",
            name="ck_chapter_projection_transition_owner_state",
        ),
        CheckConstraint(
            "((from_state IS NULL AND to_state IN ('legacy', 'projection')) OR "
            "(from_state = 'legacy' AND to_state = 'shadow') OR "
            "(from_state = 'shadow' AND to_state = 'draining') OR "
            "(from_state = 'draining' AND to_state IN ('shadow', 'projection')) OR "
            "(from_state = 'projection' AND to_state = 'legacy'))",
            name="ck_chapter_projection_transition_edge",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rollout_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_projection_rollouts.id", ondelete="SET NULL"),
    )
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    from_owner: Mapped[Optional[str]] = mapped_column(String(32))
    to_owner: Mapped[str] = mapped_column(String(32), nullable=False)
    from_state: Mapped[Optional[str]] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    generation: Mapped[int] = mapped_column(Integer, nullable=False)
    fencing_token: Mapped[int] = mapped_column(BigInteger, nullable=False)
    operator_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChapterProjectionShadowObservation(Base):
    """Append-only, redacted shadow invariant observation."""

    __tablename__ = "chapter_projection_shadow_observations"
    __table_args__ = (
        UniqueConstraint(
            "rollout_id",
            "sample_key",
            name="uq_chapter_projection_shadow_observation_sample",
        ),
        Index(
            "ix_chapter_projection_shadow_observation_created",
            "rollout_id",
            "created_at",
        ),
        Index(
            "ix_chapter_projection_shadow_observation_outcome",
            "rollout_id",
            "outcome",
            "created_at",
        ),
        CheckConstraint("revision > 0", name="ck_chapter_projection_observation_revision"),
        CheckConstraint(
            "rollout_generation >= 1",
            name="ck_chapter_projection_observation_generation",
        ),
        CheckConstraint(
            "outcome IN ('match', 'mismatch')",
            name="ck_chapter_projection_observation_outcome",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    rollout_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_projection_rollouts.id", ondelete="SET NULL"),
    )
    aggregate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    projection_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_projection_runs.id", ondelete="SET NULL"),
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rollout_generation: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_key: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    diff: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


class ChapterProjectionReplayAudit(Base):
    """Allowlisted audit record for privileged dry-run and replay commands."""

    __tablename__ = "chapter_projection_replay_audits"
    __table_args__ = (
        UniqueConstraint(
            "operator_user_id",
            "idempotency_key",
            name="uq_chapter_projection_replay_operator_key",
        ),
        Index(
            "ix_chapter_projection_replay_rate",
            "operator_user_id",
            "created_at",
        ),
        Index(
            "ix_chapter_projection_replay_project",
            "project_id",
            "chapter_id",
            "revision",
        ),
        CheckConstraint(
            "projection_name IS NULL OR projection_name IN "
            "('summary', 'memory', 'rag', 'foreshadowing', 'trace', 'reconcile')",
            name="ck_chapter_projection_replay_name",
        ),
        CheckConstraint(
            "mode IN ('dry_run', 'replay')",
            name="ck_chapter_projection_replay_mode",
        ),
        CheckConstraint(
            "status IN ('accepted', 'completed', 'rejected')",
            name="ck_chapter_projection_replay_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operator_user_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    project_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="SET NULL"),
    )
    chapter_id: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("chapters.id", ondelete="SET NULL"),
    )
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    projection_name: Mapped[Optional[str]] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="accepted",
        server_default="accepted",
    )
    request_scope: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        server_default=text("'{}'::json"),
    )
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class ChapterProjectionRetentionAudit(Base):
    """不可变的派生制品 preview/purge 审计。"""

    __tablename__ = "chapter_projection_retention_audits"
    __table_args__ = (
        UniqueConstraint(
            "operator_user_id",
            "idempotency_key",
            name="uq_chapter_projection_retention_operator_key",
        ),
        Index(
            "ix_chapter_projection_retention_rate",
            "operator_user_id",
            "created_at",
        ),
        Index(
            "ix_chapter_projection_retention_target",
            "project_id",
            "chapter_number",
            "revision",
            "artifact_generation",
        ),
        Index(
            "uq_chapter_projection_retention_completed_purge",
            "project_id",
            "chapter_number",
            "revision",
            "artifact_generation",
            "artifact_kind",
            unique=True,
            postgresql_where=text("mode = 'purge' AND status = 'completed'"),
        ),
        CheckConstraint(
            "chapter_number > 0 AND revision > 0",
            name="ck_chapter_projection_retention_positive_identity",
        ),
        CheckConstraint(
            "artifact_kind IN ('rag', 'foreshadowing')",
            name="ck_chapter_projection_retention_artifact_kind",
        ),
        CheckConstraint(
            "mode IN ('preview', 'purge')",
            name="ck_chapter_projection_retention_mode",
        ),
        CheckConstraint(
            "status IN ('completed', 'rejected')",
            name="ck_chapter_projection_retention_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    operator_user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chapter_id: Mapped[Optional[int]] = mapped_column(BigInteger)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(BigInteger, nullable=False)
    artifact_generation: Mapped[str] = mapped_column(String(36), nullable=False)
    artifact_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    projection_run_id: Mapped[Optional[str]] = mapped_column(String(36))
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(160), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    request_scope: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


__all__ = [
    "ChapterOutboxEvent",
    "ChapterProjectionReplayAudit",
    "ChapterProjectionRetentionAudit",
    "ChapterProjectionRollout",
    "ChapterProjectionRolloutTransition",
    "ChapterProjectionRun",
    "ChapterProjectionShadowObservation",
    "ChapterRevision",
]
