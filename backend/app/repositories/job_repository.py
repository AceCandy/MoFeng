# AIMETA P=持久任务仓库_任务与事件查询|R=幂等查询_事件追加_游标读取|NR=不含事务提交|E=JobRepository|X=internal|A=repository|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..models.background_task import BackgroundTask
from ..models.chapter_generation_trace import (
    ChapterGenerationTraceProjectionCheckpoint,
)
from ..models.job import (
    AIUsageRecord,
    JobActivity,
    JobEvent,
    JobEventRetention,
    JobEventStream,
    JobExecutorControl,
    JobWorkerHeartbeat,
)
from ..models.novel import NovelProject
from .base import BaseRepository
from .chapter_generation_trace_projection_repository import (
    CHAPTER_GENERATION_TRACE_PROJECTOR_NAME,
)


class JobRepository(BaseRepository[BackgroundTask]):
    """持久任务数据访问；事务边界由 JobService 持有。"""

    model = BackgroundTask

    async def get_by_idempotency_key(
        self,
        *,
        user_id: int,
        job_type: str,
        idempotency_key: str,
    ) -> Optional[BackgroundTask]:
        result = await self.session.execute(
            select(BackgroundTask).where(
                BackgroundTask.user_id == user_id,
                BackgroundTask.task_type == job_type,
                BackgroundTask.idempotency_key == idempotency_key,
            )
        )
        return result.scalars().first()

    async def get_for_update(self, job_id: str) -> Optional[BackgroundTask]:
        result = await self.session.execute(
            select(BackgroundTask)
            .where(BackgroundTask.id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_user_job_for_update(
        self,
        job_id: str,
        *,
        user_id: int,
    ) -> Optional[BackgroundTask]:
        result = await self.session.execute(
            select(BackgroundTask)
            .where(
                BackgroundTask.id == job_id,
                BackgroundTask.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_user_job(
        self,
        job_id: str,
        *,
        user_id: int,
    ) -> Optional[BackgroundTask]:
        result = await self.session.execute(
            select(BackgroundTask).where(
                BackgroundTask.id == job_id,
                BackgroundTask.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def is_project_owned_by_user(
        self,
        *,
        project_id: str,
        user_id: int,
    ) -> bool:
        result = await self.session.execute(
            select(NovelProject.id).where(
                NovelProject.id == project_id,
                NovelProject.user_id == user_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def list_user_jobs(
        self,
        *,
        user_id: int,
        limit: int,
    ) -> list[BackgroundTask]:
        result = await self.session.execute(
            select(BackgroundTask)
            .where(BackgroundTask.user_id == user_id)
            .order_by(BackgroundTask.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_user_snapshot(
        self,
        *,
        user_id: int,
        limit: int,
    ) -> tuple[list[BackgroundTask], int]:
        """用单条语句读取任务与游标，确保二者来自同一 MVCC snapshot。"""

        event_cursor = (
            select(func.coalesce(func.max(JobEvent.cursor), 0))
            .where(JobEvent.user_id == user_id)
            .scalar_subquery()
        )
        retention_cursor = (
            select(JobEventRetention.retained_through_cursor)
            .where(JobEventRetention.user_id == user_id)
            .scalar_subquery()
        )
        cursor_query = select(
            func.greatest(
                event_cursor,
                func.coalesce(retention_cursor, 0),
            ).label("resume_cursor")
        ).subquery()
        result = await self.session.execute(
            select(BackgroundTask, cursor_query.c.resume_cursor)
            .select_from(cursor_query)
            .outerjoin(BackgroundTask, BackgroundTask.user_id == user_id)
            .order_by(BackgroundTask.created_at.desc().nulls_last())
            .limit(limit)
        )
        rows = result.all()
        resume_cursor = int(rows[0][1])
        jobs = [row[0] for row in rows if row[0] is not None]
        return jobs, resume_cursor

    async def get_or_create_stream_for_update(
        self,
        *,
        stream_type: str,
        stream_id: str,
        user_id: int,
        project_id: Optional[str],
    ) -> JobEventStream:
        await self.session.execute(
            pg_insert(JobEventStream)
            .values(
                stream_type=stream_type,
                stream_id=stream_id,
                user_id=user_id,
                project_id=project_id,
                last_sequence=0,
            )
            .on_conflict_do_nothing(index_elements=["stream_type", "stream_id"])
        )
        result = await self.session.execute(
            select(JobEventStream)
            .where(
                JobEventStream.stream_type == stream_type,
                JobEventStream.stream_id == stream_id,
            )
            .with_for_update()
        )
        return result.scalar_one()

    async def get_user_stream(
        self,
        *,
        stream_type: str,
        stream_id: str,
        user_id: int,
    ) -> Optional[JobEventStream]:
        result = await self.session.execute(
            select(JobEventStream).where(
                JobEventStream.stream_type == stream_type,
                JobEventStream.stream_id == stream_id,
                JobEventStream.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_user_stream_snapshot(
        self,
        *,
        user_id: int,
        stream_type: str,
        stream_id: str,
        limit: int,
    ) -> Optional[tuple[list[BackgroundTask], int, int]]:
        """在同一 MVCC snapshot 中读取授权流、current jobs 与 resume cursor。"""

        stream_scope = (
            select(
                JobEventStream.last_sequence,
                JobEventStream.retained_through_cursor,
            )
            .where(
                JobEventStream.stream_type == stream_type,
                JobEventStream.stream_id == stream_id,
                JobEventStream.user_id == user_id,
            )
            .subquery()
        )
        event_cursor = (
            select(func.coalesce(func.max(JobEvent.cursor), 0))
            .where(
                JobEvent.stream_type == stream_type,
                JobEvent.stream_id == stream_id,
                JobEvent.user_id == user_id,
            )
            .scalar_subquery()
        )
        resume_cursor = func.greatest(
            event_cursor,
            stream_scope.c.retained_through_cursor,
        ).label("resume_cursor")
        result = await self.session.execute(
            select(
                BackgroundTask,
                resume_cursor,
                stream_scope.c.last_sequence,
            )
            .select_from(stream_scope)
            .outerjoin(
                BackgroundTask,
                and_(
                    BackgroundTask.user_id == user_id,
                    BackgroundTask.stream_type == stream_type,
                    BackgroundTask.stream_id == stream_id,
                ),
            )
            .order_by(BackgroundTask.created_at.desc().nulls_last())
            .limit(limit)
        )
        rows = result.all()
        if not rows:
            return None
        jobs = [row[0] for row in rows if row[0] is not None]
        return jobs, int(rows[0][1]), int(rows[0][2])

    async def get_retained_through_cursor(self, *, user_id: int) -> int:
        result = await self.session.execute(
            select(JobEventRetention.retained_through_cursor).where(
                JobEventRetention.user_id == user_id
            )
        )
        return int(result.scalar_one_or_none() or 0)

    async def claim_candidate(
        self,
        *,
        now: datetime,
        active_generation: int,
    ) -> Optional[BackgroundTask]:
        ready = and_(
            BackgroundTask.status.in_(("queued", "retry_wait")),
            BackgroundTask.available_at <= now,
            BackgroundTask.executor_generation == active_generation,
            BackgroundTask.cancel_requested_at.is_(None),
        )
        expired = and_(
            BackgroundTask.status == "running",
            BackgroundTask.lease_expires_at.is_not(None),
            BackgroundTask.lease_expires_at <= now,
        )
        result = await self.session.execute(
            select(BackgroundTask)
            .where(or_(ready, expired))
            .order_by(BackgroundTask.available_at.asc(), BackgroundTask.created_at.asc())
            .with_for_update(skip_locked=True)
            .execution_options(populate_existing=True)
            .limit(1)
        )
        return result.scalars().first()

    async def get_executor_control(
        self,
        *,
        for_update: bool = False,
    ) -> Optional[JobExecutorControl]:
        query = select(JobExecutorControl).where(JobExecutorControl.scope == "default")
        if for_update:
            query = query.with_for_update()
        result = await self.session.execute(query)
        return result.scalars().first()

    async def reassign_waiting_jobs(
        self,
        *,
        previous_generation: int,
        new_generation: int,
    ) -> int:
        result = await self.session.execute(
            update(BackgroundTask)
            .where(
                BackgroundTask.executor_generation == previous_generation,
                BackgroundTask.status.in_(("queued", "retry_wait", "waiting")),
            )
            .values(executor_generation=new_generation)
        )
        return int(result.rowcount or 0)

    async def has_unresolved_ambiguous_activity(self, *, job_id: str) -> bool:
        result = await self.session.execute(
            select(JobActivity.id)
            .where(
                JobActivity.job_id == job_id,
                JobActivity.side_effect_class == "ambiguous_external",
                JobActivity.status.in_(("started", "ambiguous")),
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_worker_heartbeat_for_update(
        self,
        *,
        worker_id: str,
    ) -> Optional[JobWorkerHeartbeat]:
        result = await self.session.execute(
            select(JobWorkerHeartbeat)
            .where(JobWorkerHeartbeat.worker_id == worker_id)
            .with_for_update()
        )
        return result.scalars().first()

    async def get_latest_worker_heartbeat(
        self,
        *,
        executor_generation: int,
        worker_id: Optional[str] = None,
    ) -> Optional[JobWorkerHeartbeat]:
        query = select(JobWorkerHeartbeat).where(
            JobWorkerHeartbeat.executor_generation == executor_generation
        )
        if worker_id is not None:
            query = query.where(JobWorkerHeartbeat.worker_id == worker_id)
        result = await self.session.execute(
            query.order_by(JobWorkerHeartbeat.heartbeat_at.desc()).limit(1)
        )
        return result.scalars().first()

    async def add_worker_heartbeat(
        self,
        heartbeat: JobWorkerHeartbeat,
    ) -> JobWorkerHeartbeat:
        self.session.add(heartbeat)
        await self.session.flush()
        return heartbeat

    async def add_event(self, event: JobEvent) -> JobEvent:
        self.session.add(event)
        await self.session.flush()
        return event

    async def get_activity_for_update(
        self,
        *,
        job_id: str,
        activity_key: str,
    ) -> Optional[JobActivity]:
        result = await self.session.execute(
            select(JobActivity)
            .where(
                JobActivity.job_id == job_id,
                JobActivity.activity_key == activity_key,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def get_activity(
        self,
        *,
        job_id: str,
        activity_key: str,
    ) -> Optional[JobActivity]:
        result = await self.session.execute(
            select(JobActivity).where(
                JobActivity.job_id == job_id,
                JobActivity.activity_key == activity_key,
            )
        )
        return result.scalars().first()

    async def get_latest_manual_retry_for_update(
        self,
        *,
        job_id: str,
        logical_step_key: str,
    ) -> Optional[JobActivity]:
        result = await self.session.execute(
            select(JobActivity)
            .where(
                JobActivity.job_id == job_id,
                JobActivity.activity_key.like("manual_retry:%"),
                JobActivity.side_effect_class == "ambiguous_external",
                JobActivity.status.in_(
                    ("manual_retry_pending", "started", "ambiguous", "succeeded")
                ),
                JobActivity.request_payload["logical_step_key"].as_string() == logical_step_key,
            )
            .order_by(JobActivity.updated_at.desc(), JobActivity.id.desc())
            .limit(1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return result.scalars().first()

    async def list_activities_for_update(self, *, job_id: str) -> list[JobActivity]:
        result = await self.session.execute(
            select(JobActivity)
            .where(JobActivity.job_id == job_id)
            .order_by(JobActivity.activity_key, JobActivity.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return list(result.scalars())

    async def list_ambiguous_activities(self, *, job_id: str) -> list[JobActivity]:
        result = await self.session.execute(
            select(JobActivity)
            .where(
                JobActivity.job_id == job_id,
                JobActivity.side_effect_class == "ambiguous_external",
                JobActivity.status == "ambiguous",
            )
            .order_by(JobActivity.activity_key, JobActivity.id)
        )
        return list(result.scalars())

    async def add_activity(self, activity: JobActivity) -> JobActivity:
        self.session.add(activity)
        await self.session.flush()
        return activity

    async def add_ai_usage(self, usage: AIUsageRecord) -> AIUsageRecord:
        self.session.add(usage)
        await self.session.flush()
        return usage

    async def list_events(
        self,
        *,
        user_id: int,
        after_cursor: int,
        limit: int,
    ) -> list[JobEvent]:
        result = await self.session.execute(
            select(JobEvent)
            .where(JobEvent.user_id == user_id, JobEvent.cursor > after_cursor)
            .order_by(JobEvent.cursor.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_stream_events(
        self,
        *,
        user_id: int,
        stream_type: str,
        stream_id: str,
        after_cursor: int,
        limit: int,
    ) -> list[JobEvent]:
        result = await self.session.execute(
            select(JobEvent)
            .where(
                JobEvent.user_id == user_id,
                JobEvent.stream_type == stream_type,
                JobEvent.stream_id == stream_id,
                JobEvent.cursor > after_cursor,
            )
            .order_by(JobEvent.cursor.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def delete_events_before(
        self,
        *,
        before: datetime,
    ) -> tuple[int, list[int]]:
        """删除过期事件，并在同一事务推进用户与 stream retention 水位。"""

        projected_through_cursor = await self.session.scalar(
            select(ChapterGenerationTraceProjectionCheckpoint.last_event_cursor).where(
                ChapterGenerationTraceProjectionCheckpoint.projector_name
                == CHAPTER_GENERATION_TRACE_PROJECTOR_NAME
            )
        )
        if projected_through_cursor is None:
            return 0, []
        eligible_event = (
            JobEvent.created_at < before,
            JobEvent.cursor <= projected_through_cursor,
        )
        result = await self.session.execute(
            select(JobEvent.user_id, func.max(JobEvent.cursor))
            .where(*eligible_event)
            .group_by(JobEvent.user_id)
        )
        watermarks = [
            {
                "user_id": int(user_id),
                "retained_through_cursor": int(cursor),
            }
            for user_id, cursor in result.all()
        ]
        if not watermarks:
            return 0, []

        stmt = pg_insert(JobEventRetention).values(watermarks)
        stmt = stmt.on_conflict_do_update(
            index_elements=[JobEventRetention.user_id],
            set_={
                "retained_through_cursor": func.greatest(
                    JobEventRetention.retained_through_cursor,
                    stmt.excluded.retained_through_cursor,
                ),
                "updated_at": func.now(),
            },
        )
        await self.session.execute(stmt)

        stream_watermarks = (
            select(
                JobEvent.stream_type.label("stream_type"),
                JobEvent.stream_id.label("stream_id"),
                func.max(JobEvent.cursor).label("retained_through_cursor"),
            )
            .where(*eligible_event)
            .group_by(JobEvent.stream_type, JobEvent.stream_id)
            .subquery()
        )
        await self.session.execute(
            update(JobEventStream)
            .where(
                JobEventStream.stream_type == stream_watermarks.c.stream_type,
                JobEventStream.stream_id == stream_watermarks.c.stream_id,
            )
            .values(
                retained_through_cursor=func.greatest(
                    JobEventStream.retained_through_cursor,
                    stream_watermarks.c.retained_through_cursor,
                ),
                updated_at=func.now(),
            )
        )
        delete_result = await self.session.execute(delete(JobEvent).where(*eligible_event))
        return int(delete_result.rowcount or 0), [item["user_id"] for item in watermarks]

    async def get_runtime_metric_values(self, *, now: datetime) -> dict[str, object]:
        status_result = await self.session.execute(
            select(BackgroundTask.status, func.count(BackgroundTask.id)).group_by(
                BackgroundTask.status
            )
        )
        status_counts = {str(status): int(count) for status, count in status_result.all()}
        oldest_queued_at = await self.session.scalar(
            select(func.min(BackgroundTask.created_at)).where(
                BackgroundTask.status.in_(("queued", "retry_wait"))
            )
        )
        expired_leases = await self.session.scalar(
            select(func.count(BackgroundTask.id)).where(
                BackgroundTask.status == "running",
                BackgroundTask.lease_expires_at.is_not(None),
                BackgroundTask.lease_expires_at <= now,
            )
        )
        latest_event_cursor = await self.session.scalar(
            select(func.coalesce(func.max(JobEvent.cursor), 0))
        )
        projected_event_cursor = await self.session.scalar(
            select(
                func.coalesce(ChapterGenerationTraceProjectionCheckpoint.last_event_cursor, 0)
            ).where(
                ChapterGenerationTraceProjectionCheckpoint.projector_name
                == CHAPTER_GENERATION_TRACE_PROJECTOR_NAME
            )
        )
        projected_cursor = int(projected_event_cursor or 0)
        oldest_unprojected_event_at = await self.session.scalar(
            select(func.min(JobEvent.created_at)).where(JobEvent.cursor > projected_cursor)
        )
        retained_event_count = await self.session.scalar(select(func.count(JobEvent.cursor)))
        retained_event_bytes = await self.session.scalar(
            select(func.coalesce(func.sum(func.pg_column_size(JobEvent.payload)), 0))
        )
        retention_users = await self.session.scalar(select(func.count(JobEventRetention.user_id)))
        return {
            "status_counts": status_counts,
            "oldest_queued_at": oldest_queued_at,
            "expired_leases": int(expired_leases or 0),
            "latest_event_cursor": int(latest_event_cursor or 0),
            "projected_event_cursor": projected_cursor,
            "oldest_unprojected_event_at": oldest_unprojected_event_at,
            "retained_event_count": int(retained_event_count or 0),
            "retained_event_bytes": int(retained_event_bytes or 0),
            "retention_users": int(retention_users or 0),
        }
