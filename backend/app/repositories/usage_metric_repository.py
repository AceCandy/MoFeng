# AIMETA P=使用指标仓库_指标数据访问|R=指标CRUD|NR=不含业务逻辑|E=UsageMetricRepository|X=internal|A=仓库类|D=sqlalchemy|S=db|RD=./README.ai

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from .base import BaseRepository
from ..models import UsageMetric


class UsageMetricRepository(BaseRepository[UsageMetric]):
    model = UsageMetric

    async def get_or_create(self, key: str) -> UsageMetric:
        result = await self.session.execute(select(UsageMetric).where(UsageMetric.key == key))
        instance = result.scalars().first()
        if instance is None:
            instance = UsageMetric(key=key, value=0)
            self.session.add(instance)
            await self.session.flush()
        return instance

    async def increment_atomic(self, key: str) -> None:
        """原子自增：一条 SQL upsert + 计数，避免读改写竞态。"""
        stmt = pg_insert(UsageMetric).values(key=key, value=1)
        stmt = stmt.on_conflict_do_update(
            index_elements=[UsageMetric.key],
            set_={"value": UsageMetric.value + 1},
        )
        await self.session.execute(stmt)
