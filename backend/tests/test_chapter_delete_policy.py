import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import (
    BlueprintCharacter,
    Chapter,
    ChapterEvaluation,
    ChapterGenerationTrace,
    ChapterOutline,
    ChapterOutboxEvent,
    ChapterProjectionRun,
    ChapterRevision,
    ChapterVersion,
    CharacterState,
    Foreshadowing,
    ForeshadowingStatusHistory,
    ProjectMemory,
    ChapterSnapshot,
    NovelProject,
)
from app.models.background_task import BackgroundTask
from app.models.user import User
from app.services.chapter_projection_service import ChapterProjectionService
from app.services.job_handlers import build_job_handler_registry
from app.services.job_service import JobService
from app.services.job_worker import JobWorker
from app.services.novel_service import NovelService


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_chapters_allows_draft_outlines_and_latest_completed_chapter_only(db_session_factory) -> None:
    async with db_session_factory() as session:
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
            await service.delete_chapters(project_id, [1])
        assert blocked.value.status_code == 400
        assert "最近一个已完成章节" in str(blocked.value.detail)

        await service.delete_chapters(
            project_id,
            [2, 3, 4],
            delete_artifacts_confirmed=True,
            confirmation_text="删除第2章及全部产物",
        )

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

        remaining_outlines = (await session.execute(select(ChapterOutline))).scalars().all()
        assert [outline.chapter_number for outline in remaining_outlines] == [1]
        revision = (await session.execute(select(ChapterRevision))).scalars().one()
        run = (await session.execute(select(ChapterProjectionRun))).scalars().first()
        outbox = (await session.execute(select(ChapterOutboxEvent))).scalars().one()
        dispatcher = (await session.execute(select(BackgroundTask))).scalars().one()
        assert revision.chapter_id is None
        assert revision.lifecycle == "tombstone"
        assert run is None
        assert outbox.chapter_id is None
        assert outbox.aggregate_id == str(latest_completed.id)
        assert dispatcher.task_type == "chapter_outbox_dispatch"
        assert dispatcher.payload_version == 1
        assert dispatcher.payload["outbox_event_id"] == outbox.id


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_chapters_rejects_middle_outline_deletion_that_leaves_gap(db_session_factory) -> None:

    async with db_session_factory() as session:
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


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_latest_completed_chapter_requires_confirmation_flag_not_confirmation_text(db_session_factory) -> None:

    async with db_session_factory() as session:
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


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_latest_completed_chapter_removes_finalization_artifacts_and_restores_memory(db_session_factory) -> None:
    async with db_session_factory() as session:
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
        session.add(BlueprintCharacter(project_id=project_id, name="主角", position=1))
        await session.flush()
        bp_character = (
            await session.execute(
                select(BlueprintCharacter).where(BlueprintCharacter.project_id == project_id)
            )
        ).scalars().one()
        session.add(
            CharacterState(
                id=1,
                project_id=project_id,
                character_id=bp_character.id,
                character_name="主角",
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
        manual_foreshadowing = Foreshadowing(
            project_id=project_id,
            chapter_id=latest_completed.id,
            chapter_number=2,
            content="手工伏笔",
            type="mystery",
            status="planted",
            is_manual=True,
        )
        session.add_all([auto_foreshadowing, manual_foreshadowing])
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
            delete_artifacts_confirmed=True,
            confirmation_text="删除第2章及全部产物",
        )

        deleted_snapshot = (
            await session.execute(
                select(ChapterSnapshot).where(ChapterSnapshot.chapter_number == 2)
            )
        ).scalars().one()
        deleted_state = (
            await session.execute(
                select(CharacterState).where(CharacterState.chapter_number == 2)
            )
        ).scalars().one()
        retained_foreshadowings = {
            item.content: item
            for item in (await session.execute(select(Foreshadowing))).scalars().all()
        }
        assert deleted_snapshot.is_active is False
        assert deleted_state.is_active is False
        assert retained_foreshadowings["自动伏笔"].is_active is False
        assert retained_foreshadowings["自动伏笔"].chapter_id is None
        assert retained_foreshadowings["手工伏笔"].is_active is True
        assert retained_foreshadowings["手工伏笔"].chapter_id is None
        assert len((await session.execute(select(ForeshadowingStatusHistory))).scalars().all()) == 1

        memory = (
            await session.execute(select(ProjectMemory).where(ProjectMemory.project_id == project_id))
        ).scalars().one()
        assert memory.last_updated_chapter == 1
        assert memory.global_summary == "第一章后的全局记忆"


@pytest.mark.asyncio(loop_scope="session")
async def test_tombstone_transaction_rollback_preserves_visibility(db_session_factory) -> None:
    async with db_session_factory() as session:
        project_id = "project-tombstone-rollback"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="t", initial_prompt="x"))
        chapter = Chapter(project_id=project_id, chapter_number=1, status="successful")
        session.add(chapter)
        await session.flush()
        version = ChapterVersion(chapter_id=chapter.id, content="正文")
        session.add(version)
        await session.flush()
        chapter.selected_version_id = version.id
        session.add(
            ChapterSnapshot(
                project_id=project_id,
                chapter_number=1,
                global_summary_snapshot="摘要",
            )
        )
        await session.commit()

        await ChapterProjectionService(session).create_tombstone_job(
            chapter=chapter,
            user_id=1,
            reason="rollback_test",
        )
        await session.rollback()

    async with db_session_factory() as session:
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalars().one()
        snapshot = (
            await session.execute(
                select(ChapterSnapshot).where(ChapterSnapshot.project_id == project_id)
            )
        ).scalars().one()
        assert chapter.current_revision == 0
        assert chapter.tombstone_revision == 0
        assert snapshot.is_active is True
        assert (await session.execute(select(ChapterRevision))).scalars().all() == []
        assert (await session.execute(select(ChapterOutboxEvent))).scalars().all() == []
        assert (await session.execute(select(ChapterProjectionRun))).scalars().all() == []
        assert (await session.execute(select(BackgroundTask))).scalars().all() == []


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_completed_chapter_increments_memory_version(db_session_factory) -> None:
    """删已完成章节回滚 memory 后 version 单调增（乐观锁前提，bug fix）。"""
    async with db_session_factory() as session:
        project_id = "project-memory-version"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="t", initial_prompt="x"))
        await session.flush()
        session.add(
            ProjectMemory(
                project_id=project_id,
                global_summary="第二章摘要",
                plot_arcs={"unresolved_hooks": []},
                last_updated_chapter=2,
                version=5,
            )
        )
        session.add(ChapterOutline(project_id=project_id, chapter_number=1, title="第1章", summary=""))
        session.add(ChapterOutline(project_id=project_id, chapter_number=2, title="第2章", summary=""))
        session.add(Chapter(project_id=project_id, chapter_number=1, status="successful"))
        ch2 = Chapter(project_id=project_id, chapter_number=2, status="successful")
        session.add(ch2)
        await session.flush()
        v2 = ChapterVersion(chapter_id=ch2.id, content="第二章正文")
        session.add(v2)
        await session.flush()
        ch2.selected_version_id = v2.id
        session.add(ChapterEvaluation(chapter_id=ch2.id, version_id=v2.id, feedback="ok"))
        session.add(
            ChapterGenerationTrace(
                chapter_id=ch2.id,
                project_id=project_id,
                chapter_number=2,
                node_key="draft_generation",
                node_label="生成正文",
                status="success",
            )
        )
        # chapter 1 snapshot：回滚恢复源
        session.add(
            ChapterSnapshot(
                project_id=project_id,
                chapter_number=1,
                global_summary_snapshot="第一章摘要",
                plot_arcs_snapshot={"unresolved_hooks": ["hook1"]},
            )
        )
        await session.commit()

        service = NovelService(session)
        await service.delete_chapters(
            project_id,
            [2],
            delete_artifacts_confirmed=True,
            confirmation_text="删除第2章及全部产物",
        )

        memory = (
            await session.execute(
                select(ProjectMemory).where(ProjectMemory.project_id == project_id)
            )
        ).scalars().one()
        assert memory.version == 6  # 5 + 1
        assert memory.global_summary == "第一章摘要"
        assert memory.last_updated_chapter == 1
        assert memory.plot_arcs == {"unresolved_hooks": ["hook1"]}


