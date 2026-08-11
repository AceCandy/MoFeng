from unittest.mock import AsyncMock, MagicMock

import pytest

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
