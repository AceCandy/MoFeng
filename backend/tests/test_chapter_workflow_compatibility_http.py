"""HTTP coverage for legacy writer routes during the workflow cutover window."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from test_chapter_workflow_http import _client, _seed_users_and_project, _start_payload

from app.core.config import settings
from app.models.background_task import BackgroundTask
from app.models.chapter_workflow import ChapterWorkflowCommand, ChapterWorkflowRun
from app.models.novel import Chapter, ChapterVersion

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
