import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import NovelProject
from app.models.user import User
from app.services.novel_service import NovelService


async def _session_factory_with_owner(owner_id: int = 1, project_id: str = "project-owner"):
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        session.add(User(id=owner_id, username="owner", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=owner_id, title="测试小说", initial_prompt="测试"))
        await session.commit()
    return engine, session_factory, project_id


@pytest.mark.asyncio
async def test_ensure_project_owner_returns_404_for_non_owner() -> None:
    """越权访问别人的项目必须返回 404，与"项目不存在"同码同文案，不泄露项目存在性（审计 #14）。"""

    engine, session_factory, project_id = await _session_factory_with_owner()

    async with session_factory() as session:
        with pytest.raises(HTTPException) as blocked:
            await NovelService(session).ensure_project_owner(project_id, user_id=999)

    assert blocked.value.status_code == 404
    assert blocked.value.detail == "项目不存在"
    await engine.dispose()


@pytest.mark.asyncio
async def test_ensure_project_owner_light_returns_404_for_non_owner() -> None:
    """轻量归属校验同样对越权返回 404，与完整版保持一致。"""

    engine, session_factory, project_id = await _session_factory_with_owner()

    async with session_factory() as session:
        with pytest.raises(HTTPException) as blocked:
            await NovelService(session)._ensure_project_owner_light(project_id, user_id=999)

    assert blocked.value.status_code == 404
    assert blocked.value.detail == "项目不存在"
    await engine.dispose()
