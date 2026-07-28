from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.api.routers.tasks import _public_task_response
from app.models import Chapter, ChapterOutline, ChapterVersion, NovelProject
from app.models.job import JobActivity
from app.models.user import User
from app.schemas.chapter_context import stable_digest
from app.services.chapter_finalize_service import ChapterFinalizeSubmissionService
from app.services.finalize_service import FinalizeService
from app.services.job_handlers import build_job_handler_registry
from app.services.job_service import JobService
from app.services.job_worker import JobWorker
from app.services.llm_service import LLMService
from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.services.prompt_service import PromptService


async def _seed_finalize_chapter(
    session_factory,
    *,
    user_id: int,
    project_id: str,
) -> None:
    async with session_factory() as session:
        session.add(User(id=user_id, username=f"finalizer-{user_id}", hashed_password="secret"))
        session.add(
            NovelProject(
                id=project_id,
                user_id=user_id,
                title="定稿持久任务项目",
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
        await session.flush()
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            status="waiting_for_confirm",
            generation_progress=100,
        )
        session.add(chapter)
        await session.flush()
        session.add_all(
            [
                ChapterVersion(chapter_id=chapter.id, version_label="version1", content="旧候选正文"),
                ChapterVersion(chapter_id=chapter.id, version_label="version2", content="第二候选正文"),
            ]
        )
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_submission_commits_content_with_one_queued_job(db_session_factory):
    await _seed_finalize_chapter(
        db_session_factory,
        user_id=1401,
        project_id="finalize-submit-project",
    )

    async with db_session_factory() as session:
        task = await ChapterFinalizeSubmissionService(session).submit(
            project_id="finalize-submit-project",
            chapter_number=1,
            user_id=1401,
            selected_version_index=1,
            edited_content="  最终正文  ",
            skip_vector_update=True,
            idempotency_key="finalize-submit-1",
        )
        task_id = task.id

    async with db_session_factory() as session:
        task = await JobService(session).get_job(task_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "finalize-submit-project")
            )
        ).scalar_one()
        version = await session.get(ChapterVersion, chapter.selected_version_id)

    assert task is not None
    assert task.status == "queued"
    assert task.task_type == "chapter_finalize"
    assert task.payload == {
        "project_id": "finalize-submit-project",
        "chapter_number": 1,
        "selected_version_id": chapter.selected_version_id,
        "content_hash": stable_digest("最终正文"),
        "skip_vector_update": True,
    }
    assert chapter.status == "finalizing"
    assert version is not None
    assert version.content == "最终正文"


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_worker_applies_stats_and_skips_vectors(
    db_session_factory,
    monkeypatch,
):
    await _seed_finalize_chapter(
        db_session_factory,
        user_id=1402,
        project_id="finalize-worker-project",
    )
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="测试提示词"))
    monkeypatch.setattr(LLMService, "get_summary_detached", AsyncMock(return_value="本章摘要"))
    monkeypatch.setattr(
        LLMService,
        "get_llm_response_detached",
        AsyncMock(return_value='{"items":[]}'),
    )
    embedding_call = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr(LLMService, "get_embedding_detached", embedding_call)
    monkeypatch.setattr(
        FinalizeService,
        "finalize_chapter",
        AsyncMock(
            return_value={
                "success": True,
                "updates": {"snapshot": "created", "global_summary": "updated"},
            }
        ),
    )

    async with db_session_factory() as session:
        task = await ChapterFinalizeSubmissionService(session).submit(
            project_id="finalize-worker-project",
            chapter_number=1,
            user_id=1402,
            selected_version_index=0,
            skip_vector_update=True,
        )
        task_id = task.id

    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="finalize-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        task = await JobService(session).get_job(task_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "finalize-worker-project")
            )
        ).scalar_one()
        activity_keys = set(
            (
                await session.execute(
                    select(JobActivity.activity_key).where(JobActivity.job_id == task_id)
                )
            ).scalars().all()
        )

    assert task is not None
    assert task.status == "succeeded"
    assert task.result["status"] == "applied"
    assert task.result["finalize"]["summary_generated"] is True
    assert task.result["finalize"]["memory_updated"] is True
    assert task.result["finalize"]["vector_ingested"] is False
    assert chapter.status == "successful"
    assert chapter.generation_step == "finalized"
    assert "summary_generation" in activity_keys
    assert "finalize_memory" in activity_keys
    assert "chapter_embedding" not in activity_keys
    embedding_call.assert_not_awaited()


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_worker_preserves_draft_when_external_result_is_ambiguous(
    db_session_factory,
    monkeypatch,
):
    await _seed_finalize_chapter(
        db_session_factory,
        user_id=1404,
        project_id="finalize-ambiguous-project",
    )
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="测试提示词"))
    monkeypatch.setattr(
        LLMService,
        "get_summary_detached",
        AsyncMock(side_effect=TimeoutError("provider response unknown")),
    )

    async with db_session_factory() as session:
        task = await ChapterFinalizeSubmissionService(session).submit(
            project_id="finalize-ambiguous-project",
            chapter_number=1,
            user_id=1404,
            selected_version_index=0,
            skip_vector_update=True,
        )
        task_id = task.id

    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="finalize-ambiguous-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        task = await JobService(session).get_job(task_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "finalize-ambiguous-project")
            )
        ).scalar_one()
        activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == task_id,
                    JobActivity.activity_key == "summary_generation",
                )
            )
        ).scalar_one()

    assert task is not None
    assert task.status == "needs_attention"
    assert chapter.status == "finalizing"
    assert chapter.selected_version_id is not None
    assert activity.status == "ambiguous"


@pytest.mark.asyncio(loop_scope="session")
async def test_generation_worker_publishes_only_whitelisted_result(
    db_session_factory,
    monkeypatch,
):
    async with db_session_factory() as session:
        session.add(User(id=1403, username="generator-1403", hashed_password="secret"))
        session.add(
            NovelProject(
                id="generation-worker-project",
                user_id=1403,
                title="生成持久任务项目",
                initial_prompt="测试",
            )
        )
        await session.commit()
        task = await JobService(session).enqueue_job(
            user_id=1403,
            project_id="generation-worker-project",
            job_type="chapter_generation",
            title="生成第一章正文",
            payload={
                "project_id": "generation-worker-project",
                "chapter_number": 1,
                "writing_notes": "这是私有写作指令",
                "flow_config": {"preset": "basic", "enable_rag": True},
                "from_node_key": None,
            },
            payload_version=1,
        )
        task_id = task.id

    monkeypatch.setattr(
        PipelineOrchestrator,
        "generate_chapter",
        AsyncMock(
            return_value={
                "project_id": "generation-worker-project",
                "chapter_number": 1,
                "preset": "basic",
                "best_version_index": 0,
                "variants": [{"content": "完整生成正文", "debug_metadata": {"prompt": "私有"}}],
                "review_summaries": {"version1": "评审"},
                "debug_metadata": {"prompt": "私有"},
            }
        ),
    )
    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="generation-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        task = await JobService(session).get_job(task_id)

    assert task is not None
    assert task.status == "succeeded"
    assert task.result == {
        "project_id": "generation-worker-project",
        "chapter_number": 1,
        "preset": "basic",
        "best_version_index": 0,
        "variant_count": 1,
        "review_count": 1,
    }
    assert "完整生成正文" not in str(task.result)
    assert "私有" not in str(task.result)
    public_task = _public_task_response(task, include_result=True)
    assert public_task.payload is None
    assert public_task.result == task.result
