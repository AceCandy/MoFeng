# AIMETA P=小说项目轻量详情测试|R=轻量参数透传_大字段裁剪|NR=不测试数据库查询性能|E=test:NovelService:lightweight|X=internal|A=NovelService|D=pytest|S=test|RD=../app/services/README.ai
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.novel_service import NovelService


@pytest.mark.asyncio
async def test_project_schema_can_skip_chapter_details() -> None:
    service = NovelService(SimpleNamespace())
    project = SimpleNamespace(user_id=7)
    schema = SimpleNamespace()
    service.repo.get_by_id = AsyncMock(return_value=project)
    service._serialize_project = AsyncMock(return_value=schema)

    result = await service.get_project_schema(
        "project-1",
        user_id=7,
        include_chapter_content=False,
    )

    assert result is schema
    service.repo.get_by_id.assert_awaited_once_with(
        "project-1",
        include_chapter_details=False,
    )
    service._serialize_project.assert_awaited_once_with(
        project,
        include_chapter_content=False,
    )


def test_lightweight_chapter_omits_generation_trace_payload() -> None:
    trace = SimpleNamespace(
        id=1,
        node_key="draft_generation",
        node_label="生成正文",
        stage="draft",
        status="succeeded",
        system_prompt="large system prompt",
        user_prompt="large user prompt",
        raw_response="large raw response",
        cleaned_output="large cleaned output",
        error=None,
        metadata={},
        started_at=None,
        ended_at=None,
        created_at=None,
    )
    chapter = SimpleNamespace(
        status="successful",
        word_count=1200,
        real_summary=None,
        generation_progress=100,
        generation_step="done",
        generation_step_index=1,
        generation_step_total=1,
        generation_traces=[trace],
    )

    schema = NovelService(SimpleNamespace())._build_chapter_schema_from_entities(
        chapter_number=1,
        outline=None,
        chapter=chapter,
        include_content=False,
    )

    assert schema.content is None
    assert schema.versions is None
    assert schema.generation_traces == []
