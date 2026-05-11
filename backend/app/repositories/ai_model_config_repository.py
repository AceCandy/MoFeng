# AIMETA P=个人AI模型配置仓库_供应商模型阶段路由查询|R=配置CRUD|NR=不含业务逻辑|E=AIModelConfigRepository|X=internal|A=仓库类|D=sqlalchemy|S=db|RD=./README.ai
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models import UserAIModel, UserAIStageRoute, UserModelProvider


class UserModelProviderRepository(BaseRepository[UserModelProvider]):
    model = UserModelProvider

    async def list_by_user(self, user_id: int) -> Iterable[UserModelProvider]:
        result = await self.session.execute(
            select(UserModelProvider)
            .where(UserModelProvider.user_id == user_id)
            .order_by(UserModelProvider.id)
        )
        return result.scalars().all()

    async def get_owned(self, provider_id: int, user_id: int) -> Optional[UserModelProvider]:
        result = await self.session.execute(
            select(UserModelProvider).where(
                UserModelProvider.id == provider_id,
                UserModelProvider.user_id == user_id,
            )
        )
        return result.scalars().first()


class UserAIModelRepository(BaseRepository[UserAIModel]):
    model = UserAIModel

    async def list_by_user(self, user_id: int) -> Iterable[UserAIModel]:
        result = await self.session.execute(
            select(UserAIModel)
            .options(selectinload(UserAIModel.provider))
            .where(UserAIModel.user_id == user_id)
            .order_by(UserAIModel.sort_order, UserAIModel.id)
        )
        return result.scalars().all()

    async def get_owned(self, model_id: int, user_id: int) -> Optional[UserAIModel]:
        result = await self.session.execute(
            select(UserAIModel)
            .options(selectinload(UserAIModel.provider))
            .where(UserAIModel.id == model_id, UserAIModel.user_id == user_id)
        )
        return result.scalars().first()

    async def list_enabled_by_capability(self, user_id: int, capability: str) -> Iterable[UserAIModel]:
        models = await self.list_by_user(user_id)
        return [
            model
            for model in models
            if model.is_enabled and bool((model.capabilities_json or {}).get(capability))
        ]


class UserAIStageRouteRepository(BaseRepository[UserAIStageRoute]):
    model = UserAIStageRoute

    async def list_by_user(self, user_id: int) -> Iterable[UserAIStageRoute]:
        result = await self.session.execute(
            select(UserAIStageRoute)
            .options(selectinload(UserAIStageRoute.model).selectinload(UserAIModel.provider))
            .where(UserAIStageRoute.user_id == user_id)
            .order_by(UserAIStageRoute.stage)
        )
        return result.scalars().all()

    async def get_by_stage(self, user_id: int, stage: str) -> Optional[UserAIStageRoute]:
        result = await self.session.execute(
            select(UserAIStageRoute)
            .options(selectinload(UserAIStageRoute.model).selectinload(UserAIModel.provider))
            .where(UserAIStageRoute.user_id == user_id, UserAIStageRoute.stage == stage)
        )
        return result.scalars().first()
