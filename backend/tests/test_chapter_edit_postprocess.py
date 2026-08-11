from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import Chapter, ChapterOutline, NovelProject
from app.models.foreshadowing import Foreshadowing
from app.models.job import JobActivity
from app.models.rag import RagChunk, RagSummary
from app.models.user import User
from app.schemas.chapter_context import stable_digest
from app.services.chapter_edit_service import ChapterEditService
from app.services.job_handlers import build_job_handler_registry
from app.services.job_service import JobService
from app.services.job_worker import JobExecutionContext, JobWorker
from app.services.llm_service import LLMService
from app.services.prompt_service import PromptService

CONTENT_WITH_CLUE = "那枚神秘徽章隐藏着他的身份秘密，真相显得格外蹊跷又不对劲。"


async def _seed_edit_job(
    session_factory,
    *,
    user_id: int,
    project_id: str,
    content: str = CONTENT_WITH_CLUE,
):
    async with session_factory() as session:
        session.add(User(id=user_id, username=f"editor-{user_id}", hashed_password="secret"))
        session.add(
            NovelProject(
                id=project_id,
                user_id=user_id,
                title="章节后处理项目",
                initial_prompt="测试",
            )
        )
        session.add(
            ChapterOutline(
                project_id=project_id,
                chapter_number=1,
                title="第一章",
                summary="测试大纲",
            )
        )
        await session.commit()
        edit = await ChapterEditService(session).apply_content(
            project_id=project_id,
            chapter_number=1,
            content=content,
            user_id=user_id,
            version_label="manual_edit",
        )
        return edit.job.id, edit.selected_version.id


def _mock_postprocess_external_calls(monkeypatch):
    monkeypatch.setattr(settings, "vector_store_enabled", True)
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="测试提示词"))
    summary_call = AsyncMock(return_value="本章摘要")
    foreshadowing_call = AsyncMock(
        return_value=(
            '{"items":[{"id":0,"keep":true,"type":"mystery",'
            '"keywords":["徽章","秘密"],"importance":"major","confidence":0.9}]}'
        )
    )
    embedding_call = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr(LLMService, "get_summary_detached", summary_call)
    monkeypatch.setattr(LLMService, "get_llm_response_detached", foreshadowing_call)
    monkeypatch.setattr(LLMService, "get_embedding_detached", embedding_call)
    return summary_call, foreshadowing_call, embedding_call


@pytest.mark.asyncio(loop_scope="session")
async def test_chapter_edit_service_commits_content_with_one_durable_job(db_session_factory):
    job_id, version_id = await _seed_edit_job(
        db_session_factory,
        user_id=1301,
        project_id="edit-atomic-project",
        content="原子提交正文",
    )

    async with db_session_factory() as session:
        job = await JobService(session).get_job(job_id)
        chapter = (
            await session.execute(
                select(Chapter).where(
                    Chapter.project_id == "edit-atomic-project",
                    Chapter.chapter_number == 1,
                )
            )
        ).scalar_one()

    assert job is not None
    assert job.task_type == "chapter_edit_postprocess"
    assert job.payload == {
        "project_id": "edit-atomic-project",
        "chapter_number": 1,
        "selected_version_id": version_id,
        "content_hash": stable_digest("原子提交正文"),
    }
    assert chapter.selected_version_id == version_id
    assert chapter.status == "successful"


@pytest.mark.asyncio(loop_scope="session")
async def test_postprocess_applies_summary_vectors_and_foreshadowing_atomically(
    db_session_factory,
    monkeypatch,
):
    summary_call, foreshadowing_call, embedding_call = _mock_postprocess_external_calls(monkeypatch)
    job_id, _ = await _seed_edit_job(
        db_session_factory,
        user_id=1302,
        project_id="postprocess-project",
    )
    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="chapter-postprocess-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        job = await JobService(session).get_job(job_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "postprocess-project")
            )
        ).scalar_one()
        chunk = (
            await session.execute(
                select(RagChunk).where(RagChunk.project_id == "postprocess-project")
            )
        ).scalar_one()
        summary = (
            await session.execute(
                select(RagSummary).where(RagSummary.project_id == "postprocess-project")
            )
        ).scalar_one()
        foreshadowing = (
            await session.execute(
                select(Foreshadowing).where(Foreshadowing.project_id == "postprocess-project")
            )
        ).scalar_one()
        activities = (
            (await session.execute(select(JobActivity).where(JobActivity.job_id == job_id)))
            .scalars()
            .all()
        )

    assert job is not None
    assert job.status == "succeeded"
    assert job.result["status"] == "applied"
    assert job.result["foreshadowing_sync"]["created"] == 1
    assert chapter.real_summary == "本章摘要"
    assert chunk.content == CONTENT_WITH_CLUE
    assert chunk.meta["content_hash"] == stable_digest(CONTENT_WITH_CLUE)
    assert summary.summary == "本章摘要"
    assert foreshadowing.is_manual is False
    assert {item.activity_key for item in activities} == {
        "summary_generation",
        "foreshadowing_candidate_review",
        "chapter_embedding",
    }
    assert all(item.status == "succeeded" for item in activities)
    summary_call.assert_awaited_once()
    foreshadowing_call.assert_awaited_once()
    assert embedding_call.await_count >= 2


