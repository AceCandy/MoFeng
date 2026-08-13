from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.config import settings
from app.models import (
    BlueprintCharacter,
    Chapter,
    ChapterOutboxEvent,
    ChapterOutline,
    ChapterProjectionReplayAudit,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
    ChapterSnapshot,
    ChapterVersion,
    CharacterState,
    Foreshadowing,
    NovelProject,
    RagChunk,
    RagSummary,
)
from app.models.background_task import BackgroundTask
from app.models.job import JobActivity
from app.models.user import User
from app.schemas.chapter_context import stable_digest
from app.schemas.chapter_projection import ChapterProjectionOperationRequest
from app.services.chapter_finalize_service import (
    ChapterFinalizeSubmissionService,
    PreparedChapterFinalize,
)
from app.services.chapter_projection_ops import ChapterProjectionOpsService
from app.services.chapter_projection_service import ChapterProjectionService
from app.services.job_handlers import build_job_handler_registry
from app.services.job_service import JobService
from app.services.job_worker import JobWorker
from app.services.llm_service import LLMService
from app.services.novel_service import NovelService
from app.services.prompt_service import PromptService
from app.utils.ai_telemetry import AICallResult, TokenUsage


def _ai_call_result(value, *, stage: str = "summary_memory") -> AICallResult:
    return AICallResult(
        value=value,
        provider_type="openai_compatible",
        model="test-model",
        model_id=None,
        stage=stage,
        usage=TokenUsage(),
        cost_amount=None,
        cost_currency=None,
        cost_unknown_reason="usage_unavailable",
    )


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
                ChapterVersion(
                    chapter_id=chapter.id, version_label="version1", content="旧候选正文"
                ),
                ChapterVersion(
                    chapter_id=chapter.id, version_label="version2", content="第二候选正文"
                ),
            ]
        )
        await session.commit()


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_submission_commits_content_with_one_queued_dispatcher(
    db_session_factory,
):
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
        revision = (
            await session.execute(
                select(ChapterRevision).where(ChapterRevision.chapter_id == chapter.id)
            )
        ).scalar_one()
        outbox = (
            await session.execute(
                select(ChapterOutboxEvent).where(ChapterOutboxEvent.chapter_id == chapter.id)
            )
        ).scalar_one()
        projection = (
            (
                await session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.chapter_id == chapter.id
                    )
                )
            )
            .scalars()
            .first()
        )
        job_count = await session.scalar(
            select(func.count(BackgroundTask.id)).where(
                BackgroundTask.project_id == "finalize-submit-project"
            )
        )

    assert task is not None
    assert task.status == "queued"
    assert task.task_type == "chapter_outbox_dispatch"
    assert task.payload_version == 1
    assert task.payload == {
        "project_id": "finalize-submit-project",
        "outbox_event_id": outbox.id,
        "event_type": "ChapterFinalizationRequested",
        "event_version": 2,
        "payload_fingerprint": outbox.payload_fingerprint,
    }
    assert chapter.status == "finalizing"
    assert chapter.current_revision == 1
    assert chapter.source_hash == stable_digest("最终正文")
    assert chapter.required_projection_snapshot == ["summary", "memory", "foreshadowing"]
    assert version is not None
    assert version.content == "最终正文"
    assert revision.source_content == "最终正文"
    assert revision.source_hash == chapter.source_hash
    assert outbox.event_type == "ChapterFinalizationRequested"
    assert task.stream_id == outbox.workflow_stream_id
    assert outbox.payload["workflow_stream_id"] == outbox.workflow_stream_id
    assert "source_content" not in outbox.payload
    assert projection is None
    assert job_count == 1

    async with db_session_factory() as session:
        duplicate = await ChapterFinalizeSubmissionService(session).submit(
            project_id="finalize-submit-project",
            chapter_number=1,
            user_id=1401,
            selected_version_index=1,
            edited_content="最终正文",
            skip_vector_update=True,
            idempotency_key="finalize-submit-1",
        )
        refreshed = await session.get(Chapter, chapter.id)
        revision_count = await session.scalar(
            select(func.count(ChapterRevision.id)).where(ChapterRevision.chapter_id == chapter.id)
        )

    assert duplicate.id == task.id
    assert refreshed is not None and refreshed.current_revision == 1
    assert revision_count == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_prepare_apply_reuses_workflow_stream_without_early_commit(
    isolated_pg,
):
    project_id = str(uuid4())
    workflow_stream_id = str(uuid4())
    session_factory = isolated_pg.session_factory
    await _seed_finalize_chapter(
        session_factory,
        user_id=1411,
        project_id=project_id,
    )

    async with session_factory() as session:
        service = ChapterFinalizeSubmissionService(session)
        prepared = await service.prepare(
            project_id=project_id,
            chapter_number=1,
            user_id=1411,
            selected_version_index=0,
            edited_content="workflow 定稿正文",
            skip_vector_update=True,
            idempotency_key="workflow-finalize-prepare-apply",
        )
        assert isinstance(prepared, PreparedChapterFinalize)
        result = await service.apply(
            prepared,
            workflow_stream_id=workflow_stream_id,
        )
        assert result.job.stream_id == workflow_stream_id
        assert result.outbox_event.workflow_stream_id == workflow_stream_id
        assert result.outbox_event.payload["workflow_stream_id"] == workflow_stream_id

        other_session = session_factory()
        try:
            assert await other_session.get(ChapterOutboxEvent, result.outbox_event.id) is None
        finally:
            await other_session.close()

        task = await ChapterProjectionService(session).commit_finalize(result)
        task_id = task.id
        outbox_id = result.outbox_event.id

    async with session_factory() as session:
        task = await session.get(BackgroundTask, task_id)
        outbox = await session.get(ChapterOutboxEvent, outbox_id)

    assert task is not None and task.stream_id == workflow_stream_id
    assert outbox is not None and outbox.workflow_stream_id == workflow_stream_id


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
    monkeypatch.setattr(
        LLMService,
        "get_summary_result_detached",
        AsyncMock(return_value=_ai_call_result("本章摘要")),
    )
    monkeypatch.setattr(
        LLMService,
        "get_llm_response_result_detached",
        AsyncMock(return_value=_ai_call_result('{"items":[]}', stage="foreshadowing")),
    )
    embedding_call = AsyncMock(return_value=_ai_call_result([0.1, 0.2, 0.3], stage="rag_embedding"))
    monkeypatch.setattr(LLMService, "get_embedding_result_detached", embedding_call)
    monkeypatch.setattr(
        LLMService,
        "generate_result_detached",
        AsyncMock(
            side_effect=[
                _ai_call_result("全局摘要"),
                _ai_call_result("角色状态"),
                _ai_call_result("{}"),
                _ai_call_result("章节摘要"),
            ]
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
        dispatcher_task = await JobService(session).get_job(task_id)
        assert dispatcher_task is not None
        assert dispatcher_task.status == "succeeded"
        assert dispatcher_task.result["status"] == "dispatched"
        summary_task_id = dispatcher_task.result["root_job_id"]

    for _ in range(5):
        assert await worker.run_once() is True

    async with db_session_factory() as session:
        dispatcher_task = await JobService(session).get_job(task_id)
        summary_task = await JobService(session).get_job(summary_task_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "finalize-worker-project")
            )
        ).scalar_one()
        activity_keys = set(
            (
                await session.execute(
                    select(JobActivity.activity_key)
                    .join(BackgroundTask, BackgroundTask.id == JobActivity.job_id)
                    .where(BackgroundTask.project_id == "finalize-worker-project")
                )
            )
            .scalars()
            .all()
        )
        projections = (
            (
                await session.execute(
                    select(ChapterProjectionRun)
                    .where(ChapterProjectionRun.project_id == "finalize-worker-project")
                    .order_by(ChapterProjectionRun.projection_name)
                )
            )
            .scalars()
            .all()
        )
        all_jobs = (
            (
                await session.execute(
                    select(BackgroundTask).where(
                        BackgroundTask.project_id == "finalize-worker-project"
                    )
                )
            )
            .scalars()
            .all()
        )

    assert dispatcher_task is not None
    assert dispatcher_task.status == "succeeded"
    assert dispatcher_task.result["status"] == "dispatched"
    assert dispatcher_task.result["job_ids"] == [summary_task_id]
    assert summary_task is not None
    assert summary_task.status == "succeeded"
    assert summary_task.result["status"] == "projected"
    assert summary_task.result["projection"] == "summary"
    assert chapter.status == "successful"
    assert chapter.generation_step == "finalized"
    assert "summary_generation" in activity_keys
    assert {
        "memory_global_summary",
        "memory_character_state",
        "memory_plot_arcs",
        "memory_chapter_summary",
    }.issubset(activity_keys)
    assert "rag_embedding" not in activity_keys
    assert {run.projection_name for run in projections} == {
        "summary",
        "memory",
        "foreshadowing",
        "trace",
        "rag",
        "reconcile",
    }
    assert all(run.status in {"succeeded", "skipped"} for run in projections)
    assert len(all_jobs) == 6
    embedding_call.assert_not_awaited()


