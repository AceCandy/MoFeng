from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import Chapter, ChapterOutline, ChapterVersion, NovelProject
from app.models.user import User
from app.services.chapter_generation_trace_service import ChapterGenerationTraceService
from app.services.novel_service import NovelService


@pytest.mark.asyncio(loop_scope="session")
async def test_waiting_confirmation_only_projects_the_ai_best_version(
    db_session_factory,
):
    async with db_session_factory() as session:
        project_id = "project-best-version-confirmation"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=1,
            title="第一章",
            summary="开篇",
        )
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            status="waiting_for_confirm",
        )
        session.add_all([outline, chapter])
        await session.flush()
        session.add_all(
            [
                ChapterVersion(
                    chapter_id=chapter.id,
                    version_label="v1",
                    content="未入选的原始版本",
                    metadata={"ai_review": {"is_best": False}},
                ),
                ChapterVersion(
                    chapter_id=chapter.id,
                    version_label="v2",
                    content="优选并完成润色的版本",
                    metadata={"ai_review": {"is_best": True}},
                ),
            ]
        )
        await session.commit()

        result = await session.execute(
            select(Chapter)
            .options(selectinload(Chapter.versions))
            .where(Chapter.id == chapter.id)
        )
        loaded_chapter = result.scalars().one()
        schema = NovelService(session)._build_chapter_schema_from_entities(
            chapter_number=1,
            outline=outline,
            chapter=loaded_chapter,
        )

        assert schema.versions == ["未入选的原始版本", "优选并完成润色的版本"]
        assert schema.version_selections is not None
        best_version = next(
            version
            for version in loaded_chapter.versions
            if version.metadata["ai_review"]["is_best"] is True
        )
        assert [(item.id, item.content) for item in schema.version_selections] == [
            (best_version.id, "优选并完成润色的版本")
        ]


@pytest.mark.asyncio(loop_scope="session")
async def test_waiting_confirmation_keeps_legacy_candidates_without_best_marker(
    db_session_factory,
):
    async with db_session_factory() as session:
        project_id = "project-legacy-version-confirmation"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=1,
            title="第一章",
            summary="开篇",
        )
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            status="waiting_for_confirm",
        )
        session.add_all([outline, chapter])
        await session.flush()
        session.add_all(
            [
                ChapterVersion(chapter_id=chapter.id, version_label="v1", content="旧候选一"),
                ChapterVersion(chapter_id=chapter.id, version_label="v2", content="旧候选二"),
            ]
        )
        await session.commit()

        result = await session.execute(
            select(Chapter)
            .options(selectinload(Chapter.versions))
            .where(Chapter.id == chapter.id)
        )
        loaded_chapter = result.scalars().one()
        schema = NovelService(session)._build_chapter_schema_from_entities(
            chapter_number=1,
            outline=outline,
            chapter=loaded_chapter,
        )

        assert schema.version_selections is not None
        assert [item.content for item in schema.version_selections] == ["旧候选一", "旧候选二"]


@pytest.mark.asyncio(loop_scope="session")
async def test_chapter_generation_trace_service_records_real_prompt_and_response(
    db_session_factory,
):
    async with db_session_factory() as session:
        project_id = "project-trace"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        session.add(
            ChapterOutline(project_id=project_id, chapter_number=1, title="第一章", summary="开篇")
        )
        session.add(Chapter(project_id=project_id, chapter_number=1, status="generating"))
        await session.commit()

        service = ChapterGenerationTraceService(session)
        await service.record_success(
            project_id=project_id,
            chapter_number=1,
            node_key="draft_generation",
            node_label="生成正文",
            stage="chapter_writing_1",
            system_prompt="系统提示词",
            user_prompt="真实用户 prompt",
            raw_response="模型原始响应",
            cleaned_output="清洗后的章节正文",
            metadata={"version_index": 1},
        )

        traces = await service.list_for_chapter(project_id=project_id, chapter_number=1)

        assert len(traces) == 1
        assert traces[0].node_key == "draft_generation"
        assert traces[0].status == "success"
        assert traces[0].system_prompt == "系统提示词"
        assert traces[0].user_prompt == "真实用户 prompt"
        assert traces[0].raw_response == "模型原始响应"
        assert traces[0].cleaned_output == "清洗后的章节正文"
        assert traces[0].metadata == {"version_index": 1, "uses_llm": True}
        assert traces[0].source_run_id is None
        assert traces[0].source_event_cursor is None


