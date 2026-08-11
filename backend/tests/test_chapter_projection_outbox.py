import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.models import (
    Chapter,
    ChapterOutboxEvent,
    ChapterOutline,
    ChapterProjectionRollout,
    ChapterProjectionRolloutTransition,
    ChapterProjectionReplayAudit,
    ChapterProjectionRun,
    ChapterRevision,
    ChapterSnapshot,
    ChapterVersion,
    Foreshadowing,
    NovelProject,
    RagChunk,
    RagSummary,
)
from app.models.background_task import BackgroundTask
from app.models.user import User
from app.schemas.chapter_context import stable_digest
from app.schemas.chapter_projection import ChapterProjectionOperationRequest
from app.schemas.job import (
    ChapterFinalizeOutboxPayload,
    ChapterOutboxDispatchJobPayload,
    ChapterProjectionJobPayload,
)
from app.services.chapter_outbox_dispatcher import (
    ChapterOutboxDispatcher,
    repair_chapter_outbox_backlog,
)
from app.services.chapter_finalize_service import ChapterFinalizeSubmissionService
from app.services.chapter_projection_ops import (
    ChapterProjectionConflictError,
    ChapterProjectionNotFoundError,
    ChapterProjectionOpsService,
)
from app.services.chapter_projection_rollout import ChapterProjectionRolloutService
from app.services.chapter_projection_runtime import load_current_projection
from app.services.chapter_projection_service import (
    ChapterProjectionService,
    payload_fingerprint,
)
from app.services.job_handlers import build_job_handler_registry
from app.services.job_worker import JobWorker, PermanentJobError
from app.services.novel_service import NovelService
from app.services.prompt_service import PromptService


async def _seed_active_finalize_event(
    session_factory,
    *,
    user_id: int,
    project_id: str,
    dispatch_key: str,
) -> tuple[str, ChapterOutboxDispatchJobPayload]:
    source_content = "章节正文"
    source_hash = stable_digest(source_content)
    source_generation = str(uuid4())
    event_id = str(uuid4())
    revision_id = str(uuid4())
    summary_run_id = str(uuid4())
    summary_generation = str(uuid4())
    workflow_id = str(uuid4())

    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                username=f"outbox-{user_id}",
                hashed_password="secret",
                is_admin=True,
            )
        )
        session.add(
            NovelProject(
                id=project_id,
                user_id=user_id,
                title="outbox test",
                initial_prompt="test",
            )
        )
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            status="finalizing",
            current_revision=1,
            source_hash=source_hash,
            projection_generation=source_generation,
            tombstone_revision=0,
            required_projection_snapshot=["summary"],
        )
        session.add(chapter)
        await session.flush()
        version = ChapterVersion(
            chapter_id=chapter.id,
            version_label="version1",
            content=source_content,
        )
        session.add(version)
        await session.flush()
        chapter.selected_version_id = version.id

        revision = ChapterRevision(
            id=revision_id,
            chapter_id=chapter.id,
            project_id=project_id,
            chapter_number=1,
            revision=1,
            selected_version_id=version.id,
            source_hash=source_hash,
            source_content=source_content,
            projection_context={},
            lifecycle="finalizing",
            required_projections=["summary"],
            skipped_projections=[],
            source_generation=source_generation,
        )
        rollout = ChapterProjectionRollout(
            id=str(uuid4()),
            chapter_id=chapter.id,
            project_id=project_id,
            owner="projection",
            state="projection",
            generation=1,
            fencing_token=0,
        )
        payload = ChapterFinalizeOutboxPayload(
            job_type="chapter_finalize",
            payload_version=2,
            project_id=project_id,
            chapter_id=chapter.id,
            chapter_number=1,
            chapter_revision_id=revision_id,
            revision=1,
            source_hash=source_hash,
            source_generation=source_generation,
            execution_mode="active",
            rollout_owner="projection",
            rollout_generation=1,
            rollout_fencing_token=0,
            workflow_stream_type="workflow",
            workflow_stream_id=workflow_id,
            outbox_event_id=event_id,
            selected_version_id=version.id,
            content_hash=source_hash,
            skip_vector_update=True,
            dispatch_idempotency_key=dispatch_key,
            summary_run_id=summary_run_id,
            summary_artifact_generation=summary_generation,
        ).model_dump()
        fingerprint = payload_fingerprint(payload)
        event = ChapterOutboxEvent(
            id=event_id,
            aggregate_type="chapter",
            aggregate_id=str(chapter.id),
            chapter_id=chapter.id,
            project_id=project_id,
            revision=1,
            event_type="ChapterFinalizationRequested",
            event_version=2,
            payload=payload,
            payload_fingerprint=fingerprint,
            idempotency_key=f"chapter:{chapter.id}:revision:1:finalize",
            workflow_stream_type="workflow",
            workflow_stream_id=workflow_id,
        )
        session.add_all([revision, rollout, event])
        await session.commit()

    return event_id, ChapterOutboxDispatchJobPayload(
        project_id=project_id,
        outbox_event_id=event_id,
        event_type="ChapterFinalizationRequested",
        event_version=2,
        payload_fingerprint=fingerprint,
    )


async def _seed_failed_summary_replay(
    session_factory,
    *,
    owner_user_id: int,
    operator_user_id: int,
    project_id: str,
) -> ChapterProjectionOperationRequest:
    event_id, _ = await _seed_active_finalize_event(
        session_factory,
        user_id=owner_user_id,
        project_id=project_id,
        dispatch_key=f"replay-seed:{project_id}",
    )
    async with session_factory() as session:
        event = await session.get(ChapterOutboxEvent, event_id)
        assert event is not None
        payload = ChapterFinalizeOutboxPayload.model_validate(event.payload)
        assert payload.summary_run_id is not None
        assert payload.summary_artifact_generation is not None
        revision = await session.get(ChapterRevision, payload.chapter_revision_id)
        assert revision is not None
        if operator_user_id != owner_user_id:
            session.add(
                User(
                    id=operator_user_id,
                    username=f"replay-operator-{operator_user_id}",
                    hashed_password="secret",
                    is_admin=True,
                )
            )
        session.add(
            ChapterProjectionRun(
                id=payload.summary_run_id,
                chapter_revision_id=revision.id,
                chapter_id=payload.chapter_id,
                project_id=project_id,
                revision=payload.revision,
                projection_name="summary",
                source_hash=payload.source_hash,
                artifact_generation=payload.summary_artifact_generation,
                status="failed",
                required=True,
                is_active=False,
                checkpoint={"outbox_event_id": event_id},
                result={},
            )
        )
        await session.commit()
    return ChapterProjectionOperationRequest(
        project_id=project_id,
        chapter_id=payload.chapter_id,
        revision=payload.revision,
        projection_name="summary",
        idempotency_key="summary-replay",
        reason="repair failed summary",
        outbox_event_id=event_id,
    )


