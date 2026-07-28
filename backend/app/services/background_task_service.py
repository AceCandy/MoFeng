# AIMETA P=后台任务兼容服务_旧查询入口|R=兼容创建与查询_委托durable_job|NR=不直接流转任务状态|E=BackgroundTaskService|X=internal|A=compat_facade|D=job_service|S=db|RD=./README.ai
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.background_task import BackgroundTask
from .job_service import JobService


class BackgroundTaskService:
    """旧 task API 的兼容 facade；状态流转统一由 JobService 持有。"""

    def __init__(self, session: AsyncSession):
        self.jobs = JobService(session)

    async def create_task(
        self,
        *,
        user_id: int,
        task_type: str,
        title: str,
        project_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> BackgroundTask:
        return await self.jobs.enqueue_job(
            user_id=user_id,
            job_type=task_type,
            title=title,
            project_id=project_id,
            payload=payload or {},
        )

    async def get_user_task(self, task_id: str, *, user_id: int) -> Optional[BackgroundTask]:
        return await self.jobs.get_user_task(task_id, user_id=user_id)

    async def list_user_tasks(self, *, user_id: int, limit: int = 20) -> list[BackgroundTask]:
        return await self.jobs.list_user_tasks(user_id=user_id, limit=limit)
