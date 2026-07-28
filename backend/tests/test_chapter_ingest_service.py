from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.services.chapter_ingest_service import ChapterIngestionService
from app.services.llm_service import LLMService


def test_chapter_splitter_preserves_sentence_punctuation():
    service = ChapterIngestionService()
    content = "第一句。第二句。"

    assert "".join(service._split_into_chunks(content)) == content


@pytest.mark.asyncio(loop_scope="session")
async def test_prepare_chapter_uses_detached_embedding_by_default(monkeypatch):
    previous_enabled = settings.vector_store_enabled
    settings.vector_store_enabled = True
    detached_embedding = AsyncMock(return_value=[0.1, 0.2])
    monkeypatch.setattr(LLMService, "get_embedding_detached", detached_embedding)

    try:
        service = ChapterIngestionService()
        service._text_splitter = None
        prepared = await service.prepare_chapter(
            project_id="project-1",
            chapter_number=1,
            title="第一章",
            content="章节正文",
            content_hash="content-hash",
            summary=None,
            user_id=7,
        )
    finally:
        settings.vector_store_enabled = previous_enabled

    assert prepared.complete is True
    assert len(prepared.chunk_records) == 1
    detached_embedding.assert_awaited_once_with(
        "章节正文",
        user_id=7,
        stage="rag_embedding",
    )