async def _cleanup_committed_replay_scope(
    session_factory,
    *,
    project_id: str,
    user_ids: tuple[int, ...],
) -> None:
    async with session_factory() as session:
        await session.execute(
            delete(ChapterProjectionRolloutTransition).where(
                ChapterProjectionRolloutTransition.project_id == project_id
            )
        )
        await session.execute(
            delete(ChapterProjectionReplayAudit).where(
                ChapterProjectionReplayAudit.project_id == project_id
            )
        )
        await session.execute(
            delete(ChapterOutboxEvent).where(ChapterOutboxEvent.project_id == project_id)
        )
        await session.execute(delete(NovelProject).where(NovelProject.id == project_id))
        await session.execute(delete(User).where(User.id.in_(user_ids)))
        await session.commit()


async def _wait_for_database_blockers(
    session_factory,
    *,
    blocked_pids: tuple[int, ...],
    blocker_pid: int,
) -> None:
    async def wait_until_blocked() -> None:
        async with session_factory() as observer:
            for _ in range(200):
                blockers = {
                    pid: set(await observer.scalar(select(func.pg_blocking_pids(pid))) or [])
                    for pid in blocked_pids
                }
                known_queue = {blocker_pid, *blocked_pids}
                observed_blockers = set().union(*blockers.values())
                if (
                    all(blockers[pid] for pid in blocked_pids)
                    and all(blockers[pid].issubset(known_queue) for pid in blocked_pids)
                    and blocker_pid in observed_blockers
                ):
                    return
                await asyncio.sleep(0.01)
        raise AssertionError("竞争事务未同时阻塞在 Chapter 行锁")

    await asyncio.wait_for(wait_until_blocked(), timeout=3)


async def _seed_chapter_command_race(
    session_factory,
    *,
    user_id: int,
    project_id: str,
    status: str = "waiting_for_confirm",
    selected: bool = False,
) -> int:
    async with session_factory() as session:
        session.add(
            User(
                id=user_id,
                username=f"chapter-race-{user_id}",
                hashed_password="secret",
            )
        )
        session.add(
            NovelProject(
                id=project_id,
                user_id=user_id,
                title="chapter command race",
                initial_prompt="test",
            )
        )
        session.add(
            ChapterOutline(
                project_id=project_id,
                chapter_number=1,
                title="第一章",
                summary="test",
            )
        )
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            status=status,
        )
        session.add(chapter)
        await session.flush()
        version = ChapterVersion(
            chapter_id=chapter.id,
            version_label="version1",
            content="初始候选正文",
        )
        session.add(version)
        await session.flush()
        if selected:
            chapter.selected_version_id = version.id
        await session.commit()
        return chapter.id


async def _run_chapter_lock_queue(
    session_factory,
    *,
    chapter_id: int,
    commands,
):
    """按已知顺序把独立事务排入同一个 PostgreSQL Chapter 行锁队列。"""

    started_pids: asyncio.Queue[int] = asyncio.Queue()
    tasks: list[asyncio.Task] = []

    async def run(command):
        async with session_factory() as session:
            pid = int(await session.scalar(select(func.pg_backend_pid())))
            await started_pids.put(pid)
            try:
                return await command(session)
            except Exception as exc:  # 返回领域冲突，便于同时检查两个竞争结果。
                return exc

    try:
        async with session_factory() as blocker:
            blocker_pid = int(await blocker.scalar(select(func.pg_backend_pid())))
            await blocker.execute(select(Chapter).where(Chapter.id == chapter_id).with_for_update())
            blocked_pids: list[int] = []
            for command in commands:
                tasks.append(asyncio.create_task(run(command)))
                blocked_pids.append(await asyncio.wait_for(started_pids.get(), timeout=2))
                await _wait_for_database_blockers(
                    session_factory,
                    blocked_pids=tuple(blocked_pids),
                    blocker_pid=blocker_pid,
                )
            await blocker.commit()

        return await asyncio.wait_for(asyncio.gather(*tasks), timeout=10)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio(loop_scope="session")
async def test_dispatcher_repeated_execution_reuses_child_job_and_run(
    db_session_factory,
) -> None:
    event_id, command = await _seed_active_finalize_event(
        db_session_factory,
        user_id=1501,
        project_id="outbox-idempotency-project",
        dispatch_key="outbox-idempotency-command",
    )

    async with db_session_factory() as session:
        first = await ChapterOutboxDispatcher(session).dispatch(
            command=command,
            user_id=1501,
        )
        await session.commit()

    async with db_session_factory() as session:
        second = await ChapterOutboxDispatcher(session).dispatch(
            command=command,
            user_id=1501,
        )
        await session.commit()

    async with db_session_factory() as session:
        child_jobs = (
            (
                await session.execute(
                    select(BackgroundTask).where(
                        BackgroundTask.project_id == "outbox-idempotency-project",
                        BackgroundTask.task_type == "chapter_finalize",
                    )
                )
            )
            .scalars()
            .all()
        )
        runs = (
            (
                await session.execute(
                    select(ChapterProjectionRun).where(
                        ChapterProjectionRun.project_id == "outbox-idempotency-project"
                    )
                )
            )
            .scalars()
            .all()
        )

    assert first == second
    assert first["status"] == "dispatched"
    assert first["event_id"] == event_id
    assert len(child_jobs) == 1
    assert len(runs) == 1
    assert child_jobs[0].id == first["root_job_id"]
    assert runs[0].id == first["run_ids"][0]
    assert runs[0].job_id == child_jobs[0].id


