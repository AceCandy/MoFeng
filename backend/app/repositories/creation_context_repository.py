# AIMETA P=创作上下文仓库_语义位置数据访问|R=用户列表_项目锁_字段级upsert|NR=不含鉴权或事务提交|E=CreationContextRepository|X=internal|A=仓库类|D=sqlalchemy|S=db|RD=./README.ai
from typing import Any, Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ..models.creation_context import UserCreationContext
from ..models.novel import NovelConversation, NovelProject
from .base import BaseRepository


class CreationContextRepository(BaseRepository[UserCreationContext]):
    model = UserCreationContext

    async def list_by_user(self, user_id: int) -> list[UserCreationContext]:
        result = await self.session.execute(
            select(UserCreationContext)
            .where(UserCreationContext.user_id == user_id)
            .order_by(UserCreationContext.updated_at.desc(), UserCreationContext.project_id.asc())
        )
        return list(result.scalars().all())

    async def lock_project(self, project_id: str) -> Optional[int]:
        """用项目行串行化对话推进与同项目草稿写入。"""

        return await self.session.scalar(
            select(NovelProject.user_id).where(NovelProject.id == project_id).with_for_update()
        )

    async def get_authoritative_inspiration_turn(self, project_id: str) -> int:
        value = await self.session.scalar(
            select(func.count(NovelConversation.id)).where(
                NovelConversation.project_id == project_id,
                NovelConversation.role == "assistant",
            )
        )
        return int(value or 0)

    async def upsert_fields(
        self,
        *,
        user_id: int,
        project_id: str,
        values: dict[str, Any],
    ) -> UserCreationContext:
        insert_stmt = pg_insert(UserCreationContext).values(
            user_id=user_id,
            project_id=project_id,
            **values,
        )
        update_values = {name: getattr(insert_stmt.excluded, name) for name in values}
        update_values["updated_at"] = func.now()
        stmt = insert_stmt.on_conflict_do_update(
            index_elements=[UserCreationContext.user_id, UserCreationContext.project_id],
            set_=update_values,
        ).returning(UserCreationContext)
        context = (await self.session.execute(stmt)).scalar_one_or_none()
        if context is not None:
            return context
        existing = await self.get(user_id=user_id, project_id=project_id)
        if existing is None:
            raise RuntimeError("创作上下文 upsert 未返回记录")
        return existing

    async def advance_inspiration_turn(
        self,
        *,
        user_id: int,
        project_id: str,
        turn: int,
    ) -> None:
        """对话推进时原子清空旧轮次草稿。"""

        await self.session.execute(
            update(UserCreationContext)
            .where(
                UserCreationContext.user_id == user_id,
                UserCreationContext.project_id == project_id,
                or_(
                    UserCreationContext.inspiration_turn.is_(None),
                    UserCreationContext.inspiration_turn < turn,
                ),
            )
            .values(
                inspiration_draft=None,
                inspiration_turn=turn,
                updated_at=func.now(),
            )
        )
