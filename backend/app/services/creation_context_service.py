# AIMETA P=创作上下文服务_跨设备语义恢复|R=归属校验_轮次保护_事务提交|NR=不含页面路由或本地缓存|E=CreationContextService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.creation_context import UserCreationContext
from ..repositories.creation_context_repository import CreationContextRepository
from ..schemas.creation_context import CreationContextPatch
from .novel_service import NovelService


class CreationContextService:
    """维护每用户、每项目的跨设备创作位置。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = CreationContextRepository(session)

    async def list_contexts(self, *, user_id: int) -> list[UserCreationContext]:
        return await self.repo.list_by_user(user_id)

    async def patch_context(
        self,
        *,
        user_id: int,
        project_id: str,
        patch: CreationContextPatch,
    ) -> UserCreationContext:
        await NovelService(self.session)._ensure_project_owner_light(project_id, user_id)
        if await self.repo.lock_project(project_id) is None:
            raise ValueError("项目不存在")

        values = patch.model_dump(exclude_unset=True)
        if "inspiration_turn" in values:
            authoritative_turn = await self.repo.get_authoritative_inspiration_turn(project_id)
            requested_turn = values["inspiration_turn"]
            if requested_turn > authoritative_turn:
                await self.session.rollback()
                raise ValueError("灵感轮次无效")
            if requested_turn < authoritative_turn:
                values["inspiration_draft"] = None
                values["inspiration_turn"] = authoritative_turn

        context = await self.repo.upsert_fields(
            user_id=user_id,
            project_id=project_id,
            values=values,
        )
        await self.session.commit()
        return context