@pytest.mark.asyncio(loop_scope="session")
async def test_late_tombstone_is_single_execution_and_preserves_new_generation(
    isolated_pg,
    monkeypatch,
) -> None:
    session_factory = isolated_pg.session_factory
    project_id = str(uuid4())
    owner_user_id = 1_780_000_000 + uuid4().int % 1_000_000
    old_source_generation = str(uuid4())
    old_generations = {
        "memory": str(uuid4()),
        "rag": str(uuid4()),
        "foreshadowing": str(uuid4()),
    }
    new_source_generation = str(uuid4())
    new_generations = {
        "memory": str(uuid4()),
        "rag": str(uuid4()),
        "foreshadowing": str(uuid4()),
    }
    monkeypatch.setattr("app.services.job_service.publish_background_task", AsyncMock())

    try:
        async with session_factory() as session:
            session.add(
                User(
                    id=owner_user_id,
                    username=f"tombstone-{owner_user_id}",
                    hashed_password="secret",
                )
            )
            session.add(
                NovelProject(
                    id=project_id,
                    user_id=owner_user_id,
                    title="late tombstone",
                    initial_prompt="test",
                )
            )
            chapter = Chapter(
                project_id=project_id,
                chapter_number=1,
                status="successful",
                current_revision=1,
                source_hash=stable_digest("旧正文"),
                projection_generation=old_source_generation,
                required_projection_snapshot=["memory", "rag", "foreshadowing"],
            )
            session.add(chapter)
            await session.flush()
            version = ChapterVersion(
                chapter_id=chapter.id,
                version_label="version1",
                content="旧正文",
            )
            session.add(version)
            await session.flush()
            chapter.selected_version_id = version.id
            old_revision = ChapterRevision(
                id=str(uuid4()),
                chapter_id=chapter.id,
                project_id=project_id,
                chapter_number=1,
                revision=1,
                selected_version_id=version.id,
                source_hash=chapter.source_hash,
                source_content="旧正文",
                lifecycle="successful",
                required_projections=["memory", "rag", "foreshadowing"],
                skipped_projections=[],
                source_generation=old_source_generation,
            )
            old_runs = {
                name: ChapterProjectionRun(
                    id=str(uuid4()),
                    chapter_revision_id=old_revision.id,
                    chapter_id=chapter.id,
                    project_id=project_id,
                    revision=1,
                    projection_name=name,
                    source_hash=chapter.source_hash,
                    artifact_generation=generation,
                    status="succeeded",
                    required=True,
                    is_active=True,
                    checkpoint={},
                )
                for name, generation in old_generations.items()
            }
            session.add(old_revision)
            await session.flush()
            session.add_all(old_runs.values())
            await session.flush()
            old_snapshot = ChapterSnapshot(
                project_id=project_id,
                chapter_number=1,
                global_summary_snapshot="旧摘要",
                chapter_revision=1,
                artifact_generation=old_generations["memory"],
                projection_run_id=old_runs["memory"].id,
                is_active=True,
            )
            old_chunk = RagChunk(
                id=f"{project_id}:old:chunk",
                project_id=project_id,
                chapter_number=1,
                chunk_index=0,
                content="旧正文",
                embedding=[0.1, 0.2, 0.3],
                source_revision=1,
                artifact_generation=old_generations["rag"],
                projection_run_id=old_runs["rag"].id,
                is_active=True,
            )
            old_summary = RagSummary(
                id=f"{project_id}:old:summary",
                project_id=project_id,
                chapter_number=1,
                title="第一章",
                summary="旧摘要",
                embedding=[0.1, 0.2, 0.3],
                source_revision=1,
                artifact_generation=old_generations["rag"],
                projection_run_id=old_runs["rag"].id,
                is_active=True,
            )
            old_foreshadowing = Foreshadowing(
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_number=1,
                chapter_revision=1,
                artifact_generation=old_generations["foreshadowing"],
                projection_run_id=old_runs["foreshadowing"].id,
                content="旧伏笔",
                type="mystery",
                status="planted",
                is_manual=False,
                is_active=True,
            )
            session.add_all([old_snapshot, old_chunk, old_summary, old_foreshadowing])
            await session.commit()

            dispatcher = await ChapterProjectionService(session).create_tombstone_job(
                chapter=chapter,
                user_id=owner_user_id,
                reason="chapter_regenerated",
                event_type="ChapterRevisionSuperseded",
            )
            await session.commit()
            dispatcher_id = dispatcher.id

        dispatcher_worker = JobWorker(
            session_factory=session_factory,
            registry=build_job_handler_registry(),
            worker_id=f"tombstone-dispatcher-{uuid4()}",
            lease_seconds=30,
            heartbeat_interval_seconds=5,
        )
        assert await dispatcher_worker.run_once() is True

        async with session_factory() as session:
            dispatcher = await session.get(BackgroundTask, dispatcher_id)
            assert dispatcher is not None
            command = ChapterOutboxDispatchJobPayload.model_validate(dispatcher.payload)
            original_dispatch = dict(dispatcher.result)
            tombstone_job_id = original_dispatch["root_job_id"]
            tombstone_run_id = original_dispatch["run_ids"][0]

        repeated_dispatches = []
        for _ in range(2):
            async with session_factory() as session:
                repeated_dispatches.append(
                    await ChapterOutboxDispatcher(session).dispatch(
                        command=command,
                        user_id=owner_user_id,
                    )
                )
                await session.commit()

        assert repeated_dispatches == [original_dispatch, original_dispatch]

        async with session_factory() as session:
            chapter = await session.get(Chapter, chapter.id)
            assert chapter is not None
            chapter.current_revision = 3
            chapter.tombstone_revision = 2
            chapter.source_hash = stable_digest("新正文")
            chapter.projection_generation = new_source_generation
            chapter.status = "successful"
            new_revision = ChapterRevision(
                id=str(uuid4()),
                chapter_id=chapter.id,
                project_id=project_id,
                chapter_number=1,
                revision=3,
                selected_version_id=version.id,
                source_hash=chapter.source_hash,
                source_content="新正文",
                lifecycle="successful",
                required_projections=["memory", "rag", "foreshadowing"],
                skipped_projections=[],
                source_generation=new_source_generation,
            )
            new_runs = {
                name: ChapterProjectionRun(
                    id=str(uuid4()),
                    chapter_revision_id=new_revision.id,
                    chapter_id=chapter.id,
                    project_id=project_id,
                    revision=3,
                    projection_name=name,
                    source_hash=chapter.source_hash,
                    artifact_generation=generation,
                    status="succeeded",
                    required=True,
                    is_active=True,
                    checkpoint={},
                )
                for name, generation in new_generations.items()
            }
            session.add(new_revision)
            await session.flush()
            session.add_all(new_runs.values())
            await session.flush()

            for old_run in old_runs.values():
                persisted_run = await session.get(ChapterProjectionRun, old_run.id)
                assert persisted_run is not None
                persisted_run.status = "succeeded"
                persisted_run.is_active = True
                persisted_run.error_category = None
            for old_artifact in (old_snapshot, old_chunk, old_summary, old_foreshadowing):
                persisted_artifact = await session.get(type(old_artifact), old_artifact.id)
                assert persisted_artifact is not None
                persisted_artifact.is_active = True

            new_snapshot = ChapterSnapshot(
                project_id=project_id,
                chapter_number=1,
                global_summary_snapshot="新摘要",
                chapter_revision=3,
                artifact_generation=new_generations["memory"],
                projection_run_id=new_runs["memory"].id,
                is_active=True,
            )
            new_chunk = RagChunk(
                id=f"{project_id}:new:chunk",
                project_id=project_id,
                chapter_number=1,
                chunk_index=0,
                content="新正文",
                embedding=[0.4, 0.5, 0.6],
                source_revision=3,
                artifact_generation=new_generations["rag"],
                projection_run_id=new_runs["rag"].id,
                is_active=True,
            )
            new_summary = RagSummary(
                id=f"{project_id}:new:summary",
                project_id=project_id,
                chapter_number=1,
                title="第一章",
                summary="新摘要",
                embedding=[0.4, 0.5, 0.6],
                source_revision=3,
                artifact_generation=new_generations["rag"],
                projection_run_id=new_runs["rag"].id,
                is_active=True,
            )
            new_foreshadowing = Foreshadowing(
                project_id=project_id,
                chapter_id=chapter.id,
                chapter_number=1,
                chapter_revision=3,
                artifact_generation=new_generations["foreshadowing"],
                projection_run_id=new_runs["foreshadowing"].id,
                content="新伏笔",
                type="mystery",
                status="planted",
                is_manual=False,
                is_active=True,
            )
            session.add_all([new_snapshot, new_chunk, new_summary, new_foreshadowing])
            await session.commit()
            new_artifact_ids = {
                "snapshot": new_snapshot.id,
                "chunk": new_chunk.id,
                "summary": new_summary.id,
                "foreshadowing": new_foreshadowing.id,
            }

        workers = [
            JobWorker(
                session_factory=session_factory,
                registry=build_job_handler_registry(),
                worker_id=f"tombstone-worker-{index}-{uuid4()}",
                lease_seconds=30,
                heartbeat_interval_seconds=5,
            )
            for index in range(2)
        ]
        worker_results = await asyncio.gather(*(worker.run_once() for worker in workers))
        assert sorted(worker_results) == [False, True]
        assert await workers[0].run_once() is False

        async with session_factory() as session:
            typed_job_count = await session.scalar(
                select(func.count(BackgroundTask.id)).where(
                    BackgroundTask.project_id == project_id,
                    BackgroundTask.task_type == "chapter_projection_tombstone",
                )
            )
            tombstone_run_count = await session.scalar(
                select(func.count(ChapterProjectionRun.id)).where(
                    ChapterProjectionRun.project_id == project_id,
                    ChapterProjectionRun.projection_name == "tombstone",
                )
            )
            tombstone_job = await session.get(BackgroundTask, tombstone_job_id)
            tombstone_run = await session.get(ChapterProjectionRun, tombstone_run_id)
            persisted_old_runs = [
                await session.get(ChapterProjectionRun, run.id) for run in old_runs.values()
            ]
            persisted_new_runs = [
                await session.get(ChapterProjectionRun, run.id) for run in new_runs.values()
            ]
            persisted_old_artifacts = [
                await session.get(type(artifact), artifact.id)
                for artifact in (old_snapshot, old_chunk, old_summary, old_foreshadowing)
            ]
            persisted_new_artifacts = [
                await session.get(ChapterSnapshot, new_artifact_ids["snapshot"]),
                await session.get(RagChunk, new_artifact_ids["chunk"]),
                await session.get(RagSummary, new_artifact_ids["summary"]),
                await session.get(Foreshadowing, new_artifact_ids["foreshadowing"]),
            ]

        assert typed_job_count == 1
        assert tombstone_run_count == 1
        assert tombstone_job is not None and tombstone_job.status == "succeeded"
        assert tombstone_job.result["status"] == "cleaned"
        assert tombstone_job.result["affected"] == {
            "rag_chunks": 1,
            "rag_summaries": 1,
            "snapshots": 1,
            "character_states": 0,
            "foreshadowings": 1,
            "projection_runs": 3,
        }
        assert tombstone_run is not None and tombstone_run.status == "succeeded"
        assert all(run is not None and not run.is_active for run in persisted_old_runs)
        assert all(run is not None and run.is_active for run in persisted_new_runs)
        assert all(
            artifact is not None and not artifact.is_active for artifact in persisted_old_artifacts
        )
        assert all(
            artifact is not None and artifact.is_active for artifact in persisted_new_artifacts
        )
    finally:
        await _cleanup_committed_replay_scope(
            session_factory,
            project_id=project_id,
            user_ids=(owner_user_id,),
        )


