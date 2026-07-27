from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.chapter_context import WriterPersonaContext
from app.services.constitution_service import ConstitutionService
from app.services.six_dimension_review_service import SixDimensionReviewService
from app.services.writer_persona_service import WriterPersonaService


@pytest.mark.asyncio
async def test_six_dimension_review_uses_injected_canonical_context() -> None:
    llm_service = AsyncMock()
    llm_service.generate.return_value = '{"overall_score": 95}'
    prompt_service = AsyncMock()
    prompt_service.get_prompt.return_value = (
        "{{constitution}}|{{writer_persona}}|{{chapter_number}}|{{chapter_title}}|"
        "{{chapter_content}}|{{chapter_plan}}|{{previous_summary}}|"
        "{{character_profiles}}|{{world_setting}}"
    )
    constitution_service = MagicMock()
    constitution_service.get_constitution = AsyncMock()
    persona_service = MagicMock()
    persona_service.get_active_persona = AsyncMock()
    service = SixDimensionReviewService(
        AsyncMock(),
        llm_service,
        prompt_service,
        constitution_service,
        persona_service,
    )

    result = await service.review_chapter(
        chapter_number=3,
        chapter_title="入山",
        chapter_content="章节正文",
        constitution_context="第三人称有限视角",
        writer_persona_context="语言简洁",
    )

    assert result == {"overall_score": 95}
    constitution_service.get_constitution.assert_not_awaited()
    persona_service.get_active_persona.assert_not_awaited()
    prompt = llm_service.generate.await_args.kwargs["prompt"]
    assert "第三人称有限视角" in prompt
    assert "语言简洁" in prompt


@pytest.mark.asyncio
async def test_constitution_compliance_uses_injected_canonical_context() -> None:
    llm_service = AsyncMock()
    llm_service.generate.return_value = '{"overall_compliance": true}'
    prompt_service = AsyncMock()
    prompt_service.get_prompt.return_value = (
        "{{constitution}}|{{chapter_number}}|{{chapter_title}}|{{chapter_content}}"
    )
    service = ConstitutionService(AsyncMock(), llm_service, prompt_service)
    service.get_constitution = AsyncMock()

    result = await service.check_compliance(
        chapter_number=3,
        chapter_title="入山",
        chapter_content="章节正文",
        constitution_context="不得切换全知视角",
    )

    assert result == {"overall_compliance": True}
    service.get_constitution.assert_not_awaited()


@pytest.mark.asyncio
async def test_style_compliance_uses_injected_canonical_persona() -> None:
    service = WriterPersonaService(AsyncMock(), AsyncMock(), AsyncMock())
    service.get_active_persona = AsyncMock()
    persona = WriterPersonaContext(
        prompt_context="语言简洁",
        name="冷笔",
        catchphrases=["说到底"],
        avoid_patterns=["总的来说"],
    )

    result = await service.check_style_compliance(
        project_id=None,
        chapter_content="总的来说，这里没有使用指定口头禅。",
        persona_context=persona,
    )

    assert result["compliance"] is False
    assert len(result["issues"]) == 2
    service.get_active_persona.assert_not_awaited()
