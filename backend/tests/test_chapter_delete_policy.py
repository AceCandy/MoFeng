import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models import (
    Chapter,
    ChapterEvaluation,
    ChapterGenerationTrace,
    ChapterOutline,
    ChapterVersion,
    CharacterState,
    Foreshadowing,
    ForeshadowingStatusHistory,
    ProjectMemory,
    ChapterSnapshot,
    NovelProject,
)
from app.models.user import User
from app.services.novel_service import NovelService
from app.services.vector_store_service import VectorStoreService


async def _create_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine, session_factory


@pytest.mark.asyncio
async def test_delete_chapters_allows_draft_outlines_and_latest_completed_chapter_only() -> None:
    engine, session_factory = await _create_session_factory()

    deleted_vector_batches: list[list[int]] = []

    async def delete_vectors(chapter_numbers: list[int]) -> None:
        deleted_vector_batches.append(chapter_numbers)

    async with session_factory() as session:
        project_id = "project-delete-policy"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        for number in range(1, 5):
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=number,
                    title=f"第{number}章",
                    summary=f"第{number}章摘要",
                )
            )
        session.add(Chapter(project_id=project_id, chapter_number=1, status="successful"))
        latest_completed = Chapter(project_id=project_id, chapter_number=2, status="successful")
        session.add(latest_completed)
        session.add(Chapter(project_id=project_id, chapter_number=3, status="not_generated"))
        await session.flush()
        version = ChapterVersion(chapter_id=latest_completed.id, content="第二章正文")
        session.add(version)
        await session.flush()
        latest_completed.selected_version_id = version.id
        session.add(ChapterEvaluation(chapter_id=latest_completed.id, version_id=version.id, feedback="评审"))
        session.add(
            ChapterGenerationTrace(
                chapter_id=latest_completed.id,
                project_id=project_id,
                chapter_number=2,
                node_key="draft_generation",
                node_label="生成正文",
                status="success",
            )
        )
        await session.commit()

        service = NovelService(session)

        with pytest.raises(HTTPException) as blocked:
            await service.delete_chapters(project_id, [1], delete_vector_data=delete_vectors)
        assert blocked.value.status_code == 400
        assert "最近一个已完成章节" in str(blocked.value.detail)

        await service.delete_chapters(
            project_id,
            [2, 3, 4],
            delete_vector_data=delete_vectors,
            delete_artifacts_confirmed=True,
            confirmation_text="删除第2章及全部产物",
        )
        assert deleted_vector_batches == [[2]]

        assert not (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id, Chapter.chapter_number == 2))
        ).scalars().first()
        assert not (
            await session.execute(
                select(ChapterOutline).where(
                    ChapterOutline.project_id == project_id,
                    ChapterOutline.chapter_number == 2,
                )
            )
        ).scalars().first()
        assert (await session.execute(select(ChapterVersion))).scalars().all() == []
        assert (await session.execute(select(ChapterEvaluation))).scalars().all() == []
        assert (await session.execute(select(ChapterGenerationTrace))).scalars().all() == []

        assert deleted_vector_batches == [[2]]
        remaining_outlines = (await session.execute(select(ChapterOutline))).scalars().all()
        assert [outline.chapter_number for outline in remaining_outlines] == [1]

    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_chapters_rejects_middle_outline_deletion_that_leaves_gap() -> None:
    engine, session_factory = await _create_session_factory()

    async with session_factory() as session:
        project_id = "project-delete-middle-outline"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        for number in range(1, 5):
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=number,
                    title=f"第{number}章",
                    summary=f"第{number}章摘要",
                )
            )
        session.add(Chapter(project_id=project_id, chapter_number=1, status="successful"))
        session.add(Chapter(project_id=project_id, chapter_number=2, status="not_generated"))
        await session.commit()

        with pytest.raises(HTTPException) as blocked:
            await NovelService(session).delete_chapters(project_id, [3])

        assert blocked.value.status_code == 400
        assert "只能删除尾部连续未生成章节大纲" in str(blocked.value.detail)

    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_latest_completed_chapter_requires_confirmation_flag_not_confirmation_text() -> None:
    engine, session_factory = await _create_session_factory()

    async with session_factory() as session:
        project_id = "project-delete-confirmation"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        for number in range(1, 3):
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=number,
                    title=f"第{number}章",
                    summary=f"第{number}章摘要",
                )
            )
        session.add(Chapter(project_id=project_id, chapter_number=1, status="successful"))
        latest_completed = Chapter(project_id=project_id, chapter_number=2, status="successful")
        session.add(latest_completed)
        await session.flush()
        version = ChapterVersion(chapter_id=latest_completed.id, content="第二章正文")
        session.add(version)
        await session.flush()
        latest_completed.selected_version_id = version.id
        await session.commit()

        with pytest.raises(HTTPException) as blocked:
            await NovelService(session).delete_chapters(project_id, [2])

        assert blocked.value.status_code == 400
        assert "必须二次确认删除章节及全部产物" in str(blocked.value.detail)

        await NovelService(session).delete_chapters(
            project_id,
            [2],
            delete_artifacts_confirmed=True,
            confirmation_text="旧版确认文本",
        )
        assert not (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id, Chapter.chapter_number == 2))
        ).scalars().first()

    await engine.dispose()


