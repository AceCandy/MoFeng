# AIMETA P=章节工作流stale_run收敛|R=checkpoint证据读取_轮转扫描_维护回调|NR=不执行graph节点或修改Chapter正文|E=ChapterWorkflowReconciler|X=worker|A=maintenance_service|D=langgraph,sqlalchemy|S=checkpoint,db|RD=./README.ai
"""Reconcile cross-transaction Chapter workflow state without reading trace."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from time import monotonic
from typing import Protocol, Sequence

from pydantic import ValidationError
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.chapter_workflow_checkpointer import open_chapter_workflow_checkpointer
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..schemas.chapter_workflow import ChapterWorkflowStateV1
from .chapter_workflow_graph import chapter_workflow_graph_config
from .job_service import (
    ChapterWorkflowCheckpointEvidence,
    ChapterWorkflowReconcileResult,
    JobService,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChapterWorkflowReconcileCandidate:
    """读取 checkpoint 所需的不可变 run identity。"""

    run_id: str
    workflow_version: int
    state_schema_version: int
    is_active: bool


@dataclass(frozen=True)
class ChapterWorkflowReconcileBatch:
    """一次有限批次维护结果。"""

    scanned: int
    reconciled: int
    needs_attention: int
    command_applied: int


class ChapterWorkflowCheckpointReader(Protocol):
    async def read(
        self,
        candidates: Sequence[ChapterWorkflowReconcileCandidate],
    ) -> dict[str, ChapterWorkflowCheckpointEvidence]: ...


class PostgresChapterWorkflowCheckpointReader:
    """使用 pinned saver 的 latest tuple API 读取同 thread checkpoint。"""

    def __init__(self, database_url: str | URL) -> None:
        self.database_url = database_url

    async def read(
        self,
        candidates: Sequence[ChapterWorkflowReconcileCandidate],
    ) -> dict[str, ChapterWorkflowCheckpointEvidence]:
        evidence: dict[str, ChapterWorkflowCheckpointEvidence] = {}
        async with open_chapter_workflow_checkpointer(self.database_url) as saver:
            for candidate in candidates:
                if candidate.workflow_version != 1 or candidate.state_schema_version != 1:
                    evidence[candidate.run_id] = ChapterWorkflowCheckpointEvidence(
                        checkpoint_id=None,
                        state=None,
                        reason_code="checkpoint_version_unknown",
                    )
                    continue
                try:
                    checkpoint_tuple = await saver.aget_tuple(
                        chapter_workflow_graph_config(candidate.run_id)
                    )
                except Exception:
                    logger.exception(
                        "Chapter workflow checkpoint 本轮读取失败: run_id=%s",
                        candidate.run_id,
                    )
                    evidence[candidate.run_id] = ChapterWorkflowCheckpointEvidence(
                        checkpoint_id=None,
                        state=None,
                        reason_code="checkpoint_read_unavailable",
                    )
                    continue
                evidence[candidate.run_id] = self._parse_tuple(
                    candidate,
                    checkpoint_tuple,
                )
        return evidence

    @staticmethod
    def _parse_tuple(
        candidate: ChapterWorkflowReconcileCandidate,
        checkpoint_tuple: object,
    ) -> ChapterWorkflowCheckpointEvidence:
        if checkpoint_tuple is None:
            return ChapterWorkflowCheckpointEvidence(
                checkpoint_id=None,
                state=None,
                reason_code="checkpoint_missing",
            )
        try:
            config = checkpoint_tuple.config  # type: ignore[attr-defined]
            checkpoint = checkpoint_tuple.checkpoint  # type: ignore[attr-defined]
            configurable = config["configurable"]
            checkpoint_id = configurable["checkpoint_id"]
            checkpoint_thread_id = configurable["thread_id"]
            stored_checkpoint_id = checkpoint["id"]
            channel_values = checkpoint["channel_values"]
            if (
                checkpoint_thread_id != candidate.run_id
                or not isinstance(checkpoint_id, str)
                or not checkpoint_id
                or stored_checkpoint_id != checkpoint_id
                or not isinstance(channel_values, dict)
            ):
                raise ValueError("checkpoint identity drift")
            state_values = {
                key: channel_values[key]
                for key in ChapterWorkflowStateV1.model_fields
                if key in channel_values
            }
            state = ChapterWorkflowStateV1.model_validate(state_values)
        except (KeyError, TypeError, ValueError, ValidationError):
            logger.warning(
                "Chapter workflow checkpoint 无法验证: run_id=%s reason=%s",
                candidate.run_id,
                "checkpoint_state_invalid",
            )
            return ChapterWorkflowCheckpointEvidence(
                checkpoint_id=None,
                state=None,
                reason_code="checkpoint_state_invalid",
            )
        return ChapterWorkflowCheckpointEvidence(
            checkpoint_id=checkpoint_id,
            state=state,
        )


class ChapterWorkflowReconciler:
    """轮转扫描 active/mismatched runs；每个 outcome 由 JobService 单独提交。"""

    def __init__(
        self,
        *,
        database_url: str | URL,
        batch_size: int = 25,
        interval_seconds: float = 30.0,
        checkpoint_reader: ChapterWorkflowCheckpointReader | None = None,
    ) -> None:
        if batch_size < 1:
            raise ValueError("workflow reconcile batch_size 必须大于等于 1")
        if interval_seconds <= 0:
            raise ValueError("workflow reconcile interval 必须大于 0")
        self.batch_size = batch_size
        self.interval_seconds = interval_seconds
        self.checkpoint_reader = checkpoint_reader or PostgresChapterWorkflowCheckpointReader(
            database_url
        )
        self._after_run_id: str | None = None
        self._next_run_at = 0.0

    async def __call__(self, session: AsyncSession) -> None:
        current = monotonic()
        if current < self._next_run_at:
            return
        self._next_run_at = current + self.interval_seconds
        await self.reconcile_once(session)

    async def reconcile_once(self, session: AsyncSession) -> ChapterWorkflowReconcileBatch:
        repo = ChapterWorkflowRepository(session)
        rows = await repo.list_reconciliation_candidates(
            after_run_id=self._after_run_id,
            limit=self.batch_size,
        )
        if not rows and self._after_run_id is not None:
            self._after_run_id = None
            rows = await repo.list_reconciliation_candidates(
                after_run_id=None,
                limit=self.batch_size,
            )
        candidates = [
            ChapterWorkflowReconcileCandidate(
                run_id=row.id,
                workflow_version=row.workflow_version,
                state_schema_version=row.state_schema_version,
                is_active=row.is_active,
            )
            for row in rows
        ]
        await session.commit()
        if not candidates:
            return ChapterWorkflowReconcileBatch(0, 0, 0, 0)

        checkpoint_candidates = [candidate for candidate in candidates if candidate.is_active]
        evidence = await self.checkpoint_reader.read(checkpoint_candidates)
        no_checkpoint_needed = ChapterWorkflowCheckpointEvidence(
            checkpoint_id=None,
            state=None,
        )
        results: list[ChapterWorkflowReconcileResult] = []
        for candidate in candidates:
            result = await JobService(session).reconcile_chapter_workflow(
                candidate.run_id,
                checkpoint=evidence.get(candidate.run_id, no_checkpoint_needed),
            )
            results.append(result)
        self._after_run_id = candidates[-1].run_id
        return ChapterWorkflowReconcileBatch(
            scanned=len(results),
            reconciled=sum(result.action == "reconciled" for result in results),
            needs_attention=sum(result.action == "needs_attention" for result in results),
            command_applied=sum(result.action == "command_applied" for result in results),
        )


__all__ = [
    "ChapterWorkflowCheckpointReader",
    "ChapterWorkflowReconcileBatch",
    "ChapterWorkflowReconcileCandidate",
    "ChapterWorkflowReconciler",
    "PostgresChapterWorkflowCheckpointReader",
]
