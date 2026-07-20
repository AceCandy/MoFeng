"""consistency_service async 修复测试（H5）。"""
import pytest

from app.models import NovelProject
from app.models.user import User
from app.services.consistency_service import ConsistencyService, ConsistencyCheckResult


class FakeLLMService:
    async def generate(self, prompt: str, **_: object) -> str:
        return '{"is_consistent": true, "violations": [], "summary": "一致"}'


@pytest.mark.asyncio(loop_scope="session")
async def test_get_check_context_uses_async_session_without_missing_greenlet(db_session_factory) -> None:
    """_get_check_context 改用 async query 后不再抛 MissingGreenlet（H5）。"""
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试"))
        await session.commit()

        service = ConsistencyService(session, FakeLLMService())
        # 直接调 _get_check_context：若仍用同步 self.db.query 会抛 MissingGreenlet
        context = await service._get_check_context("project-1", include_foreshadowing=True)

        assert isinstance(context, dict)


@pytest.mark.asyncio(loop_scope="session")
async def test_check_consistency_returns_result_without_500(db_session_factory) -> None:
    """check_consistency 端到端返回 ConsistencyCheckResult，不再因 MissingGreenlet 500（H5）。"""
    async with db_session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试"))
        await session.commit()

        service = ConsistencyService(session, FakeLLMService())
        result = await service.check_consistency(
            project_id="project-1",
            chapter_text="第一章正文内容。",
            user_id=1,
            include_foreshadowing=True,
        )

        assert isinstance(result, ConsistencyCheckResult)
        assert result.is_consistent is True
        assert result.check_time_ms is not None
