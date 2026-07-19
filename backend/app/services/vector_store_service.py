# AIMETA P=向量存储服务_文本向量化|R=向量存储_相似搜索|NR=不含业务逻辑|E=VectorStoreService|X=internal|A=服务类|D=pgvector|S=db|RD=./README.ai
from __future__ import annotations

"""
基于 pgvector 的向量检索服务，封装章节内容的存储与查询。

向量数据存储在主库 PostgreSQL 的 rag_chunks / rag_summaries 表中（通过
pgvector 扩展）。embedding 列为不定维 Vector()，维度由运行时 embedding 模型
决定；写入时校验当前向量维度与表已有数据一致，避免换不同维度模型导致检索错乱。

本文件中的注释均使用中文，便于团队成员快速理解 RAG 相关逻辑。
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..db.session import AsyncSessionLocal
from ..models.rag import RagChunk, RagSummary

logger = logging.getLogger(__name__)


@dataclass
class RetrievedChunk:
    """向量检索得到的剧情片段。"""

    content: str
    chapter_number: int
    chapter_title: Optional[str]
    score: float
    metadata: Dict[str, Any]


@dataclass
class RetrievedSummary:
    """向量检索得到的章节摘要。"""

    chapter_number: int
    title: str
    summary: str
    score: float


class VectorStoreService:
    """pgvector 向量库操作工具，确保不同小说项目的数据隔离。"""

    def __init__(self) -> None:
        if not settings.vector_store_enabled:
            logger.warning("未开启向量检索配置，RAG 检索将被跳过。")

    async def query_chunks(
        self,
        *,
        project_id: str,
        embedding: Sequence[float],
        top_k: Optional[int] = None,
    ) -> List[RetrievedChunk]:
        """根据查询向量检索剧情片段，结果已按相似度排序。"""
        if not settings.vector_store_enabled or not embedding:
            return []

        top_k = top_k or settings.vector_top_k_chunks
        if top_k <= 0:
            return []

        distance = RagChunk.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(RagChunk, distance)
            .where(RagChunk.project_id == project_id)
            .order_by(distance)
            .limit(top_k)
        )
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(stmt)
        except Exception as exc:  # pragma: no cover - 查询异常时仅记录
            logger.warning("向量检索剧情片段失败: %s", exc)
            return []

        items: List[RetrievedChunk] = []
        for row in result.all():
            chunk = row[0]
            items.append(
                RetrievedChunk(
                    content=chunk.content,
                    chapter_number=chunk.chapter_number,
                    chapter_title=chunk.chapter_title,
                    score=row.distance,
                    metadata=chunk.meta or {},
                )
            )
        return items

    async def query_summaries(
        self,
        *,
        project_id: str,
        embedding: Sequence[float],
        top_k: Optional[int] = None,
    ) -> List[RetrievedSummary]:
        """根据查询向量检索章节摘要列表。"""
        if not settings.vector_store_enabled or not embedding:
            return []

        top_k = top_k or settings.vector_top_k_summaries
        if top_k <= 0:
            return []

        distance = RagSummary.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(RagSummary, distance)
            .where(RagSummary.project_id == project_id)
            .order_by(distance)
            .limit(top_k)
        )
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(stmt)
        except Exception as exc:  # pragma: no cover - 查询异常时仅记录
            logger.warning("向量检索章节摘要失败: %s", exc)
            return []

        items: List[RetrievedSummary] = []
        for row in result.all():
            summary = row[0]
            items.append(
                RetrievedSummary(
                    chapter_number=summary.chapter_number,
                    title=summary.title,
                    summary=summary.summary,
                    score=row.distance,
                )
            )
        return items

    async def upsert_chunks(
        self,
        *,
        records: Iterable[Dict[str, Any]],
    ) -> None:
        """批量写入章节片段，供后续检索使用。"""
        if not settings.vector_store_enabled:
            return

        payload = list(records)
        if not payload:
            return

        dim = len(payload[0].get("embedding") or [])
        async with AsyncSessionLocal() as session:
            if not await self._assert_dimension_consistent(session, RagChunk, dim):
                return
            stmt = pg_insert(RagChunk).values(
                [
                    {
                        "id": item["id"],
                        "project_id": item["project_id"],
                        "chapter_number": item["chapter_number"],
                        "chunk_index": item["chunk_index"],
                        "chapter_title": item.get("chapter_title"),
                        "content": item["content"],
                        "embedding": item["embedding"],
                        "meta": item.get("metadata") or {},
                    }
                    for item in payload
                ]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[RagChunk.id],
                set_={
                    "content": stmt.excluded.content,
                    "embedding": stmt.excluded.embedding,
                    "metadata": stmt.excluded["metadata"],
                    "chapter_title": stmt.excluded.chapter_title,
                },
            )
            try:
                await session.execute(stmt)
                await session.commit()
            except Exception as exc:  # pragma: no cover - 写入失败时记录日志
                logger.error("写入 rag_chunks 失败: %s", exc)
                await session.rollback()
            else:
                logger.debug(
                    "已写入章节片段: project=%s chapter=%s count=%d",
                    payload[0].get("project_id"),
                    payload[0].get("chapter_number"),
                    len(payload),
                )

    async def upsert_summaries(
        self,
        *,
        records: Iterable[Dict[str, Any]],
    ) -> None:
        """同步章节摘要向量，供摘要层检索使用。"""
        if not settings.vector_store_enabled:
            return

        payload = list(records)
        if not payload:
            return

        dim = len(payload[0].get("embedding") or [])
        async with AsyncSessionLocal() as session:
            if not await self._assert_dimension_consistent(session, RagSummary, dim):
                return
            stmt = pg_insert(RagSummary).values(
                [
                    {
                        "id": item["id"],
                        "project_id": item["project_id"],
                        "chapter_number": item["chapter_number"],
                        "title": item["title"],
                        "summary": item["summary"],
                        "embedding": item["embedding"],
                    }
                    for item in payload
                ]
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[RagSummary.id],
                set_={
                    "summary": stmt.excluded.summary,
                    "embedding": stmt.excluded.embedding,
                    "title": stmt.excluded.title,
                },
            )
            try:
                await session.execute(stmt)
                await session.commit()
            except Exception as exc:  # pragma: no cover - 写入失败时记录日志
                logger.error("写入 rag_summaries 失败: %s", exc)
                await session.rollback()
            else:
                logger.debug(
                    "已写入章节摘要: project=%s chapter=%s count=%d",
                    payload[0].get("project_id"),
                    payload[0].get("chapter_number"),
                    len(payload),
                )

    async def delete_by_chapters(self, project_id: str, chapter_numbers: Sequence[int]) -> None:
        """根据章节编号批量删除对应的上下文数据。"""
        if not settings.vector_store_enabled or not chapter_numbers:
            return

        async with AsyncSessionLocal() as session:
            try:
                await session.execute(
                    delete(RagChunk).where(
                        RagChunk.project_id == project_id,
                        RagChunk.chapter_number.in_(list(chapter_numbers)),
                    )
                )
                await session.execute(
                    delete(RagSummary).where(
                        RagSummary.project_id == project_id,
                        RagSummary.chapter_number.in_(list(chapter_numbers)),
                    )
                )
                await session.commit()
                logger.info(
                    "已删除章节向量: project=%s chapters=%s",
                    project_id,
                    list(chapter_numbers),
                )
            except Exception as exc:  # pragma: no cover - 删除失败时记录日志
                logger.error("删除章节向量失败: project=%s chapters=%s error=%s", project_id, chapter_numbers, exc)
                await session.rollback()
                raise

    async def _assert_dimension_consistent(
        self,
        session: AsyncSession,
        model: type,
        embedding_dim: int,
    ) -> bool:
        """校验当前向量维度与表已有数据一致，避免换不同维度模型导致检索错乱。"""
        if embedding_dim <= 0:
            logger.error("embedding 维度为 0，跳过写入。")
            return False
        stmt = select(func.vector_dims(model.embedding)).select_from(model).limit(1)
        existing_dim = (await session.execute(stmt)).scalar_one_or_none()
        if existing_dim is None:
            return True  # 表为空，首次写入锁定维度
        if existing_dim != embedding_dim:
            logger.error(
                "向量维度不一致：rag 表已锁定 %d 维，当前 embedding 为 %d 维。"
                "换不同维度 embedding 模型需先清空 rag 表再重新 ingest。",
                existing_dim,
                embedding_dim,
            )
            return False
        return True


__all__ = [
    "VectorStoreService",
    "RetrievedChunk",
    "RetrievedSummary",
]
