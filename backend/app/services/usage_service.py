# AIMETA P=使用统计服务_API调用统计|R=统计记录_限额检查|NR=不含数据访问|E=UsageService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import AsyncSessionLocal
from ..repositories.usage_metric_repository import UsageMetricRepository


class UsageService:
    """通用计数服务，目前用于统计 API 请求次数等。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = UsageMetricRepository(session)

    async def increment(self, key: str) -> None:
        # 独立 session + 原子 upsert，避免共享 session commit 污染调用方事务
        async with AsyncSessionLocal() as session:
            repo = UsageMetricRepository(session)
            await repo.increment_atomic(key)
            await session.commit()

    async def get_value(self, key: str) -> int:
        counter = await self.repo.get_or_create(key)
        return counter.value
