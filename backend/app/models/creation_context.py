# AIMETA P=创作上下文模型_跨设备语义位置|R=页面_章节_分区_灵感草稿|NR=不含项目内容或瞬时UI|E=UserCreationContext|X=db|A=状态记录|D=sqlalchemy|S=db|RD=./README.ai
from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class UserCreationContext(Base):
    """保存用户在单个项目中的可恢复语义工作位置。"""

    __tablename__ = "user_creation_contexts"
    __table_args__ = (
        CheckConstraint(
            "surface IS NULL OR surface IN ('inspiration', 'archive', 'writing')",
            name="ck_user_creation_context_surface",
        ),
        CheckConstraint(
            "chapter_number IS NULL OR chapter_number >= 1",
            name="ck_user_creation_context_chapter_number",
        ),
        CheckConstraint(
            "desk_section IS NULL OR desk_section IN ('content', 'versions', 'evaluation')",
            name="ck_user_creation_context_desk_section",
        ),
        CheckConstraint(
            "inspiration_turn IS NULL OR inspiration_turn >= 0",
            name="ck_user_creation_context_inspiration_turn",
        ),
        Index("ix_user_creation_contexts_recent", "user_id", "updated_at"),
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("novel_projects.id", ondelete="CASCADE"),
        primary_key=True,
    )
    surface: Mapped[Optional[str]] = mapped_column(String(16))
    chapter_number: Mapped[Optional[int]] = mapped_column(Integer)
    desk_section: Mapped[Optional[str]] = mapped_column(String(16))
    inspiration_draft: Mapped[Optional[str]] = mapped_column(Text)
    inspiration_turn: Mapped[Optional[int]] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
