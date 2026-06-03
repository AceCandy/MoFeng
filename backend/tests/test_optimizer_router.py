from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routers import optimizer, writer
from app.services.chapter_word_count_settings import count_chapter_words


@pytest.mark.asyncio
async def test_apply_optimization_passes_current_user_id_to_foreshadowing_sync(monkeypatch):
    session = AsyncMock()
    current_user = SimpleNamespace(id=42)
    selected_version = SimpleNamespace(content="旧内容", created_at=datetime.now())
    chapter = SimpleNamespace(
        id="chapter-1",
        chapter_number=3,
        selected_version=selected_version,
        selected_version_id="version-1",
        versions=[selected_version],
        status=None,
        generation_progress=None,
        generation_step=None,
        generation_step_index=None,
        generation_step_total=None,
        word_count=None,
    )
    project = SimpleNamespace(chapters=[chapter])

    class DummyNovelService:
        def __init__(self, db_session):
            self.db_session = db_session

        async def ensure_project_owner(self, project_id, user_id):
            assert project_id == "project-1"
            assert user_id == current_user.id
            return project

    sync_mock = AsyncMock(return_value={"created": 0, "revealed": 0, "developing": 0})

    monkeypatch.setattr(optimizer, "NovelService", DummyNovelService)
    monkeypatch.setattr(writer, "_sync_foreshadowings_for_chapter", sync_mock)

    result = await optimizer.apply_optimization(
        request=optimizer.ApplyOptimizationRequest(
            project_id="project-1",
            chapter_number=3,
            optimized_content="新\n 内 容",
        ),
        session=session,
        current_user=current_user,
    )

    assert result["status"] == "success"
    assert selected_version.content == "新\n 内 容"
    assert chapter.word_count == count_chapter_words("新\n 内 容")
    assert sync_mock.await_count == 1
    assert sync_mock.await_args.kwargs["user_id"] == current_user.id
