import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.models.background_task import BackgroundTask
from app.models.chapter_projection import (
    ChapterOutboxEvent,
    ChapterProjectionRollout,
    ChapterProjectionRun,
    ChapterRevision,
)
from app.models.novel import Chapter, ChapterVersion, NovelProject
from app.models.rag import RagChunk, RagSummary
from app.models.user import User
from app.schemas.job import ChapterFinalizeOutboxPayload, ChapterProjectionJobPayload
from app.services.chapter_projection_contract import payload_fingerprint
from app.services.chapter_projection_runtime import (
    CurrentProjection,
    _derived_projection_id,
    enqueue_downstream_projections,
    load_current_projection,
    maybe_enqueue_reconciler,
)
from app.services.job_handlers import build_job_handler_registry
from app.services.job_service import JobService
from app.services.job_worker import JobWorker
from app.services.novel_service import NovelService
from app.services.vector_store_service import VectorStoreService


def _uuid() -> str:
    return str(uuid4())


def test_derived_projection_identity_is_stable_and_dependency_scoped() -> None:
    inputs = {
        "chapter_revision_id": _uuid(),
        "dependency_run_id": _uuid(),
        "projection_name": "memory",
        "identity": "run",
    }

    first = _derived_projection_id(**inputs)
    assert _derived_projection_id(**inputs) == first
    assert _derived_projection_id(
        **{**inputs, "dependency_run_id": _uuid()}
    ) != first
    assert _derived_projection_id(
        **{**inputs, "projection_name": "foreshadowing"}
    ) != first
    assert _derived_projection_id(**{**inputs, "identity": "artifact"}) != first


async def _add_projection_scope(session, *, user_id: int, project_id: str):
    source_hash = "a" * 64
    source_generation = _uuid()
    session.add(User(id=user_id, username=f"runtime-user-{user_id}", hashed_password="x"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="投影运行时测试",
            initial_prompt="测试",
        )
    )
    chapter = Chapter(
        project_id=project_id,
        chapter_number=1,
        status="finalizing",
        current_revision=1,
        source_hash=source_hash,
        required_projection_snapshot=["summary", "memory", "foreshadowing"],
        projection_generation=source_generation,
        tombstone_revision=0,
    )
    session.add(chapter)
    await session.flush()
    revision = ChapterRevision(
        id=_uuid(),
        chapter_id=chapter.id,
        project_id=project_id,
        chapter_number=1,
        revision=1,
        source_hash=source_hash,
        source_content="正文",
        projection_context={},
        lifecycle="finalizing",
        required_projections=["summary", "memory", "foreshadowing"],
        skipped_projections=["rag"],
        source_generation=source_generation,
    )
    rollout = ChapterProjectionRollout(
        id=_uuid(),
        chapter_id=chapter.id,
        project_id=project_id,
        owner="projection",
        state="projection",
        generation=1,
        fencing_token=0,
    )
    session.add_all([revision, rollout])
    await session.flush()
    return chapter, revision, rollout


def _payload(
    *,
    chapter: Chapter,
    revision: ChapterRevision,
    run: ChapterProjectionRun,
    dependency_run_id: str | None,
    workflow_stream_id: str | None = None,
    outbox_event_id: str | None = None,
    skip_vector_update: bool = False,
) -> ChapterProjectionJobPayload:
    return ChapterProjectionJobPayload(
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        chapter_number=chapter.chapter_number,
        chapter_revision_id=revision.id,
        revision=revision.revision,
        source_hash=revision.source_hash,
        source_generation=revision.source_generation,
        projection_run_id=run.id,
        artifact_generation=run.artifact_generation,
        workflow_stream_id=workflow_stream_id or _uuid(),
        outbox_event_id=outbox_event_id or _uuid(),
        rollout_owner="projection",
        rollout_generation=1,
        rollout_fencing_token=0,
        execution_mode="active",
        dependency_run_id=dependency_run_id,
        skip_vector_update=skip_vector_update,
    )


