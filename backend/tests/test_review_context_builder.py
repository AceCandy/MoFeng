"""
Tests for ReviewContextBuilder service
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.review_context_builder import ReviewContextBuilder
from app.services.vector_store_service import VectorStoreService
from app.models.foreshadowing import Foreshadowing


@pytest.mark.asyncio(loop_scope="session")
async def test_build_review_context_with_pending_foreshadows():
    """测试构建包含待回收伏笔的评审上下文"""
    # Mock session
    session = AsyncMock(spec=AsyncSession)

    # Mock foreshadowing query result
    mock_foreshadow = MagicMock(spec=Foreshadowing)
    mock_foreshadow.id = 1
    mock_foreshadow.chapter_number = 3
    mock_foreshadow.content = "主角发现神秘信件"
    mock_foreshadow.type = "mystery"
    mock_foreshadow.keywords = ["信件", "秘密"]
    mock_foreshadow.status = "planted"
    mock_foreshadow.importance = "major"
    mock_foreshadow.target_reveal_chapter = 10
    mock_foreshadow.related_plots = ["寻找真相"]

    # Mock execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_foreshadow]
    session.execute = AsyncMock(return_value=mock_result)

    # Mock vector store
    vector_store = MagicMock(spec=VectorStoreService)

    # Create builder
    builder = ReviewContextBuilder(session, vector_store)

    # Build context
    base_context = {
        "novel_blueprint": {},
        "chapter_outline": {},
    }

    result = await builder.build_review_context(
        project_id="test_project",
        chapter_number=5,
        chapter_content="第五章内容",
        base_context=base_context,
    )

    # Verify
    assert "pending_foreshadows" in result
    assert len(result["pending_foreshadows"]) == 1
    assert result["pending_foreshadows"][0]["content"] == "主角发现神秘信件"
    assert result["pending_foreshadows"][0]["type"] == "mystery"
    assert result["novel_blueprint"] == {}  # Base context preserved


@pytest.mark.asyncio(loop_scope="session")
async def test_build_review_context_with_plot_threads():
    """测试提取活跃情节线索"""
    session = AsyncMock(spec=AsyncSession)

    # Mock foreshadowing with plot threads
    mock_foreshadow1 = MagicMock(spec=Foreshadowing)
    mock_foreshadow1.chapter_number = 2
    mock_foreshadow1.related_plots = ["寻找真相", "复仇计划"]

    mock_foreshadow2 = MagicMock(spec=Foreshadowing)
    mock_foreshadow2.chapter_number = 4
    mock_foreshadow2.related_plots = ["寻找真相"]

    # First query returns empty (pending foreshadows)
    mock_result1 = MagicMock()
    mock_result1.scalars.return_value.all.return_value = []

    # Second query returns foreshadows with plot threads
    mock_result2 = MagicMock()
    mock_result2.scalars.return_value.all.return_value = [mock_foreshadow1, mock_foreshadow2]

    session.execute = AsyncMock(side_effect=[mock_result1, mock_result2])

    vector_store = MagicMock(spec=VectorStoreService)
    builder = ReviewContextBuilder(session, vector_store)

    result = await builder.build_review_context(
        project_id="test_project",
        chapter_number=5,
        base_context={},
    )

    # Verify plot threads
    assert "active_plot_threads" in result
    threads = result["active_plot_threads"]
    assert len(threads) == 2

    # Find specific threads
    truth_thread = next((t for t in threads if t["thread_name"] == "寻找真相"), None)
    assert truth_thread is not None
    assert truth_thread["last_mentioned_chapter"] == 4
    assert truth_thread["foreshadow_count"] == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_build_review_context_graceful_degradation():
    """测试异常时优雅降级"""
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=Exception("Database error"))

    vector_store = MagicMock(spec=VectorStoreService)
    builder = ReviewContextBuilder(session, vector_store)

    base_context = {"novel_blueprint": {"title": "测试小说"}}

    # Should not raise exception
    result = await builder.build_review_context(
        project_id="test_project",
        chapter_number=5,
        base_context=base_context,
    )

    # Base context should be preserved
    assert result["novel_blueprint"]["title"] == "测试小说"
    # Enhanced fields should be empty or missing
    assert result.get("pending_foreshadows", []) == []


@pytest.mark.asyncio(loop_scope="session")
async def test_get_pending_foreshadows_filters_correctly():
    """测试伏笔查询正确过滤"""
    session = AsyncMock(spec=AsyncSession)
    vector_store = MagicMock(spec=VectorStoreService)
    builder = ReviewContextBuilder(session, vector_store)

    # Mock multiple foreshadows
    mock_foreshadows = [
        MagicMock(
            id=i,
            chapter_number=i,
            content=f"伏笔{i}",
            type="mystery",
            keywords=[],
            status="planted",
            importance="major",
            target_reveal_chapter=10,
        )
        for i in range(1, 4)
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_foreshadows
    session.execute = AsyncMock(return_value=mock_result)

    result = await builder._get_pending_foreshadows("test_project", 5)

    # Should return all 3 foreshadows
    assert len(result) == 3
    assert all(f["chapter_number"] < 5 for f in result)


@pytest.mark.asyncio(loop_scope="session")
async def test_get_related_chapters_merges_chunks_and_summaries():
    """测试相关章节检索会合并 chunk 和 summary 结果"""
    session = AsyncMock(spec=AsyncSession)

    vector_store = MagicMock(spec=VectorStoreService)
    llm_service = AsyncMock()
    llm_service.get_embedding.return_value = [0.1, 0.2, 0.3]

    chunk_match = MagicMock(
        chapter_number=2,
        chapter_title="第二章",
        score=0.7,
        content="这里出现了神秘信件与钥匙的线索" * 20,
    )
    future_chunk = MagicMock(
        chapter_number=5,
        chapter_title="第五章",
        score=0.99,
        content="未来章节不应进入结果",
    )
    summary_match = MagicMock(
        chapter_number=2,
        title="第二章",
        summary="主角首次发现关键线索。",
        score=0.85,
    )
    summary_only = MagicMock(
        chapter_number=1,
        title="第一章",
        summary="故事开端。",
        score=0.4,
    )

    vector_store.query_chunks = AsyncMock(return_value=[chunk_match, future_chunk])
    vector_store.query_summaries = AsyncMock(return_value=[summary_match, summary_only])

    builder = ReviewContextBuilder(session, vector_store, llm_service)

    result = await builder._get_related_chapters(
        project_id="test_project",
        current_chapter=5,
        chapter_content="当前章节再次提到神秘信件和钥匙。",
        top_k=5,
        user_id=42,
    )

    assert [item["chapter_number"] for item in result] == [2, 1]
    assert result[0]["summary"] == "主角首次发现关键线索。"
    assert result[0]["relevance_score"] == 0.85
    assert result[0]["matched_content"].startswith("这里出现了神秘信件与钥匙的线索")
    assert all(item["chapter_number"] < 5 for item in result)
    llm_service.get_embedding.assert_awaited_once_with(
        "当前章节再次提到神秘信件和钥匙。",
        user_id=42,
    )
    vector_store.query_chunks.assert_awaited_once()
    vector_store.query_summaries.assert_awaited_once()