@pytest.mark.parametrize(
    ("updates", "expected_category"),
    [
        ({"payload_fingerprint": "0" * 64}, "chapter_outbox_payload_mismatch"),
        ({"event_type": "ChapterTombstoned"}, "chapter_outbox_event_missing"),
        ({"event_version": 1}, "chapter_outbox_event_missing"),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_dispatcher_rejects_mismatched_command_contract(
    db_session_factory,
    updates,
    expected_category,
) -> None:
    _, command = await _seed_active_finalize_event(
        db_session_factory,
        user_id=1502,
        project_id="outbox-command-project",
        dispatch_key="outbox-command-key",
    )
    mismatched = command.model_copy(update=updates)

    async with db_session_factory() as session:
        with pytest.raises(PermanentJobError) as raised:
            await ChapterOutboxDispatcher(session).dispatch(
                command=mismatched,
                user_id=1502,
            )

    assert raised.value.category == expected_category


@pytest.mark.asyncio(loop_scope="session")
async def test_dispatcher_rejects_tombstone_payload_event_type_mismatch(
    db_session_factory,
) -> None:
    event_id = str(uuid4())
    workflow_id = str(uuid4())
    project_id = "outbox-tombstone-project"
    payload = {
        "job_type": "chapter_projection_tombstone",
        "payload_version": 1,
        "project_id": project_id,
        "chapter_id": 999,
        "chapter_number": 1,
        "chapter_revision_id": str(uuid4()),
        "tombstone_revision": 1,
        "source_hash": "a" * 64,
        "source_generation": str(uuid4()),
        "projection_run_id": str(uuid4()),
        "artifact_generation": str(uuid4()),
        "target_revision": 0,
        "target_generation": "legacy",
        "target_artifact_generations": {},
        "event_type": "ChapterRevisionSuperseded",
        "reason": "test",
        "workflow_stream_type": "workflow",
        "workflow_stream_id": workflow_id,
    }
    fingerprint = payload_fingerprint(payload)

    async with db_session_factory() as session:
        session.add(User(id=1503, username="outbox-1503", hashed_password="secret"))
        session.add(
            NovelProject(
                id=project_id,
                user_id=1503,
                title="outbox test",
                initial_prompt="test",
            )
        )
        await session.flush()
        session.add(
            ChapterOutboxEvent(
                id=event_id,
                aggregate_type="chapter",
                aggregate_id="999",
                chapter_id=None,
                project_id=project_id,
                revision=1,
                event_type="ChapterTombstoned",
                event_version=2,
                payload=payload,
                payload_fingerprint=fingerprint,
                idempotency_key="outbox-tombstone-mismatch",
                workflow_stream_type="workflow",
                workflow_stream_id=workflow_id,
            )
        )
        await session.commit()

    command = ChapterOutboxDispatchJobPayload(
        project_id=project_id,
        outbox_event_id=event_id,
        event_type="ChapterTombstoned",
        event_version=2,
        payload_fingerprint=fingerprint,
    )
    async with db_session_factory() as session:
        with pytest.raises(PermanentJobError) as raised:
            await ChapterOutboxDispatcher(session).dispatch(
                command=command,
                user_id=1503,
            )

    assert raised.value.category == "chapter_tombstone_outbox_identity_mismatch"


@pytest.mark.asyncio(loop_scope="session")
async def test_backlog_repair_recreates_only_missing_dispatcher(
    db_session_factory,
) -> None:
    event_id, command = await _seed_active_finalize_event(
        db_session_factory,
        user_id=1504,
        project_id="outbox-backlog-project",
        dispatch_key="outbox-backlog-dispatch",
    )

    async with db_session_factory() as session:
        assert await repair_chapter_outbox_backlog(session) == 1
        await session.commit()

    async with db_session_factory() as session:
        assert await repair_chapter_outbox_backlog(session) == 0
        dispatchers = (
            (
                await session.execute(
                    select(BackgroundTask).where(
                        BackgroundTask.project_id == "outbox-backlog-project",
                        BackgroundTask.task_type == "chapter_outbox_dispatch",
                    )
                )
            )
            .scalars()
            .all()
        )

    assert len(dispatchers) == 1
    assert dispatchers[0].idempotency_key == "outbox-backlog-dispatch"
    assert dispatchers[0].payload == command.model_dump()
    assert dispatchers[0].payload["outbox_event_id"] == event_id


@pytest.mark.asyncio(loop_scope="session")
async def test_canonical_finalize_rollback_removes_revision_outbox_and_dispatcher(
    db_session_factory,
    monkeypatch,
) -> None:
    project_id = "outbox-rollback-project"
    source_content = "回滚正文"
    source_hash = stable_digest(source_content)
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="prompt"))

    async with db_session_factory() as session:
        session.add(User(id=1505, username="outbox-1505", hashed_password="secret"))
        session.add(
            NovelProject(
                id=project_id,
                user_id=1505,
                title="outbox rollback",
                initial_prompt="test",
            )
        )
        session.add(
            ChapterOutline(
                project_id=project_id,
                chapter_number=1,
                title="第一章",
                summary="test",
            )
        )
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            status="waiting_for_confirm",
        )
        session.add(chapter)
        await session.flush()
        version = ChapterVersion(
            chapter_id=chapter.id,
            version_label="version1",
            content=source_content,
        )
        session.add(version)
        await session.commit()

    async with db_session_factory() as session:
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalar_one()
        version = (
            await session.execute(
                select(ChapterVersion).where(ChapterVersion.chapter_id == chapter.id)
            )
        ).scalar_one()
        await ChapterProjectionService(session).create_finalize(
            chapter=chapter,
            selected_version=version,
            source_content=source_content,
            source_hash=source_hash,
            user_id=1505,
            skip_vector_update=True,
            idempotency_key="outbox-rollback-command",
        )
        await session.rollback()

    async with db_session_factory() as session:
        chapter = (
            await session.execute(select(Chapter).where(Chapter.project_id == project_id))
        ).scalar_one()
        revision_count = await session.scalar(
            select(func.count(ChapterRevision.id)).where(ChapterRevision.project_id == project_id)
        )
        outbox_count = await session.scalar(
            select(func.count(ChapterOutboxEvent.id)).where(
                ChapterOutboxEvent.project_id == project_id
            )
        )
        dispatcher_count = await session.scalar(
            select(func.count(BackgroundTask.id)).where(BackgroundTask.project_id == project_id)
        )
        rollout_count = await session.scalar(
            select(func.count(ChapterProjectionRollout.id)).where(
                ChapterProjectionRollout.project_id == project_id
            )
        )

    assert chapter.current_revision == 0
    assert revision_count == 0
    assert outbox_count == 0
    assert dispatcher_count == 0
    assert rollout_count == 0