async def _add_finalize_outbox(
    session,
    *,
    chapter: Chapter,
    revision: ChapterRevision,
    summary: ChapterProjectionRun,
) -> ChapterOutboxEvent:
    event_id = _uuid()
    workflow_stream_id = _uuid()
    payload = ChapterFinalizeOutboxPayload(
        job_type="chapter_finalize",
        payload_version=2,
        project_id=chapter.project_id,
        chapter_id=chapter.id,
        chapter_number=chapter.chapter_number,
        chapter_revision_id=revision.id,
        revision=revision.revision,
        source_hash=revision.source_hash,
        source_generation=revision.source_generation,
        execution_mode="active",
        rollout_owner="projection",
        rollout_generation=1,
        rollout_fencing_token=0,
        workflow_stream_type="workflow",
        workflow_stream_id=workflow_stream_id,
        outbox_event_id=event_id,
        selected_version_id=1,
        content_hash=revision.source_hash,
        skip_vector_update=True,
        dispatch_idempotency_key=f"runtime:{event_id}",
        summary_run_id=summary.id,
        summary_artifact_generation=summary.artifact_generation,
    ).model_dump()
    event = ChapterOutboxEvent(
        id=event_id,
        aggregate_type="chapter",
        aggregate_id=str(chapter.id),
        chapter_id=chapter.id,
        project_id=chapter.project_id,
        revision=revision.revision,
        event_type="ChapterFinalizationRequested",
        event_version=2,
        payload=payload,
        payload_fingerprint=payload_fingerprint(payload),
        idempotency_key=f"runtime:{event_id}:finalize",
        workflow_stream_type="workflow",
        workflow_stream_id=workflow_stream_id,
    )
    session.add(event)
    await session.flush()
    return event


@pytest.mark.asyncio(loop_scope="session")
async def test_downstream_projection_creation_is_idempotent(db_session_factory) -> None:
    async with db_session_factory() as session:
        chapter, revision, rollout = await _add_projection_scope(
            session,
            user_id=1701,
            project_id="projection-runtime-idempotency",
        )
        summary = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="summary",
            source_hash=revision.source_hash,
            artifact_generation=_uuid(),
            status="succeeded",
            required=True,
            is_active=True,
            checkpoint={},
        )
        session.add(summary)
        await session.flush()
        payload = _payload(
            chapter=chapter,
            revision=revision,
            run=summary,
            dependency_run_id=None,
        )
        current = CurrentProjection(chapter, revision, summary, rollout, None)

        first = await enqueue_downstream_projections(
            session,
            payload=payload,
            current=current,
            user_id=1701,
        )
        await session.flush()
        second = await enqueue_downstream_projections(
            session,
            payload=payload,
            current=current,
            user_id=1701,
        )
        await session.flush()

        run_count = await session.scalar(
            select(func.count(ChapterProjectionRun.id)).where(
                ChapterProjectionRun.chapter_revision_id == revision.id
            )
        )
        job_count = await session.scalar(
            select(func.count(BackgroundTask.id)).where(
                BackgroundTask.project_id == chapter.project_id
            )
        )

    assert [run.id for run in second] == [run.id for run in first]
    assert run_count == 5
    assert job_count == 3


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_rejects_non_summary_dependency(db_session_factory) -> None:
    async with db_session_factory() as session:
        chapter, revision, _ = await _add_projection_scope(
            session,
            user_id=1702,
            project_id="projection-runtime-dependency",
        )
        wrong_dependency = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="trace",
            source_hash=revision.source_hash,
            artifact_generation=_uuid(),
            status="succeeded",
            required=False,
            is_active=True,
            checkpoint={},
        )
        summary = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="summary",
            source_hash=revision.source_hash,
            artifact_generation=_uuid(),
            status="succeeded",
            required=True,
            is_active=True,
            checkpoint={},
        )
        memory = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="memory",
            source_hash=revision.source_hash,
            dependency_run_id=wrong_dependency.id,
            artifact_generation=_uuid(),
            status="queued",
            required=True,
            is_active=False,
            checkpoint={},
        )
        session.add_all([summary, wrong_dependency, memory])
        await session.flush()
        event = await _add_finalize_outbox(
            session,
            chapter=chapter,
            revision=revision,
            summary=summary,
        )
        payload = _payload(
            chapter=chapter,
            revision=revision,
            run=memory,
            dependency_run_id=wrong_dependency.id,
            workflow_stream_id=event.workflow_stream_id,
            outbox_event_id=event.id,
            skip_vector_update=True,
        )

        current = await load_current_projection(
            session,
            payload=payload,
            user_id=1702,
            job_id=_uuid(),
            expected_projection="memory",
            for_update=True,
        )

    assert current is None


