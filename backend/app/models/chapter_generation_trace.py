# AIMETA P=章节生成Trace模型_真实AI输入输出记录|R=章节节点审计日志|NR=不含业务逻辑|E=ChapterGenerationTrace|X=db|A=trace|D=sqlalchemy|S=db|RD=./README.ai
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base
from .novel import BIGINT_PK_TYPE, LONG_TEXT_TYPE


class _MetadataAccessor:
    """Descriptor 用于将 `metadata` 访问重定向到 `metadata_`。"""

    def __get__(self, instance, owner):
        if instance is None:
            return Base.metadata
        return instance.metadata_

    def __set__(self, instance, value):
        instance.metadata_ = value


class ChapterGenerationTrace(Base):
    """章节生成过程中每个节点的真实输入输出。"""

    __tablename__ = "chapter_generation_traces"
    __table_args__ = (
        Index("idx_chapter_generation_traces_chapter", "chapter_id", "node_key"),
        Index("idx_chapter_generation_traces_project_chapter", "project_id", "chapter_number"),
    )

    id: Mapped[int] = mapped_column(BIGINT_PK_TYPE, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("chapters.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[str] = mapped_column(String(36), nullable=False)
    chapter_number: Mapped[int] = mapped_column(Integer, nullable=False)
    node_key: Mapped[str] = mapped_column(String(64), nullable=False)
    node_label: Mapped[str] = mapped_column(String(128), nullable=False)
    stage: Mapped[Optional[str]] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="success", nullable=False)
    system_prompt: Mapped[Optional[str]] = mapped_column(LONG_TEXT_TYPE)
    user_prompt: Mapped[Optional[str]] = mapped_column(LONG_TEXT_TYPE)
    raw_response: Mapped[Optional[str]] = mapped_column(LONG_TEXT_TYPE)
    cleaned_output: Mapped[Optional[str]] = mapped_column(LONG_TEXT_TYPE)
    error: Mapped[Optional[str]] = mapped_column(Text)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSON)
    metadata = _MetadataAccessor()
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chapter = relationship(
        "Chapter",
        back_populates="generation_traces",
        foreign_keys=[chapter_id],
    )
