import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import (
    BlueprintCharacter,
    ChapterBlueprint,
    ChapterSnapshot,
    CharacterState,
    NovelProject,
    ProjectMemory,
)
from app.models.user import User
from app.services.finalize_service import FinalizeService


class FakeLLMService:
    async def generate(self, prompt: str, **_: object) -> str:
        if "剧情线追踪" in prompt:
            return '{"unresolved_hooks": [], "main_conflicts": [], "character_arcs": []}'
        if "章节标题" in prompt:
            return "本章摘要"
        if "角色状态" in prompt:
            return "主角：状态稳定"
        return "更新后的全局摘要"


@pytest.mark.asyncio
async def test_finalize_chapter_uses_async_session_without_missing_greenlet() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试"))
        session.add(BlueprintCharacter(project_id="project-1", name="主角", position=1))
        session.add(ChapterBlueprint(project_id="project-1", chapter_number=1))
        await session.commit()

        service = FinalizeService(session, FakeLLMService())
        result = await service.finalize_chapter(
            project_id="project-1",
            chapter_number=1,
            chapter_text="第一章正文内容。",
            user_id=1,
            skip_vector_update=True,
        )

        assert result["success"] is True
        assert result["updates"] == {
            "global_summary": "updated",
            "character_state": "updated",
            "plot_arcs": "updated",
            "snapshot": "created",
        }

        memory = (
            await session.execute(select(ProjectMemory).where(ProjectMemory.project_id == "project-1"))
        ).scalars().one()
        blueprint = (
            await session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.project_id == "project-1",
                    ChapterBlueprint.chapter_number == 1,
                )
            )
        ).scalars().one()
        snapshots = (
            await session.execute(select(ChapterSnapshot).where(ChapterSnapshot.project_id == "project-1"))
        ).scalars().all()
        states = (
            await session.execute(select(CharacterState).where(CharacterState.project_id == "project-1"))
        ).scalars().all()

        assert memory.global_summary == "更新后的全局摘要"
        assert memory.last_updated_chapter == 1
        assert memory.version == 2
        assert blueprint.is_finalized is True
        assert len(snapshots) == 1
        assert snapshots[0].chapter_summary == "本章摘要"
        assert len(states) == 1
        assert states[0].character_id is not None
        assert states[0].character_name == "主角"
        assert states[0].extra == {"raw_state_text": "主角：状态稳定"}

    await engine.dispose()


@pytest.mark.asyncio
async def test_finalize_chapter_skips_character_state_without_blueprint_character() -> None:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as session:
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id="project-1", user_id=1, title="测试项目", initial_prompt="测试"))
        session.add(ChapterBlueprint(project_id="project-1", chapter_number=1))
        await session.commit()

        service = FinalizeService(session, FakeLLMService())
        result = await service.finalize_chapter(
            project_id="project-1",
            chapter_number=1,
            chapter_text="第一章正文内容。",
            user_id=1,
            skip_vector_update=True,
        )

        assert result["success"] is True
        assert result["updates"]["character_state"] == "updated"

        states = (
            await session.execute(select(CharacterState).where(CharacterState.project_id == "project-1"))
        ).scalars().all()
        snapshots = (
            await session.execute(select(ChapterSnapshot).where(ChapterSnapshot.project_id == "project-1"))
        ).scalars().all()

        # 没有蓝图角色时不能写 character_id=0，否则 MySQL 外键会在定稿时回滚整笔事务。
        assert states == []
        assert snapshots[0].character_states_snapshot == {"raw_text": "主角：状态稳定"}

    await engine.dispose()
