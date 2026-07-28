# AIMETA P=章节导入服务_批量章节导入|R=批量导入_格式解析|NR=不含内容生成|E=ChapterIngestService|X=internal|A=服务类|D=sqlalchemy|S=db,fs|RD=./README.ai
from __future__ import annotations

"""
章节向量入库服务：在章节确认后负责切分文本、生成嵌入并写入向量库。

全部注释使用中文，方便团队成员阅读理解。
"""

import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..services.llm_service import LLMService
from ..services.vector_store_service import VectorStoreService

logger = logging.getLogger(__name__)

try:  # noqa: SIM105 - 提示缺少可选依赖
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:  # pragma: no cover - 未安装时会走后备方案
    RecursiveCharacterTextSplitter = None  # type: ignore[assignment]


EmbeddingProvider = Callable[[str], Awaitable[List[float]]]


@dataclass(frozen=True)
class PreparedChapterIngestion:
    """已完成外部 embedding、等待数据库事务应用的章节投影。"""

    enabled: bool
    complete: bool
    chunk_records: List[Dict[str, Any]]
    summary_records: List[Dict[str, Any]]

    def to_payload(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "complete": self.complete,
            "chunk_records": self.chunk_records,
            "summary_records": self.summary_records,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PreparedChapterIngestion":
        return cls(
            enabled=bool(payload.get("enabled")),
            complete=bool(payload.get("complete")),
            chunk_records=list(payload.get("chunk_records") or []),
            summary_records=list(payload.get("summary_records") or []),
        )


class ChapterIngestionService:
    """封装章节内容与摘要的向量化与入库流程。"""

    def __init__(
        self,
        *,
        vector_store: Optional[VectorStoreService] = None,
    ) -> None:
        self._vector_store = vector_store or VectorStoreService()
        self._text_splitter = self._init_text_splitter()

    async def ingest_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        title: str,
        content: str,
        summary: Optional[str],
        user_id: int,
    ) -> None:
        """将章节正文与摘要写入向量库，供后续 RAG 检索使用。"""
        prepared = await self.prepare_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            title=title,
            content=content,
            content_hash="",
            summary=summary,
            user_id=user_id,
        )
        if not prepared.enabled:
            return
        if not prepared.complete:
            logger.warning(
                "章节向量仅生成部分 embedding: project=%s chapter=%s",
                project_id,
                chapter_number,
            )
        async with AsyncSessionLocal() as session:
            try:
                await self.apply_prepared(
                    session,
                    project_id=project_id,
                    chapter_number=chapter_number,
                    prepared=prepared,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def prepare_chapter(
        self,
        *,
        project_id: str,
        chapter_number: int,
        title: str,
        content: str,
        content_hash: str,
        summary: Optional[str],
        user_id: int,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ) -> PreparedChapterIngestion:
        """只执行文本切分与 embedding，不写数据库。"""

        if not settings.vector_store_enabled:
            logger.warning("向量库未启用，跳过章节向量写入: project=%s chapter=%s", project_id, chapter_number)
            return PreparedChapterIngestion(False, True, [], [])

        async def embed(text: str) -> List[float]:
            if embedding_provider is not None:
                return await embedding_provider(text)
            return await LLMService.get_embedding_detached(
                text,
                user_id=user_id,
                stage="rag_embedding",
            )

        chunks = self._split_into_chunks(content)
        chunk_records: List[Dict[str, Any]] = []
        missing_embeddings = 0
        for index, chunk_text in enumerate(chunks):
            embedding = await embed(chunk_text)
            if not embedding:
                missing_embeddings += 1
                continue
            record_id = f"{project_id}:{chapter_number}:{index}"
            chunk_records.append(
                {
                    "id": record_id,
                    "project_id": project_id,
                    "chapter_number": chapter_number,
                    "chunk_index": index,
                    "chapter_title": title,
                    "content": chunk_text,
                    "embedding": embedding,
                    "metadata": {
                        "chunk_id": record_id,
                        "length": len(chunk_text),
                        "content_hash": content_hash,
                    },
                }
            )

        summary_records: List[Dict[str, Any]] = []
        cleaned_summary = (summary or "").strip()
        if cleaned_summary:
            summary_embedding = await embed(cleaned_summary)
            if summary_embedding:
                summary_records.append(
                    {
                        "id": f"{project_id}:{chapter_number}:summary",
                        "project_id": project_id,
                        "chapter_number": chapter_number,
                        "title": title,
                        "summary": cleaned_summary,
                        "embedding": summary_embedding,
                    }
                )
            else:
                missing_embeddings += 1

        return PreparedChapterIngestion(
            enabled=True,
            complete=missing_embeddings == 0,
            chunk_records=chunk_records,
            summary_records=summary_records,
        )

    async def apply_prepared(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        chapter_number: int,
        prepared: PreparedChapterIngestion,
    ) -> None:
        """把已计算投影写入调用方事务，不自行提交。"""

        if not prepared.enabled:
            return
        await self._vector_store.apply_chapter_projection(
            session,
            project_id=project_id,
            chapter_number=chapter_number,
            chunk_records=prepared.chunk_records,
            summary_records=prepared.summary_records,
        )

    async def delete_chapters(self, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """从向量库中删除指定章节的所有片段与摘要。"""
        if not settings.vector_store_enabled or not chapter_numbers:
            return
        logger.info(
            "准备删除章节向量: project=%s chapters=%s",
            project_id,
            list(chapter_numbers),
        )
        await self._vector_store.delete_by_chapters(project_id, list(chapter_numbers))

    def _split_into_chunks(self, text: str) -> List[str]:
        """按照配置的 chunk 大小与重叠度切分章节正文。"""
        normalized = text.strip()
        if not normalized:
            return []

        if self._text_splitter:
            parts = [segment.strip() for segment in self._text_splitter.split_text(normalized)]
            filtered = [part for part in parts if part]
            if filtered:
                logger.debug(
                    "使用 LangChain 文本切分器完成分段: count=%d chunk_size=%d overlap=%d",
                    len(filtered),
                    settings.vector_chunk_size,
                    settings.vector_chunk_overlap,
                )
                return filtered

        return self._legacy_split(normalized)

    @staticmethod
    def _find_split_offset(segment: str) -> Optional[int]:
        """在片段内部寻找更自然的分割点，优先换行，其次常见标点。"""
        candidates: Dict[str, int] = {}
        newline_pos = segment.rfind("\n\n")
        if newline_pos == -1:
            newline_pos = segment.rfind("\n")
        if newline_pos > 0:
            candidates["newline"] = newline_pos

        punctuation_marks = ["。", "！", "？", "!", "?", ".", ";", "；"]
        for mark in punctuation_marks:
            idx = segment.rfind(mark)
            if idx > 0:
                candidates.setdefault("punctuation", idx + len(mark))

        if not candidates:
            return None

        # 选择最接近末尾但又不过短的分割点
        best_offset = max(candidates.values())
        if best_offset < len(segment) * 0.4:
            return None
        return best_offset

    def _init_text_splitter(self) -> Optional["RecursiveCharacterTextSplitter"]:
        """初始化 LangChain 文本切分器，可根据配置动态调整。"""
        if RecursiveCharacterTextSplitter is None:
            logger.warning("未安装 langchain-text-splitters，章节切分将回退至内置策略。")
            return None

        chunk_size = settings.vector_chunk_size
        overlap = min(settings.vector_chunk_overlap, chunk_size // 2)
        separators = [
            "\n\n",
            "\n",
            "。", "！", "？",
            "!", "?", "；", ";",
            "，", ",",
            " ",
        ]
        splitter = RecursiveCharacterTextSplitter(
            separators=separators,
            chunk_size=chunk_size,
            chunk_overlap=overlap,
            keep_separator="end",
            strip_whitespace=True,
        )
        logger.info(
            "已初始化 LangChain 文本切分器: chunk_size=%d overlap=%d",
            chunk_size,
            overlap,
        )
        return splitter

    def _legacy_split(self, text: str) -> List[str]:
        """内置切分策略，作为 LangChain 缺失时的后备方案。"""
        chunk_size = settings.vector_chunk_size
        overlap = min(settings.vector_chunk_overlap, chunk_size // 2)

        chunks: List[str] = []
        start = 0
        total_length = len(text)

        while start < total_length:
            end = min(total_length, start + chunk_size)
            segment = text[start:end]

            split_offset = self._find_split_offset(segment)
            if split_offset is not None and start + split_offset < total_length:
                end = start + split_offset
                segment = text[start:end]

            chunk_text = segment.strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end >= total_length:
                break
            start = max(0, end - overlap)

        logger.debug(
            "使用内置策略完成章节切分: count=%d chunk_size=%d overlap=%d",
            len(chunks),
            chunk_size,
            overlap,
        )
        return chunks


__all__ = ["ChapterIngestionService", "PreparedChapterIngestion"]