@pytest.mark.parametrize(
    "summary_status",
    ["queued", "running", "retry_wait", "failed", "needs_attention"],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_downstream_rejects_every_non_succeeded_summary_status(
    db_session_factory,
    summary_status,
) -> None:
    async with db_session_factory() as session:
        chapter, revision, _ = await _add_projection_scope(
            session,
            user_id=1705,
            project_id=f"runtime-summary-{summary_status}",
        )
        summary = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="summary",
            source_hash=revision.source_hash,
            artifact_generation=_uuid(),
            status=summary_status,
            required=True,
            is_active=False,
            checkpoint={},
        )
        memory = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="memory",
            source_hash=revision.source_hash,
            dependency_run_id=summary.id,
            artifact_generation=_uuid(),
            status="queued",
            required=True,
            is_active=False,
            checkpoint={},
        )
        session.add_all([summary, memory])
        await session.flush()
        event = await _add_finalize_outbox(
            session,
            chapter=chapter,
            revision=revision,
            summary=summary,
        )
        payload = _payload(
            chapter=chapter,
            revision=revision,
            run=memory,
            dependency_run_id=summary.id,
            workflow_stream_id=event.workflow_stream_id,
            outbox_event_id=event.id,
            skip_vector_update=True,
        )

        current = await load_current_projection(
            session,
            payload=payload,
            user_id=1705,
            job_id=_uuid(),
            expected_projection="memory",
            for_update=True,
        )

    assert current is None


