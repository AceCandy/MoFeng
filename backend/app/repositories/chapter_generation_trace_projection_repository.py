"""Persistence boundary for the JobEvent-backed generation trace view."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.chapter_generation_trace import (
    ChapterGenerationTrace,
    ChapterGenerationTraceProjectionCheckpoint,
)
from ..models.chapter_workflow import ChapterWorkflowRun
from ..models.job import JobEvent

CHAPTER_GENERATION_TRACE_PROJECTOR_NAME = "chapter_generation_trace_v1"


class ChapterGenerationTraceProjectionRepository:
    """原子锁定 projector cursor，并幂等写入兼容 trace 视图。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def lock_checkpoint(
        self,
    ) -> ChapterGenerationTraceProjectionCheckpoint | None:
        result = await self.session.execute(
            select(ChapterGenerationTraceProjectionCheckpoint)
            .where(
                ChapterGenerationTraceProjectionCheckpoint.projector_name
                == CHAPTER_GENERATION_TRACE_PROJECTOR_NAME
            )
            .with_for_update(skip_locked=True)
        )
        return cast(
            ChapterGenerationTraceProjectionCheckpoint | None,
            result.scalars().first(),
        )

    async def checkpoint_exists(self) -> bool:
        projector_name = await self.session.scalar(
            select(ChapterGenerationTraceProjectionCheckpoint.projector_name).where(
                ChapterGenerationTraceProjectionCheckpoint.projector_name
                == CHAPTER_GENERATION_TRACE_PROJECTOR_NAME
            )
        )
        return projector_name is not None

    async def list_events_after(
        self,
        *,
        after_cursor: int,
        limit: int,
    ) -> list[JobEvent]:
        result = await self.session.execute(
            select(JobEvent)
            .where(JobEvent.cursor > after_cursor)
            .order_by(JobEvent.cursor)
            .limit(limit)
        )
        return list(result.scalars())

    async def list_run_events_after(
        self,
        *,
        run_id: str,
        after_cursor: int,
        limit: int,
    ) -> list[JobEvent]:
        result = await self.session.execute(
            select(JobEvent)
            .where(
                JobEvent.stream_type == "workflow",
                JobEvent.stream_id == run_id,
                JobEvent.cursor > after_cursor,
            )
            .order_by(JobEvent.cursor)
            .limit(limit)
        )
        return list(result.scalars())

    async def get_runs(self, run_ids: Iterable[str]) -> dict[str, ChapterWorkflowRun]:
        identities = tuple(set(run_ids))
        if not identities:
            return {}
        result = await self.session.execute(
            select(ChapterWorkflowRun).where(ChapterWorkflowRun.id.in_(identities))
        )
        return {run.id: run for run in result.scalars()}

    async def get_run(self, run_id: str) -> ChapterWorkflowRun | None:
        return await self.session.get(ChapterWorkflowRun, run_id)

    async def upsert_traces(self, rows: Sequence[dict[str, object]]) -> int:
        if not rows:
            return 0
        statement = pg_insert(ChapterGenerationTrace.__table__).values(list(rows))
        result = await self.session.execute(
            statement.on_conflict_do_nothing(constraint="uq_chapter_generation_trace_source")
        )
        return int(result.rowcount or 0)
