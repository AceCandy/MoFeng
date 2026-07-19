import pytest
from fastapi import HTTPException

from app.models import NovelProject
from app.models.user import User
from app.services.novel_service import NovelService


async def _seed_owner(db_session_factory, owner_id: int = 1, project_id: str = "project-owner") -> str:
    async with db_session_factory() as session:
        session.add(User(id=owner_id, username="owner", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=owner_id, title="测试小说", initial_prompt="测试"))
        await session.commit()
    return project_id


@pytest.mark.asyncio(loop_scope="session")
async def test_ensure_project_owner_returns_404_for_non_owner(db_session_factory) -> None:
    """越权访问别人的项目必须返回 404，与"项目不存在"同码同文案，不泄露项目存在性（审计 #14）。"""
    project_id = await _seed_owner(db_session_factory)

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as blocked:
            await NovelService(session).ensure_project_owner(project_id, user_id=999)

    assert blocked.value.status_code == 404
    assert blocked.value.detail == "项目不存在"


@pytest.mark.asyncio(loop_scope="session")
async def test_ensure_project_owner_light_returns_404_for_non_owner(db_session_factory) -> None:
    """轻量归属校验同样对越权返回 404，与完整版保持一致。"""
    project_id = await _seed_owner(db_session_factory)

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as blocked:
            await NovelService(session)._ensure_project_owner_light(project_id, user_id=999)

    assert blocked.value.status_code == 404
    assert blocked.value.detail == "项目不存在"