@pytest.mark.asyncio(loop_scope="session")
async def test_postprocess_stops_when_content_changes_after_llm(
    db_session_factory,
    monkeypatch,
):
    monkeypatch.setattr(settings, "vector_store_enabled", True)
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="测试提示词"))
    job_id, _ = await _seed_edit_job(
        db_session_factory,
        user_id=1303,
        project_id="postprocess-stale-after-llm",
    )

    async def edit_during_summary(*args, **kwargs):
        async with db_session_factory() as session:
            await ChapterEditService(session).apply_content(
                project_id="postprocess-stale-after-llm",
                chapter_number=1,
                content="更新后的正文",
                user_id=1303,
                version_label="manual_edit",
            )
        return "旧正文摘要"

    summary_call = AsyncMock(side_effect=edit_during_summary)
    embedding_call = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr(LLMService, "get_summary_detached", summary_call)
    monkeypatch.setattr(
        LLMService, "get_llm_response_detached", AsyncMock(return_value='{"items":[]}')
    )
    monkeypatch.setattr(LLMService, "get_embedding_detached", embedding_call)
    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="stale-after-llm-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        job = await JobService(session).get_job(job_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "postprocess-stale-after-llm")
            )
        ).scalar_one()
        chunks = (
            (
                await session.execute(
                    select(RagChunk).where(RagChunk.project_id == "postprocess-stale-after-llm")
                )
            )
            .scalars()
            .all()
        )

    assert job is not None
    assert job.status == "succeeded"
    assert job.result["status"] == "superseded"
    assert chapter.real_summary is None
    assert chunks == []
    summary_call.assert_awaited_once()
    embedding_call.assert_not_awaited()


@pytest.mark.asyncio(loop_scope="session")
async def test_final_outcome_cas_rejects_content_changed_after_compute(
    db_session_factory,
    monkeypatch,
):
    _mock_postprocess_external_calls(monkeypatch)
    job_id, _ = await _seed_edit_job(
        db_session_factory,
        user_id=1304,
        project_id="postprocess-final-cas",
    )
    registry = build_job_handler_registry()
    definition = registry.get("chapter_edit_postprocess", 1)
    assert definition is not None

    async with db_session_factory() as session:
        lease = await JobService(session).claim_next(
            worker_id="final-cas-worker",
            lease_seconds=30,
        )
    assert lease is not None
    context = JobExecutionContext(
        lease=lease,
        side_effect_class=definition.side_effect_class,
        session_factory=db_session_factory,
    )
    outcome = await definition.handler(context)

    async with db_session_factory() as session:
        await ChapterEditService(session).apply_content(
            project_id="postprocess-final-cas",
            chapter_number=1,
            content="计算完成后提交的新正文",
            user_id=1304,
            version_label="manual_edit",
        )
    async with db_session_factory() as session:
        await JobService(session).mark_succeeded(
            lease,
            result=outcome.result,
            outcome_writer=outcome.outcome_writer,
        )

    async with db_session_factory() as session:
        job = await JobService(session).get_job(job_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "postprocess-final-cas")
            )
        ).scalar_one()
        chunks = (
            (
                await session.execute(
                    select(RagChunk).where(RagChunk.project_id == "postprocess-final-cas")
                )
            )
            .scalars()
            .all()
        )
        foreshadowings = (
            (
                await session.execute(
                    select(Foreshadowing).where(Foreshadowing.project_id == "postprocess-final-cas")
                )
            )
            .scalars()
            .all()
        )

    assert job is not None
    assert job.status == "succeeded"
    assert job.result["status"] == "superseded"
    assert chapter.real_summary is None
    assert chunks == []
    assert foreshadowings == []