@pytest.mark.asyncio(loop_scope="session")
async def test_legacy_finalize_artifacts_follow_canonical_revision_and_tombstone(
    db_session_factory,
    monkeypatch,
):
    project_id = "finalize-legacy-lineage-project"
    user_id = 1406
    await _seed_finalize_chapter(
        db_session_factory,
        user_id=user_id,
        project_id=project_id,
    )
    monkeypatch.setattr(settings, "vector_store_enabled", True)
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="测试提示词"))
    monkeypatch.setattr(
        LLMService,
        "get_summary_detached",
        AsyncMock(return_value="legacy 章节摘要"),
    )
    monkeypatch.setattr(
        LLMService,
        "get_llm_response_detached",
        AsyncMock(
            return_value=(
                '{"items":[{"id":0,"keep":true,"type":"mystery",'
                '"keywords":["徽章","秘密"],"importance":"major","confidence":0.9}]}'
            )
        ),
    )
    memory_results = ["legacy 全局摘要", "主角：状态稳定", "{}", "legacy 记忆摘要"]
    legacy_generate = AsyncMock(side_effect=AssertionError("不应再调用 legacy finalize monolith"))
    memory_call = AsyncMock(side_effect=memory_results.copy())
    embedding_call = AsyncMock(return_value=[0.1, 0.2, 0.3])
    monkeypatch.setattr(LLMService, "generate", legacy_generate)
    monkeypatch.setattr(
        LLMService,
        "generate_detached",
        memory_call,
    )
    monkeypatch.setattr(LLMService, "get_embedding_detached", embedding_call)

    async with db_session_factory() as session:
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalar_one()
        session.add_all(
            [
                BlueprintCharacter(project_id=project_id, name="主角", position=1),
                ChapterProjectionRollout(
                    id=str(uuid4()),
                    chapter_id=chapter.id,
                    project_id=project_id,
                    owner="legacy",
                    state="legacy",
                    generation=1,
                    fencing_token=0,
                    transition_sequence=0,
                ),
            ]
        )
        await session.commit()

        dispatcher = await ChapterFinalizeSubmissionService(session).submit(
            project_id=project_id,
            chapter_number=1,
            user_id=user_id,
            selected_version_index=0,
            edited_content="那枚神秘徽章隐藏着他的身份秘密，真相显得格外蹊跷又不对劲。",
            skip_vector_update=False,
        )
        dispatcher_id = dispatcher.id

    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="legacy-lineage-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    assert await worker.run_once() is True
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        dispatcher = await JobService(session).get_job(dispatcher_id)
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalar_one()
        revision = (
            await session.execute(
                select(ChapterRevision).where(ChapterRevision.chapter_id == chapter.id)
            )
        ).scalar_one()
        snapshot = (
            await session.execute(
                select(ChapterSnapshot).where(
                    ChapterSnapshot.project_id == project_id,
                    ChapterSnapshot.chapter_number == 1,
                    ChapterSnapshot.is_active.is_(True),
                )
            )
        ).scalar_one()
        states = list(
            (
                await session.execute(
                    select(CharacterState).where(CharacterState.project_id == project_id)
                )
            )
            .scalars()
            .all()
        )
        chunks = list(
            (await session.execute(select(RagChunk).where(RagChunk.project_id == project_id)))
            .scalars()
            .all()
        )
        summaries = list(
            (await session.execute(select(RagSummary).where(RagSummary.project_id == project_id)))
            .scalars()
            .all()
        )
        foreshadowings = list(
            (
                await session.execute(
                    select(Foreshadowing).where(Foreshadowing.project_id == project_id)
                )
            )
            .scalars()
            .all()
        )

        assert dispatcher is not None
        assert dispatcher.result["status"] == "dispatched"
        assert chapter.status == "successful"
        assert revision.lifecycle == "successful"
        assert snapshot.chapter_revision == chapter.current_revision == 1
        assert snapshot.artifact_generation == "legacy"
        assert snapshot.projection_run_id is None
        assert len(states) == 1
        assert all(
            state.chapter_revision == 1
            and state.artifact_generation == "legacy"
            and state.projection_run_id is None
            for state in states
        )
        assert chunks
        assert summaries
        assert all(
            item.source_revision == 1
            and item.artifact_generation == "legacy"
            and item.projection_run_id is None
            for item in [*chunks, *summaries]
        )
        assert len(foreshadowings) == 1
        assert foreshadowings[0].chapter_revision == 1
        assert foreshadowings[0].artifact_generation == "legacy"
        assert foreshadowings[0].projection_run_id is None

        await NovelService(session).delete_chapters(
            project_id,
            [1],
            delete_artifacts_confirmed=True,
            confirmation_text="删除第1章及全部产物",
        )

    async with db_session_factory() as session:
        snapshot = await session.get(ChapterSnapshot, snapshot.id)
        states = [await session.get(CharacterState, state.id) for state in states]
        chunks = [await session.get(RagChunk, chunk.id) for chunk in chunks]
        summaries = [await session.get(RagSummary, summary.id) for summary in summaries]
        foreshadowings = [
            await session.get(Foreshadowing, foreshadowing.id) for foreshadowing in foreshadowings
        ]
        assert snapshot is not None
        assert snapshot.is_active is False
        assert all(item is not None and item.is_active is False for item in states)
        assert all(item is not None and item.is_active is False for item in chunks)
        assert all(item is not None and item.is_active is False for item in summaries)
        assert all(item is not None and item.is_active is False for item in foreshadowings)

    legacy_generate.assert_not_awaited()
    assert memory_call.await_count == 4
    assert embedding_call.await_count >= 2


