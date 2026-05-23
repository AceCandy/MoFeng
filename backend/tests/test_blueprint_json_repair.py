from unittest.mock import AsyncMock

import pytest

from app.api.routers.novels import _parse_blueprint_json_with_repair


@pytest.mark.asyncio
async def test_parse_blueprint_json_uses_raw_json_without_repair():
    llm_service = AsyncMock()

    result = await _parse_blueprint_json_with_repair(
        project_id="project-1",
        user_id=7,
        llm_service=llm_service,
        blueprint_raw='```json\n{"title": "测试蓝图"}\n```',
    )

    assert result == {"title": "测试蓝图"}
    llm_service.get_llm_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_parse_blueprint_json_repairs_malformed_json_once():
    llm_service = AsyncMock()
    llm_service.get_llm_response.return_value = """
    {
      "title": "修复后的蓝图",
      "target_audience": "长篇小说读者",
      "genre": "玄幻",
      "style": "沉稳",
      "tone": "热血",
      "one_sentence_summary": "一句话概要",
      "full_synopsis": "完整概要",
      "world_setting": {},
      "characters": [],
      "relationships": [],
      "chapter_outline": []
    }
    """

    result = await _parse_blueprint_json_with_repair(
        project_id="project-1",
        user_id=7,
        llm_service=llm_service,
        blueprint_raw='{"title": "缺逗号"\n "target_audience": "读者"}',
    )

    assert result["title"] == "修复后的蓝图"
    llm_service.get_llm_response.assert_awaited_once()
    repair_call = llm_service.get_llm_response.await_args.kwargs
    assert repair_call["temperature"] == 0.0
    assert repair_call["timeout"] == 180.0
    assert repair_call["stage"] == "world_blueprint"
