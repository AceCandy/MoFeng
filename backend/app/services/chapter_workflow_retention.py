# AIMETA P=章节工作流终态保留清理|R=保护矩阵_私有payload清理_checkpoint删除|NR=不删除业务审计或canonical数据|E=ChapterWorkflowRetentionService|X=worker|A=maintenance_service|D=sqlalchemy,langgraph|S=db,checkpoint|RD=./README.ai
"""Idempotently remove terminal workflow private state after its retention window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol, Sequence

from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.chapter_workflow_checkpointer import open_chapter_workflow_checkpointer
from ..models.chapter_workflow import ChapterWorkflowCommand, ChapterWorkflowRun
from ..models.novel import Chapter
from ..repositories.chapter_workflow_repository import ChapterWorkflowRepository
from ..repositories.job_repository import JobRepository
from ..repositories.novel_repository import NovelRepository
from .chapter_workflow_reconciler import (
    ChapterWorkflowCheckpointReader,
    ChapterWorkflowReconcileCandidate,
)

_RUN_TERMINAL_STATUSES = frozenset({"successful", "failed", "cancelled", "superseded"})
_JOB_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "dead_letter", "cancelled"})
_RETENTION_PENDING_CHECKPOINT = "__retention_pending__"


class ChapterWorkflowCheckpointCleaner(Protocol):
    async def delete_threads(self, run_ids: Sequence[str]) -> None: ...


class PostgresChapterWorkflowCheckpointCleaner:
    """使用 pinned saver API 删除完整 thread，且不执行 runtime DDL。"""

    def __init__(self, database_url: str | URL) -> None:
        self.database_url = database_url

    async def delete_threads(self, run_ids: Sequence[str]) -> None:
        if not run_ids:
            return
        async with open_chapter_workflow_checkpointer(self.database_url) as saver:
            for run_id in run_ids:
                await saver.adelete_thread(run_id)


@dataclass(frozen=True)
class ChapterWorkflowRetentionResult:
    scanned: int
    cleaned_runs: int
    deleted_threads: int
    scrubbed_commands: int
    scrubbed_activities: int
    protected_current_revision: int
    checkpoint_unavailable: int


@dataclass(frozen=True)
class _RetentionCandidate:
    run_id: str
    root_job_id: str
    workflow_version: int
    state_schema_version: int
    checkpoint_id: str | None


class ChapterWorkflowRetentionService:
    """清理可再生私有状态，同时保留 durable identity 与审计事实。"""

    def __init__(
        self,
        session: AsyncSession,
        *,
        checkpoint_reader: ChapterWorkflowCheckpointReader,
        checkpoint_cleaner: ChapterWorkflowCheckpointCleaner,
    ) -> None:
        self.session = session
        self.workflow_repo = ChapterWorkflowRepository(session)
        self.job_repo = JobRepository(session)
        self.novel_repo = NovelRepository(session)
        self.checkpoint_reader = checkpoint_reader
        self.checkpoint_cleaner = checkpoint_cleaner

    async def cleanup(
        self,
        *,
        before: datetime,
        limit: int = 100,
    ) -> ChapterWorkflowRetentionResult:
        if before.tzinfo is None or before.utcoffset() is None:
            raise ValueError("workflow retention before 必须包含时区")
        if not 1 <= limit <= 500:
            raise ValueError("workflow retention limit 必须在 1 到 500 之间")

        after_run_id: str | None = None
        scanned = 0
        cleaned_runs = 0
        deleted_threads = 0
        scrubbed_commands = 0
        scrubbed_activities = 0
        protected_current_revision = 0
        checkpoint_unavailable = 0

        while cleaned_runs < limit:
            rows = await self.workflow_repo.list_retention_candidates(
                before=before,
                after_run_id=after_run_id,
                limit=limit,
            )
            if not rows:
                break
            candidates = [
                _RetentionCandidate(
                    run_id=run.id,
                    root_job_id=run.root_job_id,
                    workflow_version=run.workflow_version,
                    state_schema_version=run.state_schema_version,
                    checkpoint_id=run.checkpoint_id,
                )
                for run in rows
            ]
            scanned += len(candidates)
            after_run_id = candidates[-1].run_id
            evidence = await self.checkpoint_reader.read(
                [
                    ChapterWorkflowReconcileCandidate(
                        run_id=item.run_id,
                        workflow_version=item.workflow_version,
                        state_schema_version=item.state_schema_version,
                        is_active=False,
                    )
                    for item in candidates
                    if item.checkpoint_id not in {None, _RETENTION_PENDING_CHECKPOINT}
                ]
            )
            prepared: list[_RetentionCandidate] = []

            for candidate in candidates:
                if cleaned_runs + len(prepared) >= limit:
                    break
                job = await self.job_repo.get_for_update(candidate.root_job_id)
                if job is None:
                    continue
                run = await self.workflow_repo.get_by_root_job_for_update(job.id)
                if run is None:
                    continue
                chapter = await self.novel_repo.get_chapter_for_update(
                    project_id=run.project_id,
                    chapter_number=run.chapter_number,
                )
                if chapter is None or run.chapter_id != chapter.id:
                    continue
                commands = await self.workflow_repo.list_commands_for_update(run.id)
                activities = await self.job_repo.list_activities_for_update(job_id=job.id)
                if not self._still_eligible(
                    run=run,
                    job_status=job.status,
                    job_completed_at=job.completed_at,
                    commands=commands,
                    before=before,
                    candidate=candidate,
                ):
                    continue

                if await self._may_own_current_revision(run=run, chapter=chapter):
                    protected_current_revision += 1
                    continue

                item = evidence.get(run.id)
                payloads_scrubbed = all(
                    command.payload == {} and command.result_payload is None for command in commands
                ) and all(
                    activity.request_payload == {} and activity.result_payload is None
                    for activity in activities
                )
                if candidate.checkpoint_id == _RETENTION_PENDING_CHECKPOINT:
                    if not payloads_scrubbed:
                        checkpoint_unavailable += 1
                        continue
                elif candidate.checkpoint_id is not None:
                    if item is None or item.reason_code is not None:
                        if not (
                            item is not None
                            and item.reason_code == "checkpoint_missing"
                            and payloads_scrubbed
                        ):
                            checkpoint_unavailable += 1
                            continue
                    elif item.checkpoint_id != candidate.checkpoint_id or item.state is None:
                        checkpoint_unavailable += 1
                        continue
                    elif (
                        item.state.target_chapter_revision is not None
                        and item.state.target_chapter_revision == chapter.current_revision
                    ):
                        protected_current_revision += 1
                        continue

                for command in commands:
                    if command.payload or command.result_payload is not None:
                        command.payload = {}
                        command.result_payload = None
                        scrubbed_commands += 1
                for activity in activities:
                    if activity.request_payload or activity.result_payload is not None:
                        activity.request_payload = {}
                        activity.result_payload = None
                        scrubbed_activities += 1
                run.checkpoint_id = _RETENTION_PENDING_CHECKPOINT
                prepared.append(candidate)

            await self.session.commit()
            run_ids = [candidate.run_id for candidate in prepared]
            if run_ids:
                await self.checkpoint_cleaner.delete_threads(run_ids)

                for candidate in prepared:
                    job = await self.job_repo.get_for_update(candidate.root_job_id)
                    if job is None:
                        continue
                    run = await self.workflow_repo.get_by_root_job_for_update(job.id)
                    if run is not None and run.checkpoint_id == _RETENTION_PENDING_CHECKPOINT:
                        run.checkpoint_id = None
                await self.session.commit()
                cleaned_runs += len(prepared)
                deleted_threads += len(run_ids)

            if len(rows) < limit:
                break

        return ChapterWorkflowRetentionResult(
            scanned=scanned,
            cleaned_runs=cleaned_runs,
            deleted_threads=deleted_threads,
            scrubbed_commands=scrubbed_commands,
            scrubbed_activities=scrubbed_activities,
            protected_current_revision=protected_current_revision,
            checkpoint_unavailable=checkpoint_unavailable,
        )

    async def _may_own_current_revision(
        self,
        *,
        run: ChapterWorkflowRun,
        chapter: Chapter,
    ) -> bool:
        """缺少 canonical lineage 时宁可保留，也不清理可能属于当前 revision 的 run。"""

        current_revision = int(chapter.current_revision or 0)
        if current_revision != run.base_revision + 1:
            return False
        stream_ids = await self.workflow_repo.list_revision_workflow_stream_ids(
            chapter_id=chapter.id,
            revision=current_revision,
        )
        return not stream_ids or run.id in stream_ids

    @staticmethod
    def _still_eligible(
        *,
        run: ChapterWorkflowRun,
        job_status: str,
        job_completed_at: datetime | None,
        commands: Sequence[ChapterWorkflowCommand],
        before: datetime,
        candidate: _RetentionCandidate,
    ) -> bool:
        return bool(
            run.id == candidate.run_id
            and run.checkpoint_id == candidate.checkpoint_id
            and not run.is_active
            and run.status in _RUN_TERMINAL_STATUSES
            and run.completed_at is not None
            and run.completed_at < before
            and run.successor_run_id is None
            and job_status in _JOB_TERMINAL_STATUSES
            and job_completed_at is not None
            and job_completed_at < before
            and all(command.status != "pending" for command in commands)
        )


__all__ = [
    "ChapterWorkflowCheckpointCleaner",
    "ChapterWorkflowRetentionResult",
    "ChapterWorkflowRetentionService",
    "PostgresChapterWorkflowCheckpointCleaner",
]
