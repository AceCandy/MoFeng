# AIMETA P=LLM配置服务_模型配置业务逻辑|R=配置管理_模型选择|NR=不含模型调用|E=LLMConfigService|X=internal|A=服务类|D=sqlalchemy|S=db|RD=./README.ai
import logging
from typing import List, Optional
from urllib.parse import urlparse

from fastapi import HTTPException, status
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.crypto import decrypt, encrypt
from ..core.ssrf import assert_safe_base_url
from ..models import LLMConfig, UserAIModel, UserAIStageRoute, UserModelProvider
from ..repositories.ai_model_config_repository import (
    UserAIModelRepository,
    UserAIStageRouteRepository,
    UserModelProviderRepository,
)
from ..repositories.llm_config_repository import LLMConfigRepository
from ..repositories.system_config_repository import SystemConfigRepository
from ..schemas.llm_config import (
    LLMConfigBundle,
    LLMConfigCreate,
    LLMConfigRead,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    StageRouteRead,
    StageRoutesPayload,
    UserAIModelCreate,
    UserAIModelRead,
    UserAIModelUpdate,
)

logger = logging.getLogger(__name__)

CHAT_STAGE_KEYS = {
    "import_analysis",
    "concept_conversation",
    "world_blueprint",
    "chapter_outline",
    "chapter_blueprint",
    "chapter_mission",
    "chapter_preview",
    "chapter_writing",
    "chapter_rewrite",
    "chapter_compression",
    "chapter_enrichment",
    "version_review",
    "chapter_optimization",
    "deep_review",
    "emotion_analysis",
    "consistency_check",
    "summary_memory",
    "rag_query",
    "foreshadowing",
}
EMBEDDING_STAGE_KEYS = {"rag_embedding"}
ALL_STAGE_KEYS = CHAT_STAGE_KEYS | EMBEDDING_STAGE_KEYS
DEFAULT_PROVIDER_CAPABILITIES = {"chat": True, "embedding": False, "tts": False}


