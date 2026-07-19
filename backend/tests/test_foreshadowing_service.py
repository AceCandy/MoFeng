import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.foreshadowing_service import ForeshadowingService


@pytest.mark.asyncio(loop_scope="session")
async def test_get_unresolved_foreshadowings_uses_active_statuses_and_previous_chapters():
    session = AsyncMock()
    service = ForeshadowingService(session)

    foreshadowing_1 = MagicMock(id=1, status="planted", chapter_number=1)
    foreshadowing_2 = MagicMock(id=2, status="developing", chapter_number=3)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [foreshadowing_1, foreshadowing_2]
    session.execute.return_value = mock_result

    result = await service.get_unresolved_foreshadowings("project-1", 5)

    assert result == [foreshadowing_1, foreshadowing_2]
    session.execute.assert_awaited_once()
    compiled = str(session.execute.await_args.args[0])
    assert "project_id" in compiled
    assert "chapter_number <" in compiled
    assert "status IN" in compiled


@pytest.mark.asyncio(loop_scope="session")
async def test_analyze_foreshadowings_counts_revealed_and_reuses_existing_analysis():
    session = AsyncMock()
    service = ForeshadowingService(session)

    resolved = MagicMock(status="revealed", chapter_number=2, resolved_chapter_number=5, type="mystery", resolutions=[])
    planted = MagicMock(status="planted", chapter_number=4, resolved_chapter_number=None, type="clue", resolutions=[])
    abandoned = MagicMock(status="abandoned", chapter_number=1, resolved_chapter_number=None, type="hint", resolutions=[])

    foreshadowing_result = MagicMock()
    foreshadowing_result.scalars.return_value.all.return_value = [resolved, planted, abandoned]
    existing_analysis = MagicMock()

    session.execute.return_value = foreshadowing_result
    session.scalar.return_value = existing_analysis

    analysis = await service.analyze_foreshadowings("project-1")

    assert analysis is existing_analysis
    assert analysis.total_foreshadowings == 3
    assert analysis.resolved_count == 1
    assert analysis.unresolved_count == 1
    assert analysis.abandoned_count == 1
    assert analysis.avg_resolution_distance == 3
    assert analysis.unresolved_ratio == pytest.approx(1 / 3)
    assert analysis.pattern_analysis == {"mystery": 1, "clue": 1, "hint": 1}
    session.scalar.assert_awaited_once()
    session.flush.assert_awaited_once()
