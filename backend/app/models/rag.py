# AIMETA P=RAG向量模型_章节片段与摘要向量|R=rag_chunks_rag_summaries|NR=不含业务逻辑|E=RagChunk_RagSummary|X=internal|A=ORM模型|D=sqlalchemy_pgvector|S=db|RD=./README.ai
"""RAG 向量检索模型（pgvector）。

存储章节正文片段与摘要的向量，供 RAG 检索使用。embedding 列采用不定维
Vector()，维度由运行时 embedding 模型决定；写入时由 VectorStoreService 校验
当前向量维度与表已有数据一致，避免换不同维度模型导致检索错乱。
"""

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class RagChunk(Base):
    """章节正文片段向量记录。"""

    __tablename__ = "rag_chunks"
    __table_args__ = (
        Index("idx_rag_chunks_project", "project_id", "chapter_number"),
        Index("ix_rag_chunks_active", "project_id", "chapter_number", "is_active"),
        Index("ix_rag_chunks_generation", "project_id", "chapter_number", "artifact_generation"),
    )

    id: Mapped[str] = mapped_column(String(192), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chapter_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(), nullable=False)
    source_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    artifact_generation: Mapped[str] = mapped_column(
        String(36), nullable=False, default="legacy", server_default="legacy"
    )
    projection_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_projection_runs.id", ondelete="SET NULL"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    # metadata 是 SQLAlchemy DeclarativeBase 保留属性，属性名用 meta 映射列名 metadata
    meta: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class RagSummary(Base):
    """章节摘要向量记录。"""

    __tablename__ = "rag_summaries"
    __table_args__ = (
        Index("idx_rag_summaries_project", "project_id", "chapter_number"),
        Index("ix_rag_summaries_active", "project_id", "chapter_number", "is_active"),
        Index("ix_rag_summaries_generation", "project_id", "chapter_number", "artifact_generation"),
    )

    id: Mapped[str] = mapped_column(String(192), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("novel_projects.id", ondelete="CASCADE"), nullable=False
    )
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(), nullable=False)
    source_revision: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )
    artifact_generation: Mapped[str] = mapped_column(
        String(36), nullable=False, default="legacy", server_default="legacy"
    )
    projection_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("chapter_projection_runs.id", ondelete="SET NULL"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


__all__ = ["RagChunk", "RagSummary"]