@pytest.mark.asyncio
async def test_delete_latest_completed_chapter_removes_finalization_artifacts_and_restores_memory() -> None:
    engine, session_factory = await _create_session_factory()
    deleted_vector_batches: list[list[int]] = []

    async def delete_vectors(chapter_numbers: list[int]) -> None:
        deleted_vector_batches.append(chapter_numbers)

    async with session_factory() as session:
        project_id = "project-delete-artifacts"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        for number in range(1, 3):
            session.add(
                ChapterOutline(
                    project_id=project_id,
                    chapter_number=number,
                    title=f"第{number}章",
                    summary=f"第{number}章摘要",
                )
            )
        first_chapter = Chapter(project_id=project_id, chapter_number=1, status="successful")
        latest_completed = Chapter(project_id=project_id, chapter_number=2, status="successful")
        session.add_all([first_chapter, latest_completed])
        await session.flush()

        first_version = ChapterVersion(chapter_id=first_chapter.id, content="第一章正文")
        second_version = ChapterVersion(chapter_id=latest_completed.id, content="第二章正文")
        session.add_all([first_version, second_version])
        await session.flush()
        first_chapter.selected_version_id = first_version.id
        latest_completed.selected_version_id = second_version.id

        session.add(ProjectMemory(project_id=project_id, global_summary="第二章后的全局记忆", last_updated_chapter=2))
        session.add(
            ChapterSnapshot(
                project_id=project_id,
                chapter_number=1,
                global_summary_snapshot="第一章后的全局记忆",
                plot_arcs_snapshot={"stage": "chapter1"},
                chapter_summary="第一章梳理",
            )
        )
        session.add(
            ChapterSnapshot(
                project_id=project_id,
                chapter_number=2,
                global_summary_snapshot="第二章后的全局记忆",
                plot_arcs_snapshot={"stage": "chapter2"},
                chapter_summary="第二章梳理",
            )
        )
        session.add(
            CharacterState(
                id=1,
                project_id=project_id,
                character_id=0,
                character_name="__all__",
                chapter_number=2,
                extra={"raw_state_text": "第二章角色状态"},
            )
        )
        auto_foreshadowing = Foreshadowing(
            project_id=project_id,
            chapter_id=latest_completed.id,
            chapter_number=2,
            content="自动伏笔",
            type="mystery",
            status="planted",
            is_manual=False,
        )
        session.add(auto_foreshadowing)
        await session.flush()
        session.add(
            ForeshadowingStatusHistory(
                foreshadowing_id=auto_foreshadowing.id,
                old_status=None,
                new_status="planted",
                chapter_number=2,
            )
        )
        await session.commit()

        await NovelService(session).delete_chapters(
            project_id,
            [2],
            delete_vector_data=delete_vectors,
            delete_artifacts_confirmed=True,
            confirmation_text="删除第2章及全部产物",
        )

        assert deleted_vector_batches == [[2]]
        assert (await session.execute(select(ChapterSnapshot).where(ChapterSnapshot.chapter_number == 2))).scalars().all() == []
        assert (await session.execute(select(CharacterState).where(CharacterState.chapter_number == 2))).scalars().all() == []
        assert (await session.execute(select(Foreshadowing))).scalars().all() == []
        assert (await session.execute(select(ForeshadowingStatusHistory))).scalars().all() == []

        memory = (
            await session.execute(select(ProjectMemory).where(ProjectMemory.project_id == project_id))
        ).scalars().one()
        assert memory.last_updated_chapter == 1
        assert memory.global_summary == "第一章后的全局记忆"

    await engine.dispose()


@pytest.mark.asyncio
async def test_vector_store_delete_by_chapters_propagates_delete_failures() -> None:
    class FailingClient:
        async def execute(self, *_args, **_kwargs):
            raise RuntimeError("vector delete failed")

    service = object.__new__(VectorStoreService)
    service._client = FailingClient()
    service._schema_ready = True

    with pytest.raises(RuntimeError, match="vector delete failed"):
        await service.delete_by_chapters("project-vector-failure", [2])
