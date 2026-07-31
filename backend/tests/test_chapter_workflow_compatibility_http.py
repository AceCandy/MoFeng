# AIMETA P=章节工作流兼容HTTP与发布演练|R=legacy_facade_gate切换_单owner与canonical结果|NR=不执行完整graph或外部provider|E=test_*|X=internal|A=integration_test|D=pytest,httpx,postgresql|S=test|RD=../app/services/README.ai
"""HTTP coverage for legacy writer routes during the workflow cutover window."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from test_chapter_workflow_http import _client, _seed_users_and_project, _start_payload

from app.core.config import settings
from app.models import ChapterOutboxEvent, ChapterRevision
from app.models.background_task import BackgroundTask
from app.models.chapter_workflow import ChapterWorkflowCommand, ChapterWorkflowRun
from app.models.novel import Chapter, ChapterVersion
from app.services.chapter_workflow_finalize import (
    ChapterWorkflowFinalizeInput,
    ChapterWorkflowFinalizeService,
)
from app.services.job_registry import SideEffectClass
from app.services.job_service import JobService
from app.services.job_worker import JobExecutionContext

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _count(session, model: type) -> int:
    return int((await session.execute(select(func.count()).select_from(model))).scalar_one())


async def _start_workflow(isolated_pg) -> dict:
    async with _client(isolated_pg, user_id=6101) as client:
        response = await client.post(
            "/api/writer/chapter-workflows",
            json=_start_payload(),
        )
    assert response.status_code == 202
    return response.json()["snapshot"]


async def _seed(isolated_pg) -> None:
    async with isolated_pg.session_factory() as session:
        await _seed_users_and_project(session)


async def _set_run_state(
    isolated_pg,
    *,
    run_id: str,
    run_status: str,
    job_status: str,
    node_key: str,
    checkpoint_id: str,
    chapter_status: str | None = None,
) -> None:
    async with isolated_pg.session_factory() as session:
        run = await session.get(ChapterWorkflowRun, run_id)
        assert run is not None
        job = await session.get(BackgroundTask, run.root_job_id)
        assert job is not None
        run.status = run_status
        run.node_key = node_key
        run.checkpoint_id = checkpoint_id
        run.row_revision = 7
        job.status = job_status
        if chapter_status is not None:
            chapter = await session.get(Chapter, run.chapter_id)
            assert chapter is not None
            chapter.status = chapter_status
        await session.commit()


async def _add_candidate_versions(isolated_pg, *, run_id: str) -> list[int]:
    async with isolated_pg.session_factory() as session:
        chapter = (
            (
                await session.execute(
                    select(Chapter).where(
                        Chapter.project_id == "workflow-http-project",
                        Chapter.chapter_number == 1,
                    )
                )
            )
            .scalars()
            .one()
        )
        versions = [
            ChapterVersion(
                chapter_id=chapter.id,
                version_label=f"v{ordinal}",
                content=f"candidate {ordinal}",
                metadata={"_chapter_workflow": {"run_id": run_id, "ordinal": ordinal}},
            )
            for ordinal in (1, 2)
        ]
        session.add_all(versions)
        await session.commit()
        return [version.id for version in versions]


async def _add_legacy_version(isolated_pg) -> int:
    async with isolated_pg.session_factory() as session:
        chapter = Chapter(project_id="workflow-http-project", chapter_number=1)
        session.add(chapter)
        await session.flush()
        version = ChapterVersion(
            chapter_id=chapter.id,
            version_label="legacy-v1",
            content="legacy candidate",
            metadata={"provider": "legacy"},
        )
        session.add(version)
        await session.commit()
        return version.id


async def _finalize_candidate_once(
    isolated_pg,
    *,
    run_id: str,
    root_job_id: str,
    selected_version_id: int,
) -> int:
    async with isolated_pg.session_factory() as session:
        lease = await JobService(session).claim_next(
            worker_id=f"rollout-drill-{run_id}",
            lease_seconds=60,
        )
    assert lease is not None
    assert lease.job_id == root_job_id
    execution = JobExecutionContext(
        lease=lease,
        side_effect_class=SideEffectClass.TRANSACTIONAL,
        session_factory=isolated_pg.session_factory,
    )
    request = ChapterWorkflowFinalizeInput(
        run_id=run_id,
        candidate_version_ids=[selected_version_id],
        selected_version_id=selected_version_id,
    )
    service = ChapterWorkflowFinalizeService(execution)
    first = await service.execute(request)
    replay = await service.execute(request)
    assert replay == first
    return first.result.target_chapter_revision


async def test_legacy_generation_drains_when_start_gate_is_closed(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", False)
    await _seed(isolated_pg)

    async with _client(isolated_pg, user_id=6101) as client:
        response = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            headers={"Idempotency-Key": "legacy-retry-1"},
            json={
                "chapter_number": 1,
                "writing_notes": "legacy drain",
                "from_node_key": "draft_generation",
            },
        )

    assert response.status_code == 202
    assert response.json()["task_type"] == "chapter_generation"
    async with isolated_pg.session_factory() as session:
        job = (await session.execute(select(BackgroundTask))).scalars().one()
        assert job.payload["from_node_key"] == "draft_generation"
        assert await _count(session, ChapterWorkflowRun) == 0


async def test_legacy_generate_uses_one_workflow_root_when_gate_is_open(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", True)
    await _seed(isolated_pg)
    payload = {"chapter_number": 1, "writing_notes": "compat start"}

    async with _client(isolated_pg, user_id=6101) as client:
        first = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            json=payload,
        )
        monkeypatch.setattr(settings, "chapter_workflow_start_enabled", False)
        second = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            json=payload,
        )

    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["task_type"] == "chapter_workflow"
    assert first.json()["stream_type"] == "workflow"
    assert first.json()["payload"] is None
    async with isolated_pg.session_factory() as session:
        assert await _count(session, BackgroundTask) == 1
        assert await _count(session, ChapterWorkflowRun) == 1
        legacy_jobs = (
            await session.execute(
                select(BackgroundTask).where(BackgroundTask.task_type == "chapter_generation")
            )
        ).scalars()
        assert list(legacy_jobs) == []


async def test_rollout_gate_open_shares_one_owner_across_legacy_and_new_http(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", True)
    await _seed(isolated_pg)

    async with _client(isolated_pg, user_id=6101) as client:
        legacy_start = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            headers={"Idempotency-Key": "rollout-start-1"},
            json={"chapter_number": 1, "writing_notes": "rollout drill"},
        )
        current = await client.get(
            "/api/writer/chapter-workflows/current",
            params={"project_id": "workflow-http-project", "chapter_number": 1},
        )

    assert legacy_start.status_code == 202
    assert current.status_code == 200
    snapshot = current.json()["snapshot"]
    assert snapshot["root_job_id"] == legacy_start.json()["id"]
    assert current.json()["events_url"].endswith(snapshot["run_id"])

    version_ids = await _add_candidate_versions(isolated_pg, run_id=snapshot["run_id"])
    await _set_run_state(
        isolated_pg,
        run_id=snapshot["run_id"],
        run_status="waiting_for_selection",
        job_status="waiting",
        node_key="waiting_for_selection",
        checkpoint_id="rollout-drill-checkpoint",
        chapter_status="waiting_for_confirm",
    )

    command_id = "77777777-7777-4777-8777-777777777777"
    async with _client(isolated_pg, user_id=6101) as client:
        refreshed = await client.get(
            "/api/writer/chapter-workflows/current",
            params={"project_id": "workflow-http-project", "chapter_number": 1},
        )
        refreshed_snapshot = refreshed.json()["snapshot"]
        command_response = await client.post(
            f"/api/writer/chapter-workflows/{snapshot['run_id']}/commands",
            json={
                "command_id": command_id,
                "type": "select",
                "payload_version": 1,
                "payload": {"selected_version_id": version_ids[0]},
                "expected_run_revision": refreshed_snapshot["row_revision"],
                "expected_chapter_revision": refreshed_snapshot["current_chapter_revision"],
                "expected_checkpoint_id": refreshed_snapshot["checkpoint_id"],
            },
        )

    assert command_response.status_code == 202
    assert command_response.json()["command_id"] == command_id
    assert command_response.json()["snapshot"]["run_id"] == snapshot["run_id"]
    target_revision = await _finalize_candidate_once(
        isolated_pg,
        run_id=snapshot["run_id"],
        root_job_id=snapshot["root_job_id"],
        selected_version_id=version_ids[0],
    )

    async with isolated_pg.session_factory() as session:
        run = (await session.execute(select(ChapterWorkflowRun))).scalars().one()
        command = (await session.execute(select(ChapterWorkflowCommand))).scalars().one()
        chapter = (await session.execute(select(Chapter))).scalars().one()
        revision = (await session.execute(select(ChapterRevision))).scalars().one()
        outbox = (await session.execute(select(ChapterOutboxEvent))).scalars().one()
        task_types = list((await session.execute(select(BackgroundTask.task_type))).scalars())

        assert await _count(session, ChapterWorkflowRun) == 1
        assert await _count(session, ChapterWorkflowCommand) == 1
        assert await _count(session, ChapterRevision) == 1
        assert await _count(session, ChapterOutboxEvent) == 1

    assert run.id == command.run_id == snapshot["run_id"]
    assert run.root_job_id == snapshot["root_job_id"]
    assert command.id == command_id
    assert command.payload == {"selected_version_id": version_ids[0]}
    assert chapter.selected_version_id == revision.selected_version_id == version_ids[0]
    assert chapter.current_revision == revision.revision == target_revision == 1
    assert outbox.workflow_stream_id == snapshot["run_id"]
    assert task_types.count("chapter_workflow") == 1
    assert task_types.count("chapter_outbox_dispatch") == 1
    assert "chapter_generation" not in task_types


async def test_legacy_select_drains_when_no_workflow_exists(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", False)
    await _seed(isolated_pg)
    selected_version_id = await _add_legacy_version(isolated_pg)

    async with _client(isolated_pg, user_id=6101) as client:
        response = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/select",
            headers={"Idempotency-Key": "legacy-select-1"},
            json={"chapter_number": 1, "version_index": 0},
        )

    assert response.status_code == 202
    assert response.json()["task_type"] == "chapter_outbox_dispatch"
    async with isolated_pg.session_factory() as session:
        job = (await session.execute(select(BackgroundTask))).scalars().one()
        chapter = (await session.execute(select(Chapter))).scalars().one()
        assert job.task_type == "chapter_outbox_dispatch"
        assert chapter.selected_version_id == selected_version_id
        assert await _count(session, ChapterWorkflowRun) == 0
        assert await _count(session, ChapterWorkflowCommand) == 0


async def test_active_workflow_select_is_idempotent_and_never_enqueues_finalize(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", True)
    await _seed(isolated_pg)
    snapshot = await _start_workflow(isolated_pg)
    version_ids = await _add_candidate_versions(isolated_pg, run_id=snapshot["run_id"])
    await _set_run_state(
        isolated_pg,
        run_id=snapshot["run_id"],
        run_status="waiting_for_selection",
        job_status="waiting",
        node_key="waiting_for_selection",
        checkpoint_id="compat-select-checkpoint",
    )
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", False)

    async with _client(isolated_pg, user_id=6101) as client:
        first = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/select",
            headers={"Idempotency-Key": "select-candidate-1"},
            json={"chapter_number": 1, "version_index": 0},
        )
        second = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/select",
            headers={"Idempotency-Key": "select-candidate-1"},
            json={"chapter_number": 1, "version_index": 0},
        )
        conflicting = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/select",
            headers={"Idempotency-Key": "select-candidate-1"},
            json={"chapter_number": 1, "version_index": 1},
        )

    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"] == snapshot["root_job_id"]
    assert first.json()["payload"] is None
    assert conflicting.status_code == 409
    assert conflicting.json() == {"detail": "workflow_command_identity_conflict"}
    async with isolated_pg.session_factory() as session:
        command = (await session.execute(select(ChapterWorkflowCommand))).scalars().one()
        assert command.type == "select"
        assert command.payload == {"selected_version_id": version_ids[0]}
        assert await _count(session, BackgroundTask) == 1


async def test_rollback_gate_closed_drains_active_owner_without_duplicate_outcome(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", True)
    await _seed(isolated_pg)
    snapshot = await _start_workflow(isolated_pg)
    version_ids = await _add_candidate_versions(isolated_pg, run_id=snapshot["run_id"])
    await _set_run_state(
        isolated_pg,
        run_id=snapshot["run_id"],
        run_status="waiting_for_selection",
        job_status="waiting",
        node_key="waiting_for_selection",
        checkpoint_id="rollback-drill-checkpoint",
        chapter_status="waiting_for_confirm",
    )
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", False)

    async with _client(isolated_pg, user_id=6101) as client:
        legacy_generate = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            headers={"Idempotency-Key": "previous-frontend-generate-1"},
            json={"chapter_number": 1, "writing_notes": "rollback drain"},
        )
        first_select = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/select",
            headers={"Idempotency-Key": "previous-frontend-select-1"},
            json={"chapter_number": 1, "version_index": 0},
        )
        replayed_select = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/select",
            headers={"Idempotency-Key": "previous-frontend-select-1"},
            json={"chapter_number": 1, "version_index": 0},
        )

    assert legacy_generate.status_code == first_select.status_code == 202
    assert replayed_select.status_code == 202
    assert (
        legacy_generate.json()["id"]
        == first_select.json()["id"]
        == replayed_select.json()["id"]
        == snapshot["root_job_id"]
    )
    target_revision = await _finalize_candidate_once(
        isolated_pg,
        run_id=snapshot["run_id"],
        root_job_id=snapshot["root_job_id"],
        selected_version_id=version_ids[0],
    )

    async with isolated_pg.session_factory() as session:
        run = (await session.execute(select(ChapterWorkflowRun))).scalars().one()
        command = (await session.execute(select(ChapterWorkflowCommand))).scalars().one()
        chapter = (await session.execute(select(Chapter))).scalars().one()
        revision = (await session.execute(select(ChapterRevision))).scalars().one()
        outbox = (await session.execute(select(ChapterOutboxEvent))).scalars().one()
        task_types = list((await session.execute(select(BackgroundTask.task_type))).scalars())

        assert await _count(session, ChapterWorkflowRun) == 1
        assert await _count(session, ChapterWorkflowCommand) == 1
        assert await _count(session, ChapterRevision) == 1
        assert await _count(session, ChapterOutboxEvent) == 1

    assert run.id == command.run_id == snapshot["run_id"]
    assert run.root_job_id == snapshot["root_job_id"]
    assert command.type == "select"
    assert command.payload == {"selected_version_id": version_ids[0]}
    assert chapter.selected_version_id == revision.selected_version_id == version_ids[0]
    assert chapter.current_revision == revision.revision == target_revision == 1
    assert outbox.workflow_stream_id == snapshot["run_id"]
    assert task_types.count("chapter_workflow") == 1
    assert task_types.count("chapter_outbox_dispatch") == 1
    assert "chapter_generation" not in task_types


async def test_active_workflow_rejects_unrepresentable_finalize_options(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", True)
    await _seed(isolated_pg)
    snapshot = await _start_workflow(isolated_pg)
    await _add_candidate_versions(isolated_pg, run_id=snapshot["run_id"])
    await _set_run_state(
        isolated_pg,
        run_id=snapshot["run_id"],
        run_status="waiting_for_selection",
        job_status="waiting",
        node_key="waiting_for_selection",
        checkpoint_id="compat-finalize-checkpoint",
    )

    async with _client(isolated_pg, user_id=6101) as client:
        response = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/1/confirm-finalize",
            json={
                "selected_version_index": 0,
                "edited_content": "cannot be represented",
                "skip_vector_update": False,
            },
        )

    assert response.status_code == 409
    assert response.json() == {"detail": "workflow_finalize_options_unsupported"}
    async with isolated_pg.session_factory() as session:
        assert await _count(session, ChapterWorkflowCommand) == 0
        assert await _count(session, BackgroundTask) == 1


async def test_active_workflow_from_node_maps_only_to_matching_retry(
    isolated_pg,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", True)
    await _seed(isolated_pg)
    snapshot = await _start_workflow(isolated_pg)
    await _set_run_state(
        isolated_pg,
        run_id=snapshot["run_id"],
        run_status="retry_wait",
        job_status="retry_wait",
        node_key="generate_candidates",
        checkpoint_id="compat-retry-checkpoint",
    )
    monkeypatch.setattr(settings, "chapter_workflow_start_enabled", False)

    async with _client(isolated_pg, user_id=6101) as client:
        mismatch = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            json={"chapter_number": 1, "from_node_key": "quality_review"},
        )
        first = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            headers={"Idempotency-Key": "retry-generation-1"},
            json={"chapter_number": 1, "from_node_key": "draft_generation"},
        )
        second = await client.post(
            "/api/writer/novels/workflow-http-project/chapters/generate",
            headers={"Idempotency-Key": "retry-generation-1"},
            json={"chapter_number": 1, "from_node_key": "draft_generation"},
        )

    assert mismatch.status_code == 409
    assert mismatch.json() == {"detail": "workflow_retry_node_mismatch"}
    assert first.status_code == second.status_code == 202
    assert first.json()["id"] == second.json()["id"] == snapshot["root_job_id"]
    async with isolated_pg.session_factory() as session:
        command = (await session.execute(select(ChapterWorkflowCommand))).scalars().one()
        assert command.type == "retry"
        assert command.status == "applied"
        assert await _count(session, BackgroundTask) == 1