@pytest.mark.asyncio(loop_scope="session")
async def test_legacy_finalize_dead_letters_incompatible_memory_activity(
    db_session_factory,
    monkeypatch,
):
    project_id = "finalize-legacy-activity-project"
    user_id = 1407
    await _seed_finalize_chapter(
        db_session_factory,
        user_id=user_id,
        project_id=project_id,
    )
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="测试提示词"))
    monkeypatch.setattr(
        LLMService,
        "get_summary_detached",
        AsyncMock(return_value="legacy 章节摘要"),
    )
    monkeypatch.setattr(
        LLMService,
        "get_llm_response_detached",
        AsyncMock(return_value='{"items":[]}'),
    )
    memory_call = AsyncMock(side_effect=AssertionError("不得重放历史 memory 外部调用"))
    monkeypatch.setattr(LLMService, "generate_detached", memory_call)

    async with db_session_factory() as session:
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalar_one()
        session.add(
            ChapterProjectionRollout(
                id=str(uuid4()),
                chapter_id=chapter.id,
                project_id=project_id,
                owner="legacy",
                state="legacy",
                generation=1,
                fencing_token=0,
                transition_sequence=0,
            )
        )
        await session.commit()
        dispatcher = await ChapterFinalizeSubmissionService(session).submit(
            project_id=project_id,
            chapter_number=1,
            user_id=user_id,
            selected_version_index=0,
            skip_vector_update=True,
        )
        dispatcher_id = dispatcher.id

    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="legacy-activity-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        dispatcher = await JobService(session).get_job(dispatcher_id)
        assert dispatcher is not None
        legacy_job_id = dispatcher.result["root_job_id"]
        legacy_job = await JobService(session).get_job(legacy_job_id)
        assert legacy_job is not None
        now = datetime.now(timezone.utc)
        session.add(
            JobActivity(
                id=str(uuid4()),
                job_id=legacy_job_id,
                activity_key="finalize_memory",
                side_effect_class="ambiguous_external",
                status="succeeded",
                provider_request_key=str(uuid4()),
                attempt=0,
                fencing_token=0,
                request_payload={
                    "project_id": legacy_job.payload["project_id"],
                    "chapter_number": legacy_job.payload["chapter_number"],
                    "content_hash": legacy_job.payload["content_hash"],
                    "skip_vector_update": legacy_job.payload["skip_vector_update"],
                },
                result_payload={"success": True, "updated_fields": []},
                started_at=now,
                completed_at=now,
                updated_at=now,
            )
        )
        await session.commit()

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        legacy_job = await JobService(session).get_job(legacy_job_id)
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalar_one()
        snapshots = list(
            (
                await session.execute(
                    select(ChapterSnapshot).where(ChapterSnapshot.project_id == project_id)
                )
            )
            .scalars()
            .all()
        )

    assert legacy_job is not None
    assert legacy_job.status == "dead_letter"
    assert legacy_job.error_category == "legacy_memory_result_incompatible"
    assert chapter.status == "finalizing"
    assert snapshots == []
    memory_call.assert_not_awaited()


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
        "get_summary_result_detached",
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
        dispatcher_task = await JobService(session).get_job(task_id)
        assert dispatcher_task is not None
        assert dispatcher_task.status == "succeeded"
        assert dispatcher_task.result["status"] == "dispatched"
        summary_task_id = dispatcher_task.result["root_job_id"]

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        dispatcher_task = await JobService(session).get_job(task_id)
        summary_task = await JobService(session).get_job(summary_task_id)
        chapter = (
            await session.execute(
                select(Chapter).where(Chapter.project_id == "finalize-ambiguous-project")
            )
        ).scalar_one()
        activity = (
            await session.execute(
                select(JobActivity).where(
                    JobActivity.job_id == summary_task_id,
                    JobActivity.activity_key == "summary_generation",
                )
            )
        ).scalar_one()
        projection = (
            await session.execute(
                select(ChapterProjectionRun).where(ChapterProjectionRun.job_id == summary_task_id)
            )
        ).scalar_one()

    assert dispatcher_task is not None
    assert dispatcher_task.status == "succeeded"
    assert dispatcher_task.result["status"] == "dispatched"
    assert summary_task is not None
    assert summary_task.status == "needs_attention"
    assert chapter.status == "finalizing"
    assert chapter.selected_version_id is not None
    assert activity.status == "ambiguous"
    assert projection.status == "needs_attention"


