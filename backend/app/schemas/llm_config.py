# AIMETA P=LLM配置模式_模型配置请求响应|R=LLM配置结构|NR=不含业务逻辑|E=LLMConfigSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
from decimal import Decimal
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl, StringConstraints, model_validator


ProviderType = Literal["openai_compatible", "anthropic", "ollama", "custom"]
TTSProtocol = Literal["mimo_chat_audio", "openai_speech"]
PricePerMillion = Annotated[
    Decimal,
    Field(ge=0, max_digits=24, decimal_places=12),
]
CurrencyCode = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_upper=True,
        min_length=3,
        max_length=3,
        pattern=r"^[A-Za-z]{3}$",
    ),
]


class LLMConfigBase(BaseModel):
    llm_provider_url: Optional[HttpUrl] = Field(default=None, description="自定义 LLM 服务地址")
    llm_provider_api_key: Optional[str] = Field(default=None, description="自定义 LLM API Key")
    llm_provider_model: Optional[str] = Field(default=None, description="自定义模型名称")
    embedding_provider_url: Optional[HttpUrl] = Field(
        default=None,
        description="自定义向量模型服务地址，留空则复用主模型地址",
    )
    embedding_provider_api_key: Optional[str] = Field(
        default=None,
        description="自定义向量模型 API Key，留空则复用主模型 API Key",
    )
    embedding_provider_model: Optional[str] = Field(default=None, description="自定义向量模型名称")
    embedding_provider_format: Optional[Literal["openai", "ollama"]] = Field(
        default=None,
        description="向量请求协议格式：openai 或 ollama；留空时使用系统默认配置。",
    )


class LLMConfigCreate(LLMConfigBase):
    pass


class LLMConfigRead(LLMConfigBase):
    user_id: int

    class Config:
        from_attributes = True


class ModelListRequest(BaseModel):
    llm_provider_url: Optional[str] = Field(default=None, description="LLM 服务地址")
    llm_provider_api_key: Optional[str] = Field(default=None, description="LLM API Key，可为空")


class ProviderBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: ProviderType = "openai_compatible"
    base_url: str = Field(min_length=1)
    api_key: Optional[str] = None
    capabilities: Dict[str, bool] = Field(
        default_factory=lambda: {"chat": True, "embedding": False, "tts": False}
    )
    is_enabled: bool = True


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    provider_type: Optional[ProviderType] = None
    base_url: Optional[str] = Field(default=None, min_length=1)
    api_key: Optional[str] = None
    capabilities: Optional[Dict[str, bool]] = None
    is_enabled: Optional[bool] = None


class ProviderRead(BaseModel):
    id: int
    user_id: int
    name: str
    provider_type: str
    base_url: str
    api_key_preview: Optional[str] = None
    capabilities: Dict[str, bool]
    is_enabled: bool

    model_config = {"from_attributes": True}


class UserAIModelBase(BaseModel):
    provider_id: int
    display_name: str = Field(min_length=1, max_length=120)
    model_name: str = Field(min_length=1, max_length=160)
    capabilities: Dict[str, bool] = Field(
        default_factory=lambda: {"chat": True, "embedding": False, "tts": False}
    )
    context_window: Optional[int] = None
    is_default_chat: bool = False
    is_default_embedding: bool = False
    is_default_tts: bool = False
    tts_protocol: Optional[TTSProtocol] = None
    tts_voice: Optional[str] = Field(default=None, max_length=120)
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0)
    input_price_per_million: Optional[PricePerMillion] = None
    output_price_per_million: Optional[PricePerMillion] = None
    cached_input_price_per_million: Optional[PricePerMillion] = None
    cache_write_input_price_per_million: Optional[PricePerMillion] = None
    pricing_currency: Optional[CurrencyCode] = None
    is_enabled: bool = True
    sort_order: int = 0

    @model_validator(mode="after")
    def validate_tts_configuration(self):
        if self.is_default_tts and not self.capabilities.get("tts"):
            raise ValueError("默认语音朗读模型必须启用 TTS 能力")
        if self.capabilities.get("tts"):
            if not self.tts_protocol:
                raise ValueError("TTS 模型必须选择语音协议")
        return self


class UserAIModelCreate(UserAIModelBase):
    pass


class UserAIModelUpdate(BaseModel):
    provider_id: Optional[int] = None
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    model_name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    capabilities: Optional[Dict[str, bool]] = None
    context_window: Optional[int] = None
    is_default_chat: Optional[bool] = None
    is_default_embedding: Optional[bool] = None
    is_default_tts: Optional[bool] = None
    tts_protocol: Optional[TTSProtocol] = None
    tts_voice: Optional[str] = Field(default=None, max_length=120)
    tts_speed: Optional[float] = Field(default=None, ge=0.5, le=2.0)
    input_price_per_million: Optional[PricePerMillion] = None
    output_price_per_million: Optional[PricePerMillion] = None
    cached_input_price_per_million: Optional[PricePerMillion] = None
    cache_write_input_price_per_million: Optional[PricePerMillion] = None
    pricing_currency: Optional[CurrencyCode] = None
    is_enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class UserAIModelRead(BaseModel):
    id: int
    user_id: int
    provider_id: int
    display_name: str
    model_name: str
    capabilities: Dict[str, bool]
    context_window: Optional[int] = None
    is_default_chat: bool
    is_default_embedding: bool
    is_default_tts: bool
    tts_protocol: Optional[TTSProtocol] = None
    tts_voice: Optional[str] = None
    tts_speed: float
    input_price_per_million: Optional[Decimal] = None
    output_price_per_million: Optional[Decimal] = None
    cached_input_price_per_million: Optional[Decimal] = None
    cache_write_input_price_per_million: Optional[Decimal] = None
    pricing_currency: Optional[CurrencyCode] = None
    is_enabled: bool
    sort_order: int

    model_config = {"from_attributes": True}


class StageRouteRead(BaseModel):
    stage: str
    model_id: int


class StageRouteUpsert(BaseModel):
    stage: str
    model_id: int


class StageRoutesPayload(BaseModel):
    routes: List[StageRouteUpsert]


class LLMConfigBundle(BaseModel):
    legacy: Optional[LLMConfigRead] = None
    providers: List[ProviderRead] = Field(default_factory=list)
    models: List[UserAIModelRead] = Field(default_factory=list)
    stage_routes: List[StageRouteRead] = Field(default_factory=list)
