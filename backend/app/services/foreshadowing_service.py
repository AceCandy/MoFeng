# AIMETA P=伏笔服务_伏笔管理业务逻辑|R=伏笔CRUD_回收追踪|NR=不含自动分析|E=ForeshadowingService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
"""伏笔管理服务"""

import logging
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.foreshadowing import Foreshadowing

logger = logging.getLogger(__name__)

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
        count_query = (
            select(func.count())
            .select_from(Foreshadowing)
            .where(
                Foreshadowing.project_id == project_id,
                Foreshadowing.is_active.is_(True),
            )
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
            (
                await self.session.execute(
                    select(Foreshadowing).where(
                        Foreshadowing.id == foreshadowing_id,
                        Foreshadowing.is_active.is_(True),
                    )
                )
            )
            .scalars()
            .first()
        )
        if not foreshadowing:
            raise ValueError(f"伏笔不存在: {foreshadowing_id}")

        foreshadowing.status = ABANDONED_FORESHADOWING_STATUS
        if reason:
            foreshadowing.author_note = (
                f"{foreshadowing.author_note or ''}\n[放弃原因]: {reason}".strip()
            )

        await self.session.flush()
        logger.info(f"放弃伏笔: foreshadowing={foreshadowing_id}")
        return foreshadowing
