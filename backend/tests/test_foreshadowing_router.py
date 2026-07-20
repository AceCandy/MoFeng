"""foreshadowing router 越权与正常访问测试（H1）。"""
import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

from app.api.routers.foreshadowing import list_foreshadowings
from app.models import NovelProject
from app.models.user import User


async def _seed_owner_project(db_session_factory, owner_id: int = 1, project_id: str = "p1") -> str:
    async with db_session_factory() as session:
        session.add(User(id=owner_id, username="owner", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=owner_id, title="测试小说", initial_prompt="测试"))
        await session.commit()
    return project_id


@pytest.mark.asyncio(loop_scope="session")
async def test_list_foreshadowings_returns_404_for_non_owner(db_session_factory) -> None:
    """非项目拥有者访问伏笔列表返回 404，与“项目不存在”同码同文案，不泄露项目存在性（审计 #14 / H1）。"""
    project_id = await _seed_owner_project(db_session_factory)
    other_user = MagicMock(id=999)

    async with db_session_factory() as session:
        with pytest.raises(HTTPException) as blocked:
            await list_foreshadowings(
                project_id=project_id,
                status=None,
                foreshadowing_type=None,
                limit=100,
                offset=0,
                session=session,
                current_user=other_user,
            )

    assert blocked.value.status_code == 404
    assert blocked.value.detail == "项目不存在"


@pytest.mark.asyncio(loop_scope="session")
async def test_list_foreshadowings_returns_data_for_owner(db_session_factory) -> None:
    """项目拥有者访问伏笔列表正常返回，校验不误伤合法 owner（H1）。"""
    project_id = await _seed_owner_project(db_session_factory)
    owner = MagicMock(id=1)

    async with db_session_factory() as session:
        response = await list_foreshadowings(
            project_id=project_id,
            status=None,
            foreshadowing_type=None,
            limit=100,
            offset=0,
            session=session,
            current_user=owner,
        )

    assert response["total"] == 0
    assert response["data"] == []