@pytest.mark.asyncio(loop_scope="session")
async def test_projection_rejects_outbox_identity_drift(db_session_factory) -> None:
    async with db_session_factory() as session:
        chapter, revision, _ = await _add_projection_scope(
            session,
            user_id=1703,
            project_id="projection-runtime-outbox",
        )
        summary = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="summary",
            source_hash=revision.source_hash,
            artifact_generation=_uuid(),
            status="succeeded",
            required=True,
            is_active=True,
            checkpoint={},
        )
        memory = ChapterProjectionRun(
            id=_uuid(),
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            revision=1,
            projection_name="memory",
            source_hash=revision.source_hash,
            dependency_run_id=summary.id,
            artifact_generation=_uuid(),
            status="queued",
            required=True,
            is_active=False,
            checkpoint={},
        )
        session.add_all([summary, memory])
        await session.flush()
        event = await _add_finalize_outbox(
            session,
            chapter=chapter,
            revision=revision,
            summary=summary,
        )
        payload = _payload(
            chapter=chapter,
            revision=revision,
            run=memory,
            dependency_run_id=summary.id,
            workflow_stream_id=event.workflow_stream_id,
            outbox_event_id=event.id,
            skip_vector_update=True,
        )

        assert (
            await load_current_projection(
                session,
                payload=payload,
                user_id=1703,
                job_id=_uuid(),
                expected_projection="memory",
                for_update=False,
            )
            is not None
        )
        for drifted_payload in (
            payload.model_copy(update={"outbox_event_id": _uuid()}),
            payload.model_copy(update={"workflow_stream_id": _uuid()}),
        ):
            assert (
                await load_current_projection(
                    session,
                    payload=drifted_payload,
                    user_id=1703,
                    job_id=_uuid(),
                    expected_projection="memory",
                    for_update=False,
                )
                is None
            )

        event.payload = {**event.payload, "skip_vector_update": False}
        await session.flush()
        assert (
            await load_current_projection(
                session,
                payload=payload,
                user_id=1703,
                job_id=_uuid(),
                expected_projection="memory",
                for_update=False,
            )
            is None
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_vector_activation_requires_current_canonical_identity(
    db_session_factory,
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.services.vector_store_service.settings.vector_store_enabled", True)
    async with db_session_factory() as session:
        chapter, revision, _ = await _add_projection_scope(
            session,
            user_id=1704,
            project_id="projection-runtime-vector-cas",
        )
        vector_store = VectorStoreService()

        def records(generation: str):
            return (
                [
                    {
                        "id": f"vector-cas:{generation}:chunk",
                        "project_id": chapter.project_id,
                        "chapter_number": chapter.chapter_number,
                        "chunk_index": 0,
                        "chapter_title": "第一章",
                        "content": generation,
                        "embedding": [0.1, 0.2, 0.3],
                        "source_revision": revision.revision,
                        "artifact_generation": generation,
                        "projection_run_id": None,
                        "metadata": {},
                    }
                ],
                [
                    {
                        "id": f"vector-cas:{generation}:summary",
                        "project_id": chapter.project_id,
                        "chapter_number": chapter.chapter_number,
                        "title": "第一章",
                        "summary": generation,
                        "embedding": [0.1, 0.2, 0.3],
                        "source_revision": revision.revision,
                        "artifact_generation": generation,
                        "projection_run_id": None,
                    }
                ],
            )

        async def activate(generation: str) -> None:
            chunks, summaries = records(generation)
            await vector_store.apply_chapter_projection(
                session,
                project_id=chapter.project_id,
                chapter_number=chapter.chapter_number,
                revision=revision.revision,
                artifact_generation=generation,
                projection_run_id=None,
                expected_source_hash=revision.source_hash,
                expected_source_generation=revision.source_generation,
                chunk_records=chunks,
                summary_records=summaries,
                activate=True,
            )

        await activate("vector-generation-1")
        await activate("vector-generation-2")
        await session.flush()

        chunks = list(
            (
                await session.execute(
                    select(RagChunk).where(RagChunk.project_id == chapter.project_id)
                )
            ).scalars().all()
        )
        summaries = list(
            (
                await session.execute(
                    select(RagSummary).where(RagSummary.project_id == chapter.project_id)
                )
            ).scalars().all()
        )
        assert {row.artifact_generation for row in chunks if row.is_active} == {
            "vector-generation-2"
        }
        assert {row.artifact_generation for row in summaries if row.is_active} == {
            "vector-generation-2"
        }

        chapter.current_revision = 2
        chapter.source_hash = "b" * 64
        chapter.projection_generation = _uuid()
        await session.flush()
        with pytest.raises(ValueError, match="章节向量激活条件已失效"):
            await activate("vector-generation-3")

        assert await session.get(RagChunk, "vector-cas:vector-generation-3:chunk") is None
        assert await session.get(RagSummary, "vector-cas:vector-generation-3:summary") is None
        assert {row.artifact_generation for row in chunks if row.is_active} == {
            "vector-generation-2"
        }


@pytest.mark.asyncio(loop_scope="session")
async def test_paused_reconciler_cannot_finalize_a_regenerated_revision(
    isolated_pg,
    monkeypatch,
) -> None:
    session_factory = isolated_pg.session_factory
    project_id = str(uuid4())
    owner_user_id = 1_770_000_000 + uuid4().int % 1_000_000
    writer_ready = asyncio.Event()
    resume_writer = asyncio.Event()
    worker_task: asyncio.Task | None = None
    monkeypatch.setattr(
        "app.services.job_service.publish_background_task",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.novel_service.publish_background_task",
        AsyncMock(),
    )

    try:
        async with session_factory() as session:
            chapter, revision, rollout = await _add_projection_scope(
                session,
                user_id=owner_user_id,
                project_id=project_id,
            )
            version = ChapterVersion(
                chapter_id=chapter.id,
                version_label="version1",
                content="旧 revision 正文",
            )
            session.add(version)
            await session.flush()
            chapter.selected_version_id = version.id

            summary = ChapterProjectionRun(
                id=_uuid(),
                chapter_revision_id=revision.id,
                chapter_id=chapter.id,
                project_id=project_id,
                revision=1,
                projection_name="summary",
                source_hash=revision.source_hash,
                artifact_generation=_uuid(),
                status="succeeded",
                required=True,
                is_active=True,
                checkpoint={},
            )
            memory = ChapterProjectionRun(
                id=_uuid(),
                chapter_revision_id=revision.id,
                chapter_id=chapter.id,
                project_id=project_id,
                revision=1,
                projection_name="memory",
                source_hash=revision.source_hash,
                dependency_run_id=summary.id,
                artifact_generation=_uuid(),
                status="succeeded",
                required=True,
                is_active=True,
                checkpoint={},
            )
            foreshadowing = ChapterProjectionRun(
                id=_uuid(),
                chapter_revision_id=revision.id,
                chapter_id=chapter.id,
                project_id=project_id,
                revision=1,
                projection_name="foreshadowing",
                source_hash=revision.source_hash,
                dependency_run_id=summary.id,
                artifact_generation=_uuid(),
                status="succeeded",
                required=True,
                is_active=True,
                checkpoint={},
            )
            session.add_all([summary, memory, foreshadowing])
            await session.flush()
            event = await _add_finalize_outbox(
                session,
                chapter=chapter,
                revision=revision,
                summary=summary,
            )
            summary_payload = _payload(
                chapter=chapter,
                revision=revision,
                run=summary,
                dependency_run_id=None,
                workflow_stream_id=event.workflow_stream_id,
                outbox_event_id=event.id,
                skip_vector_update=True,
            )
            reconcile = await maybe_enqueue_reconciler(
                session,
                payload=summary_payload,
                current=CurrentProjection(chapter, revision, summary, rollout, None),
                user_id=owner_user_id,
            )
            assert reconcile is not None and reconcile.job_id is not None
            chapter_id = chapter.id
            revision_id = revision.id
            reconcile_id = reconcile.id
            reconcile_job_id = reconcile.job_id
            await session.commit()

        original_mark_succeeded = JobService.mark_succeeded

        async def pause_reconcile_outcome(
            service,
            lease,
            *,
            result=None,
            outcome_writer=None,
            now=None,
        ):
            if lease.job_id == reconcile_job_id:
                writer_ready.set()
                await resume_writer.wait()
            return await original_mark_succeeded(
                service,
                lease,
                result=result,
                outcome_writer=outcome_writer,
                now=now,
            )

        monkeypatch.setattr(JobService, "mark_succeeded", pause_reconcile_outcome)
        worker = JobWorker(
            session_factory=session_factory,
            registry=build_job_handler_registry(),
            worker_id=f"reconcile-race-{uuid4()}",
            lease_seconds=30,
            heartbeat_interval_seconds=5,
        )
        worker_task = asyncio.create_task(worker.run_once())
        await asyncio.wait_for(writer_ready.wait(), timeout=5)

        async with session_factory() as session:
            chapter = await session.get(Chapter, chapter_id)
            assert chapter is not None
            await NovelService(session).replace_chapter_versions(
                chapter,
                ["新 revision 候选正文"],
            )

        resume_writer.set()
        assert await asyncio.wait_for(worker_task, timeout=5) is True

        async with session_factory() as session:
            chapter = await session.get(Chapter, chapter_id)
            old_revision = await session.get(ChapterRevision, revision_id)
            reconcile_run = await session.get(ChapterProjectionRun, reconcile_id)
            reconcile_job = await session.get(BackgroundTask, reconcile_job_id)
            finalized_count = await session.scalar(
                select(func.count(ChapterOutboxEvent.id)).where(
                    ChapterOutboxEvent.project_id == project_id,
                    ChapterOutboxEvent.event_type == "ChapterFinalized",
                )
            )

        assert chapter is not None
        assert chapter.current_revision == 2
        assert chapter.status == "waiting_for_confirm"
        assert old_revision is not None and old_revision.lifecycle == "superseded"
        assert reconcile_run is not None and reconcile_run.status == "stale"
        assert reconcile_job is not None and reconcile_job.result["status"] == "stale"
        assert finalized_count == 0
    finally:
        resume_writer.set()
        if worker_task is not None and not worker_task.done():
            worker_task.cancel()
        if worker_task is not None:
            await asyncio.gather(worker_task, return_exceptions=True)
        async with session_factory() as session:
            await session.execute(
                delete(ChapterOutboxEvent).where(
                    ChapterOutboxEvent.project_id == project_id
                )
            )
            await session.execute(
                delete(NovelProject).where(NovelProject.id == project_id)
            )
            await session.execute(delete(User).where(User.id == owner_user_id))
            await session.commit()
