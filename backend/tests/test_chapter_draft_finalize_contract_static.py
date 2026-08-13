from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.novel import (
    Chapter,
    ChapterGenerationStatus,
    ConfirmFinalizeChapterRequest,
    ConfirmFinalizeChapterResponse,
    ConfirmFinalizeStats,
    ForeshadowingSyncStats,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_SOURCE = ROOT / "app/schemas/novel.py"


def _source() -> str:
    return SCHEMAS_SOURCE.read_text(encoding="utf-8")


def test_chapter_generation_status_includes_finalizing() -> None:
    source = _source()

    assert 'FINALIZING = "finalizing"' in source


def test_confirm_finalize_contracts_exist() -> None:
    source = _source()

    assert "class ConfirmFinalizeChapterRequest(BaseModel):" in source
    assert "selected_version_index: int" in source
    assert "edited_content: Optional[str] = None" in source
    assert "skip_vector_update: bool = False" in source
    assert "class ForeshadowingSyncStats(BaseModel):" in source
    assert "created: int = 0" in source
    assert "developing: int = 0" in source
    assert "revealed: int = 0" in source
    assert "class ConfirmFinalizeChapterResponse(BaseModel):" in source
    assert "chapter: Chapter" in source
    assert "finalize: ConfirmFinalizeStats" in source


def test_generation_flow_no_longer_exposes_async_finalize_flag() -> None:
    schema_source = SCHEMAS_SOURCE.read_text(encoding="utf-8")

    assert "async_finalize" not in schema_source


def test_chapter_generation_status_finalizing_value() -> None:
    assert ChapterGenerationStatus.FINALIZING.value == "finalizing"


def test_confirm_finalize_request_defaults_and_validation() -> None:
    request = ConfirmFinalizeChapterRequest(selected_version_index=0)

    assert request.selected_version_index == 0
    assert request.edited_content is None
    assert request.skip_vector_update is False

    with pytest.raises(ValidationError):
        ConfirmFinalizeChapterRequest(selected_version_index=-1)


def test_confirm_finalize_stats_default_factory_creates_distinct_nested_models() -> None:
    first = ConfirmFinalizeStats()
    second = ConfirmFinalizeStats()

    assert first.foreshadowing_sync is not second.foreshadowing_sync
    assert first.foreshadowing_sync == ForeshadowingSyncStats(created=0, developing=0, revealed=0)
    assert second.foreshadowing_sync == ForeshadowingSyncStats(created=0, developing=0, revealed=0)


def test_confirm_finalize_response_holds_models() -> None:
    chapter = Chapter(chapter_number=1, title="第一章", summary="摘要")
    finalize = ConfirmFinalizeStats()

    response = ConfirmFinalizeChapterResponse(chapter=chapter, finalize=finalize)

    assert response.chapter == chapter
    assert response.finalize == finalize
    assert isinstance(response.chapter, Chapter)
    assert isinstance(response.finalize, ConfirmFinalizeStats)
    assert isinstance(response.finalize.foreshadowing_sync, ForeshadowingSyncStats)
