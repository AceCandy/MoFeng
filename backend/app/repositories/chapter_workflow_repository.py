# AIMETA P=章节工作流仓库_run与command查询|R=活动run查询_锁行_command幂等|NR=不提交事务或执行graph|E=ChapterWorkflowRepository|X=internal|A=repository|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, cast, exists, func, literal, not_, or_, select
from sqlalchemy.dialects.postgresql import JSONB

from ..models.background_task import BackgroundTask
from ..models.chapter_projection import ChapterOutboxEvent
from ..models.chapter_workflow import (
    CHAPTER_WORKFLOW_RESET_CHECKPOINT_DELETE_PENDING,
    ChapterWorkflowCommand,
    ChapterWorkflowRun,
)
from ..models.job import JobActivity, JobEvent
from ..models.novel import Chapter
from .base import BaseRepository


class ChapterWorkflowRepository(BaseRepository[ChapterWorkflowRun]):
    """Workflow persistence queries; the service owns every commit."""

    model = ChapterWorkflowRun

    async def get_for_update(self, run_id: str) -> Optional[ChapterWorkflowRun]:
        result = await self.session.execute(
            select(ChapterWorkflowRun)
            .where(ChapterWorkflowRun.id == run_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_by_root_job_for_update(
        self,
        root_job_id: str,
    ) -> Optional[ChapterWorkflowRun]:
        """在 root JobRun 已锁定后锁定其唯一 workflow run。"""

        result = await self.session.execute(
            select(ChapterWorkflowRun)
            .where(ChapterWorkflowRun.root_job_id == root_job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_user_run(
        self,
        run_id: str,
        *,
        user_id: int,
    ) -> Optional[ChapterWorkflowRun]:
        result = await self.session.execute(
            select(ChapterWorkflowRun).where(
                ChapterWorkflowRun.id == run_id,
                ChapterWorkflowRun.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def get_current_user_run(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
    ) -> Optional[ChapterWorkflowRun]:
        """返回 owner scope 内可恢复的当前 run，不暴露 successor predecessor。"""

        terminal_chapter_exists = exists(
            select(Chapter.id).where(
                Chapter.id == ChapterWorkflowRun.chapter_id,
                Chapter.status != "not_generated",
            )
        )
        result = await self.session.execute(
            select(ChapterWorkflowRun)
            .where(
                ChapterWorkflowRun.user_id == user_id,
                ChapterWorkflowRun.project_id == project_id,
                ChapterWorkflowRun.chapter_number == chapter_number,
                or_(
                    ChapterWorkflowRun.is_active.is_(True),
                    and_(
                        ChapterWorkflowRun.is_active.is_(False),
                        ChapterWorkflowRun.status.in_(("successful", "failed", "cancelled")),
                        ChapterWorkflowRun.successor_run_id.is_(None),
                        terminal_chapter_exists,
                    ),
                ),
            )
            .order_by(
                ChapterWorkflowRun.is_active.desc(),
                ChapterWorkflowRun.base_revision.desc(),
                ChapterWorkflowRun.updated_at.desc(),
                ChapterWorkflowRun.created_at.desc(),
                ChapterWorkflowRun.id.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def get_checkpoint_delete_pending_user_run(
        self,
        *,
        user_id: int,
        project_id: str,
        chapter_number: int,
    ) -> Optional[ChapterWorkflowRun]:
        """返回重置已生效、但 checkpoint thread 仍待幂等删除的 run。"""

        result = await self.session.execute(
            select(ChapterWorkflowRun)
            .where(
                ChapterWorkflowRun.user_id == user_id,
                ChapterWorkflowRun.project_id == project_id,
                ChapterWorkflowRun.chapter_number == chapter_number,
                ChapterWorkflowRun.checkpoint_id
                == CHAPTER_WORKFLOW_RESET_CHECKPOINT_DELETE_PENDING,
            )
            .order_by(
                ChapterWorkflowRun.base_revision.desc(),
                ChapterWorkflowRun.updated_at.desc(),
                ChapterWorkflowRun.id.desc(),
            )
            .limit(1)
        )
        return result.scalars().first()

    async def get_active_run(
        self,
        *,
        project_id: str,
        chapter_number: int,
        base_revision: int,
    ) -> Optional[ChapterWorkflowRun]:
        result = await self.session.execute(
            select(ChapterWorkflowRun).where(
                ChapterWorkflowRun.project_id == project_id,
                ChapterWorkflowRun.chapter_number == chapter_number,
                ChapterWorkflowRun.base_revision == base_revision,
                ChapterWorkflowRun.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def get_latest_retryable_run(
        self,
        *,
        project_id: str,
        chapter_number: int,
        base_revision: int,
    ) -> Optional[ChapterWorkflowRun]:
        """返回 current-base 上最近的确定失败 run，供 legacy retry adapter 定位。"""

        result = await self.session.execute(
            select(ChapterWorkflowRun)
            .where(
                ChapterWorkflowRun.project_id == project_id,
                ChapterWorkflowRun.chapter_number == chapter_number,
                ChapterWorkflowRun.base_revision == base_revision,
                ChapterWorkflowRun.status.in_(("retry_wait", "failed")),
            )
            .order_by(ChapterWorkflowRun.created_at.desc(), ChapterWorkflowRun.id.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def list_reconciliation_candidates(
        self,
        *,
        after_run_id: str | None,
        limit: int,
    ) -> list[ChapterWorkflowRun]:
        """轮转读取 active、状态失配或仍有 pending command 的 run identity。"""

        valid_status_pair = or_(
            and_(BackgroundTask.status == "queued", ChapterWorkflowRun.status == "queued"),
            and_(
                BackgroundTask.status == "running",
                ChapterWorkflowRun.status.in_(("running", "finalizing")),
            ),
            and_(
                BackgroundTask.status == "retry_wait",
                ChapterWorkflowRun.status == "retry_wait",
            ),
            and_(
                BackgroundTask.status == "waiting",
                ChapterWorkflowRun.status.in_(("waiting_for_selection", "projection_pending")),
            ),
            and_(
                BackgroundTask.status == "needs_attention",
                ChapterWorkflowRun.status == "needs_attention",
            ),
            and_(
                BackgroundTask.status == "succeeded",
                ChapterWorkflowRun.status == "successful",
            ),
            and_(
                BackgroundTask.status.in_(("failed", "dead_letter")),
                ChapterWorkflowRun.status == "failed",
            ),
            and_(
                BackgroundTask.status == "cancelled",
                ChapterWorkflowRun.status.in_(("cancelled", "superseded")),
            ),
        )
        pending_command = exists(
            select(ChapterWorkflowCommand.id).where(
                ChapterWorkflowCommand.run_id == ChapterWorkflowRun.id,
                ChapterWorkflowCommand.status == "pending",
            )
        )
        query = (
            select(ChapterWorkflowRun)
            .join(BackgroundTask, BackgroundTask.id == ChapterWorkflowRun.root_job_id)
            .where(
                or_(
                    ChapterWorkflowRun.is_active.is_(True),
                    not_(valid_status_pair),
                    pending_command,
                )
            )
            .order_by(ChapterWorkflowRun.id)
            .limit(limit)
        )
        if after_run_id is not None:
            query = query.where(ChapterWorkflowRun.id > after_run_id)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def get_command(
        self,
        command_id: str,
    ) -> Optional[ChapterWorkflowCommand]:
        result = await self.session.execute(
            select(ChapterWorkflowCommand).where(ChapterWorkflowCommand.id == command_id)
        )
        return result.scalars().first()

    async def get_command_for_update(
        self,
        command_id: str,
    ) -> Optional[ChapterWorkflowCommand]:
        """在 root JobRun、workflow run 与 Chapter 之后锁定 command。"""

        result = await self.session.execute(
            select(ChapterWorkflowCommand)
            .where(ChapterWorkflowCommand.id == command_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def list_pending_commands_for_update(
        self,
        run_id: str,
    ) -> list[ChapterWorkflowCommand]:
        result = await self.session.execute(
            select(ChapterWorkflowCommand)
            .where(
                ChapterWorkflowCommand.run_id == run_id,
                ChapterWorkflowCommand.status == "pending",
            )
            .order_by(ChapterWorkflowCommand.created_at, ChapterWorkflowCommand.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(result.scalars())

    async def list_commands_for_update(
        self,
        run_id: str,
    ) -> list[ChapterWorkflowCommand]:
        result = await self.session.execute(
            select(ChapterWorkflowCommand)
            .where(ChapterWorkflowCommand.run_id == run_id)
            .order_by(ChapterWorkflowCommand.created_at, ChapterWorkflowCommand.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(result.scalars())

    async def get_applied_retry_for_expected_state(
        self,
        *,
        run_id: str,
        expected_run_revision: int,
        expected_chapter_revision: int,
        expected_checkpoint_id: str,
    ) -> Optional[ChapterWorkflowCommand]:
        """返回同一前置状态已经选定的唯一 retry target。"""

        result = await self.session.execute(
            select(ChapterWorkflowCommand)
            .where(
                ChapterWorkflowCommand.run_id == run_id,
                ChapterWorkflowCommand.type == "retry",
                ChapterWorkflowCommand.status == "applied",
                ChapterWorkflowCommand.expected_run_revision == expected_run_revision,
                ChapterWorkflowCommand.expected_chapter_revision == expected_chapter_revision,
                ChapterWorkflowCommand.expected_checkpoint_id == expected_checkpoint_id,
            )
            .order_by(ChapterWorkflowCommand.created_at, ChapterWorkflowCommand.id)
            .limit(1)
        )
        return result.scalars().first()

    async def get_observability_values(
        self,
        *,
        window_started_at: datetime,
    ) -> dict[str, object]:
        """聚合 workflow current row 与保留期内的公开审计事件。"""

        state_rows = list(
            (
                await self.session.execute(
                    select(
                        ChapterWorkflowRun.status,
                        func.count(ChapterWorkflowRun.id),
                        func.min(ChapterWorkflowRun.updated_at),
                    ).group_by(ChapterWorkflowRun.status)
                )
            ).all()
        )
        active_row = (
            await self.session.execute(
                select(
                    func.count(ChapterWorkflowRun.id),
                    func.min(ChapterWorkflowRun.created_at),
                ).where(ChapterWorkflowRun.is_active.is_(True))
            )
        ).one()

        waiting_event_status = JobEvent.payload["workflow"]["status"].as_string()
        latest_waiting_event = (
            select(
                JobEvent.stream_id.label("run_id"),
                waiting_event_status.label("status"),
                func.max(JobEvent.created_at).label("entered_at"),
            )
            .where(
                JobEvent.stream_type == "workflow",
                JobEvent.event_type == "workflow.waiting",
            )
            .group_by(JobEvent.stream_id, waiting_event_status)
            .subquery()
        )
        waiting_state_rows = list(
            (
                await self.session.execute(
                    select(
                        ChapterWorkflowRun.status,
                        func.count(ChapterWorkflowRun.id),
                        func.min(
                            func.coalesce(
                                latest_waiting_event.c.entered_at,
                                ChapterWorkflowRun.updated_at,
                            )
                        ),
                    )
                    .join(
                        BackgroundTask,
                        BackgroundTask.id == ChapterWorkflowRun.root_job_id,
                    )
                    .outerjoin(
                        latest_waiting_event,
                        and_(
                            latest_waiting_event.c.run_id == ChapterWorkflowRun.id,
                            latest_waiting_event.c.status == ChapterWorkflowRun.status,
                        ),
                    )
                    .where(
                        BackgroundTask.status == "waiting",
                        ChapterWorkflowRun.status.in_(
                            ("waiting_for_selection", "projection_pending")
                        ),
                    )
                    .group_by(ChapterWorkflowRun.status)
                )
            ).all()
        )

        workflow_payload = JobEvent.payload["workflow"]
        command_payload = workflow_payload["command"]
        command_type = command_payload["type"].as_string()
        rejection_code = command_payload["rejection_code"].as_string()
        rejection_rows = list(
            (
                await self.session.execute(
                    select(command_type, rejection_code, func.count(JobEvent.cursor))
                    .where(
                        JobEvent.stream_type == "workflow",
                        JobEvent.event_type == "workflow.command.rejected",
                        JobEvent.created_at >= window_started_at,
                    )
                    .group_by(command_type, rejection_code)
                )
            ).all()
        )

        reconciliation_reason = workflow_payload["reason_code"].as_string()
        reconciliation_rows = list(
            (
                await self.session.execute(
                    select(reconciliation_reason, func.count(JobEvent.cursor))
                    .where(
                        JobEvent.stream_type == "workflow",
                        JobEvent.event_type == "workflow.reconciled",
                        JobEvent.created_at >= window_started_at,
                    )
                    .group_by(reconciliation_reason)
                )
            ).all()
        )
        return {
            "state_rows": state_rows,
            "active_row": tuple(active_row),
            "waiting_state_rows": waiting_state_rows,
            "rejection_rows": rejection_rows,
            "reconciliation_rows": reconciliation_rows,
        }

    async def list_retention_candidates(
        self,
        *,
        before: datetime,
        after_run_id: str | None,
        limit: int,
    ) -> list[ChapterWorkflowRun]:
        """按稳定游标返回仍有 checkpoint 或私有 payload 的过期 terminal run。"""

        empty_json = cast(literal("{}"), JSONB)
        null_json = cast(literal("null"), JSONB)
        command_private_payload = exists(
            select(ChapterWorkflowCommand.id).where(
                ChapterWorkflowCommand.run_id == ChapterWorkflowRun.id,
                or_(
                    cast(ChapterWorkflowCommand.payload, JSONB) != empty_json,
                    cast(ChapterWorkflowCommand.result_payload, JSONB) != null_json,
                ),
            )
        )
        activity_private_payload = exists(
            select(JobActivity.id).where(
                JobActivity.job_id == ChapterWorkflowRun.root_job_id,
                or_(
                    cast(JobActivity.request_payload, JSONB) != empty_json,
                    cast(JobActivity.result_payload, JSONB) != null_json,
                ),
            )
        )
        query = (
            select(ChapterWorkflowRun)
            .join(BackgroundTask, BackgroundTask.id == ChapterWorkflowRun.root_job_id)
            .where(
                ChapterWorkflowRun.is_active.is_(False),
                ChapterWorkflowRun.status.in_(("successful", "failed", "cancelled", "superseded")),
                ChapterWorkflowRun.completed_at.is_not(None),
                ChapterWorkflowRun.completed_at < before,
                ChapterWorkflowRun.successor_run_id.is_(None),
                BackgroundTask.status.in_(("succeeded", "failed", "dead_letter", "cancelled")),
                BackgroundTask.completed_at.is_not(None),
                BackgroundTask.completed_at < before,
                not_(
                    exists(
                        select(ChapterWorkflowCommand.id).where(
                            ChapterWorkflowCommand.run_id == ChapterWorkflowRun.id,
                            ChapterWorkflowCommand.status == "pending",
                        )
                    )
                ),
                or_(
                    ChapterWorkflowRun.checkpoint_id.is_not(None),
                    command_private_payload,
                    activity_private_payload,
                ),
            )
            .order_by(ChapterWorkflowRun.id)
            .limit(limit)
        )
        if after_run_id is not None:
            query = query.where(ChapterWorkflowRun.id > after_run_id)
        result = await self.session.execute(query)
        return list(result.scalars())

    async def list_revision_workflow_stream_ids(
        self,
        *,
        chapter_id: int,
        revision: int,
    ) -> set[str]:
        """读取 canonical revision 的 workflow lineage，供 retention fail closed。"""

        result = await self.session.execute(
            select(ChapterOutboxEvent.workflow_stream_id).where(
                ChapterOutboxEvent.chapter_id == chapter_id,
                ChapterOutboxEvent.revision == revision,
                ChapterOutboxEvent.workflow_stream_type == "workflow",
                ChapterOutboxEvent.workflow_stream_id.is_not(None),
            )
        )
        return {stream_id for stream_id in result.scalars() if stream_id}

    async def list_checkpoint_runs_for_observability(self) -> list[ChapterWorkflowRun]:
        result = await self.session.execute(
            select(ChapterWorkflowRun)
            .where(
                ChapterWorkflowRun.is_active.is_(True),
                ChapterWorkflowRun.status.in_(
                    ("waiting_for_selection", "projection_pending", "needs_attention")
                ),
            )
            .order_by(ChapterWorkflowRun.id)
        )
        return list(result.scalars())
