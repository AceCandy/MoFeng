from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.routers import optimizer


@pytest.mark.asyncio(loop_scope="session")
async def test_apply_optimization_enqueues_unified_postprocess(monkeypatch):
    session = object()
    current_user = SimpleNamespace(id=42)
    captured = {}

    class DummyChapterEditService:
        def __init__(self, db_session):
            assert db_session is session

        async def apply_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(job=SimpleNamespace(id="postprocess-job"))

    monkeypatch.setattr(optimizer, "ChapterEditService", DummyChapterEditService)

    result = await optimizer.apply_optimization(
        request=optimizer.ApplyOptimizationRequest(
            project_id="project-1",
            chapter_number=3,
            optimized_content="新\n 内 容",
        ),
        session=session,
        current_user=current_user,
    )

    assert result == {
        "status": "accepted",
        "message": "优化内容已应用，章节后处理已进入队列",
        "task_id": "postprocess-job",
    }
    assert captured == {
        "project_id": "project-1",
        "chapter_number": 3,
        "content": "新\n 内 容",
        "user_id": current_user.id,
        "version_label": "optimized",
    }


def test_optimizer_does_not_import_writer_private_foreshadowing_logic() -> None:
    source = optimizer.__file__
    assert source is not None
    text = Path(source).read_text(encoding="utf-8")

    assert "from .writer import" not in text
    assert "_sync_foreshadowings_for_chapter" not in text


def test_optimizer_frontend_uses_durable_acceptance_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    api_source = (root / "frontend/src/api/novel.ts").read_text(encoding="utf-8")
    response_block = api_source.split("export interface ApplyOptimizationResponse", 1)[1].split("}", 1)[0]
    writing_desk = (root / "frontend/src/composables/useWritingDeskOptimize.ts").read_text(encoding="utf-8")
    chapter_content = (
        root / "frontend/src/components/writing-desk/workspace/ChapterContent.vue"
    ).read_text(encoding="utf-8")

    assert "status: 'accepted'" in response_block
    assert "task_id: string" in response_block
    assert "foreshadowing_sync" not in response_block
    assert "applyResult.foreshadowing_sync" not in writing_desk
    assert "applyResult.foreshadowing_sync" not in chapter_content
    assert "globalAlert.showToast(applyResult.message, 'success')" in writing_desk
    assert "globalAlert.showToast(applyResult.message, 'success')" in chapter_content