@pytest.mark.asyncio(loop_scope="session")
async def test_deleted_chapter_tombstone_worker_completes_typed_run(db_session_factory) -> None:
    async with db_session_factory() as session:
        project_id = "project-tombstone-worker"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="t", initial_prompt="x"))
        session.add(
            ChapterOutline(
                project_id=project_id,
                chapter_number=1,
                title="第1章",
                summary="",
            )
        )
        chapter = Chapter(project_id=project_id, chapter_number=1, status="successful")
        session.add(chapter)
        await session.flush()
        version = ChapterVersion(chapter_id=chapter.id, content="正文")
        session.add(version)
        await session.flush()
        chapter.selected_version_id = version.id
        await session.commit()

        await NovelService(session).delete_chapters(
            project_id,
            [1],
            delete_artifacts_confirmed=True,
        )
        dispatcher = (
            await session.execute(
                select(BackgroundTask).where(BackgroundTask.project_id == project_id)
            )
        ).scalars().one()
        dispatcher_id = dispatcher.id

    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="tombstone-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        dispatcher = await JobService(session).get_job(dispatcher_id)
        assert dispatcher is not None
        assert dispatcher.status == "succeeded"
        assert dispatcher.result["status"] == "dispatched"
        tombstone_job_id = dispatcher.result["root_job_id"]

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        dispatcher = await JobService(session).get_job(dispatcher_id)
        job = await JobService(session).get_job(tombstone_job_id)
        run = (
            await session.execute(
                select(ChapterProjectionRun).where(
                    ChapterProjectionRun.job_id == tombstone_job_id
                )
            )
        ).scalars().one()
        assert dispatcher is not None
        assert dispatcher.result["job_ids"] == [tombstone_job_id]
        assert job is not None and job.status == "succeeded"
        assert job.result["status"] == "cleaned"
        assert run.status == "succeeded"
        assert run.is_active is False
        assert run.result["projection"] == "tombstone"
