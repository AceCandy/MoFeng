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

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..models.novel import Chapter
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
        session: AsyncSession,
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
            .where(RagChunk.project_id == project_id, RagChunk.is_active.is_(True))
            .order_by(distance)
            .limit(top_k)
        )
        try:
            result = await session.execute(stmt)
            rows = result.all()
        except Exception as exc:
            logger.warning("向量检索剧情片段失败: %s", exc)
            raise

        items: List[RetrievedChunk] = []
        for row in rows:
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
        session: AsyncSession,
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
            .where(RagSummary.project_id == project_id, RagSummary.is_active.is_(True))
            .order_by(distance)
            .limit(top_k)
        )
        try:
            result = await session.execute(stmt)
            rows = result.all()
        except Exception as exc:
            logger.warning("向量检索章节摘要失败: %s", exc)
            raise

        items: List[RetrievedSummary] = []
        for row in rows:
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
        session: AsyncSession,
        *,
        records: Iterable[Dict[str, Any]],
    ) -> None:
        """在调用方事务内批量写入章节片段。"""
        if not settings.vector_store_enabled:
            return

        payload = list(records)
        if not payload:
            return

        if not await self._upsert_chunks_in_session(session, payload):
            raise ValueError("章节正文 embedding 维度与现有向量不一致")

    async def upsert_summaries(
        self,
        session: AsyncSession,
        *,
        records: Iterable[Dict[str, Any]],
    ) -> None:
        """在调用方事务内同步章节摘要向量。"""
        if not settings.vector_store_enabled:
            return

        payload = list(records)
        if not payload:
            return

        if not await self._upsert_summaries_in_session(session, payload):
            raise ValueError("章节摘要 embedding 维度与现有向量不一致")

    async def apply_chapter_projection(
        self,
        session: AsyncSession,
        *,
        project_id: str,
        chapter_number: int,
        revision: int,
        artifact_generation: str,
        projection_run_id: Optional[str],
        expected_source_hash: Optional[str],
        expected_source_generation: Optional[str],
        chunk_records: Iterable[Dict[str, Any]],
        summary_records: Iterable[Dict[str, Any]],
        activate: bool = True,
    ) -> None:
        """写入 generation；active owner 才在同一事务切换可见性。"""

        if not settings.vector_store_enabled:
            return
        if activate and revision > 0:
            if not expected_source_hash or not expected_source_generation:
                raise ValueError("章节向量激活缺少 canonical identity")
            current_chapter_id = await session.scalar(
                select(Chapter.id)
                .where(
                    Chapter.project_id == project_id,
                    Chapter.chapter_number == chapter_number,
                    Chapter.current_revision == revision,
                    Chapter.source_hash == expected_source_hash,
                    Chapter.projection_generation == expected_source_generation,
                    Chapter.tombstone_revision < revision,
                )
                .with_for_update()
            )
            if current_chapter_id is None:
                raise ValueError("章节向量激活条件已失效")
        chunks = list(chunk_records)
        summaries = list(summary_records)
        for item in [*chunks, *summaries]:
            if item.get("project_id") != project_id or item.get("chapter_number") != chapter_number:
                raise ValueError("章节向量记录与目标章节不匹配")
            if (
                int(item.get("source_revision", 0)) != revision
                or item.get("artifact_generation") != artifact_generation
                or item.get("projection_run_id") != projection_run_id
            ):
                raise ValueError("章节向量记录与目标 revision/generation 不匹配")

        if not await self._upsert_chunks_in_session(session, chunks, is_active=False):
            raise ValueError("章节正文 embedding 维度与现有向量不一致")
        if not await self._upsert_summaries_in_session(session, summaries, is_active=False):
            raise ValueError("章节摘要 embedding 维度与现有向量不一致")

        if not activate:
            return

        await session.execute(
            update(RagChunk)
            .where(
                RagChunk.project_id == project_id,
                RagChunk.chapter_number == chapter_number,
                RagChunk.is_active.is_(True),
                RagChunk.artifact_generation != artifact_generation,
            )
            .values(is_active=False)
        )
        await session.execute(
            update(RagSummary)
            .where(
                RagSummary.project_id == project_id,
                RagSummary.chapter_number == chapter_number,
                RagSummary.is_active.is_(True),
                RagSummary.artifact_generation != artifact_generation,
            )
            .values(is_active=False)
        )
        await session.execute(
            update(RagChunk)
            .where(
                RagChunk.project_id == project_id,
                RagChunk.chapter_number == chapter_number,
                RagChunk.artifact_generation == artifact_generation,
            )
            .values(is_active=True)
        )
        await session.execute(
            update(RagSummary)
            .where(
                RagSummary.project_id == project_id,
                RagSummary.chapter_number == chapter_number,
                RagSummary.artifact_generation == artifact_generation,
            )
            .values(is_active=True)
        )

    async def _upsert_chunks_in_session(
        self,
        session: AsyncSession,
        payload: List[Dict[str, Any]],
        *,
        is_active: Optional[bool] = None,
    ) -> bool:
        if not payload:
            return True
        dim = len(payload[0].get("embedding") or [])
        if not await self._assert_dimension_consistent(session, RagChunk, dim):
            return False
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
                    "source_revision": int(item.get("source_revision", 0)),
                    "artifact_generation": item.get("artifact_generation", "legacy"),
                    "projection_run_id": item.get("projection_run_id"),
                    "is_active": bool(item.get("is_active", True)) if is_active is None else is_active,
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
                "source_revision": stmt.excluded.source_revision,
                "artifact_generation": stmt.excluded.artifact_generation,
                "projection_run_id": stmt.excluded.projection_run_id,
                "is_active": stmt.excluded.is_active,
            },
        )
        await session.execute(stmt)
        return True

    async def _upsert_summaries_in_session(
        self,
        session: AsyncSession,
        payload: List[Dict[str, Any]],
        *,
        is_active: Optional[bool] = None,
    ) -> bool:
        if not payload:
            return True
        dim = len(payload[0].get("embedding") or [])
        if not await self._assert_dimension_consistent(session, RagSummary, dim):
            return False
        stmt = pg_insert(RagSummary).values(
            [
                {
                    "id": item["id"],
                    "project_id": item["project_id"],
                    "chapter_number": item["chapter_number"],
                    "title": item["title"],
                    "summary": item["summary"],
                    "embedding": item["embedding"],
                    "source_revision": int(item.get("source_revision", 0)),
                    "artifact_generation": item.get("artifact_generation", "legacy"),
                    "projection_run_id": item.get("projection_run_id"),
                    "is_active": bool(item.get("is_active", True)) if is_active is None else is_active,
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
                "source_revision": stmt.excluded.source_revision,
                "artifact_generation": stmt.excluded.artifact_generation,
                "projection_run_id": stmt.excluded.projection_run_id,
                "is_active": stmt.excluded.is_active,
            },
        )
        await session.execute(stmt)
        return True

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