@pytest.mark.parametrize(
    ("drift", "expected_code"),
    [
        ("revision_tombstoned", "revision_tombstoned"),
        ("outbox_payload", "outbox_payload_mismatch"),
        ("rollout_fence", "rollout_identity_mismatch"),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_replay_rejects_locked_scope_identity_drift(
    db_session_factory,
    drift,
    expected_code,
) -> None:
    project_id = str(uuid4())
    request = await _seed_failed_summary_replay(
        db_session_factory,
        owner_user_id=1510,
        operator_user_id=1510,
        project_id=project_id,
    )

    async with db_session_factory() as session:
        if drift == "revision_tombstoned":
            revision = (
                await session.execute(
                    select(ChapterRevision).where(ChapterRevision.project_id == project_id)
                )
            ).scalar_one()
            revision.tombstoned_at = datetime.now(timezone.utc)
        elif drift == "outbox_payload":
            event = await session.get(ChapterOutboxEvent, request.outbox_event_id)
            assert event is not None
            event.payload = {
                **event.payload,
                "skip_vector_update": not event.payload["skip_vector_update"],
            }
        else:
            rollout = (
                await session.execute(
                    select(ChapterProjectionRollout).where(
                        ChapterProjectionRollout.project_id == project_id
                    )
                )
            ).scalar_one()
            rollout.generation += 1
            rollout.fencing_token += 1
        await session.commit()

    async with db_session_factory() as session:
        with pytest.raises(ChapterProjectionConflictError) as raised:
            await ChapterProjectionOpsService(session).execute(
                request=request,
                operator_user_id=1510,
                mode="replay",
            )

    assert raised.value.code == expected_code


@pytest.mark.asyncio(loop_scope="session")
@pytest.mark.parametrize(
    "operator_update",
    ({"is_admin": False}, {"is_active": False}),
    ids=("non-admin", "inactive-admin"),
)
async def test_projection_operation_rejects_unauthorized_operator_without_audit(
    db_session_factory,
    operator_update,
) -> None:
    project_id = str(uuid4())
    request = await _seed_failed_summary_replay(
        db_session_factory,
        owner_user_id=1509,
        operator_user_id=1509,
        project_id=project_id,
    )
    async with db_session_factory() as session:
        operator = await session.get(User, 1509)
        assert operator is not None
        for field, value in operator_update.items():
            setattr(operator, field, value)
        await session.commit()

    async with db_session_factory() as session:
        with pytest.raises(ChapterProjectionNotFoundError) as raised:
            await ChapterProjectionOpsService(session).execute(
                request=request,
                operator_user_id=1509,
                mode="dry_run",
            )
        audit_count = await session.scalar(
            select(func.count(ChapterProjectionReplayAudit.id)).where(
                ChapterProjectionReplayAudit.project_id == project_id
            )
        )

    assert raised.value.code == "operator_not_authorized"
    assert audit_count == 0


@pytest.mark.asyncio(loop_scope="session")
async def test_different_operators_concurrently_replay_one_projection_once(
    isolated_pg,
    monkeypatch,
) -> None:
    session_factory = isolated_pg.session_factory
    project_id = str(uuid4())
    owner_user_id = 1_700_000_000 + uuid4().int % 10_000_000
    operator_user_id = owner_user_id + 1
    monkeypatch.setattr(
        "app.services.chapter_projection_ops.publish_background_task",
        AsyncMock(),
    )
    tasks: list[asyncio.Task] = []

    try:
        request = await _seed_failed_summary_replay(
            session_factory,
            owner_user_id=owner_user_id,
            operator_user_id=operator_user_id,
            project_id=project_id,
        )
        started_pids: asyncio.Queue[int] = asyncio.Queue()

        async def replay(user_id: int, key: str):
            async with session_factory() as session:
                pid = int(await session.scalar(select(func.pg_backend_pid())))
                await started_pids.put(pid)
                try:
                    return await ChapterProjectionOpsService(session).execute(
                        request=request.model_copy(update={"idempotency_key": key}),
                        operator_user_id=user_id,
                        mode="replay",
                    )
                except ChapterProjectionConflictError as exc:
                    return exc

        async with session_factory() as blocker:
            blocker_pid = int(await blocker.scalar(select(func.pg_backend_pid())))
            await blocker.execute(
                select(Chapter).where(Chapter.id == request.chapter_id).with_for_update()
            )
            tasks = [
                asyncio.create_task(replay(owner_user_id, "summary-replay-owner")),
                asyncio.create_task(replay(operator_user_id, "summary-replay-operator")),
            ]
            blocked_pids = (
                await asyncio.wait_for(started_pids.get(), timeout=2),
                await asyncio.wait_for(started_pids.get(), timeout=2),
            )
            await _wait_for_database_blockers(
                session_factory,
                blocked_pids=blocked_pids,
                blocker_pid=blocker_pid,
            )
            await blocker.commit()

        results = await asyncio.wait_for(asyncio.gather(*tasks), timeout=5)
        queued = [result for result in results if not isinstance(result, Exception)]
        rejected = [result for result in results if isinstance(result, Exception)]

        assert len(queued) == 1
        assert queued[0].status == "queued"
        assert len(rejected) == 1
        assert rejected[0].code == "projection_in_progress"

        async with session_factory() as session:
            runs = list(
                (
                    await session.execute(
                        select(ChapterProjectionRun).where(
                            ChapterProjectionRun.project_id == project_id,
                            ChapterProjectionRun.projection_name == "summary",
                        )
                    )
                )
                .scalars()
                .all()
            )
            jobs = list(
                (
                    await session.execute(
                        select(BackgroundTask).where(
                            BackgroundTask.project_id == project_id,
                            BackgroundTask.task_type == "chapter_finalize",
                        )
                    )
                )
                .scalars()
                .all()
            )
            audits = list(
                (
                    await session.execute(
                        select(ChapterProjectionReplayAudit).where(
                            ChapterProjectionReplayAudit.project_id == project_id
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert sorted(run.status for run in runs) == ["failed", "queued"]
        assert len(jobs) == 1
        assert sorted(audit.status for audit in audits) == ["completed", "rejected"]
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await _cleanup_committed_replay_scope(
            session_factory,
            project_id=project_id,
            user_ids=(owner_user_id, operator_user_id),
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_replay_and_rollout_fence_change_finish_without_deadlock(
    isolated_pg,
    monkeypatch,
) -> None:
    session_factory = isolated_pg.session_factory
    project_id = str(uuid4())
    owner_user_id = 1_720_000_000 + uuid4().int % 10_000_000
    monkeypatch.setattr(
        "app.services.chapter_projection_ops.publish_background_task",
        AsyncMock(),
    )
    tasks: list[asyncio.Task] = []

    try:
        request = await _seed_failed_summary_replay(
            session_factory,
            owner_user_id=owner_user_id,
            operator_user_id=owner_user_id,
            project_id=project_id,
        )
        started_pids: asyncio.Queue[int] = asyncio.Queue()

        async def replay():
            async with session_factory() as session:
                pid = int(await session.scalar(select(func.pg_backend_pid())))
                await started_pids.put(pid)
                try:
                    return await ChapterProjectionOpsService(session).execute(
                        request=request,
                        operator_user_id=owner_user_id,
                        mode="replay",
                    )
                except ChapterProjectionConflictError as exc:
                    return exc

        async def advance_rollout_fence() -> None:
            async with session_factory() as session:
                pid = int(await session.scalar(select(func.pg_backend_pid())))
                await started_pids.put(pid)
                _, rollout = await ChapterProjectionRolloutService(session)._load_chapter_rollout(
                    project_id=project_id,
                    chapter_id=request.chapter_id,
                    for_update=True,
                )
                rollout.generation += 1
                rollout.fencing_token += 1
                await session.commit()

        async with session_factory() as blocker:
            blocker_pid = int(await blocker.scalar(select(func.pg_backend_pid())))
            await blocker.execute(
                select(Chapter).where(Chapter.id == request.chapter_id).with_for_update()
            )
            tasks = [
                asyncio.create_task(replay()),
                asyncio.create_task(advance_rollout_fence()),
            ]
            blocked_pids = (
                await asyncio.wait_for(started_pids.get(), timeout=2),
                await asyncio.wait_for(started_pids.get(), timeout=2),
            )
            await _wait_for_database_blockers(
                session_factory,
                blocked_pids=blocked_pids,
                blocker_pid=blocker_pid,
            )
            await blocker.commit()

        replay_result, _ = await asyncio.wait_for(
            asyncio.gather(*tasks),
            timeout=5,
        )

        async with session_factory() as session:
            rollout = (
                await session.execute(
                    select(ChapterProjectionRollout).where(
                        ChapterProjectionRollout.project_id == project_id
                    )
                )
            ).scalar_one()
            jobs = list(
                (
                    await session.execute(
                        select(BackgroundTask).where(
                            BackgroundTask.project_id == project_id,
                            BackgroundTask.task_type == "chapter_finalize",
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert (rollout.generation, rollout.fencing_token) == (2, 1)
            if isinstance(replay_result, ChapterProjectionConflictError):
                assert replay_result.code == "rollout_identity_mismatch"
                assert jobs == []
            else:
                assert replay_result.status == "queued"
                assert len(jobs) == 1
                payload = ChapterProjectionJobPayload.model_validate(jobs[0].payload)
                assert (
                    await load_current_projection(
                        session,
                        payload=payload,
                        user_id=owner_user_id,
                        job_id=jobs[0].id,
                        expected_projection="summary",
                        for_update=False,
                    )
                    is None
                )
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        await _cleanup_committed_replay_scope(
            session_factory,
            project_id=project_id,
            user_ids=(owner_user_id,),
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_concurrent_finalize_commands_allocate_monotonic_revisions(
    isolated_pg,
    monkeypatch,
) -> None:
    session_factory = isolated_pg.session_factory
    project_id = str(uuid4())
    owner_user_id = 1_740_000_000 + uuid4().int % 1_000_000
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="prompt"))
    monkeypatch.setattr(
        "app.services.chapter_projection_service.publish_background_task",
        AsyncMock(),
    )

    try:
        chapter_id = await _seed_chapter_command_race(
            session_factory,
            user_id=owner_user_id,
            project_id=project_id,
        )

        async def first_finalize(session):
            return await ChapterFinalizeSubmissionService(session).submit(
                project_id=project_id,
                chapter_number=1,
                user_id=owner_user_id,
                selected_version_index=0,
                edited_content="第一份定稿正文",
                skip_vector_update=True,
                idempotency_key=f"{project_id}:finalize:1",
            )

        async def second_finalize(session):
            return await ChapterFinalizeSubmissionService(session).submit(
                project_id=project_id,
                chapter_number=1,
                user_id=owner_user_id,
                selected_version_index=0,
                edited_content="第二份定稿正文",
                skip_vector_update=True,
                idempotency_key=f"{project_id}:finalize:2",
            )

        results = await _run_chapter_lock_queue(
            session_factory,
            chapter_id=chapter_id,
            commands=(first_finalize, second_finalize),
        )
        assert all(not isinstance(result, Exception) for result in results), results

        async with session_factory() as session:
            chapter = await session.get(Chapter, chapter_id)
            revisions = list(
                (
                    await session.execute(
                        select(ChapterRevision)
                        .where(ChapterRevision.project_id == project_id)
                        .order_by(ChapterRevision.revision)
                    )
                )
                .scalars()
                .all()
            )
            events = list(
                (
                    await session.execute(
                        select(ChapterOutboxEvent)
                        .where(ChapterOutboxEvent.project_id == project_id)
                        .order_by(ChapterOutboxEvent.revision)
                    )
                )
                .scalars()
                .all()
            )
            version = (
                await session.execute(
                    select(ChapterVersion).where(ChapterVersion.chapter_id == chapter_id)
                )
            ).scalar_one()

        assert chapter is not None
        assert chapter.current_revision == 2
        assert chapter.source_hash == stable_digest("第二份定稿正文")
        assert [revision.revision for revision in revisions] == [1, 2]
        assert [revision.lifecycle for revision in revisions] == ["superseded", "finalizing"]
        assert [revision.source_content for revision in revisions] == [
            "第一份定稿正文",
            "第二份定稿正文",
        ]
        assert [event.event_type for event in events] == [
            "ChapterFinalizationRequested",
            "ChapterFinalizationRequested",
        ]
        assert version.content == "第二份定稿正文"
    finally:
        await _cleanup_committed_replay_scope(
            session_factory,
            project_id=project_id,
            user_ids=(owner_user_id,),
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_finalize_then_regenerate_supersedes_freshly_locked_revision(
    isolated_pg,
    monkeypatch,
) -> None:
    session_factory = isolated_pg.session_factory
    project_id = str(uuid4())
    owner_user_id = 1_750_000_000 + uuid4().int % 1_000_000
    monkeypatch.setattr(PromptService, "get_prompt", AsyncMock(return_value="prompt"))
    monkeypatch.setattr(
        "app.services.chapter_projection_service.publish_background_task",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "app.services.novel_service.publish_background_task",
        AsyncMock(),
    )

    try:
        chapter_id = await _seed_chapter_command_race(
            session_factory,
            user_id=owner_user_id,
            project_id=project_id,
        )

        async def finalize(session):
            return await ChapterFinalizeSubmissionService(session).submit(
                project_id=project_id,
                chapter_number=1,
                user_id=owner_user_id,
                selected_version_index=0,
                edited_content="刚提交的定稿正文",
                skip_vector_update=True,
                idempotency_key=f"{project_id}:finalize",
            )

        async def regenerate(session):
            stale_chapter = (
                await session.execute(select(Chapter).where(Chapter.id == chapter_id))
            ).scalar_one()
            return await NovelService(session).replace_chapter_versions(
                stale_chapter,
                ["再生成候选正文"],
            )

        results = await _run_chapter_lock_queue(
            session_factory,
            chapter_id=chapter_id,
            commands=(finalize, regenerate),
        )
        assert all(not isinstance(result, Exception) for result in results), results

        async with session_factory() as session:
            chapter = await session.get(Chapter, chapter_id)
            revisions = list(
                (
                    await session.execute(
                        select(ChapterRevision)
                        .where(ChapterRevision.project_id == project_id)
                        .order_by(ChapterRevision.revision)
                    )
                )
                .scalars()
                .all()
            )
            events = list(
                (
                    await session.execute(
                        select(ChapterOutboxEvent)
                        .where(ChapterOutboxEvent.project_id == project_id)
                        .order_by(ChapterOutboxEvent.revision)
                    )
                )
                .scalars()
                .all()
            )
            versions = list(
                (
                    await session.execute(
                        select(ChapterVersion).where(ChapterVersion.chapter_id == chapter_id)
                    )
                )
                .scalars()
                .all()
            )

        assert chapter is not None
        assert chapter.current_revision == 2
        assert chapter.tombstone_revision == 2
        assert chapter.status == "waiting_for_confirm"
        assert chapter.selected_version_id is None
        assert [revision.revision for revision in revisions] == [1, 2]
        assert [revision.lifecycle for revision in revisions] == ["superseded", "tombstone"]
        assert [event.event_type for event in events] == [
            "ChapterFinalizationRequested",
            "ChapterRevisionSuperseded",
        ]
        assert len(versions) == 1
        assert versions[0].content == "再生成候选正文"
    finally:
        await _cleanup_committed_replay_scope(
            session_factory,
            project_id=project_id,
            user_ids=(owner_user_id,),
        )


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_then_finalize_fails_explicitly_after_chapter_disappears(
    isolated_pg,
    monkeypatch,
) -> None:
    session_factory = isolated_pg.session_factory
    project_id = str(uuid4())
    owner_user_id = 1_760_000_000 + uuid4().int % 1_000_000
    monkeypatch.setattr(
        "app.services.novel_service.publish_background_task",
        AsyncMock(),
    )

    try:
        chapter_id = await _seed_chapter_command_race(
            session_factory,
            user_id=owner_user_id,
            project_id=project_id,
            status="successful",
            selected=True,
        )

        async def delete_chapter(session):
            return await NovelService(session).delete_chapters(
                project_id,
                [1],
                delete_artifacts_confirmed=True,
                confirmation_text="删除第1章及全部产物",
            )

        async def finalize(session):
            return await ChapterFinalizeSubmissionService(session).submit(
                project_id=project_id,
                chapter_number=1,
                user_id=owner_user_id,
                selected_version_index=0,
                edited_content="不应提交的正文",
                skip_vector_update=True,
                idempotency_key=f"{project_id}:late-finalize",
            )

        deleted, rejected = await _run_chapter_lock_queue(
            session_factory,
            chapter_id=chapter_id,
            commands=(delete_chapter, finalize),
        )

        assert deleted is None
        assert isinstance(rejected, ValueError)
        assert str(rejected) == "章节不存在"

        async with session_factory() as session:
            chapter = await session.get(Chapter, chapter_id)
            revisions = list(
                (
                    await session.execute(
                        select(ChapterRevision).where(ChapterRevision.project_id == project_id)
                    )
                )
                .scalars()
                .all()
            )
            events = list(
                (
                    await session.execute(
                        select(ChapterOutboxEvent).where(
                            ChapterOutboxEvent.project_id == project_id
                        )
                    )
                )
                .scalars()
                .all()
            )

        assert chapter is None
        assert [(revision.revision, revision.lifecycle) for revision in revisions] == [
            (1, "tombstone")
        ]
        assert [(event.revision, event.event_type) for event in events] == [
            (1, "ChapterTombstoned")
        ]
    finally:
        await _cleanup_committed_replay_scope(
            session_factory,
            project_id=project_id,
            user_ids=(owner_user_id,),
        )
