# AIMETA P=章节投影状态判定|R=最新run选择_确定失败重试集合|NR=不查询数据库或写入projection|E=latest_projection_runs_retryable_projection_names|X=internal|A=domain_policy|D=sqlalchemy_models|S=none|RD=./README.ai
"""Shared deterministic policies over one locked Chapter projection run set."""

from __future__ import annotations

from collections.abc import Iterable

from ..models.chapter_projection import ChapterProjectionRun

RETRYABLE_PROJECTION_STATUSES = frozenset({"failed", "dead_letter"})


def latest_projection_runs(
    runs: Iterable[ChapterProjectionRun],
) -> dict[str, ChapterProjectionRun]:
    """按既有 replay 顺序选出每种 projection 的最新 run。"""

    latest: dict[str, ChapterProjectionRun] = {}
    for run in runs:
        current = latest.get(run.projection_name)
        if current is None or (
            run.created_at is not None,
            run.created_at,
            run.id,
        ) > (
            current.created_at is not None,
            current.created_at,
            current.id,
        ):
            latest[run.projection_name] = run
    return latest


def retryable_projection_names(
    runs: Iterable[ChapterProjectionRun],
    *,
    required_projections: Iterable[str],
) -> tuple[str, ...]:
    """只返回当前修订中最新且确定失败的 canonical projection。"""

    required = set(required_projections)
    retryable_names = required | {"summary"}
    latest = latest_projection_runs(runs)
    return tuple(
        sorted(
            name
            for name, run in latest.items()
            if name in retryable_names and run.status in RETRYABLE_PROJECTION_STATUSES
        )
    )


__all__ = [
    "RETRYABLE_PROJECTION_STATUSES",
    "latest_projection_runs",
    "retryable_projection_names",
]