@pytest.mark.asyncio(loop_scope="session")
async def test_chapter_generation_trace_service_records_node_duration_ms(db_session_factory):
    async with db_session_factory() as session:
        project_id = "project-trace-duration"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        session.add(
            ChapterOutline(project_id=project_id, chapter_number=1, title="第一章", summary="开篇")
        )
        session.add(Chapter(project_id=project_id, chapter_number=1, status="generating"))
        await session.commit()

        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ended_at = started_at + timedelta(milliseconds=2500)
        service = ChapterGenerationTraceService(session)
        await service.record_success(
            project_id=project_id,
            chapter_number=1,
            node_key="context_prep",
            node_label="整理前文",
            metadata={"actions": ["读取前文章节"]},
            started_at=started_at,
            ended_at=ended_at,
        )

        traces = await service.list_for_chapter(project_id=project_id, chapter_number=1)

        assert traces[0].metadata["duration_ms"] == 2500


@pytest.mark.asyncio(loop_scope="session")
async def test_chapter_generation_trace_service_marks_whether_node_used_llm(db_session_factory):
    async with db_session_factory() as session:
        project_id = "project-trace-llm-flag"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        session.add(
            ChapterOutline(project_id=project_id, chapter_number=1, title="第一章", summary="开篇")
        )
        session.add(Chapter(project_id=project_id, chapter_number=1, status="generating"))
        await session.commit()

        service = ChapterGenerationTraceService(session)
        await service.record_success(
            project_id=project_id,
            chapter_number=1,
            node_key="context_prep",
            node_label="整理前文",
            metadata={"actions": ["读取前文章节"]},
        )
        await service.record_success(
            project_id=project_id,
            chapter_number=1,
            node_key="draft_generation",
            node_label="生成正文",
            user_prompt="真实用户 prompt",
            raw_response="模型原始响应",
            metadata={
                "model_calls": [
                    {
                        "stage": "chapter_writing_1",
                        "call_type": "chat_llm",
                        "purpose": "生成正文",
                    }
                ]
            },
        )

        traces = await service.list_for_chapter(project_id=project_id, chapter_number=1)

        assert traces[0].metadata["uses_llm"] is False
        assert traces[1].metadata["uses_llm"] is True


@pytest.mark.asyncio(loop_scope="session")
async def test_novel_service_serializes_chapter_generation_traces(db_session_factory):
    async with db_session_factory() as session:
        project_id = "project-trace-schema"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        project = NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试")
        session.add(project)
        outline = ChapterOutline(
            project_id=project_id, chapter_number=1, title="第一章", summary="开篇"
        )
        chapter = Chapter(project_id=project_id, chapter_number=1, status="generating")
        session.add_all([outline, chapter])
        await session.commit()

        started_at = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        ended_at = started_at + timedelta(milliseconds=1234)
        await ChapterGenerationTraceService(session).record_success(
            project_id=project_id,
            chapter_number=1,
            node_key="draft_generation",
            node_label="生成正文",
            stage="chapter_writing_1",
            system_prompt="系统提示词",
            user_prompt="真实用户 prompt",
            raw_response="模型原始响应",
            cleaned_output="清洗后的章节正文",
            started_at=started_at,
            ended_at=ended_at,
        )

        result = await session.execute(
            select(Chapter)
            .options(selectinload(Chapter.generation_traces))
            .where(Chapter.project_id == project_id, Chapter.chapter_number == 1)
        )
        loaded_chapter = result.scalars().first()

        schema = NovelService(session)._build_chapter_schema_from_entities(
            chapter_number=1,
            outline=outline,
            chapter=loaded_chapter,
        )

        assert schema.generation_traces is not None
        assert [trace.node_key for trace in schema.generation_traces] == ["draft_generation"]
        assert schema.generation_traces[0].uses_llm is True
        assert schema.generation_traces[0].duration_ms == 1234
        assert schema.generation_traces[0].user_prompt == "真实用户 prompt"
        assert schema.generation_traces[0].raw_response == "模型原始响应"


@pytest.mark.asyncio(loop_scope="session")
async def test_novel_service_get_chapter_schema_loads_generation_traces(db_session_factory):
    async with db_session_factory() as session:
        project_id = "project-trace-single-chapter"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(NovelProject(id=project_id, user_id=1, title="测试小说", initial_prompt="测试"))
        session.add(
            ChapterOutline(project_id=project_id, chapter_number=1, title="第一章", summary="开篇")
        )
        session.add(Chapter(project_id=project_id, chapter_number=1, status="generating"))
        await session.commit()

        await ChapterGenerationTraceService(session).record_success(
            project_id=project_id,
            chapter_number=1,
            node_key="draft_generation",
            node_label="生成正文",
            stage="chapter_writing_1",
            user_prompt="单章接口真实 prompt",
            raw_response="单章接口真实 response",
        )
        session.expunge_all()

        schema = await NovelService(session).get_chapter_schema(project_id, 1, 1)

        assert [trace.node_key for trace in schema.generation_traces] == ["draft_generation"]
        assert schema.generation_traces[0].user_prompt == "单章接口真实 prompt"
        assert schema.generation_traces[0].raw_response == "单章接口真实 response"
