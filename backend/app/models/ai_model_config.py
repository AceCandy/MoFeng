# AIMETA P=个人AI模型配置模型_供应商模型和阶段路由|R=模型配置表|NR=不含调用逻辑|E=UserModelProvider_UserAIModel_UserAIStageRoute|X=internal|A=ORM模型|D=sqlalchemy|S=db|RD=./README.ai
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from ..db.base import Base


class UserModelProvider(Base):
    """用户级模型供应商档案，保存 API 地址和密钥。"""

    __tablename__ = "user_model_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    provider_type: Mapped[str] = mapped_column(
        String(32), default="openai_compatible", nullable=False
    )
    base_url: Mapped[str] = mapped_column(Text, nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    api_key_preview: Mapped[str | None] = mapped_column(String(32))
    capabilities_json: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: {"chat": True, "embedding": False, "tts": False},
        nullable=False,
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    models: Mapped[list["UserAIModel"]] = relationship(
        "UserAIModel",
        back_populates="provider",
        cascade="all, delete-orphan",
    )


class UserAIModel(Base):
    """用户登记的可用模型，归属一个供应商档案。"""

    __tablename__ = "user_ai_models"
    __table_args__ = (
        CheckConstraint(
            "input_price_per_million IS NULL OR input_price_per_million >= 0",
            name="ck_user_ai_models_input_price",
        ),
        CheckConstraint(
            "output_price_per_million IS NULL OR output_price_per_million >= 0",
            name="ck_user_ai_models_output_price",
        ),
        CheckConstraint(
            "cached_input_price_per_million IS NULL OR cached_input_price_per_million >= 0",
            name="ck_user_ai_models_cached_input_price",
        ),
        CheckConstraint(
            "cache_write_input_price_per_million IS NULL OR cache_write_input_price_per_million >= 0",
            name="ck_user_ai_models_cache_write_price",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int] = mapped_column(
        ForeignKey("user_model_providers.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    capabilities_json: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    context_window: Mapped[int | None] = mapped_column(Integer)
    is_default_chat: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default_embedding: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_default_tts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    tts_protocol: Mapped[str | None] = mapped_column(String(32))
    tts_voice: Mapped[str | None] = mapped_column(String(120))
    tts_speed: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    input_price_per_million: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    output_price_per_million: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    cached_input_price_per_million: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    cache_write_input_price_per_million: Mapped[Decimal | None] = mapped_column(Numeric(24, 12))
    pricing_currency: Mapped[str | None] = mapped_column(String(3))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    provider: Mapped[UserModelProvider] = relationship("UserModelProvider", back_populates="models")


class UserAIStageRoute(Base):
    """用户级 AI 阶段到模型的默认路由。"""

    __tablename__ = "user_ai_stage_routes"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    stage: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[int] = mapped_column(
        ForeignKey("user_ai_models.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    model: Mapped[UserAIModel] = relationship("UserAIModel")
