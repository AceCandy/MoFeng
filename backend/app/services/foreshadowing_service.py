# AIMETA P=伏笔服务_伏笔管理业务逻辑|R=伏笔CRUD_回收追踪|NR=不含自动分析|E=ForeshadowingService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
"""伏笔管理服务"""
import logging
from typing import List, Optional, Dict
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.foreshadowing import (
    Foreshadowing,
    ForeshadowingReminder,
)

logger = logging.getLogger(__name__)

ACTIVE_FORESHADOWING_STATUSES = ("planted", "developing", "partial")
ABANDONED_FORESHADOWING_STATUS = "abandoned"


class ForeshadowingService:
    """伏笔管理服务"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_foreshadowings(
        self,
        project_id: str,
        status: Optional[str] = None,
        foreshadowing_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[List[Foreshadowing], int]:
        """获取伏笔列表"""
        query = select(Foreshadowing).where(
            Foreshadowing.project_id == project_id,
            Foreshadowing.is_active.is_(True),
        )

        if status:
            query = query.where(Foreshadowing.status == status)
        if foreshadowing_type:
            query = query.where(Foreshadowing.type == foreshadowing_type)

        # 获取总数
        count_query = select(func.count()).select_from(Foreshadowing).where(
            Foreshadowing.project_id == project_id,
            Foreshadowing.is_active.is_(True),
        )
        if status:
            count_query = count_query.where(Foreshadowing.status == status)
        if foreshadowing_type:
            count_query = count_query.where(Foreshadowing.type == foreshadowing_type)

        total = await self.session.scalar(count_query)

        # 分页
        query = query.order_by(Foreshadowing.chapter_number).limit(limit).offset(offset)
        result = await self.session.execute(query)
        foreshadowings = result.scalars().all()

        return foreshadowings, total

    async def abandon_foreshadowing(
        self,
        foreshadowing_id: int,
        reason: Optional[str] = None,
    ) -> Foreshadowing:
        """放弃伏笔"""
        foreshadowing = (
            await self.session.execute(
                select(Foreshadowing).where(
                    Foreshadowing.id == foreshadowing_id,
                    Foreshadowing.is_active.is_(True),
                )
            )
        ).scalars().first()
        if not foreshadowing:
            raise ValueError(f"伏笔不存在: {foreshadowing_id}")

        foreshadowing.status = ABANDONED_FORESHADOWING_STATUS
        if reason:
            foreshadowing.author_note = f"{foreshadowing.author_note or ''}\n[放弃原因]: {reason}".strip()

        await self.session.flush()
        logger.info(f"放弃伏笔: foreshadowing={foreshadowing_id}")
        return foreshadowing

    async def get_unresolved_foreshadowings(
        self,
        project_id: str,
        current_chapter_number: int,
    ) -> List[Foreshadowing]:
        """获取未回收的伏笔"""
        query = select(Foreshadowing).where(
            and_(
                Foreshadowing.project_id == project_id,
                Foreshadowing.status.in_(ACTIVE_FORESHADOWING_STATUSES),
                Foreshadowing.chapter_number < current_chapter_number,
                Foreshadowing.is_active.is_(True),
            )
        ).order_by(Foreshadowing.chapter_number)

        result = await self.session.execute(query)
        return result.scalars().all()

    async def create_reminder(
        self,
        project_id: str,
        foreshadowing_id: int,
        reminder_type: str,
        message: str,
        suggested_chapter_range: Optional[Dict[str, int]] = None,
    ) -> ForeshadowingReminder:
        """创建提醒"""
        reminder = ForeshadowingReminder(
            project_id=project_id,
            foreshadowing_id=foreshadowing_id,
            reminder_type=reminder_type,
            message=message,
            suggested_chapter_range=suggested_chapter_range,
        )
        self.session.add(reminder)
        await self.session.flush()
        logger.info(f"创建提醒: foreshadowing={foreshadowing_id}, type={reminder_type}")
        return reminder

    async def check_and_create_reminders(
        self,
        project_id: str,
        current_chapter_number: int,
        total_chapters: int,
    ) -> List[ForeshadowingReminder]:
        """检查并创建提醒"""
        reminders = []

        # 获取未回收的伏笔
        unresolved = await self.get_unresolved_foreshadowings(project_id, current_chapter_number)

        for foreshadowing in unresolved:
            # 检查是否已有活跃提醒
            existing_query = select(ForeshadowingReminder).where(
                and_(
                    ForeshadowingReminder.foreshadowing_id == foreshadowing.id,
                    ForeshadowingReminder.status == "active",
                )
            )
            existing = await self.session.scalar(existing_query)
            if existing:
                continue

            # 长期未提及提醒
            distance = current_chapter_number - foreshadowing.chapter_number
            if distance > 10:
                reminder = await self.create_reminder(
                    project_id=project_id,
                    foreshadowing_id=foreshadowing.id,
                    reminder_type="long_time_no_mention",
                    message=f"第 {foreshadowing.chapter_number} 章埋下的伏笔已有 {distance} 章未提及，是否打算在后续章节中解答？",
                    suggested_chapter_range={
                        "start": current_chapter_number + 1,
                        "end": min(current_chapter_number + 5, total_chapters),
                    },
                )
                reminders.append(reminder)

            # 接近结局提醒
            if current_chapter_number > total_chapters * 0.8:
                reminder = await self.create_reminder(
                    project_id=project_id,
                    foreshadowing_id=foreshadowing.id,
                    reminder_type="unresolved",
                    message=f"小说即将结束，第 {foreshadowing.chapter_number} 章的伏笔仍未回收",
                )
                reminders.append(reminder)

        return reminders