class LLMConfigService:
    """用户自定义 LLM 配置服务。"""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LLMConfigRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self.provider_repo = UserModelProviderRepository(session)
        self.model_repo = UserAIModelRepository(session)
        self.stage_route_repo = UserAIStageRouteRepository(session)

    @staticmethod
    def _mask_api_key(api_key: Optional[str]) -> Optional[str]:
        cleaned = (api_key or "").strip()
        if not cleaned:
            return None
        return f"******{cleaned[-4:]}"

    @staticmethod
    def _check_base_url(base_url: Optional[str]) -> None:
        try:
            assert_safe_base_url(base_url, allow_private=settings.allow_private_llm_endpoints)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    @staticmethod
    def _pick_default_model(models: list, *, capability: str):
        for model in models:
            capabilities = model.capabilities_json or {}
            if model.is_enabled and capabilities.get(capability):
                return model
        return None

    @staticmethod
    def stage_capability(stage: str) -> str:
        if stage in EMBEDDING_STAGE_KEYS:
            return "embedding"
        if stage in CHAT_STAGE_KEYS:
            return "chat"
        raise ValueError(f"unknown AI stage: {stage}")

    @staticmethod
    def _model_to_read(model) -> UserAIModelRead:
        return UserAIModelRead(
            id=model.id,
            user_id=model.user_id,
            provider_id=model.provider_id,
            display_name=model.display_name,
            model_name=model.model_name,
            capabilities=model.capabilities_json or {},
            context_window=model.context_window,
            is_default_chat=model.is_default_chat,
            is_default_embedding=model.is_default_embedding,
            is_default_tts=getattr(model, "is_default_tts", False),
            tts_protocol=getattr(model, "tts_protocol", None),
            tts_voice=getattr(model, "tts_voice", None),
            tts_speed=getattr(model, "tts_speed", 1.0),
            input_price_per_million=model.input_price_per_million,
            output_price_per_million=model.output_price_per_million,
            cached_input_price_per_million=model.cached_input_price_per_million,
            cache_write_input_price_per_million=model.cache_write_input_price_per_million,
            pricing_currency=model.pricing_currency,
            is_enabled=model.is_enabled,
            sort_order=model.sort_order,
        )

    @staticmethod
    def _normalize_capabilities(
        raw: Optional[dict], fallback: Optional[dict] = None
    ) -> dict[str, bool]:
        source = raw or fallback or DEFAULT_PROVIDER_CAPABILITIES
        return {
            "chat": bool(source.get("chat")),
            "embedding": bool(source.get("embedding")),
            "tts": bool(source.get("tts")),
        }

    @staticmethod
    def _validate_tts_model(model) -> None:
        supports_tts = bool((model.capabilities_json or {}).get("tts"))
        if getattr(model, "is_default_tts", False) and not supports_tts:
            raise ValueError("默认语音朗读模型必须启用 TTS 能力")
        if not supports_tts:
            return
        if not getattr(model, "tts_protocol", None):
            raise ValueError("TTS 模型必须选择语音协议")
        # 音色与倍速改为朗读时在控件选择（全局偏好），不再要求模型预置

    @classmethod
    def _provider_to_read(
        cls, provider, fallback_capabilities: Optional[dict] = None
    ) -> ProviderRead:
        return ProviderRead(
            id=provider.id,
            user_id=provider.user_id,
            name=provider.name,
            provider_type=provider.provider_type,
            base_url=provider.base_url,
            api_key_preview=provider.api_key_preview,
            capabilities=cls._normalize_capabilities(
                getattr(provider, "capabilities_json", None),
                fallback_capabilities,
            ),
            is_enabled=provider.is_enabled,
        )

    @staticmethod
    def _route_to_read(route) -> StageRouteRead:
        return StageRouteRead(stage=route.stage, model_id=route.model_id)

    def _identify_provider(self, base_url: Optional[str]) -> str:
        """根据 base_url 识别 LLM 提供商"""
        if not base_url:
            return "openai"

        url_lower = base_url.lower()
        parsed = urlparse(url_lower)
        host = parsed.netloc or parsed.path

        # 识别常见提供商
        if "openai.com" in host or "api.openai.com" in host:
            return "openai"
        elif "anthropic.com" in host or "api.anthropic.com" in host:
            return "anthropic"
        elif "generativelanguage.googleapis.com" in host or "google" in host:
            return "google"
        elif "azure" in host:
            return "azure"
        elif "cohere" in host:
            return "cohere"
        elif "ollama" in host or ":11434" in host or host.endswith("11434"):
            return "ollama"
        elif "together" in host or "together.ai" in host:
            return "together"
        elif "deepseek" in host:
            return "deepseek"
        elif "moonshot" in host:
            return "moonshot"
        elif "zhipu" in host or "bigmodel.cn" in host:
            return "zhipu"
        elif "baidu" in host or "qianfan" in host:
            return "baidu"
        else:
            # 默认使用 OpenAI-like API
            return "openai-like"

    def _resolve_provider_for_model_list(
        self,
        provider_type: Optional[str],
        base_url: Optional[str],
    ) -> str:
        normalized = (provider_type or "").strip().lower()
        if normalized == "openai_compatible":
            return "openai-like"
        if normalized in {"anthropic", "ollama"}:
            return normalized
        return self._identify_provider(base_url)

    @staticmethod
    def _anthropic_endpoint_url(base_url: Optional[str], endpoint: str) -> str:
        trimmed = (base_url or "https://api.anthropic.com/v1").strip().rstrip("/")
        endpoint_path = endpoint.strip("/")
        lowered = trimmed.lower()
        if lowered.endswith(f"/{endpoint_path}"):
            return trimmed
        if lowered.endswith("/v1"):
            return f"{trimmed}/{endpoint_path}"
        return f"{trimmed}/v1/{endpoint_path}"

    @staticmethod
    def _normalize_ollama_base_url(base_url: Optional[str]) -> str:
        """归一化 Ollama 地址，兼容误填 /v1、/api 等后缀。"""
        candidate = (base_url or "http://localhost:11434").strip().rstrip("/")
        removable_suffixes = ("/v1/models", "/v1/embeddings", "/v1", "/api")
        changed = True
        while changed:
            changed = False
            lowered = candidate.lower()
            for suffix in removable_suffixes:
                if lowered.endswith(suffix):
                    candidate = candidate[: -len(suffix)].rstrip("/")
                    changed = True
                    break
        return candidate or "http://localhost:11434"

    def _build_url(self, base_url: Optional[str], default_url: str, path_suffix: str) -> str:
        """统一的 URL 构建逻辑，避免路径重复"""
        if base_url:
            url = base_url.rstrip("/")
            # 如果 URL 已经包含路径后缀，则直接使用
            if not url.endswith(path_suffix):
                url += path_suffix
        else:
            url = default_url
        return url

    async def upsert_config(self, user_id: int, payload: LLMConfigCreate) -> LLMConfigRead:
        instance = await self.repo.get_by_user(user_id)
        data = payload.model_dump(exclude_unset=True)
        if "llm_provider_url" in data and data["llm_provider_url"] is not None:
            # HttpUrl 类型统一转为字符串写入
            data["llm_provider_url"] = str(data["llm_provider_url"])
        if "embedding_provider_url" in data and data["embedding_provider_url"] is not None:
            # HttpUrl 类型统一转为字符串写入
            data["embedding_provider_url"] = str(data["embedding_provider_url"])

        # 默认模式固定为 openai：仅在用户显式选择 ollama 时写入 ollama。
        if "embedding_provider_format" in data:
            raw_format = (data["embedding_provider_format"] or "").strip().lower()
            data["embedding_provider_format"] = (
                raw_format if raw_format in {"openai", "ollama"} else "openai"
            )
        elif not instance or not (instance.embedding_provider_format or "").strip():
            data["embedding_provider_format"] = "openai"
        logger.info(
            "upsert llm config: user_id=%s embedding_provider_format=%s explicit_format=%s",
            user_id,
            data.get(
                "embedding_provider_format",
                instance.embedding_provider_format if instance else None,
            ),
            "embedding_provider_format" in payload.model_dump(exclude_unset=True),
        )

        if instance:
            # Keep partial-update semantics via exclude_unset, while still allowing
            # explicit null values to clear persisted fields.
            for key, value in data.items():
                setattr(instance, key, value)
            await self.session.flush()
        else:
            instance = LLMConfig(user_id=user_id, **data)
            await self.repo.add(instance)
        await self.session.commit()
        return LLMConfigRead.model_validate(instance)

    async def get_config(self, user_id: int) -> Optional[LLMConfigRead]:
        instance = await self.repo.get_by_user(user_id)
        return LLMConfigRead.model_validate(instance) if instance else None

    async def delete_config(self, user_id: int) -> bool:
        instance = await self.repo.get_by_user(user_id)
        if not instance:
            return False
        await self.repo.delete(instance)
        await self.session.commit()
        return True

    async def list_bundle(self, user_id: int) -> LLMConfigBundle:
        legacy = await self.get_config(user_id)
        provider_items = list(await self.provider_repo.list_by_user(user_id))
        model_items = list(await self.model_repo.list_by_user(user_id))
        provider_fallbacks = self._infer_provider_capabilities(model_items)
        providers = [
            self._provider_to_read(item, provider_fallbacks.get(item.id)) for item in provider_items
        ]
        models = [self._model_to_read(item) for item in model_items]
        routes = [
            self._route_to_read(item) for item in await self.stage_route_repo.list_by_user(user_id)
        ]
        return LLMConfigBundle(
            legacy=legacy, providers=providers, models=models, stage_routes=routes
        )

    @staticmethod
    def _infer_provider_capabilities(models: list) -> dict[int, dict[str, bool]]:
        inferred: dict[int, dict[str, bool]] = {}
        for model in models:
            capabilities = model.capabilities_json or {}
            provider_caps = inferred.setdefault(
                model.provider_id,
                {"chat": False, "embedding": False, "tts": False},
            )
            provider_caps["chat"] = provider_caps["chat"] or bool(capabilities.get("chat"))
            provider_caps["embedding"] = provider_caps["embedding"] or bool(
                capabilities.get("embedding")
            )
            provider_caps["tts"] = provider_caps["tts"] or bool(capabilities.get("tts"))
        return inferred

    async def create_provider(self, user_id: int, payload: ProviderCreate) -> ProviderRead:
        self._check_base_url(payload.base_url)
        provider = UserModelProvider(
            user_id=user_id,
            name=payload.name.strip(),
            provider_type=payload.provider_type,
            base_url=payload.base_url.strip().rstrip("/"),
            api_key_encrypted=encrypt((payload.api_key or "").strip() or None),
            api_key_preview=self._mask_api_key(payload.api_key),
            capabilities_json=self._normalize_capabilities(payload.capabilities),
            is_enabled=payload.is_enabled,
        )
        await self.provider_repo.add(provider)
        await self.session.commit()
        return self._provider_to_read(provider)

    async def list_providers(self, user_id: int) -> list[ProviderRead]:
        return [
            self._provider_to_read(item) for item in await self.provider_repo.list_by_user(user_id)
        ]

    async def get_provider_models(self, user_id: int, provider_id: int) -> List[str]:
        provider = await self.provider_repo.get_owned(provider_id, user_id)
        if not provider:
            raise ValueError("provider not found")
        if not provider.is_enabled:
            raise ValueError("provider disabled")
        return await self.get_available_models(
            api_key=decrypt(provider.api_key_encrypted),
            base_url=provider.base_url,
            provider_type=provider.provider_type,
        )

    async def update_provider(
        self, user_id: int, provider_id: int, payload: ProviderUpdate
    ) -> ProviderRead:
        provider = await self.provider_repo.get_owned(provider_id, user_id)
        if not provider:
            raise ValueError("provider not found")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            provider.name = data["name"].strip()
        if "provider_type" in data and data["provider_type"] is not None:
            provider.provider_type = data["provider_type"]
        if "base_url" in data and data["base_url"] is not None:
            self._check_base_url(data["base_url"])
            provider.base_url = data["base_url"].strip().rstrip("/")
        if "api_key" in data:
            provider.api_key_encrypted = encrypt((data["api_key"] or "").strip() or None)
            provider.api_key_preview = self._mask_api_key(data["api_key"])
        if "capabilities" in data and data["capabilities"] is not None:
            provider.capabilities_json = self._normalize_capabilities(data["capabilities"])
        if "is_enabled" in data and data["is_enabled"] is not None:
            provider.is_enabled = data["is_enabled"]
        await self.session.commit()
        return self._provider_to_read(provider)

    async def delete_provider(self, user_id: int, provider_id: int) -> bool:
        provider = await self.provider_repo.get_owned(provider_id, user_id)
        if not provider:
            raise ValueError("provider not found")

        provider_models = [
            model
            for model in await self.model_repo.list_by_user(user_id)
            if model.provider_id == provider_id
        ]
        provider_model_ids = {model.id for model in provider_models}

        # 先清理阶段路由，再删除模型和供应商，避免配置指向失效模型。
        routes = list(await self.stage_route_repo.list_by_user(user_id))
        for route in routes:
            if route.model_id in provider_model_ids:
                await self.stage_route_repo.delete(route)
        for model in provider_models:
            await self.model_repo.delete(model)

        await self.provider_repo.delete(provider)
        await self.session.commit()
        return True

    async def create_model(self, user_id: int, payload: UserAIModelCreate) -> UserAIModelRead:
        if payload.is_default_tts:
            await self.model_repo.lock_user_configuration(user_id)
        provider = await self.provider_repo.get_owned(payload.provider_id, user_id)
        if not provider:
            raise ValueError("provider not found")
        model = UserAIModel(
            user_id=user_id,
            provider_id=payload.provider_id,
            display_name=payload.display_name.strip(),
            model_name=payload.model_name.strip(),
            capabilities_json=payload.capabilities,
            context_window=payload.context_window,
            is_default_chat=payload.is_default_chat,
            is_default_embedding=payload.is_default_embedding,
            is_default_tts=payload.is_default_tts,
            tts_protocol=payload.tts_protocol,
            tts_voice=(payload.tts_voice or "").strip() or None,
            tts_speed=payload.tts_speed,
            input_price_per_million=payload.input_price_per_million,
            output_price_per_million=payload.output_price_per_million,
            cached_input_price_per_million=payload.cached_input_price_per_million,
            cache_write_input_price_per_million=payload.cache_write_input_price_per_million,
            pricing_currency=payload.pricing_currency,
            is_enabled=payload.is_enabled,
            sort_order=payload.sort_order,
        )
        await self.model_repo.add(model)
        await self._normalize_default_flags(user_id, model)
        await self.session.commit()
        return self._model_to_read(model)

    async def list_models(self, user_id: int) -> list[UserAIModelRead]:
        return [self._model_to_read(item) for item in await self.model_repo.list_by_user(user_id)]

    async def update_model(
        self, user_id: int, model_id: int, payload: UserAIModelUpdate
    ) -> UserAIModelRead:
        await self.model_repo.lock_user_configuration(user_id)
        model = await self.model_repo.get_owned(model_id, user_id)
        if not model:
            raise ValueError("model not found")
        data = payload.model_dump(exclude_unset=True)
        if "provider_id" in data and data["provider_id"] is not None:
            provider = await self.provider_repo.get_owned(data["provider_id"], user_id)
            if not provider:
                raise ValueError("provider not found")
            model.provider_id = data["provider_id"]
        if "display_name" in data and data["display_name"] is not None:
            model.display_name = data["display_name"].strip()
        if "model_name" in data and data["model_name"] is not None:
            model.model_name = data["model_name"].strip()
        if "capabilities" in data and data["capabilities"] is not None:
            model.capabilities_json = data["capabilities"]
        if "context_window" in data:
            model.context_window = data["context_window"]
        if "is_default_chat" in data and data["is_default_chat"] is not None:
            model.is_default_chat = data["is_default_chat"]
        if "is_default_embedding" in data and data["is_default_embedding"] is not None:
            model.is_default_embedding = data["is_default_embedding"]
        if "is_default_tts" in data and data["is_default_tts"] is not None:
            model.is_default_tts = data["is_default_tts"]
        if "tts_protocol" in data:
            model.tts_protocol = data["tts_protocol"]
        if "tts_voice" in data:
            model.tts_voice = (data["tts_voice"] or "").strip() or None
        if "tts_speed" in data and data["tts_speed"] is not None:
            model.tts_speed = data["tts_speed"]
        for pricing_field in (
            "input_price_per_million",
            "output_price_per_million",
            "cached_input_price_per_million",
            "cache_write_input_price_per_million",
            "pricing_currency",
        ):
            if pricing_field in data:
                setattr(model, pricing_field, data[pricing_field])
        if "is_enabled" in data and data["is_enabled"] is not None:
            model.is_enabled = data["is_enabled"]
        if "sort_order" in data and data["sort_order"] is not None:
            model.sort_order = data["sort_order"]
        self._validate_tts_model(model)
        await self._normalize_default_flags(user_id, model)
        await self.session.commit()
        return self._model_to_read(model)

    async def delete_model(self, user_id: int, model_id: int) -> bool:
        model = await self.model_repo.get_owned(model_id, user_id)
        if not model:
            raise ValueError("model not found")
        if model.is_default_chat:
            raise ValueError("主模型不能直接删除，请先选择另一个主模型。")
        if model.is_default_embedding:
            raise ValueError("当前向量模型不能直接删除，请先选择另一个向量模型。")
        if getattr(model, "is_default_tts", False):
            raise ValueError("当前语音朗读模型不能直接删除，请先选择另一个语音朗读模型。")

        # 删除模型前主动清理阶段路由，避免留下指向已删除模型的配置。
        routes = list(await self.stage_route_repo.list_by_user(user_id))
        for route in routes:
            if route.model_id == model.id:
                await self.stage_route_repo.delete(route)

        await self.model_repo.delete(model)
        await self.session.commit()
        return True

    async def _normalize_default_flags(self, user_id: int, changed_model) -> None:
        if getattr(changed_model, "is_default_tts", False):
            models = list(await self.model_repo.list_by_user_for_update(user_id))
        else:
            models = list(await self.model_repo.list_by_user(user_id))
        if changed_model.is_default_chat:
            for model in models:
                if model.id != changed_model.id:
                    model.is_default_chat = False
        if changed_model.is_default_embedding:
            changed_model.is_enabled = True
            for model in models:
                if model.id != changed_model.id:
                    model.is_default_embedding = False
                    # 向量模型是记忆检索的唯一入口，避免多个 embedding 同时启用。
                    if (model.capabilities_json or {}).get("embedding"):
                        model.is_enabled = False
        if getattr(changed_model, "is_default_tts", False):
            changed_model.is_enabled = True
            for model in models:
                if model.id != changed_model.id:
                    model.is_default_tts = False

    async def upsert_stage_routes(
        self, user_id: int, payload: StageRoutesPayload
    ) -> list[StageRouteRead]:
        incoming_stages = {item.stage for item in payload.routes}
        for item in payload.routes:
            capability = self.stage_capability(item.stage)
            model = await self.model_repo.get_owned(item.model_id, user_id)
            if not model:
                raise ValueError(f"model not found for stage {item.stage}")
            if not (model.capabilities_json or {}).get(capability):
                raise ValueError(f"model {model.model_name} does not support {capability}")
            if not model.is_enabled:
                raise ValueError(f"model {model.model_name} disabled")
            provider = getattr(model, "provider", None)
            if not provider or not provider.is_enabled:
                raise ValueError(f"provider disabled for model {model.model_name}")
            route = await self.stage_route_repo.get_by_stage(user_id, item.stage)
            if route:
                route.model_id = item.model_id
            else:
                await self.stage_route_repo.add(
                    UserAIStageRoute(user_id=user_id, stage=item.stage, model_id=item.model_id)
                )
        existing_routes = list(await self.stage_route_repo.list_by_user(user_id))
        for route in existing_routes:
            if route.stage in ALL_STAGE_KEYS and route.stage not in incoming_stages:
                await self.stage_route_repo.delete(route)
        await self.session.commit()
        return [
            self._route_to_read(item) for item in await self.stage_route_repo.list_by_user(user_id)
        ]

    async def get_available_models(
        self,
        api_key: Optional[str],
        base_url: Optional[str] = None,
        provider_type: Optional[str] = None,
    ) -> List[str]:
        """使用指定的凭证获取可用的模型列表"""
        self._check_base_url(base_url)
        provider = self._resolve_provider_for_model_list(provider_type, base_url)
        logger.info(
            "识别到 LLM 提供商: %s (provider_type: %s, base_url: %s, has_api_key=%s)",
            provider,
            provider_type,
            base_url,
            bool(api_key),
        )

        try:
            # 根据不同提供商获取模型列表
            if provider == "anthropic":
                return await self._get_anthropic_models(api_key, base_url)
            elif provider == "google":
                return await self._get_google_models(api_key, base_url)
            elif provider == "azure":
                return await self._get_azure_models(api_key, base_url)
            elif provider == "cohere":
                return await self._get_cohere_models(api_key, base_url)
            elif provider == "ollama":
                return await self._get_ollama_models(base_url)
            else:
                # OpenAI 和 OpenAI-like (包括 together, deepseek, moonshot, zhipu 等)
                return await self._get_openai_like_models(api_key, base_url)
        except Exception as e:
            error_msg = str(e)
            logger.error(
                "获取模型列表失败: provider=%s, error=%s", provider, error_msg, exc_info=True
            )

            # 提供更友好的错误信息
            if "Connection error" in error_msg or "disconnected" in error_msg.lower():
                logger.warning("连接错误，可能是 API URL 配置错误或网络问题")
            elif "401" in error_msg or "Unauthorized" in error_msg:
                logger.warning("认证失败，请检查 API Key 是否正确")
            elif "404" in error_msg or "Not Found" in error_msg:
                logger.warning("API 端点不存在，请检查 URL 是否正确")

            return []

    async def _get_openai_like_models(
        self, api_key: Optional[str], base_url: Optional[str]
    ) -> List[str]:
        """获取 OpenAI 或 OpenAI-like API 的模型列表"""
        import httpx
        from openai import APIConnectionError, APIError

        if not api_key:
            # 无 Key 场景下直接走 HTTP（不带 Authorization）
            return await self._get_models_via_http(api_key=None, base_url=base_url)

        client = None
        try:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=httpx.Timeout(30.0, connect=10.0),
                max_retries=2,
            )

            logger.info("尝试获取模型列表: base_url=%s", base_url)
            models_response = await client.models.list()
            model_ids = [model.id for model in models_response.data]
            logger.info("成功获取 %d 个 OpenAI-like 模型", len(model_ids))
            return sorted(model_ids)

        except APIConnectionError as e:
            logger.error("API 连接错误: %s", str(e), exc_info=True)
            # 某些自建服务可能不支持 /v1/models 端点，尝试使用 httpx 直接请求
            return await self._get_models_via_http(api_key, base_url)

        except APIError as e:
            logger.error(
                "API 调用错误: status_code=%s, message=%s",
                getattr(e, "status_code", "unknown"),
                str(e),
            )
            return await self._get_models_via_http(api_key, base_url)

        except Exception as e:
            logger.error("获取 OpenAI-like 模型列表失败: %s", str(e), exc_info=True)
            return await self._get_models_via_http(api_key, base_url)
        finally:
            if client is not None:
                await client.close()

    async def _get_models_via_http(
        self, api_key: Optional[str], base_url: Optional[str]
    ) -> List[str]:
        """使用 httpx 直接请求模型列表（备选方案）"""
        import httpx

        try:
            # 构建完整的 URL
            if base_url:
                url = base_url.rstrip("/") + "/models"
            else:
                url = "https://api.openai.com/v1/models"

            headers = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            logger.info("使用 HTTP 直接请求模型列表: url=%s", url)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=headers)

                logger.info("HTTP 响应状态码: %d", response.status_code)

                if response.status_code == 200:
                    data = response.json()
                    models = data.get("data", [])
                    model_ids = [model.get("id") for model in models if model.get("id")]
                    logger.info("通过 HTTP 成功获取 %d 个模型", len(model_ids))
                    return sorted(model_ids)
                elif response.status_code == 404:
                    logger.warning("模型列表端点不存在 (404)，该服务可能不支持模型列表查询")
                    return []
                elif response.status_code == 401:
                    logger.warning("认证失败 (401)，请检查 API Key 是否正确")
                    return []
                else:
                    logger.warning(
                        "HTTP 请求失败: status=%d, body=%s",
                        response.status_code,
                        response.text[:200],
                    )
                    return []

        except httpx.TimeoutException:
            logger.error("HTTP 请求超时")
            return []
        except httpx.ConnectError as e:
            logger.error("无法连接到服务器: %s", str(e))
            return []
        except Exception as e:
            logger.error("HTTP 请求失败: %s", str(e), exc_info=True)
            return []

    async def _get_ollama_models(self, base_url: Optional[str]) -> List[str]:
        """获取 Ollama 本地模型列表（无需 API Key）。"""
        import httpx

        normalized_base = self._normalize_ollama_base_url(base_url)
        tags_url = f"{normalized_base}/api/tags"
        try:
            logger.info("请求 Ollama 模型列表: url=%s", tags_url)
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(tags_url)
                response.raise_for_status()
                payload = response.json()
            models = payload.get("models", []) if isinstance(payload, dict) else []
            model_names = [
                model.get("name")
                for model in models
                if isinstance(model, dict)
                and isinstance(model.get("name"), str)
                and model.get("name")
            ]
            logger.info("成功获取 %d 个 Ollama 模型", len(model_names))
            return sorted(model_names)
        except Exception as e:
            logger.error(
                "获取 Ollama 模型列表失败: base=%s error=%s", normalized_base, str(e), exc_info=True
            )
            return []

    async def _get_anthropic_models(
        self, api_key: Optional[str], base_url: Optional[str]
    ) -> List[str]:
        """获取 Anthropic 模型列表，失败或为空时返回空列表（不回退硬编码模型）。"""
        import httpx

        if not api_key:
            return []
        models_url = self._anthropic_endpoint_url(base_url, "models")
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        }
        try:
            logger.info("请求 Anthropic 模型列表: url=%s", models_url)
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(models_url, headers=headers)
                response.raise_for_status()
                payload = response.json()
            model_ids = [
                item.get("id")
                for item in payload.get("data", [])
                if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
            ]
            logger.info("成功获取 %d 个 Anthropic 模型", len(model_ids))
            return sorted(model_ids)
        except Exception as e:
            logger.error(
                "获取 Anthropic 模型列表失败: base=%s error=%s", base_url, str(e), exc_info=True
            )
            return []

    async def _get_google_models(self, api_key: str, base_url: Optional[str]) -> List[str]:
        """获取 Google Gemini 的模型列表"""
        import httpx

        try:
            # 使用统一的 URL 构建方法
            url = self._build_url(
                base_url, "https://generativelanguage.googleapis.com/v1beta", "/v1beta"
            )
            url += f"/models?key={api_key}"

            logger.info("请求 Google 模型列表: url=%s", url.replace(api_key, "***"))

            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)

                logger.info("HTTP 响应状态码: %d", response.status_code)
                response.raise_for_status()
                data = response.json()

                model_ids = []
                for model in data.get("models", []):
                    model_name = model.get("name", "")
                    # 移除 "models/" 前缀
                    if model_name.startswith("models/"):
                        model_name = model_name[7:]
                    # 只返回生成模型（非 embedding 模型）
                    if "generateContent" in model.get("supportedGenerationMethods", []):
                        model_ids.append(model_name)

                logger.info("成功获取 %d 个 Google 模型", len(model_ids))
                return sorted(model_ids)
        except httpx.HTTPStatusError as e:
            logger.error(
                "Google API HTTP 错误: status=%d, message=%s", e.response.status_code, str(e)
            )
            # 返回常用的 Gemini 模型作为备选
            return [
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro",
            ]
        except httpx.TimeoutException:
            logger.error("Google API 请求超时")
            return [
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro",
            ]
        except Exception as e:
            logger.error("获取 Google 模型列表失败: %s", str(e), exc_info=True)
            # 返回常用的 Gemini 模型作为备选
            return [
                "gemini-2.0-flash-exp",
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro",
            ]

    async def _get_azure_models(self, api_key: str, base_url: Optional[str]) -> List[str]:
        """获取 Azure OpenAI 的模型列表"""
        # Azure OpenAI 的部署是用户自定义的，无法直接列举
        # 返回常见的 Azure OpenAI 模型名称
        logger.info("返回 Azure OpenAI 预定义模型列表")
        return [
            "gpt-4",
            "gpt-4-32k",
            "gpt-4-turbo",
            "gpt-4o",
            "gpt-35-turbo",
            "gpt-35-turbo-16k",
        ]

    async def _get_cohere_models(self, api_key: str, base_url: Optional[str]) -> List[str]:
        """获取 Cohere 的模型列表"""
        import httpx

        try:
            # 使用统一的 URL 构建方法
            url = self._build_url(base_url, "https://api.cohere.ai/v1", "/v1")
            url += "/models"

            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }

            logger.info("请求 Cohere 模型列表: url=%s", url)

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, timeout=30.0)

                logger.info("HTTP 响应状态码: %d", response.status_code)
                response.raise_for_status()
                data = response.json()

                model_ids = [
                    model.get("name") for model in data.get("models", []) if model.get("name")
                ]
                logger.info("成功获取 %d 个 Cohere 模型", len(model_ids))
                return sorted(model_ids)
        except httpx.HTTPStatusError as e:
            logger.error(
                "Cohere API HTTP 错误: status=%d, message=%s", e.response.status_code, str(e)
            )
            return [
                "command-r-plus",
                "command-r",
                "command",
                "command-light",
            ]
        except httpx.TimeoutException:
            logger.error("Cohere API 请求超时")
            return [
                "command-r-plus",
                "command-r",
                "command",
                "command-light",
            ]
        except Exception as e:
            logger.error("获取 Cohere 模型列表失败: %s", str(e), exc_info=True)
            # 返回常用的 Cohere 模型作为备选
            return [
                "command-r-plus",
                "command-r",
                "command",
                "command-light",
            ]