@pytest.mark.asyncio(loop_scope="session")
async def test_failed_summary_replay_completes_without_regenerating_canonical_content(
    db_session_factory,
    monkeypatch,
):
    project_id = str(uuid4())
    user_id = 1405
    await _seed_finalize_chapter(
        db_session_factory,
        user_id=user_id,
        project_id=project_id,
    )
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="测试提示词"))
    monkeypatch.setattr(
        LLMService,
        "get_summary_result_detached",
        AsyncMock(return_value=_ai_call_result("")),
    )

    async with db_session_factory() as session:
        operator = await session.get(User, user_id)
        assert operator is not None
        operator.is_admin = True
        await session.commit()
        dispatcher = await ChapterFinalizeSubmissionService(session).submit(
            project_id=project_id,
            chapter_number=1,
            user_id=user_id,
            selected_version_index=0,
            edited_content="无需重新生成的最终正文",
            skip_vector_update=True,
        )
        dispatcher_id = dispatcher.id

    worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="finalize-failed-summary-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    assert await worker.run_once() is True

    async with db_session_factory() as session:
        dispatcher = await JobService(session).get_job(dispatcher_id)
        assert dispatcher is not None
        summary_job_id = dispatcher.result["root_job_id"]

    assert await worker.run_once() is True

    async with db_session_factory() as session:
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalar_one()
        revision = (
            await session.execute(
                select(ChapterRevision).where(ChapterRevision.chapter_id == chapter.id)
            )
        ).scalar_one()
        outbox = (
            await session.execute(
                select(ChapterOutboxEvent).where(
                    ChapterOutboxEvent.chapter_id == chapter.id,
                    ChapterOutboxEvent.event_type == "ChapterFinalizationRequested",
                )
            )
        ).scalar_one()
        failed_run = (
            await session.execute(
                select(ChapterProjectionRun).where(ChapterProjectionRun.job_id == summary_job_id)
            )
        ).scalar_one()
        selected_version_id = chapter.selected_version_id
        source_generation = revision.source_generation

    assert chapter.status == "finalizing"
    assert chapter.current_revision == 1
    assert revision.lifecycle == "finalizing"
    assert revision.source_content == "无需重新生成的最终正文"
    assert failed_run.status == "failed"
    assert failed_run.is_active is False

    request = ChapterProjectionOperationRequest(
        project_id=project_id,
        chapter_id=chapter.id,
        revision=revision.revision,
        projection_name="summary",
        idempotency_key="repair-failed-summary",
        reason="修复 provider 后继续定稿",
        outbox_event_id=outbox.id,
    )
    async with db_session_factory() as session:
        replay = await ChapterProjectionOpsService(session).execute(
            request=request,
            operator_user_id=user_id,
            mode="replay",
        )

    assert replay.status == "queued"
    assert replay.job_id is not None
    assert replay.projection_run_id is not None

    async with db_session_factory() as session:
        replay_run = await session.get(ChapterProjectionRun, replay.projection_run_id)
        replay_audit = (
            await session.execute(
                select(ChapterProjectionReplayAudit).where(
                    ChapterProjectionReplayAudit.project_id == project_id
                )
            )
        ).scalar_one()
        summary_runs = list(
            (
                await session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.chapter_id == chapter.id,
                        ChapterProjectionRun.projection_name == "summary",
                    )
                )
            )
            .scalars()
            .all()
        )

    assert replay_run is not None
    assert replay_run.replay_of_run_id == failed_run.id
    assert sorted(run.status for run in summary_runs) == ["failed", "queued"]
    assert replay_audit.status == "completed"
    assert replay_audit.result["job_id"] == replay.job_id

    monkeypatch.setattr(
        LLMService,
        "get_summary_result_detached",
        AsyncMock(return_value=_ai_call_result("修复后的章节摘要")),
    )
    monkeypatch.setattr(
        LLMService,
        "get_llm_response_result_detached",
        AsyncMock(return_value=_ai_call_result('{"items":[]}', stage="foreshadowing")),
    )
    monkeypatch.setattr(
        LLMService,
        "generate_result_detached",
        AsyncMock(
            side_effect=[
                _ai_call_result("全局摘要"),
                _ai_call_result("角色状态"),
                _ai_call_result("{}"),
                _ai_call_result("章节摘要"),
            ]
        ),
    )

    replay_worker = JobWorker(
        session_factory=db_session_factory,
        registry=build_job_handler_registry(),
        worker_id="finalize-summary-replay-worker",
        lease_seconds=30,
        heartbeat_interval_seconds=5,
    )
    for _ in range(5):
        assert await replay_worker.run_once() is True
    assert await replay_worker.run_once() is False

    async with db_session_factory() as session:
        chapter = await session.get(Chapter, chapter.id)
        revision = await session.get(ChapterRevision, revision.id)
        selected_version = await session.get(ChapterVersion, selected_version_id)
        revision_count = await session.scalar(
            select(func.count(ChapterRevision.id)).where(ChapterRevision.project_id == project_id)
        )
        version_count = await session.scalar(
            select(func.count(ChapterVersion.id)).where(ChapterVersion.chapter_id == chapter.id)
        )
        finalized_count = await session.scalar(
            select(func.count(ChapterOutboxEvent.id)).where(
                ChapterOutboxEvent.project_id == project_id,
                ChapterOutboxEvent.event_type == "ChapterFinalized",
            )
        )
        finalization_requested_count = await session.scalar(
            select(func.count(ChapterOutboxEvent.id)).where(
                ChapterOutboxEvent.project_id == project_id,
                ChapterOutboxEvent.event_type == "ChapterFinalizationRequested",
            )
        )
        summary_runs = list(
            (
                await session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.chapter_id == chapter.id,
                        ChapterProjectionRun.projection_name == "summary",
                    )
                )
            )
            .scalars()
            .all()
        )
        downstream_runs = list(
            (
                await session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.chapter_id == chapter.id,
                        ChapterProjectionRun.projection_name.in_(
                            ["memory", "foreshadowing", "trace", "rag"]
                        ),
                    )
                )
            )
            .scalars()
            .all()
        )

    assert chapter is not None
    assert chapter.status == "successful"
    assert chapter.current_revision == 1
    assert chapter.selected_version_id == selected_version_id
    assert revision is not None
    assert revision.lifecycle == "successful"
    assert revision.source_generation == source_generation
    assert revision.source_content == "无需重新生成的最终正文"
    assert selected_version is not None
    assert selected_version.content == "无需重新生成的最终正文"
    assert revision_count == 1
    assert version_count == 2
    assert finalized_count == 1
    assert finalization_requested_count == 1
    assert sorted(run.status for run in summary_runs) == ["failed", "succeeded"]
    assert {run.dependency_run_id for run in downstream_runs} == {replay.projection_run_id}
