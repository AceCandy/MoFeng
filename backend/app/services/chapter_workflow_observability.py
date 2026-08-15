# AIMETA P=章节工作流运行时可观测性|R=有界聚合_checkpoint对账_稳定告警|NR=不暴露tenant身份或私有payload|E=ChapterWorkflowObservabilityService|X=worker_cli|A=read_service|D=sqlalchemy,langgraph|S=db|RD=./README.ai
"""Build bounded Chapter workflow metrics and stable operational alerts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from .chapter_workflow_reconciler import (
    ChapterWorkflowCheckpointReader,
    ChapterWorkflowReconcileCandidate,
)

_RUN_STATUSES = frozenset(
    {
        "queued",
        "running",
        "retry_wait",
        "waiting_for_selection",
        "finalizing",
        "projection_pending",
        "needs_attention",
        "successful",
        "failed",
        "cancelled",
        "superseded",
    }
)
_COMMAND_TYPES = frozenset({"select", "retry", "retry_external", "retry_projection", "cancel"})
_COMMAND_REJECTION_CODES = frozenset(
    {
        "actor_mismatch",
        "ambiguous_activity_required",
        "ambiguous_command_type_required",
        "command_rejected",
        "invalid_activity_key",
        "invalid_ambiguous_activity_request",
        "invalid_command_payload",
        "invalid_command_status",
        "possible_duplicate_ack_required",
        "run_not_awaiting_ambiguous_resolution",
        "stale_chapter_revision",
        "stale_checkpoint",
        "stale_run_revision",
        "unsupported_payload_version",
    }
)
_RECONCILIATION_REASONS = frozenset(
    {
        "chapter_binding_mismatch",
        "chapter_missing",
        "chapter_revision_superseded",
        "checkpoint_command_mismatch",
        "checkpoint_drift",
        "checkpoint_identity_mismatch",
        "checkpoint_missing",
        "checkpoint_node_drift",
        "checkpoint_state_invalid",
        "checkpoint_version_unknown",
        "job_run_status_mismatch",
        "projection_completed",
        "root_terminal_run_active",
        "workflow_identity_mismatch",
        "workflow_run_missing",
    }
)
_CHECKPOINT_PROBLEMS = frozenset(
    {
        "checkpoint_drift",
        "checkpoint_missing",
        "checkpoint_node_drift",
        "checkpoint_read_unavailable",
        "checkpoint_state_invalid",
        "checkpoint_version_unknown",
    }
)
_CHECKPOINT_UNAVAILABLE = frozenset(
    {
        "checkpoint_read_unavailable",
        "checkpoint_state_invalid",
        "checkpoint_version_unknown",
    }
)
_WAITING_STATUSES = frozenset({"waiting_for_selection", "projection_pending", "needs_attention"})


@dataclass(frozen=True)
class ChapterWorkflowRuntimeMetrics:
    """无身份和私有 payload 的 workflow 聚合快照。"""

    window_seconds: int
    status_counts: dict[str, int]
    oldest_state_age_seconds: dict[str, float]
    active_runs: int
    oldest_active_age_seconds: Optional[float]
    waiting_runs: int
    oldest_waiting_duration_seconds: Optional[float]
    command_rejections: int
    command_rejection_type_counts: dict[str, int]
    command_rejection_reason_counts: dict[str, int]
    needs_attention: int
    oldest_needs_attention_age_seconds: Optional[float]
    checkpoint_runs_observed: int
    checkpoint_lag: int
    checkpoint_problem_counts: dict[str, int]
    projection_lag: int
    oldest_projection_lag_seconds: Optional[float]
    reconciler_fix_counts: dict[str, int]
    alerts: tuple[str, ...]


@dataclass(frozen=True)
class _ActiveRunSnapshot:
    run_id: str
    workflow_version: int
    state_schema_version: int
    status: str
    node_key: str
    checkpoint_id: Optional[str]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _age_seconds(now: datetime, value: object) -> Optional[float]:
    if not isinstance(value, datetime):
        return None
    return max(0.0, (now - value).total_seconds())


def _normalized_label(value: object, allowed: frozenset[str]) -> str:
    return value if isinstance(value, str) and value in allowed else "unknown"


def _add_count(counts: dict[str, int], label: str, raw_count: object) -> None:
    if isinstance(raw_count, bool) or not isinstance(raw_count, int):
        raise RuntimeError("chapter workflow observability count 无效")
    counts[label] = counts.get(label, 0) + raw_count


def _count_and_timestamp(value: object) -> tuple[int, object]:
    if not isinstance(value, tuple) or len(value) != 2:
        raise RuntimeError("chapter workflow current metrics 无效")
    count, timestamp = value
    if isinstance(count, bool) or not isinstance(count, int):
        raise RuntimeError("chapter workflow current metrics 无效")
    return count, timestamp


class ChapterWorkflowObservabilityService:
    """Read current/event/checkpoint facts without creating a second control plane."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        checkpoint_reader: ChapterWorkflowCheckpointReader,
    ) -> None:
        self.repo = ChapterWorkflowRepository(session)
        self.checkpoint_reader = checkpoint_reader

    async def get_runtime_metrics(
        self,
        *,
        now: Optional[datetime] = None,
        window_seconds: int = 3600,
        waiting_alert_after_seconds: int = 86400,
        projection_alert_after_seconds: int = 900,
    ) -> ChapterWorkflowRuntimeMetrics:
        if window_seconds < 1:
            raise ValueError("workflow metrics window_seconds 必须大于 0")
        if waiting_alert_after_seconds < 1 or projection_alert_after_seconds < 1:
            raise ValueError("workflow metrics alert threshold 必须大于 0")
        checked_at = now or _utc_now()
        values = await self.repo.get_observability_values(
            window_started_at=checked_at - timedelta(seconds=window_seconds)
        )
        checkpoint_runs = await self.repo.list_checkpoint_runs_for_observability()
        snapshots = [
            _ActiveRunSnapshot(
                run_id=run.id,
                workflow_version=run.workflow_version,
                state_schema_version=run.state_schema_version,
                status=run.status,
                node_key=run.node_key,
                checkpoint_id=run.checkpoint_id,
            )
            for run in checkpoint_runs
        ]

        status_counts: dict[str, int] = {}
        oldest_state_age_seconds: dict[str, float] = {}
        state_rows = values["state_rows"]
        if not isinstance(state_rows, list):
            raise RuntimeError("chapter workflow state metrics 无效")
        for raw_status, count, oldest_updated_at in state_rows:
            status = _normalized_label(raw_status, _RUN_STATUSES)
            _add_count(status_counts, status, count)
            age = _age_seconds(checked_at, oldest_updated_at)
            if age is not None:
                oldest_state_age_seconds[status] = max(
                    age,
                    oldest_state_age_seconds.get(status, 0.0),
                )

        active_count, oldest_active_at = _count_and_timestamp(values["active_row"])
        waiting_status_counts: dict[str, int] = {}
        waiting_state_age_seconds: dict[str, float] = {}
        waiting_state_rows = values["waiting_state_rows"]
        if not isinstance(waiting_state_rows, list):
            raise RuntimeError("chapter workflow waiting metrics 无效")
        for raw_status, count, oldest_waiting_at in waiting_state_rows:
            status = _normalized_label(raw_status, _WAITING_STATUSES)
            _add_count(waiting_status_counts, status, count)
            age = _age_seconds(checked_at, oldest_waiting_at)
            if age is not None:
                waiting_state_age_seconds[status] = max(
                    age,
                    waiting_state_age_seconds.get(status, 0.0),
                )
        waiting_count = sum(waiting_status_counts.values())

        rejection_type_counts: dict[str, int] = {}
        rejection_reason_counts: dict[str, int] = {}
        command_rejections = 0
        rejection_rows = values["rejection_rows"]
        if not isinstance(rejection_rows, list):
            raise RuntimeError("chapter workflow rejection metrics 无效")
        for raw_type, raw_reason, count in rejection_rows:
            command_type = _normalized_label(raw_type, _COMMAND_TYPES)
            reason = _normalized_label(raw_reason, _COMMAND_REJECTION_CODES)
            _add_count(rejection_type_counts, command_type, count)
            _add_count(rejection_reason_counts, reason, count)
            command_rejections += count

        reconciler_fix_counts: dict[str, int] = {}
        reconciliation_rows = values["reconciliation_rows"]
        if not isinstance(reconciliation_rows, list):
            raise RuntimeError("chapter workflow reconciliation metrics 无效")
        for raw_reason, count in reconciliation_rows:
            reason = _normalized_label(raw_reason, _RECONCILIATION_REASONS)
            _add_count(reconciler_fix_counts, reason, count)

        checkpoint_problem_counts = await self._checkpoint_problem_counts(snapshots)
        checkpoint_lag = sum(checkpoint_problem_counts.values())
        needs_attention = status_counts.get("needs_attention", 0)
        projection_lag = waiting_status_counts.get("projection_pending", 0)
        oldest_waiting_duration = max(waiting_state_age_seconds.values(), default=None)
        oldest_projection_lag = waiting_state_age_seconds.get("projection_pending")

        alerts: list[str] = []
        if (
            oldest_waiting_duration is not None
            and oldest_waiting_duration >= waiting_alert_after_seconds
        ):
            alerts.append("chapter_workflow_waiting_stuck")
        if command_rejections:
            alerts.append("chapter_workflow_command_rejected")
        if needs_attention:
            alerts.append("chapter_workflow_needs_attention")
        if checkpoint_lag:
            alerts.append("chapter_workflow_checkpoint_lag")
        if any(checkpoint_problem_counts.get(code, 0) for code in _CHECKPOINT_UNAVAILABLE):
            alerts.append("chapter_workflow_checkpoint_unavailable")
        if (
            oldest_projection_lag is not None
            and oldest_projection_lag >= projection_alert_after_seconds
        ):
            alerts.append("chapter_workflow_projection_lag")
        if sum(
            count
            for reason, count in reconciler_fix_counts.items()
            if reason != "projection_completed"
        ):
            alerts.append("chapter_workflow_reconciler_repairs")

        return ChapterWorkflowRuntimeMetrics(
            window_seconds=window_seconds,
            status_counts=dict(sorted(status_counts.items())),
            oldest_state_age_seconds=dict(sorted(oldest_state_age_seconds.items())),
            active_runs=active_count,
            oldest_active_age_seconds=_age_seconds(checked_at, oldest_active_at),
            waiting_runs=waiting_count,
            oldest_waiting_duration_seconds=oldest_waiting_duration,
            command_rejections=command_rejections,
            command_rejection_type_counts=dict(sorted(rejection_type_counts.items())),
            command_rejection_reason_counts=dict(sorted(rejection_reason_counts.items())),
            needs_attention=needs_attention,
            oldest_needs_attention_age_seconds=oldest_state_age_seconds.get("needs_attention"),
            checkpoint_runs_observed=len(snapshots),
            checkpoint_lag=checkpoint_lag,
            checkpoint_problem_counts=dict(sorted(checkpoint_problem_counts.items())),
            projection_lag=projection_lag,
            oldest_projection_lag_seconds=oldest_projection_lag,
            reconciler_fix_counts=dict(sorted(reconciler_fix_counts.items())),
            alerts=tuple(sorted(alerts)),
        )

    async def _checkpoint_problem_counts(
        self,
        snapshots: list[_ActiveRunSnapshot],
    ) -> dict[str, int]:
        if not snapshots:
            return {}
        candidates = [
            ChapterWorkflowReconcileCandidate(
                run_id=run.run_id,
                workflow_version=run.workflow_version,
                state_schema_version=run.state_schema_version,
                is_active=True,
            )
            for run in snapshots
        ]
        evidence = await self.checkpoint_reader.read(candidates)
        counts: dict[str, int] = {}
        for run in snapshots:
            item = evidence.get(run.run_id)
            problem: Optional[str] = None
            if item is None:
                problem = "checkpoint_read_unavailable"
            elif item.reason_code is not None:
                initial_without_checkpoint = (
                    item.reason_code == "checkpoint_missing"
                    and run.checkpoint_id is None
                    and run.status in {"queued", "retry_wait"}
                    and run.node_key == "freeze_base_context"
                )
                if not initial_without_checkpoint:
                    problem = _normalized_label(item.reason_code, _CHECKPOINT_PROBLEMS)
            elif run.status in _WAITING_STATUSES and item.checkpoint_id != run.checkpoint_id:
                problem = "checkpoint_drift"
            elif (
                run.status in _WAITING_STATUSES
                and item.checkpoint_id == run.checkpoint_id
                and item.state is not None
                and item.state.node_key != run.node_key
            ):
                problem = "checkpoint_node_drift"
            if problem is not None:
                _add_count(counts, problem, 1)
        return counts


__all__ = [
    "ChapterWorkflowObservabilityService",
    "ChapterWorkflowRuntimeMetrics",
]
