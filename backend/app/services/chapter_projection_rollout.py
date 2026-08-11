# AIMETA P=章节投影发布状态机_影子验证与原子切换|R=owner状态迁移_制品提升_精确回滚_审计|NR=不执行投影计算或任务claim|E=ChapterProjectionRolloutService|X=internal|A=事务服务|D=sqlalchemy|S=db|RD=./README.ai
"""Transactional rollout state machine and shadow artifact promotion."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from ..models.chapter_blueprint import ChapterBlueprint
from ..models.chapter_projection import (
    ChapterProjectionRollout,
    ChapterProjectionRolloutTransition,
    ChapterProjectionRun,
    ChapterProjectionShadowObservation,
    ChapterRevision,
)
from ..models.foreshadowing import Foreshadowing, ForeshadowingStatusHistory
from ..models.memory_layer import CharacterState
from ..models.novel import Chapter
from ..models.project_memory import ChapterSnapshot, ProjectMemory
from ..models.rag import RagChunk, RagSummary
from ..schemas.job import ChapterProjectionJobPayload
from .foreshadowing_sync_service import (
    ForeshadowingSyncService,
    deserialize_foreshadowing_plan,
)

NONTERMINAL_JOB_STATUSES = {"queued", "running", "retry_wait", "waiting"}
ALLOWED_TRANSITIONS = {
    ("legacy", "shadow"),
    ("shadow", "draining"),
    ("shadow", "legacy"),
    ("draining", "projection"),
    ("draining", "shadow"),
    ("projection", "legacy"),
}
ROLLOUT_OWNER_BY_STATE = {
    "legacy": "legacy",
    "shadow": "legacy",
    "draining": "legacy",
    "projection": "projection",
}


class ChapterProjectionRolloutError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class ChapterProjectionRolloutNotFoundError(ChapterProjectionRolloutError):
    pass


class ChapterProjectionRolloutConflictError(ChapterProjectionRolloutError):
    pass


class ChapterProjectionObservationPendingError(ChapterProjectionRolloutError):
    pass


@dataclass(frozen=True)
class RolloutGate:
    ready: bool
    reasons: tuple[str, ...]


def evaluate_rollout_gate(
    *,
    state: str,
    now: datetime,
    observation_deadline_at: Optional[datetime],
    required_observations: int,
    successful_observations: int,
    failed_observations: int,
    latest_outcome: Optional[str],
    latest_revision: Optional[int],
    current_revision: int,
    shadow_diff: Optional[dict[str, Any]],
) -> RolloutGate:
    """Evaluate the redacted, deterministic cutover gate."""

    reasons: list[str] = []
    if state not in {"shadow", "draining"}:
        reasons.append("rollout_not_shadow_or_draining")
    if observation_deadline_at is None or now < observation_deadline_at:
        reasons.append("observation_window_not_elapsed")
    if required_observations < 1 or successful_observations < required_observations:
        reasons.append("insufficient_shadow_observations")
    if failed_observations > 0:
        reasons.append("shadow_observation_failed")
    if latest_outcome != "match" or latest_revision != current_revision:
        reasons.append("current_revision_not_observed")
    if int((shadow_diff or {}).get("unexplained_count", 0)) > 0:
        reasons.append("shadow_diff_gate_failed")
    return RolloutGate(not reasons, tuple(reasons))


def validate_rollout_transition(from_state: str, to_state: str) -> None:
    if (from_state, to_state) not in ALLOWED_TRANSITIONS:
        raise ChapterProjectionRolloutConflictError("illegal_rollout_transition")


def validate_rollout_owner_state(owner: str, state: str) -> None:
    """Reject corrupted owner/state pairs before they can cross a fence."""

    if ROLLOUT_OWNER_BY_STATE.get(state) != owner:
        raise ChapterProjectionRolloutConflictError("rollout_owner_state_invalid")


def _stable_digest(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _value_digest(value: Any) -> Optional[str]:
    if value in (None, "", [], {}):
        return None
    return _stable_digest(value)


class ChapterProjectionRolloutService:
    """Own per-Chapter rollout locks, audit rows, observations and promotion."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def ensure_projection_rollout(
        self,
        *,
        chapter: Chapter,
    ) -> ChapterProjectionRollout:
        """Create the greenfield projection owner and its first audit row."""

        locked_chapter = (
            (
                await self.session.execute(
                    select(Chapter)
                    .where(
                        Chapter.id == chapter.id,
                        Chapter.project_id == chapter.project_id,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if locked_chapter is None:
            raise ChapterProjectionRolloutNotFoundError("chapter_not_found")
        chapter = locked_chapter
        rollout = (
            (
                await self.session.execute(
                    select(ChapterProjectionRollout)
                    .where(ChapterProjectionRollout.chapter_id == chapter.id)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if rollout is not None:
            validate_rollout_owner_state(rollout.owner, rollout.state)
            return rollout
        rollout = ChapterProjectionRollout(
            id=str(uuid4()),
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            owner="projection",
            state="projection",
            generation=1,
            fencing_token=0,
            transition_sequence=0,
        )
        self.session.add(rollout)
        await self._append_transition(
            rollout=rollout,
            chapter=chapter,
            from_owner=None,
            from_state=None,
            operator_user_id=None,
            reason="greenfield projection owner",
            details={},
        )
        return rollout

    async def get_status(
        self,
        *,
        project_id: str,
        chapter_id: int,
    ) -> dict[str, Any]:
        chapter, rollout = await self._load_chapter_rollout(
            project_id=project_id,
            chapter_id=chapter_id,
            for_update=False,
        )
        latest = await self._latest_observation(rollout.id)
        gate = evaluate_rollout_gate(
            state=rollout.state,
            now=datetime.now(timezone.utc),
            observation_deadline_at=rollout.observation_deadline_at,
            required_observations=rollout.required_observations,
            successful_observations=rollout.successful_observations,
            failed_observations=rollout.failed_observations,
            latest_outcome=latest.outcome if latest is not None else None,
            latest_revision=latest.revision if latest is not None else None,
            current_revision=int(chapter.current_revision or 0),
            shadow_diff=rollout.shadow_diff,
        )
        return self._status_payload(chapter, rollout, gate)

    async def enter_shadow(
        self,
        *,
        project_id: str,
        chapter_id: int,
        expected_generation: int,
        expected_fencing_token: int,
        observation_seconds: int,
        required_observations: int,
        operator_user_id: int,
        reason: str,
    ) -> dict[str, Any]:
        chapter, rollout = await self._load_or_create_legacy_rollout(
            project_id=project_id,
            chapter_id=chapter_id,
            operator_user_id=operator_user_id,
        )
        self._require_cas(
            rollout,
            expected_generation=expected_generation,
            expected_fencing_token=expected_fencing_token,
        )
        validate_rollout_transition(rollout.state, "shadow")
        previous_owner, previous_state = rollout.owner, rollout.state
        now = datetime.now(timezone.utc)
        rollout.state = "shadow"
        rollout.owner = "legacy"
        rollout.generation += 1
        rollout.fencing_token += 1
        rollout.observation_started_at = now
        rollout.observation_deadline_at = now + timedelta(seconds=observation_seconds)
        rollout.required_observations = required_observations
        rollout.successful_observations = 0
        rollout.failed_observations = 0
        rollout.last_observed_at = None
        rollout.shadow_digest = None
        rollout.shadow_diff = None
        rollout.rollback_manifest = None
        await self._append_transition(
            rollout=rollout,
            chapter=chapter,
            from_owner=previous_owner,
            from_state=previous_state,
            operator_user_id=operator_user_id,
            reason=reason,
            details={
                "observation_seconds": observation_seconds,
                "required_observations": required_observations,
            },
        )
        gate = evaluate_rollout_gate(
            state=rollout.state,
            now=now,
            observation_deadline_at=rollout.observation_deadline_at,
            required_observations=rollout.required_observations,
            successful_observations=0,
            failed_observations=0,
            latest_outcome=None,
            latest_revision=None,
            current_revision=int(chapter.current_revision or 0),
            shadow_diff=None,
        )
        return self._status_payload(chapter, rollout, gate)

    async def prepare_cutover(
        self,
        *,
        project_id: str,
        chapter_id: int,
        expected_generation: int,
        expected_fencing_token: int,
        operator_user_id: int,
        reason: str,
    ) -> dict[str, Any]:
        chapter, rollout = await self._load_chapter_rollout(
            project_id=project_id,
            chapter_id=chapter_id,
            for_update=True,
        )
        self._require_cas(
            rollout,
            expected_generation=expected_generation,
            expected_fencing_token=expected_fencing_token,
        )
        validate_rollout_transition(rollout.state, "draining")
        latest = await self._latest_observation(rollout.id, for_update=True)
        gate = evaluate_rollout_gate(
            state=rollout.state,
            now=datetime.now(timezone.utc),
            observation_deadline_at=rollout.observation_deadline_at,
            required_observations=rollout.required_observations,
            successful_observations=rollout.successful_observations,
            failed_observations=rollout.failed_observations,
            latest_outcome=latest.outcome if latest is not None else None,
            latest_revision=latest.revision if latest is not None else None,
            current_revision=int(chapter.current_revision or 0),
            shadow_diff=rollout.shadow_diff,
        )
        if not gate.ready:
            raise ChapterProjectionRolloutConflictError(gate.reasons[0])
        if await self._has_nonterminal_chapter_jobs(chapter):
            raise ChapterProjectionRolloutConflictError("rollout_jobs_not_drained")

        previous_owner, previous_state = rollout.owner, rollout.state
        rollout.state = "draining"
        rollout.fencing_token += 1
        await self._append_transition(
            rollout=rollout,
            chapter=chapter,
            from_owner=previous_owner,
            from_state=previous_state,
            operator_user_id=operator_user_id,
            reason=reason,
            details={"gate": "passed"},
        )
        drained_gate = RolloutGate(True, ())
        return self._status_payload(chapter, rollout, drained_gate)

    async def complete_cutover(
        self,
        *,
        project_id: str,
        chapter_id: int,
        expected_generation: int,
        expected_fencing_token: int,
        operator_user_id: int,
        reason: str,
    ) -> dict[str, Any]:
        chapter, rollout = await self._load_chapter_rollout(
            project_id=project_id,
            chapter_id=chapter_id,
            for_update=True,
        )
        self._require_cas(
            rollout,
            expected_generation=expected_generation,
            expected_fencing_token=expected_fencing_token,
        )
        validate_rollout_transition(rollout.state, "projection")
        latest = await self._latest_observation(rollout.id, for_update=True)
        gate = evaluate_rollout_gate(
            state=rollout.state,
            now=datetime.now(timezone.utc),
            observation_deadline_at=rollout.observation_deadline_at,
            required_observations=rollout.required_observations,
            successful_observations=rollout.successful_observations,
            failed_observations=rollout.failed_observations,
            latest_outcome=latest.outcome if latest is not None else None,
            latest_revision=latest.revision if latest is not None else None,
            current_revision=int(chapter.current_revision or 0),
            shadow_diff=rollout.shadow_diff,
        )
        if not gate.ready:
            raise ChapterProjectionRolloutConflictError(gate.reasons[0])
        if await self._has_nonterminal_chapter_jobs(chapter):
            raise ChapterProjectionRolloutConflictError("rollout_jobs_not_drained")

        manifest = await self._promote_shadow_artifacts(chapter=chapter, rollout=rollout)
        previous_owner, previous_state = rollout.owner, rollout.state
        now = datetime.now(timezone.utc)
        rollout.owner = "projection"
        rollout.state = "projection"
        rollout.generation += 1
        rollout.fencing_token += 1
        rollout.cutover_at = now
        rollout.rollback_manifest = manifest
        await self._append_transition(
            rollout=rollout,
            chapter=chapter,
            from_owner=previous_owner,
            from_state=previous_state,
            operator_user_id=operator_user_id,
            reason=reason,
            details={
                "revision": int(chapter.current_revision or 0),
                "promoted_projection_count": len(manifest["projection_run_ids"]),
            },
        )
        return self._status_payload(
            chapter, rollout, RolloutGate(False, ("rollout_not_shadow_or_draining",))
        )

    async def rollback(
        self,
        *,
        project_id: str,
        chapter_id: int,
        expected_generation: int,
        expected_fencing_token: int,
        operator_user_id: int,
        reason: str,
    ) -> dict[str, Any]:
        chapter, rollout = await self._load_chapter_rollout(
            project_id=project_id,
            chapter_id=chapter_id,
            for_update=True,
        )
        self._require_cas(
            rollout,
            expected_generation=expected_generation,
            expected_fencing_token=expected_fencing_token,
        )
        target_state = "shadow" if rollout.state == "draining" else "legacy"
        validate_rollout_transition(rollout.state, target_state)
        if await self._has_nonterminal_chapter_jobs(chapter):
            raise ChapterProjectionRolloutConflictError("rollout_jobs_not_drained")
        if rollout.state == "projection":
            await self._restore_legacy_artifacts(chapter=chapter, rollout=rollout)

        previous_owner, previous_state = rollout.owner, rollout.state
        rollout.owner = "legacy"
        rollout.state = target_state
        rollout.generation += 1
        rollout.fencing_token += 1
        rollout.rollback_at = datetime.now(timezone.utc)
        await self._append_transition(
            rollout=rollout,
            chapter=chapter,
            from_owner=previous_owner,
            from_state=previous_state,
            operator_user_id=operator_user_id,
            reason=reason,
            details={"restored_artifacts": previous_state == "projection"},
        )
        latest = await self._latest_observation(rollout.id)
        gate = evaluate_rollout_gate(
            state=rollout.state,
            now=datetime.now(timezone.utc),
            observation_deadline_at=rollout.observation_deadline_at,
            required_observations=rollout.required_observations,
            successful_observations=rollout.successful_observations,
            failed_observations=rollout.failed_observations,
            latest_outcome=latest.outcome if latest is not None else None,
            latest_revision=latest.revision if latest is not None else None,
            current_revision=int(chapter.current_revision or 0),
            shadow_diff=rollout.shadow_diff,
        )
        return self._status_payload(chapter, rollout, gate)

    async def record_shadow_observation(
        self,
        *,
        payload: ChapterProjectionJobPayload,
        reconcile_run: ChapterProjectionRun,
        chapter: Chapter,
        revision: ChapterRevision,
        rollout: ChapterProjectionRollout,
    ) -> ChapterProjectionShadowObservation:
        """Record one revision sample without exposing artifact values in the diff."""

        if rollout.owner != "legacy" or rollout.state != "shadow":
            raise ChapterProjectionRolloutConflictError("rollout_not_shadow")
        if payload.execution_mode != "shadow":
            raise ChapterProjectionRolloutConflictError("projection_not_shadow_mode")
        sample_key = f"revision:{revision.revision}:reconcile:{reconcile_run.id}"
        existing = (
            (
                await self.session.execute(
                    select(ChapterProjectionShadowObservation).where(
                        ChapterProjectionShadowObservation.rollout_id == rollout.id,
                        ChapterProjectionShadowObservation.sample_key == sample_key,
                    )
                )
            )
            .scalars()
            .first()
        )
        if existing is not None:
            return existing

        legacy_job = (
            await self.session.get(BackgroundTask, revision.legacy_job_id)
            if revision.legacy_job_id is not None
            else None
        )
        if legacy_job is not None and legacy_job.status in NONTERMINAL_JOB_STATUSES:
            raise ChapterProjectionObservationPendingError("legacy_owner_job_not_terminal")

        runs = list(
            (
                await self.session.execute(
                    select(ChapterProjectionRun)
                    .where(ChapterProjectionRun.chapter_revision_id == revision.id)
                    .order_by(
                        ChapterProjectionRun.updated_at,
                        ChapterProjectionRun.id,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        by_name = {run.projection_name: run for run in runs}
        required = set(revision.required_projections or [])
        violations: list[str] = []
        if (
            legacy_job is None
            or legacy_job.status != "succeeded"
            or not isinstance(legacy_job.result, dict)
            or legacy_job.result.get("status") != "applied"
        ):
            violations.append("legacy_owner_job_not_succeeded")

        for name in sorted(required):
            run = by_name.get(name)
            if run is None or run.status != "succeeded":
                violations.append(f"required_projection_not_succeeded:{name}")
            elif run.is_active:
                violations.append(f"shadow_projection_became_active:{name}")

        summary_run = by_name.get("summary")
        summary_value = (
            (summary_run.result or {}).get("summary") if summary_run is not None else None
        )
        if not summary_value:
            violations.append("shadow_summary_missing")

        memory_run = by_name.get("memory")
        staged_snapshot = None
        if memory_run is not None:
            staged_snapshot = (
                (
                    await self.session.execute(
                        select(ChapterSnapshot).where(
                            ChapterSnapshot.project_id == chapter.project_id,
                            ChapterSnapshot.chapter_number == chapter.chapter_number,
                            ChapterSnapshot.chapter_revision == revision.revision,
                            ChapterSnapshot.artifact_generation == memory_run.artifact_generation,
                            ChapterSnapshot.projection_run_id == memory_run.id,
                        )
                    )
                )
                .scalars()
                .first()
            )
        if staged_snapshot is None:
            violations.append("shadow_memory_snapshot_missing")
        elif staged_snapshot.is_active:
            violations.append("shadow_memory_snapshot_became_active")

        rag_run = by_name.get("rag")
        rag_chunk_count = 0
        rag_summary_count = 0
        if "rag" in required and rag_run is not None:
            rag_chunk_count = int(
                await self.session.scalar(
                    select(func.count(RagChunk.id)).where(
                        RagChunk.project_id == chapter.project_id,
                        RagChunk.chapter_number == chapter.chapter_number,
                        RagChunk.source_revision == revision.revision,
                        RagChunk.artifact_generation == rag_run.artifact_generation,
                        RagChunk.projection_run_id == rag_run.id,
                        RagChunk.is_active.is_(False),
                    )
                )
                or 0
            )
            rag_summary_count = int(
                await self.session.scalar(
                    select(func.count(RagSummary.id)).where(
                        RagSummary.project_id == chapter.project_id,
                        RagSummary.chapter_number == chapter.chapter_number,
                        RagSummary.source_revision == revision.revision,
                        RagSummary.artifact_generation == rag_run.artifact_generation,
                        RagSummary.projection_run_id == rag_run.id,
                        RagSummary.is_active.is_(False),
                    )
                )
                or 0
            )
            if rag_chunk_count == 0:
                violations.append("shadow_rag_chunks_missing")

        foreshadowing_run = by_name.get("foreshadowing")
        plan_payload = (
            (foreshadowing_run.result or {}).get("plan") if foreshadowing_run is not None else None
        )
        expected_candidates = (
            len(plan_payload.get("candidates") or []) if isinstance(plan_payload, dict) else 0
        )
        staged_candidates = 0
        if foreshadowing_run is not None:
            staged_candidates = int(
                await self.session.scalar(
                    select(func.count(Foreshadowing.id)).where(
                        Foreshadowing.project_id == chapter.project_id,
                        Foreshadowing.chapter_id == chapter.id,
                        Foreshadowing.chapter_revision == revision.revision,
                        Foreshadowing.artifact_generation == foreshadowing_run.artifact_generation,
                        Foreshadowing.projection_run_id == foreshadowing_run.id,
                        Foreshadowing.is_active.is_(False),
                    )
                )
                or 0
            )
        if staged_candidates != expected_candidates:
            violations.append("shadow_foreshadowing_candidate_count_mismatch")

        legacy_snapshot = (
            (
                await self.session.execute(
                    select(ChapterSnapshot)
                    .where(
                        ChapterSnapshot.project_id == chapter.project_id,
                        ChapterSnapshot.chapter_number == chapter.chapter_number,
                        ChapterSnapshot.is_active.is_(True),
                    )
                    .order_by(ChapterSnapshot.id.desc())
                )
            )
            .scalars()
            .first()
        )
        safe_comparison = {
            "legacy": {
                "summary_digest": _value_digest(chapter.real_summary),
                "snapshot_present": legacy_snapshot is not None,
                "snapshot_digest": _value_digest(
                    {
                        "summary": legacy_snapshot.global_summary_snapshot,
                        "plot_arcs": legacy_snapshot.plot_arcs_snapshot,
                    }
                    if legacy_snapshot is not None
                    else None
                ),
            },
            "projection": {
                "summary_digest": _value_digest(summary_value),
                "snapshot_present": staged_snapshot is not None,
                "snapshot_digest": _value_digest(
                    {
                        "summary": staged_snapshot.global_summary_snapshot,
                        "plot_arcs": staged_snapshot.plot_arcs_snapshot,
                    }
                    if staged_snapshot is not None
                    else None
                ),
                "rag_chunk_count": rag_chunk_count,
                "rag_summary_count": rag_summary_count,
                "foreshadowing_candidate_count": staged_candidates,
            },
        }
        content_differences = [
            key
            for key in ("summary_digest", "snapshot_digest")
            if safe_comparison["legacy"].get(key) != safe_comparison["projection"].get(key)
        ]
        diff = {
            "unexplained_count": len(violations),
            "violations": violations,
            "content_difference_count": len(content_differences),
            "content_difference_fields": content_differences,
            "comparison": safe_comparison,
        }
        digest = _stable_digest(diff)
        outcome = "match" if not violations else "mismatch"
        observation = ChapterProjectionShadowObservation(
            id=str(uuid4()),
            rollout_id=rollout.id,
            aggregate_id=str(chapter.id),
            project_id=chapter.project_id,
            chapter_id=chapter.id,
            projection_run_id=reconcile_run.id,
            revision=revision.revision,
            rollout_generation=rollout.generation,
            sample_key=sample_key,
            outcome=outcome,
            digest=digest,
            diff=diff,
        )
        self.session.add(observation)
        rollout.shadow_digest = digest
        rollout.shadow_diff = diff
        rollout.last_observed_at = datetime.now(timezone.utc)
        if outcome == "match":
            rollout.successful_observations += 1
            revision.lifecycle = "shadow_ready"
        else:
            rollout.failed_observations += 1
            revision.lifecycle = "shadow_mismatch"
        return observation

    async def _load_chapter_rollout(
        self,
        *,
        project_id: str,
        chapter_id: int,
        for_update: bool,
    ) -> tuple[Chapter, ChapterProjectionRollout]:
        chapter_stmt = select(Chapter).where(
            Chapter.id == chapter_id,
            Chapter.project_id == project_id,
        )
        if for_update:
            chapter_stmt = chapter_stmt.with_for_update()
        chapter = (await self.session.execute(chapter_stmt)).scalars().first()
        if chapter is None:
            raise ChapterProjectionRolloutNotFoundError("chapter_rollout_not_found")
        rollout_stmt = select(ChapterProjectionRollout).where(
            ChapterProjectionRollout.chapter_id == chapter.id,
            ChapterProjectionRollout.project_id == chapter.project_id,
        )
        if for_update:
            rollout_stmt = rollout_stmt.with_for_update()
        rollout = (await self.session.execute(rollout_stmt)).scalars().first()
        if rollout is None:
            raise ChapterProjectionRolloutNotFoundError("chapter_rollout_not_found")
        validate_rollout_owner_state(rollout.owner, rollout.state)
        return chapter, rollout

    async def _load_or_create_legacy_rollout(
        self,
        *,
        project_id: str,
        chapter_id: int,
        operator_user_id: int,
    ) -> tuple[Chapter, ChapterProjectionRollout]:
        chapter = (
            (
                await self.session.execute(
                    select(Chapter)
                    .where(Chapter.id == chapter_id, Chapter.project_id == project_id)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if chapter is None:
            raise ChapterProjectionRolloutNotFoundError("chapter_not_found")
        rollout = (
            (
                await self.session.execute(
                    select(ChapterProjectionRollout)
                    .where(ChapterProjectionRollout.chapter_id == chapter.id)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if rollout is not None:
            validate_rollout_owner_state(rollout.owner, rollout.state)
            return chapter, rollout
        rollout = ChapterProjectionRollout(
            id=str(uuid4()),
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            owner="legacy",
            state="legacy",
            generation=1,
            fencing_token=0,
            transition_sequence=0,
        )
        self.session.add(rollout)
        await self._append_transition(
            rollout=rollout,
            chapter=chapter,
            from_owner=None,
            from_state=None,
            operator_user_id=operator_user_id,
            reason="initialize legacy rollout",
            details={},
        )
        return chapter, rollout

    @staticmethod
    def _require_cas(
        rollout: ChapterProjectionRollout,
        *,
        expected_generation: int,
        expected_fencing_token: int,
    ) -> None:
        if (
            rollout.generation != expected_generation
            or rollout.fencing_token != expected_fencing_token
        ):
            raise ChapterProjectionRolloutConflictError("rollout_cas_mismatch")

    async def _append_transition(
        self,
        *,
        rollout: ChapterProjectionRollout,
        chapter: Chapter,
        from_owner: Optional[str],
        from_state: Optional[str],
        operator_user_id: Optional[int],
        reason: str,
        details: dict[str, Any],
    ) -> None:
        validate_rollout_owner_state(rollout.owner, rollout.state)
        rollout.transition_sequence += 1
        self.session.add(
            ChapterProjectionRolloutTransition(
                id=str(uuid4()),
                rollout_id=rollout.id,
                aggregate_id=str(chapter.id),
                project_id=chapter.project_id,
                chapter_id=chapter.id,
                sequence=rollout.transition_sequence,
                from_owner=from_owner,
                to_owner=rollout.owner,
                from_state=from_state,
                to_state=rollout.state,
                generation=rollout.generation,
                fencing_token=rollout.fencing_token,
                operator_user_id=operator_user_id,
                reason=reason,
                details=details,
            )
        )
        await self.session.flush()

    async def _latest_observation(
        self,
        rollout_id: str,
        *,
        for_update: bool = False,
    ) -> Optional[ChapterProjectionShadowObservation]:
        stmt = (
            select(ChapterProjectionShadowObservation)
            .where(ChapterProjectionShadowObservation.rollout_id == rollout_id)
            .order_by(
                ChapterProjectionShadowObservation.created_at.desc(),
                ChapterProjectionShadowObservation.id.desc(),
            )
            .limit(1)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return (await self.session.execute(stmt)).scalars().first()

    async def _has_nonterminal_chapter_jobs(self, chapter: Chapter) -> bool:
        # Worker outcome transactions lock BackgroundTask before Chapter. A read is
        # sufficient here and avoids the inverse Chapter -> BackgroundTask lock order.
        jobs = list(
            (
                await self.session.execute(
                    select(BackgroundTask).where(
                        BackgroundTask.project_id == chapter.project_id,
                        BackgroundTask.status.in_(NONTERMINAL_JOB_STATUSES),
                        or_(
                            BackgroundTask.task_type == "chapter_finalize",
                            BackgroundTask.task_type.like("chapter_projection_%"),
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )
        for job in jobs:
            payload = job.payload if isinstance(job.payload, dict) else {}
            if payload.get("chapter_id") == chapter.id or (
                payload.get("project_id") == chapter.project_id
                and payload.get("chapter_number") == chapter.chapter_number
            ):
                return True
        return False

    async def _promote_shadow_artifacts(
        self,
        *,
        chapter: Chapter,
        rollout: ChapterProjectionRollout,
    ) -> dict[str, Any]:
        revision = (
            (
                await self.session.execute(
                    select(ChapterRevision)
                    .where(
                        ChapterRevision.chapter_id == chapter.id,
                        ChapterRevision.revision == chapter.current_revision,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if revision is None or revision.lifecycle != "shadow_ready":
            raise ChapterProjectionRolloutConflictError("shadow_revision_not_ready")
        runs = list(
            (
                await self.session.execute(
                    select(ChapterProjectionRun)
                    .where(ChapterProjectionRun.chapter_revision_id == revision.id)
                    .order_by(
                        ChapterProjectionRun.updated_at,
                        ChapterProjectionRun.id,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        by_name = {run.projection_name: run for run in runs}
        required = set(revision.required_projections or [])
        if any(
            by_name.get(name) is None
            or by_name[name].status != "succeeded"
            or by_name[name].is_active
            for name in required
        ):
            raise ChapterProjectionRolloutConflictError("shadow_required_projection_not_ready")
        promoted_runs = [run for run in by_name.values() if run.status in {"succeeded", "skipped"}]

        summary_run = by_name.get("summary")
        memory_run = by_name.get("memory")
        rag_run = by_name.get("rag")
        foreshadowing_run = by_name.get("foreshadowing")
        if summary_run is None or memory_run is None or foreshadowing_run is None:
            raise ChapterProjectionRolloutConflictError("shadow_projection_manifest_incomplete")
        summary = str((summary_run.result or {}).get("summary") or "").strip()
        if not summary:
            raise ChapterProjectionRolloutConflictError("shadow_summary_missing")

        staged_snapshot = (
            (
                await self.session.execute(
                    select(ChapterSnapshot)
                    .where(
                        ChapterSnapshot.project_id == chapter.project_id,
                        ChapterSnapshot.chapter_number == chapter.chapter_number,
                        ChapterSnapshot.chapter_revision == revision.revision,
                        ChapterSnapshot.artifact_generation == memory_run.artifact_generation,
                        ChapterSnapshot.projection_run_id == memory_run.id,
                        ChapterSnapshot.is_active.is_(False),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if staged_snapshot is None:
            raise ChapterProjectionRolloutConflictError("shadow_memory_snapshot_missing")
        legacy_snapshot = (
            (
                await self.session.execute(
                    select(ChapterSnapshot)
                    .where(
                        ChapterSnapshot.project_id == chapter.project_id,
                        ChapterSnapshot.chapter_number == chapter.chapter_number,
                        ChapterSnapshot.is_active.is_(True),
                        ChapterSnapshot.id != staged_snapshot.id,
                    )
                    .order_by(ChapterSnapshot.id.desc())
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if legacy_snapshot is None:
            raise ChapterProjectionRolloutConflictError("legacy_memory_snapshot_missing")

        memory = (
            (
                await self.session.execute(
                    select(ProjectMemory)
                    .where(ProjectMemory.project_id == chapter.project_id)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if memory is None:
            raise ChapterProjectionRolloutConflictError("project_memory_missing")
        if int(memory.last_updated_chapter or 0) > chapter.chapter_number:
            raise ChapterProjectionRolloutConflictError("project_memory_advanced")

        staged_character_ids = list(
            (
                await self.session.scalars(
                    select(CharacterState.id)
                    .where(
                        CharacterState.project_id == chapter.project_id,
                        CharacterState.chapter_number == chapter.chapter_number,
                        CharacterState.chapter_revision == revision.revision,
                        CharacterState.artifact_generation == memory_run.artifact_generation,
                        CharacterState.projection_run_id == memory_run.id,
                        CharacterState.is_active.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )

        legacy_character_rows = list(
            (
                await self.session.execute(
                    select(CharacterState)
                    .where(
                        CharacterState.project_id == chapter.project_id,
                        CharacterState.chapter_number == chapter.chapter_number,
                        CharacterState.is_active.is_(True),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        legacy_character_ids = [item.id for item in legacy_character_rows]
        legacy_rag_chunk_rows = list(
            (
                await self.session.execute(
                    select(RagChunk)
                    .where(
                        RagChunk.project_id == chapter.project_id,
                        RagChunk.chapter_number == chapter.chapter_number,
                        RagChunk.is_active.is_(True),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        legacy_rag_chunk_ids = [item.id for item in legacy_rag_chunk_rows]
        legacy_rag_summary_rows = list(
            (
                await self.session.execute(
                    select(RagSummary)
                    .where(
                        RagSummary.project_id == chapter.project_id,
                        RagSummary.chapter_number == chapter.chapter_number,
                        RagSummary.is_active.is_(True),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        legacy_rag_summary_ids = [item.id for item in legacy_rag_summary_rows]
        legacy_foreshadowing_rows = list(
            (
                await self.session.execute(
                    select(Foreshadowing)
                    .where(
                        Foreshadowing.project_id == chapter.project_id,
                        Foreshadowing.chapter_id == chapter.id,
                        Foreshadowing.is_manual.is_(False),
                        Foreshadowing.is_active.is_(True),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        legacy_foreshadowing_ids = [item.id for item in legacy_foreshadowing_rows]
        staged_rag_chunk_ids: list[str] = []
        staged_rag_summary_ids: list[str] = []
        if rag_run is not None and rag_run.status == "succeeded":
            staged_rag_chunk_ids = list(
                (
                    await self.session.scalars(
                        select(RagChunk.id)
                        .where(
                            RagChunk.project_id == chapter.project_id,
                            RagChunk.chapter_number == chapter.chapter_number,
                            RagChunk.source_revision == revision.revision,
                            RagChunk.artifact_generation == rag_run.artifact_generation,
                            RagChunk.projection_run_id == rag_run.id,
                            RagChunk.is_active.is_(False),
                        )
                        .with_for_update()
                    )
                ).all()
            )
            staged_rag_summary_ids = list(
                (
                    await self.session.scalars(
                        select(RagSummary.id)
                        .where(
                            RagSummary.project_id == chapter.project_id,
                            RagSummary.chapter_number == chapter.chapter_number,
                            RagSummary.source_revision == revision.revision,
                            RagSummary.artifact_generation == rag_run.artifact_generation,
                            RagSummary.projection_run_id == rag_run.id,
                            RagSummary.is_active.is_(False),
                        )
                        .with_for_update()
                    )
                ).all()
            )

        plan_payload = (foreshadowing_run.result or {}).get("plan")
        if not isinstance(plan_payload, dict):
            raise ChapterProjectionRolloutConflictError("shadow_foreshadowing_plan_missing")
        plan = deserialize_foreshadowing_plan(plan_payload)
        staged_foreshadowing_ids = list(
            (
                await self.session.scalars(
                    select(Foreshadowing.id)
                    .where(
                        Foreshadowing.project_id == chapter.project_id,
                        Foreshadowing.chapter_id == chapter.id,
                        Foreshadowing.chapter_revision == revision.revision,
                        Foreshadowing.artifact_generation == foreshadowing_run.artifact_generation,
                        Foreshadowing.projection_run_id == foreshadowing_run.id,
                        Foreshadowing.is_active.is_(False),
                    )
                    .with_for_update()
                )
            ).all()
        )
        if len(staged_foreshadowing_ids) != len(plan.candidates):
            raise ChapterProjectionRolloutConflictError(
                "shadow_foreshadowing_candidate_count_mismatch"
            )
        source_ids = [item.id for item in plan.active]
        source_rows = []
        if source_ids:
            source_rows = list(
                (
                    await self.session.execute(
                        select(Foreshadowing)
                        .where(
                            Foreshadowing.project_id == chapter.project_id,
                            Foreshadowing.id.in_(source_ids),
                            Foreshadowing.is_active.is_(True),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
        source_by_id = {item.id: item for item in source_rows}
        if any(
            source_by_id.get(item.id) is None or source_by_id[item.id].status != item.status
            for item in plan.active
        ):
            raise ChapterProjectionRolloutConflictError("foreshadowing_source_changed")
        foreshadowing_states = []
        for item in source_rows:
            decision = plan.status_decisions.get(item.id, "unchanged")
            expected_status = item.status
            expected_resolved_chapter_id = item.resolved_chapter_id
            expected_resolved_chapter_number = item.resolved_chapter_number
            if decision == "revealed":
                expected_status = "revealed"
                expected_resolved_chapter_id = chapter.id
                expected_resolved_chapter_number = chapter.chapter_number
            elif item.status == "planted" and decision == "developing":
                expected_status = "developing"
            foreshadowing_states.append(
                {
                    "id": item.id,
                    "project_id": item.project_id,
                    "chapter_id": item.chapter_id,
                    "chapter_number": item.chapter_number,
                    "chapter_revision": item.chapter_revision,
                    "artifact_generation": item.artifact_generation,
                    "projection_run_id": item.projection_run_id,
                    "is_manual": item.is_manual,
                    "status": item.status,
                    "resolved_chapter_id": item.resolved_chapter_id,
                    "resolved_chapter_number": item.resolved_chapter_number,
                    "expected_status": expected_status,
                    "expected_resolved_chapter_id": expected_resolved_chapter_id,
                    "expected_resolved_chapter_number": expected_resolved_chapter_number,
                }
            )

        blueprint = (
            (
                await self.session.execute(
                    select(ChapterBlueprint)
                    .where(
                        ChapterBlueprint.project_id == chapter.project_id,
                        ChapterBlueprint.chapter_number == chapter.chapter_number,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )

        manifest = {
            "revision": revision.revision,
            "projection_rollout_generation": rollout.generation + 1,
            "previous_real_summary": chapter.real_summary,
            "promoted_real_summary": summary,
            "chapter_state": {
                "status": chapter.status,
                "generation_progress": chapter.generation_progress,
                "generation_step": chapter.generation_step,
                "generation_step_index": chapter.generation_step_index,
                "generation_step_total": chapter.generation_step_total,
            },
            "promoted_chapter_state": {
                "status": "successful",
                "generation_progress": 100,
                "generation_step": "finalized",
                "generation_step_index": 4,
                "generation_step_total": 4,
            },
            "revision_lifecycle": revision.lifecycle,
            "blueprint_state": (
                {"id": blueprint.id, "is_finalized": blueprint.is_finalized}
                if blueprint is not None
                else None
            ),
            "project_memory_state": {
                "global_summary": memory.global_summary,
                "plot_arcs": memory.plot_arcs,
                "last_updated_chapter": memory.last_updated_chapter,
                "projection_revision": memory.projection_revision,
                "projection_generation": memory.projection_generation,
            },
            "promoted_project_memory_state": {
                "global_summary": staged_snapshot.global_summary_snapshot or "",
                "plot_arcs": staged_snapshot.plot_arcs_snapshot or {},
                "last_updated_chapter": chapter.chapter_number,
                "projection_revision": revision.revision,
                "projection_generation": memory_run.artifact_generation,
            },
            "legacy_snapshot_id": legacy_snapshot.id,
            "legacy_snapshot_identity": {
                "project_id": legacy_snapshot.project_id,
                "chapter_number": legacy_snapshot.chapter_number,
                "chapter_revision": legacy_snapshot.chapter_revision,
                "artifact_generation": legacy_snapshot.artifact_generation,
            },
            "promoted_snapshot_id": staged_snapshot.id,
            "legacy_character_state_ids": legacy_character_ids,
            "legacy_character_state_identities": [
                {
                    "id": item.id,
                    "chapter_revision": item.chapter_revision,
                    "artifact_generation": item.artifact_generation,
                    "projection_run_id": item.projection_run_id,
                }
                for item in legacy_character_rows
            ],
            "promoted_character_state_ids": staged_character_ids,
            "legacy_rag_chunk_ids": legacy_rag_chunk_ids,
            "legacy_rag_chunk_identities": [
                {
                    "id": item.id,
                    "source_revision": item.source_revision,
                    "artifact_generation": item.artifact_generation,
                    "projection_run_id": item.projection_run_id,
                }
                for item in legacy_rag_chunk_rows
            ],
            "legacy_rag_summary_ids": legacy_rag_summary_ids,
            "legacy_rag_summary_identities": [
                {
                    "id": item.id,
                    "source_revision": item.source_revision,
                    "artifact_generation": item.artifact_generation,
                    "projection_run_id": item.projection_run_id,
                }
                for item in legacy_rag_summary_rows
            ],
            "promoted_rag_chunk_ids": staged_rag_chunk_ids,
            "promoted_rag_summary_ids": staged_rag_summary_ids,
            "legacy_foreshadowing_ids": legacy_foreshadowing_ids,
            "legacy_foreshadowing_identities": [
                {
                    "id": item.id,
                    "chapter_id": item.chapter_id,
                    "chapter_number": item.chapter_number,
                    "chapter_revision": item.chapter_revision,
                    "artifact_generation": item.artifact_generation,
                    "projection_run_id": item.projection_run_id,
                    "is_manual": item.is_manual,
                }
                for item in legacy_foreshadowing_rows
            ],
            "promoted_foreshadowing_ids": staged_foreshadowing_ids,
            "foreshadowing_states": foreshadowing_states,
            "projection_run_ids": [run.id for run in by_name.values()],
            "promoted_projection_run_ids": [run.id for run in promoted_runs],
            "previous_active_projection_run_ids": [run.id for run in runs if run.is_active],
            "projection_run_ids_by_name": {name: run.id for name, run in by_name.items()},
            "projection_generations": {
                name: run.artifact_generation for name, run in by_name.items()
            },
        }

        if set(manifest["promoted_projection_run_ids"]) & set(
            manifest["previous_active_projection_run_ids"]
        ):
            raise ChapterProjectionRolloutConflictError("shadow_projection_owner_overlap")

        chapter.real_summary = summary
        await self.session.execute(
            update(ChapterSnapshot)
            .where(
                ChapterSnapshot.project_id == chapter.project_id,
                ChapterSnapshot.chapter_number == chapter.chapter_number,
                ChapterSnapshot.is_active.is_(True),
            )
            .values(is_active=False)
        )
        staged_snapshot.is_active = True
        await self.session.execute(
            update(CharacterState)
            .where(
                CharacterState.project_id == chapter.project_id,
                CharacterState.chapter_number == chapter.chapter_number,
                CharacterState.is_active.is_(True),
            )
            .values(is_active=False)
        )
        await self.session.execute(
            update(CharacterState)
            .where(
                CharacterState.project_id == chapter.project_id,
                CharacterState.chapter_number == chapter.chapter_number,
                CharacterState.chapter_revision == revision.revision,
                CharacterState.artifact_generation == memory_run.artifact_generation,
                CharacterState.projection_run_id == memory_run.id,
            )
            .values(is_active=True)
        )
        memory.global_summary = staged_snapshot.global_summary_snapshot or ""
        memory.plot_arcs = staged_snapshot.plot_arcs_snapshot or {}
        memory.last_updated_chapter = chapter.chapter_number
        memory.projection_revision = revision.revision
        memory.projection_generation = memory_run.artifact_generation
        memory.version = int(memory.version or 0) + 1
        if blueprint is not None:
            blueprint.is_finalized = True

        if rag_run is not None and rag_run.status == "succeeded":
            await self.session.execute(
                update(RagChunk)
                .where(
                    RagChunk.project_id == chapter.project_id,
                    RagChunk.chapter_number == chapter.chapter_number,
                    RagChunk.is_active.is_(True),
                )
                .values(is_active=False)
            )
            await self.session.execute(
                update(RagSummary)
                .where(
                    RagSummary.project_id == chapter.project_id,
                    RagSummary.chapter_number == chapter.chapter_number,
                    RagSummary.is_active.is_(True),
                )
                .values(is_active=False)
            )
            await self.session.execute(
                update(RagChunk)
                .where(
                    RagChunk.project_id == chapter.project_id,
                    RagChunk.chapter_number == chapter.chapter_number,
                    RagChunk.source_revision == revision.revision,
                    RagChunk.artifact_generation == rag_run.artifact_generation,
                    RagChunk.projection_run_id == rag_run.id,
                )
                .values(is_active=True)
            )
            await self.session.execute(
                update(RagSummary)
                .where(
                    RagSummary.project_id == chapter.project_id,
                    RagSummary.chapter_number == chapter.chapter_number,
                    RagSummary.source_revision == revision.revision,
                    RagSummary.artifact_generation == rag_run.artifact_generation,
                    RagSummary.projection_run_id == rag_run.id,
                )
                .values(is_active=True)
            )

        await ForeshadowingSyncService(self.session).promote_staged_plan(
            project_id=chapter.project_id,
            chapter=chapter,
            plan_payload=plan_payload,
            chapter_revision=revision.revision,
            artifact_generation=foreshadowing_run.artifact_generation,
            projection_run_id=foreshadowing_run.id,
        )
        await self.session.execute(
            update(ChapterProjectionRun)
            .where(
                ChapterProjectionRun.chapter_id == chapter.id,
                ChapterProjectionRun.revision == revision.revision,
                ChapterProjectionRun.is_active.is_(True),
            )
            .values(is_active=False)
        )
        for run in promoted_runs:
            run.is_active = True
        chapter.status = "successful"
        chapter.generation_progress = 100
        chapter.generation_step = "finalized"
        chapter.generation_step_index = 4
        chapter.generation_step_total = 4
        revision.lifecycle = "successful"
        return manifest

    @staticmethod
    def _manifest_ids(
        manifest: dict[str, Any],
        key: str,
        expected_type: type,
    ) -> list[Any]:
        values = manifest.get(key)
        if not isinstance(values, list) or any(
            type(value) is not expected_type for value in values
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        if len(values) != len(set(values)):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        return values

    @staticmethod
    def _manifest_mapping(
        value: Any,
        fields: dict[str, tuple[type, ...]],
    ) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        for key, allowed_types in fields.items():
            if key not in value or not any(
                type(value[key]) is allowed_type for allowed_type in allowed_types
            ):
                raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        return value

    @classmethod
    def _manifest_identities(
        cls,
        manifest: dict[str, Any],
        key: str,
        fields: dict[str, tuple[type, ...]],
    ) -> dict[Any, dict[str, Any]]:
        values = manifest.get(key)
        if not isinstance(values, list):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        identities = [cls._manifest_mapping(value, fields) for value in values]
        ids = [identity["id"] for identity in identities]
        if len(ids) != len(set(ids)):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        return {identity["id"]: identity for identity in identities}

    @staticmethod
    def _require_exact_ids(
        actual: list[Any],
        expected: list[Any],
        error_code: str,
    ) -> None:
        if len(actual) != len(expected) or set(actual) != set(expected):
            raise ChapterProjectionRolloutConflictError(error_code)

    async def _restore_legacy_artifacts(
        self,
        *,
        chapter: Chapter,
        rollout: ChapterProjectionRollout,
    ) -> None:
        manifest = rollout.rollback_manifest
        if not isinstance(manifest, dict):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_missing")
        none_type = type(None)
        self._manifest_mapping(
            manifest,
            {
                "revision": (int,),
                "projection_rollout_generation": (int,),
                "previous_real_summary": (str, none_type),
                "promoted_real_summary": (str,),
                "revision_lifecycle": (str,),
                "legacy_snapshot_id": (int,),
                "promoted_snapshot_id": (int,),
            },
        )
        if (
            manifest["revision"] != int(chapter.current_revision or 0)
            or manifest["projection_rollout_generation"] != rollout.generation
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_stale")

        generations = manifest.get("projection_generations")
        run_ids_by_name = manifest.get("projection_run_ids_by_name")
        if (
            not isinstance(generations, dict)
            or not isinstance(run_ids_by_name, dict)
            or not generations
            or set(generations) != set(run_ids_by_name)
            or any(
                type(name) is not str or type(value) is not str
                for name, value in generations.items()
            )
            or any(
                type(name) is not str or type(value) is not str
                for name, value in run_ids_by_name.items()
            )
            or len(run_ids_by_name.values()) != len(set(run_ids_by_name.values()))
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        chapter_fields = {
            "status": (str,),
            "generation_progress": (int,),
            "generation_step": (str, none_type),
            "generation_step_index": (int,),
            "generation_step_total": (int,),
        }
        chapter_state = self._manifest_mapping(manifest.get("chapter_state"), chapter_fields)
        promoted_chapter_state = self._manifest_mapping(
            manifest.get("promoted_chapter_state"), chapter_fields
        )
        memory_fields = {
            "global_summary": (str, none_type),
            "plot_arcs": (dict, none_type),
            "last_updated_chapter": (int,),
            "projection_revision": (int,),
            "projection_generation": (str, none_type),
        }
        memory_state = self._manifest_mapping(manifest.get("project_memory_state"), memory_fields)
        promoted_memory_state = self._manifest_mapping(
            manifest.get("promoted_project_memory_state"), memory_fields
        )
        legacy_snapshot_identity = self._manifest_mapping(
            manifest.get("legacy_snapshot_identity"),
            {
                "project_id": (str,),
                "chapter_number": (int,),
                "chapter_revision": (int,),
                "artifact_generation": (str,),
            },
        )
        blueprint_state = manifest.get("blueprint_state")
        if blueprint_state is not None:
            blueprint_state = self._manifest_mapping(
                blueprint_state,
                {"id": (int,), "is_finalized": (bool,)},
            )

        memory_generation = generations.get("memory")
        memory_run_id = run_ids_by_name.get("memory")
        foreshadowing_generation = generations.get("foreshadowing")
        foreshadowing_run_id = run_ids_by_name.get("foreshadowing")
        if not all(
            isinstance(value, str)
            for value in (
                memory_generation,
                memory_run_id,
                foreshadowing_generation,
                foreshadowing_run_id,
            )
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        legacy_character_ids = self._manifest_ids(manifest, "legacy_character_state_ids", int)
        promoted_character_ids = self._manifest_ids(manifest, "promoted_character_state_ids", int)
        legacy_chunk_ids = self._manifest_ids(manifest, "legacy_rag_chunk_ids", str)
        legacy_summary_ids = self._manifest_ids(manifest, "legacy_rag_summary_ids", str)
        promoted_chunk_ids = self._manifest_ids(manifest, "promoted_rag_chunk_ids", str)
        promoted_summary_ids = self._manifest_ids(manifest, "promoted_rag_summary_ids", str)
        legacy_foreshadowing_ids = self._manifest_ids(manifest, "legacy_foreshadowing_ids", int)
        promoted_foreshadowing_ids = self._manifest_ids(manifest, "promoted_foreshadowing_ids", int)
        promoted_run_ids = self._manifest_ids(manifest, "promoted_projection_run_ids", str)
        previous_active_run_ids = self._manifest_ids(
            manifest, "previous_active_projection_run_ids", str
        )

        projection_run_ids = self._manifest_ids(manifest, "projection_run_ids", str)
        if (
            set(projection_run_ids) != set(run_ids_by_name.values())
            or not set(promoted_run_ids).issubset(projection_run_ids)
            or set(promoted_run_ids) & set(previous_active_run_ids)
            or set(legacy_character_ids) & set(promoted_character_ids)
            or set(legacy_chunk_ids) & set(promoted_chunk_ids)
            or set(legacy_summary_ids) & set(promoted_summary_ids)
            or set(legacy_foreshadowing_ids) & set(promoted_foreshadowing_ids)
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        legacy_character_identities = self._manifest_identities(
            manifest,
            "legacy_character_state_identities",
            {
                "id": (int,),
                "chapter_revision": (int,),
                "artifact_generation": (str,),
                "projection_run_id": (str, none_type),
            },
        )
        legacy_chunk_identities = self._manifest_identities(
            manifest,
            "legacy_rag_chunk_identities",
            {
                "id": (str,),
                "source_revision": (int,),
                "artifact_generation": (str,),
                "projection_run_id": (str, none_type),
            },
        )
        legacy_summary_identities = self._manifest_identities(
            manifest,
            "legacy_rag_summary_identities",
            {
                "id": (str,),
                "source_revision": (int,),
                "artifact_generation": (str,),
                "projection_run_id": (str, none_type),
            },
        )
        legacy_foreshadowing_identities = self._manifest_identities(
            manifest,
            "legacy_foreshadowing_identities",
            {
                "id": (int,),
                "chapter_id": (int, none_type),
                "chapter_number": (int,),
                "chapter_revision": (int,),
                "artifact_generation": (str,),
                "projection_run_id": (str, none_type),
                "is_manual": (bool,),
            },
        )
        if (
            set(legacy_character_ids) != set(legacy_character_identities)
            or set(legacy_chunk_ids) != set(legacy_chunk_identities)
            or set(legacy_summary_ids) != set(legacy_summary_identities)
            or set(legacy_foreshadowing_ids) != set(legacy_foreshadowing_identities)
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        states = manifest.get("foreshadowing_states")
        if not isinstance(states, list):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        state_fields = {
            "id": (int,),
            "project_id": (str,),
            "chapter_id": (int, none_type),
            "chapter_number": (int,),
            "chapter_revision": (int,),
            "artifact_generation": (str,),
            "projection_run_id": (str, none_type),
            "is_manual": (bool,),
            "status": (str,),
            "resolved_chapter_id": (int, none_type),
            "resolved_chapter_number": (int, none_type),
            "expected_status": (str,),
            "expected_resolved_chapter_id": (int, none_type),
            "expected_resolved_chapter_number": (int, none_type),
        }
        states = [self._manifest_mapping(item, state_fields) for item in states]
        state_ids = [item["id"] for item in states]
        if len(state_ids) != len(set(state_ids)):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        if (
            manifest["revision_lifecycle"] != "shadow_ready"
            or not manifest["promoted_real_summary"].strip()
            or promoted_chapter_state
            != {
                "status": "successful",
                "generation_progress": 100,
                "generation_step": "finalized",
                "generation_step_index": 4,
                "generation_step_total": 4,
            }
            or promoted_memory_state["last_updated_chapter"] != chapter.chapter_number
            or promoted_memory_state["projection_revision"] != manifest["revision"]
            or promoted_memory_state["projection_generation"] != memory_generation
            or legacy_snapshot_identity["project_id"] != chapter.project_id
            or legacy_snapshot_identity["chapter_number"] != chapter.chapter_number
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        revision = (
            (
                await self.session.execute(
                    select(ChapterRevision)
                    .where(
                        ChapterRevision.chapter_id == chapter.id,
                        ChapterRevision.revision == chapter.current_revision,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if revision is None or revision.lifecycle != "successful":
            raise ChapterProjectionRolloutConflictError("rollback_revision_advanced")
        previous_lifecycle = manifest.get("revision_lifecycle")
        if not isinstance(previous_lifecycle, str):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        current_chapter_state = {
            "status": chapter.status,
            "generation_progress": chapter.generation_progress,
            "generation_step": chapter.generation_step,
            "generation_step_index": chapter.generation_step_index,
            "generation_step_total": chapter.generation_step_total,
        }
        if current_chapter_state != promoted_chapter_state or chapter.real_summary != manifest.get(
            "promoted_real_summary"
        ):
            raise ChapterProjectionRolloutConflictError("rollback_chapter_advanced")

        memory = (
            (
                await self.session.execute(
                    select(ProjectMemory)
                    .where(ProjectMemory.project_id == chapter.project_id)
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        current_memory_state = (
            {
                "global_summary": memory.global_summary,
                "plot_arcs": memory.plot_arcs,
                "last_updated_chapter": memory.last_updated_chapter,
                "projection_revision": memory.projection_revision,
                "projection_generation": memory.projection_generation,
            }
            if memory is not None
            else None
        )
        if memory is None or current_memory_state != promoted_memory_state:
            raise ChapterProjectionRolloutConflictError("rollback_memory_advanced")

        legacy_snapshot_id = manifest.get("legacy_snapshot_id")
        promoted_snapshot_id = manifest.get("promoted_snapshot_id")
        if type(legacy_snapshot_id) is not int or type(promoted_snapshot_id) is not int:
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        snapshots = list(
            (
                await self.session.execute(
                    select(ChapterSnapshot)
                    .where(ChapterSnapshot.id.in_([legacy_snapshot_id, promoted_snapshot_id]))
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        snapshots_by_id = {item.id: item for item in snapshots}
        legacy_snapshot = snapshots_by_id.get(legacy_snapshot_id)
        promoted_snapshot = snapshots_by_id.get(promoted_snapshot_id)
        if legacy_snapshot is None:
            raise ChapterProjectionRolloutConflictError("rollback_legacy_snapshot_missing")
        if (
            legacy_snapshot.project_id != legacy_snapshot_identity.get("project_id")
            or legacy_snapshot.project_id != chapter.project_id
            or legacy_snapshot.chapter_number != legacy_snapshot_identity.get("chapter_number")
            or legacy_snapshot.chapter_number != chapter.chapter_number
            or legacy_snapshot.chapter_revision != legacy_snapshot_identity.get("chapter_revision")
            or legacy_snapshot.artifact_generation
            != legacy_snapshot_identity.get("artifact_generation")
            or legacy_snapshot.is_active
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        if (
            promoted_snapshot is None
            or promoted_snapshot.project_id != chapter.project_id
            or promoted_snapshot.chapter_number != chapter.chapter_number
            or promoted_snapshot.chapter_revision != revision.revision
            or promoted_snapshot.artifact_generation != memory_generation
            or promoted_snapshot.projection_run_id != memory_run_id
            or not promoted_snapshot.is_active
        ):
            raise ChapterProjectionRolloutConflictError("rollback_projection_artifacts_advanced")

        blueprint = (
            (
                await self.session.execute(
                    select(ChapterBlueprint)
                    .where(
                        ChapterBlueprint.project_id == chapter.project_id,
                        ChapterBlueprint.chapter_number == chapter.chapter_number,
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .first()
        )
        if blueprint_state is None:
            if blueprint is not None:
                raise ChapterProjectionRolloutConflictError("rollback_blueprint_advanced")
        elif (
            not isinstance(blueprint_state, dict)
            or type(blueprint_state.get("id")) is not int
            or type(blueprint_state.get("is_finalized")) is not bool
            or blueprint is None
            or blueprint.id != blueprint_state["id"]
            or not blueprint.is_finalized
        ):
            raise ChapterProjectionRolloutConflictError("rollback_blueprint_advanced")

        all_run_ids = sorted(set(projection_run_ids + previous_active_run_ids))
        runs = (
            list(
                (
                    await self.session.execute(
                        select(ChapterProjectionRun)
                        .where(
                            ChapterProjectionRun.id.in_(all_run_ids),
                            ChapterProjectionRun.chapter_id == chapter.id,
                            ChapterProjectionRun.revision == revision.revision,
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if all_run_ids
            else []
        )
        self._require_exact_ids(
            [run.id for run in runs],
            all_run_ids,
            "rollback_projection_runs_advanced",
        )
        promoted_run_id_set = set(promoted_run_ids)
        previous_run_id_set = set(previous_active_run_ids)
        runs_by_id = {run.id: run for run in runs}
        if any(run.is_active != (run.id in promoted_run_id_set) for run in runs):
            raise ChapterProjectionRolloutConflictError("rollback_projection_runs_advanced")
        if any(
            runs_by_id[run_id].projection_name != projection_name
            or runs_by_id[run_id].artifact_generation != generations[projection_name]
            for projection_name, run_id in run_ids_by_name.items()
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        foreshadowing_run = runs_by_id.get(foreshadowing_run_id)
        plan_payload = (
            (foreshadowing_run.result or {}).get("plan") if foreshadowing_run is not None else None
        )
        if not isinstance(plan_payload, dict):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        try:
            plan = deserialize_foreshadowing_plan(plan_payload)
        except (TypeError, ValueError, KeyError) as exc:
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid") from exc
        if set(state_ids) != {item.id for item in plan.active}:
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        promoted_character_rows = list(
            (
                await self.session.execute(
                    select(CharacterState)
                    .where(
                        CharacterState.project_id == chapter.project_id,
                        CharacterState.chapter_number == chapter.chapter_number,
                        CharacterState.chapter_revision == revision.revision,
                        CharacterState.artifact_generation == memory_generation,
                        CharacterState.projection_run_id == memory_run_id,
                        CharacterState.is_active.is_(True),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        self._require_exact_ids(
            [item.id for item in promoted_character_rows],
            promoted_character_ids,
            "rollback_projection_artifacts_advanced",
        )
        legacy_character_rows = (
            list(
                (
                    await self.session.execute(
                        select(CharacterState)
                        .where(
                            CharacterState.id.in_(legacy_character_ids),
                            CharacterState.project_id == chapter.project_id,
                            CharacterState.chapter_number == chapter.chapter_number,
                            CharacterState.is_active.is_(False),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if legacy_character_ids
            else []
        )
        self._require_exact_ids(
            [item.id for item in legacy_character_rows],
            legacy_character_ids,
            "rollback_manifest_invalid",
        )
        if any(
            item.chapter_revision != legacy_character_identities[item.id]["chapter_revision"]
            or item.artifact_generation
            != legacy_character_identities[item.id]["artifact_generation"]
            or item.projection_run_id != legacy_character_identities[item.id]["projection_run_id"]
            for item in legacy_character_rows
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        rag_generation = generations.get("rag")
        rag_run_id = run_ids_by_name.get("rag")
        if (promoted_chunk_ids or promoted_summary_ids) and (
            not isinstance(rag_generation, str) or not isinstance(rag_run_id, str)
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        promoted_chunk_rows = (
            list(
                (
                    await self.session.execute(
                        select(RagChunk)
                        .where(
                            RagChunk.project_id == chapter.project_id,
                            RagChunk.chapter_number == chapter.chapter_number,
                            RagChunk.source_revision == revision.revision,
                            RagChunk.artifact_generation == rag_generation,
                            RagChunk.projection_run_id == rag_run_id,
                            RagChunk.is_active.is_(True),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if isinstance(rag_generation, str) and isinstance(rag_run_id, str)
            else []
        )
        promoted_summary_rows = (
            list(
                (
                    await self.session.execute(
                        select(RagSummary)
                        .where(
                            RagSummary.project_id == chapter.project_id,
                            RagSummary.chapter_number == chapter.chapter_number,
                            RagSummary.source_revision == revision.revision,
                            RagSummary.artifact_generation == rag_generation,
                            RagSummary.projection_run_id == rag_run_id,
                            RagSummary.is_active.is_(True),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if isinstance(rag_generation, str) and isinstance(rag_run_id, str)
            else []
        )
        self._require_exact_ids(
            [item.id for item in promoted_chunk_rows],
            promoted_chunk_ids,
            "rollback_projection_artifacts_advanced",
        )
        self._require_exact_ids(
            [item.id for item in promoted_summary_rows],
            promoted_summary_ids,
            "rollback_projection_artifacts_advanced",
        )
        legacy_chunk_rows = (
            list(
                (
                    await self.session.execute(
                        select(RagChunk)
                        .where(
                            RagChunk.id.in_(legacy_chunk_ids),
                            RagChunk.project_id == chapter.project_id,
                            RagChunk.chapter_number == chapter.chapter_number,
                            RagChunk.is_active.is_(False),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if legacy_chunk_ids
            else []
        )
        legacy_summary_rows = (
            list(
                (
                    await self.session.execute(
                        select(RagSummary)
                        .where(
                            RagSummary.id.in_(legacy_summary_ids),
                            RagSummary.project_id == chapter.project_id,
                            RagSummary.chapter_number == chapter.chapter_number,
                            RagSummary.is_active.is_(False),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if legacy_summary_ids
            else []
        )
        self._require_exact_ids(
            [item.id for item in legacy_chunk_rows],
            legacy_chunk_ids,
            "rollback_manifest_invalid",
        )
        self._require_exact_ids(
            [item.id for item in legacy_summary_rows],
            legacy_summary_ids,
            "rollback_manifest_invalid",
        )
        if any(
            item.source_revision != legacy_chunk_identities[item.id]["source_revision"]
            or item.artifact_generation != legacy_chunk_identities[item.id]["artifact_generation"]
            or item.projection_run_id != legacy_chunk_identities[item.id]["projection_run_id"]
            for item in legacy_chunk_rows
        ) or any(
            item.source_revision != legacy_summary_identities[item.id]["source_revision"]
            or item.artifact_generation != legacy_summary_identities[item.id]["artifact_generation"]
            or item.projection_run_id != legacy_summary_identities[item.id]["projection_run_id"]
            for item in legacy_summary_rows
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")

        promoted_foreshadowing_rows = list(
            (
                await self.session.execute(
                    select(Foreshadowing)
                    .where(
                        Foreshadowing.project_id == chapter.project_id,
                        Foreshadowing.chapter_id == chapter.id,
                        Foreshadowing.chapter_revision == revision.revision,
                        Foreshadowing.artifact_generation == foreshadowing_generation,
                        Foreshadowing.projection_run_id == foreshadowing_run_id,
                        Foreshadowing.is_active.is_(True),
                    )
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        self._require_exact_ids(
            [item.id for item in promoted_foreshadowing_rows],
            promoted_foreshadowing_ids,
            "rollback_projection_artifacts_advanced",
        )
        legacy_foreshadowing_rows = (
            list(
                (
                    await self.session.execute(
                        select(Foreshadowing)
                        .where(
                            Foreshadowing.id.in_(legacy_foreshadowing_ids),
                            Foreshadowing.project_id == chapter.project_id,
                            Foreshadowing.chapter_id == chapter.id,
                            Foreshadowing.is_manual.is_(False),
                            Foreshadowing.is_active.is_(False),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if legacy_foreshadowing_ids
            else []
        )
        self._require_exact_ids(
            [item.id for item in legacy_foreshadowing_rows],
            legacy_foreshadowing_ids,
            "rollback_manifest_invalid",
        )
        if any(
            item.chapter_id != legacy_foreshadowing_identities[item.id]["chapter_id"]
            or item.chapter_number != legacy_foreshadowing_identities[item.id]["chapter_number"]
            or item.chapter_revision != legacy_foreshadowing_identities[item.id]["chapter_revision"]
            or item.artifact_generation
            != legacy_foreshadowing_identities[item.id]["artifact_generation"]
            or item.projection_run_id
            != legacy_foreshadowing_identities[item.id]["projection_run_id"]
            or item.is_manual != legacy_foreshadowing_identities[item.id]["is_manual"]
            for item in legacy_foreshadowing_rows
        ):
            raise ChapterProjectionRolloutConflictError("rollback_manifest_invalid")
        state_rows = (
            list(
                (
                    await self.session.execute(
                        select(Foreshadowing)
                        .where(
                            Foreshadowing.id.in_(state_ids),
                            Foreshadowing.project_id == chapter.project_id,
                            Foreshadowing.is_active.is_(True),
                        )
                        .with_for_update()
                    )
                )
                .scalars()
                .all()
            )
            if state_ids
            else []
        )
        self._require_exact_ids(
            [item.id for item in state_rows],
            state_ids,
            "rollback_foreshadowing_advanced",
        )
        state_by_id = {item.id: item for item in state_rows}
        for previous in states:
            current = state_by_id[previous["id"]]
            if (
                current.project_id != previous["project_id"]
                or current.chapter_id != previous["chapter_id"]
                or current.chapter_number != previous["chapter_number"]
                or current.chapter_revision != previous["chapter_revision"]
                or current.artifact_generation != previous["artifact_generation"]
                or current.projection_run_id != previous["projection_run_id"]
                or current.is_manual != previous["is_manual"]
                or current.status != previous["expected_status"]
                or current.resolved_chapter_id != previous["expected_resolved_chapter_id"]
                or current.resolved_chapter_number != previous["expected_resolved_chapter_number"]
            ):
                raise ChapterProjectionRolloutConflictError("rollback_foreshadowing_advanced")

        promoted_snapshot.is_active = False
        legacy_snapshot.is_active = True
        for item in promoted_character_rows:
            item.is_active = False
        for item in legacy_character_rows:
            item.is_active = True
        for item in promoted_chunk_rows + promoted_summary_rows:
            item.is_active = False
        for item in legacy_chunk_rows + legacy_summary_rows:
            item.is_active = True
        for item in promoted_foreshadowing_rows:
            item.is_active = False
        for item in legacy_foreshadowing_rows:
            item.is_active = True
        for run in runs:
            run.is_active = run.id in previous_run_id_set

        for previous in states:
            current = state_by_id[previous["id"]]
            old_status = current.status
            current.status = previous["status"]
            current.resolved_chapter_id = previous.get("resolved_chapter_id")
            current.resolved_chapter_number = previous.get("resolved_chapter_number")
            if old_status != current.status:
                self.session.add(
                    ForeshadowingStatusHistory(
                        foreshadowing_id=current.id,
                        old_status=old_status,
                        new_status=current.status,
                        chapter_number=chapter.chapter_number,
                        chapter_revision=chapter.current_revision,
                        artifact_generation=foreshadowing_generation,
                        projection_run_id=foreshadowing_run_id,
                        reason="章节投影 rollout 回滚",
                    )
                )

        chapter.real_summary = manifest.get("previous_real_summary")
        chapter.status = chapter_state["status"]
        chapter.generation_progress = chapter_state["generation_progress"]
        chapter.generation_step = chapter_state["generation_step"]
        chapter.generation_step_index = chapter_state["generation_step_index"]
        chapter.generation_step_total = chapter_state["generation_step_total"]
        revision.lifecycle = previous_lifecycle
        if blueprint is not None and isinstance(blueprint_state, dict):
            blueprint.is_finalized = blueprint_state["is_finalized"]
        memory.global_summary = memory_state.get("global_summary")
        memory.plot_arcs = memory_state.get("plot_arcs")
        memory.last_updated_chapter = memory_state["last_updated_chapter"]
        memory.projection_revision = memory_state["projection_revision"]
        memory.projection_generation = memory_state.get("projection_generation")
        memory.version = int(memory.version or 0) + 1

    @staticmethod
    def _status_payload(
        chapter: Chapter,
        rollout: ChapterProjectionRollout,
        gate: RolloutGate,
    ) -> dict[str, Any]:
        return {
            "project_id": chapter.project_id,
            "chapter_id": chapter.id,
            "owner": rollout.owner,
            "state": rollout.state,
            "generation": rollout.generation,
            "fencing_token": rollout.fencing_token,
            "transition_sequence": rollout.transition_sequence,
            "observation_started_at": rollout.observation_started_at,
            "observation_deadline_at": rollout.observation_deadline_at,
            "required_observations": rollout.required_observations,
            "successful_observations": rollout.successful_observations,
            "failed_observations": rollout.failed_observations,
            "last_observed_at": rollout.last_observed_at,
            "shadow_digest": rollout.shadow_digest,
            "shadow_diff": rollout.shadow_diff,
            "cutover_at": rollout.cutover_at,
            "rollback_at": rollout.rollback_at,
            "gate_ready": gate.ready,
            "gate_reasons": list(gate.reasons),
        }


__all__ = [
    "ChapterProjectionObservationPendingError",
    "ChapterProjectionRolloutConflictError",
    "ChapterProjectionRolloutError",
    "ChapterProjectionRolloutNotFoundError",
    "ChapterProjectionRolloutService",
    "RolloutGate",
    "evaluate_rollout_gate",
    "validate_rollout_owner_state",
    "validate_rollout_transition",
]
