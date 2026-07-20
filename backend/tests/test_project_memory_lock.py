import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.routers.projects import ProjectMemoryPayload, put_project_memory
from app.models import NovelProject, ProjectMemory
from app.models.user import User
from app.schemas.user import UserInDB


async def _seed_owner(db_session_factory, project_id: str = "p1") -> None:
    async with db_session_factory() as session:
        session.add(User(id=1, username="owner", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="t", initial_prompt="x"))
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_put_project_memory_optimistic_lock_conflict(db_session_factory) -> None:
    """expected_version 不匹配返回 409，memory 不被覆盖。"""
    await _seed_owner(db_session_factory)
    async with db_session_factory() as session:
        current_user = UserInDB(id=1, username="owner", hashed_password="secret")
        # 新建 memory（version=1，不传 expected_version 跳过守卫）
        await put_project_memory("p1", ProjectMemoryPayload(global_summary="初始"), session, current_user)

    async with db_session_factory() as session:
        current_user = UserInDB(id=1, username="owner", hashed_password="secret")
        with pytest.raises(HTTPException) as exc:
            await put_project_memory(
                "p1",
                ProjectMemoryPayload(global_summary="新值", expected_version=999),
                session,
                current_user,
            )
        assert exc.value.status_code == 409

    # memory 未被覆盖
    async with db_session_factory() as verify:
        memory = (
            await verify.execute(
                select(ProjectMemory).where(ProjectMemory.project_id == "p1")
            )
        ).scalars().one()
        assert memory.global_summary == "初始"
        assert memory.version == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_put_project_memory_optimistic_lock_success(db_session_factory) -> None:
    """expected_version 匹配 -> 更新成功，version+1。"""
    await _seed_owner(db_session_factory)
    async with db_session_factory() as session:
        current_user = UserInDB(id=1, username="owner", hashed_password="secret")
        res1 = await put_project_memory("p1", ProjectMemoryPayload(global_summary="初始"), session, current_user)
        assert res1["memory"]["version"] == 1

        res2 = await put_project_memory(
            "p1",
            ProjectMemoryPayload(global_summary="新值", expected_version=1),
            session,
            current_user,
        )
        assert res2["memory"]["version"] == 2
        assert res2["memory"]["global_summary"] == "新值"
