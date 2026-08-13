# AIMETA P=LLM服务_大模型调用封装|R=API调用_流式生成|NR=不含业务逻辑|E=LLMService|X=internal|A=服务类|D=openai,httpx|S=net|RD=./README.ai
import asyncio
import logging
import os
import random
from typing import Any, AsyncGenerator, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException
from openai import (
    APIConnectionError,
    APITimeoutError,
    AsyncOpenAI,
    InternalServerError,
    PermissionDeniedError,
)

from ..core.config import settings
from ..core.crypto import decrypt
from ..core.ssrf import assert_safe_base_url
from ..db.session import AsyncSessionLocal
from ..repositories.ai_model_config_repository import (
    UserAIModelRepository,
    UserAIStageRouteRepository,
)
from ..repositories.llm_config_repository import LLMConfigRepository
from ..repositories.system_config_repository import SystemConfigRepository
from ..services.llm_config_service import CHAT_STAGE_KEYS, EMBEDDING_STAGE_KEYS
from ..services.prompt_service import PromptService
from ..services.usage_service import UsageService
from ..utils.ai_telemetry import (
    AICallResult,
    TokenUsage,
    normalize_openai_embedding_usage,
)
from ..utils.llm_tool import ChatMessage, LLMClient

logger = logging.getLogger(__name__)
LLM_RETRY_MAX_ATTEMPTS = 3
LLM_RETRY_BASE_DELAY_SECONDS = 1.0
LLM_RETRY_MAX_DELAY_SECONDS = 8.0
LLM_RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}
LLM_RETRYABLE_ERROR_KEYWORDS = (
    "concurrency limit exceeded",
    "please retry later",
    "rate limit",
    "too many requests",
    "temporarily unavailable",
    "temporary unavailable",
    "overloaded",
)
LLM_NON_RETRYABLE_ERROR_KEYWORDS = (
    "api key",
    "invalid key",
    "insufficient_quota",
    "quota exceeded",
    "billing",
    "permission denied",
    "model_not_found",
    "model not found",
)

try:  # pragma: no cover - 运行环境未安装时兼容
    from ollama import AsyncClient as OllamaAsyncClient
except ImportError:  # pragma: no cover - Ollama 为可选依赖
    OllamaAsyncClient = None


class LLMService:
    """封装与大模型交互的所有逻辑，包括模型配置解析与调用。"""

    def __init__(self, session):
        self.session = session
        self.llm_repo = LLMConfigRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self.ai_model_repo = UserAIModelRepository(session)
        self.stage_route_repo = UserAIStageRouteRepository(session)
        self.usage_service = UsageService(session)

    @staticmethod
    def _get_llm_error_status_code(exc: Exception) -> Optional[int]:
        status_code = getattr(exc, "status_code", None)
        if isinstance(status_code, int):
            return status_code

        response = getattr(exc, "response", None)
        response_status = getattr(response, "status_code", None)
        if isinstance(response_status, int):
            return response_status
        return None

    @staticmethod
    def _extract_llm_error_detail(exc: Exception, default: str) -> str:
        response = getattr(exc, "response", None)
        if response is not None:
            try:
                payload = response.json()
            except Exception:
                payload = None

            if isinstance(payload, dict):
                error_data = payload.get("error", {})
                if isinstance(error_data, dict):
                    detail = error_data.get("message_zh") or error_data.get("message")
                    if detail:
                        return str(detail)
                elif isinstance(error_data, str) and error_data.strip():
                    return error_data.strip()

                for key in ("message_zh", "message", "detail"):
                    detail = payload.get(key)
                    if detail:
                        return str(detail)

        detail = str(exc).strip()
        return detail or default

    @staticmethod
    def _retry_after_seconds(exc: Exception) -> Optional[float]:
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", None)
        if not headers:
            return None

        retry_after = headers.get("retry-after") or headers.get("Retry-After")
        if not retry_after:
            return None
        try:
            value = float(retry_after)
        except ValueError:
            return None
        return max(0.0, min(value, LLM_RETRY_MAX_DELAY_SECONDS))

    @classmethod
    def _is_retryable_llm_error(cls, exc: Exception) -> bool:
        if isinstance(exc, PermissionDeniedError):
            return False

        detail = cls._extract_llm_error_detail(exc, "").lower()
        if any(keyword in detail for keyword in LLM_NON_RETRYABLE_ERROR_KEYWORDS):
            return False

        status_code = cls._get_llm_error_status_code(exc)
        if status_code in LLM_RETRYABLE_STATUS_CODES:
            return True

        if isinstance(
            exc,
            (
                httpx.RemoteProtocolError,
                httpx.ReadTimeout,
                APIConnectionError,
                APITimeoutError,
                InternalServerError,
            ),
        ):
            return True

        return any(keyword in detail for keyword in LLM_RETRYABLE_ERROR_KEYWORDS)

    @classmethod
    def _llm_retry_delay_seconds(cls, exc: Exception, attempt: int) -> float:
        retry_after = cls._retry_after_seconds(exc)
        if retry_after is not None:
            return retry_after

        delay = LLM_RETRY_BASE_DELAY_SECONDS * (2 ** max(attempt - 1, 0))
        jitter = random.uniform(0, 0.4)
        return min(delay + jitter, LLM_RETRY_MAX_DELAY_SECONDS)

    @classmethod
    def _safe_llm_error_reason(cls, exc: Exception) -> str:
        status_code = cls._get_llm_error_status_code(exc)
        if isinstance(exc, PermissionDeniedError) or status_code == 403:
            return "AI 服务拒绝访问"
        if isinstance(exc, (httpx.ReadTimeout, APITimeoutError)) or status_code == 408:
            return "AI 服务响应超时"
        if isinstance(exc, (httpx.RemoteProtocolError, APIConnectionError)):
            return "AI 服务连接失败"
        if status_code == 400:
            return "AI 服务请求参数错误"
        if status_code == 401:
            return "AI 服务认证失败"
        if status_code == 404:
            return "AI 服务端点或模型不存在"
        if status_code == 409:
            return "AI 服务请求冲突"
        if status_code == 429:
            return "AI 服务请求频率或并发超限"
        if status_code is not None and status_code >= 500:
            return "AI 服务上游故障"
        return "AI 服务 API 调用失败"

    @classmethod
    def _log_llm_call_failure(
        cls,
        exc: Exception,
        config: Dict[str, Any],
        *,
        user_id: Optional[int],
        stage: str,
    ) -> None:
        logger.error(
            "LLM call failed: stage=%s provider=%s provider_type=%s model=%s "
            "status_code=%s reason=%s error_type=%s user_id=%s",
            stage,
            config.get("provider_name") or "unknown",
            config.get("provider_type") or "unknown",
            config.get("model") or "unknown",
            cls._get_llm_error_status_code(exc) or "unknown",
            cls._safe_llm_error_reason(exc),
            type(exc).__name__,
            user_id,
        )

    @classmethod
    def _raise_llm_stream_error(
        cls,
        exc: Exception,
        config: Dict[str, Any],
        user_id: Optional[int],
        *,
        stage: str,
    ) -> None:
        cls._log_llm_call_failure(exc, config, user_id=user_id, stage=stage)
        if isinstance(exc, InternalServerError):
            detail = cls._extract_llm_error_detail(exc, "AI 服务内部错误，请稍后重试")
            raise HTTPException(status_code=503, detail=detail) from exc

        if isinstance(
            exc, (httpx.RemoteProtocolError, httpx.ReadTimeout, APIConnectionError, APITimeoutError)
        ):
            if isinstance(exc, httpx.RemoteProtocolError):
                detail = "AI 服务连接被意外中断，请稍后重试"
            elif isinstance(exc, (httpx.ReadTimeout, APITimeoutError)):
                detail = "AI 服务响应超时，请稍后重试"
            else:
                detail = "无法连接到 AI 服务，请稍后重试"
            raise HTTPException(status_code=503, detail=detail) from exc

        if isinstance(exc, PermissionDeniedError):
            detail = "AI 服务拒绝访问（可能被上游安全策略拦截），请稍后重试或更换可用 API 地址"
            raise HTTPException(status_code=503, detail=detail) from exc

        if cls._is_retryable_llm_error(exc):
            detail = cls._extract_llm_error_detail(exc, "AI 服务繁忙，请稍后重试")
            raise HTTPException(status_code=503, detail=detail) from exc

        raise exc

    async def get_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> str:
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
            model_id=model_id,
        )

    @classmethod
    async def get_llm_response_detached(
        cls,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        session_factory=AsyncSessionLocal,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> str:
        """短事务解析模型配置，关闭会话后再等待外部模型响应。"""

        async with session_factory() as session:
            service = cls(session)
            config = await service._resolve_llm_config(
                user_id,
                stage=stage,
                model_id=model_id,
            )

        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await service._stream_and_collect_with_config(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
        )

    @classmethod
    async def get_llm_response_result_detached(
        cls,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        session_factory=AsyncSessionLocal,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
        provider_request_key: Optional[str] = None,
    ) -> AICallResult[str]:
        """短事务解析路由，并返回供 durable activity 持久化的完整结果。"""

        async with session_factory() as session:
            service = cls(session)
            config = await service._resolve_llm_config(
                user_id,
                stage=stage,
                model_id=model_id,
            )
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        return await service._stream_and_collect_with_config_result(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
            provider_request_key=provider_request_key,
        )

    async def stream_llm_response(
        self,
        system_prompt: str,
        conversation_history: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        response_format: Optional[str] = "json_object",
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stage: str = "concept_conversation",
        model_id: Optional[int] = None,
    ) -> AsyncGenerator[str, None]:
        """流式输出模型文本片段，供 SSE 接口边生成边返回。"""
        messages = [{"role": "system", "content": system_prompt}, *conversation_history]
        config = await self._resolve_llm_config(user_id, stage=stage, model_id=model_id)
        client = LLMClient(
            api_key=config["api_key"],
            base_url=config.get("base_url"),
            provider_type=config.get("provider_type"),
        )
        chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

        full_response = ""
        finish_reason = None

        logger.info(
            "Streaming LLM response to client: model=%s user_id=%s messages=%d",
            config.get("model"),
            user_id,
            len(messages),
        )

        try:
            async for part in client.stream_chat(
                messages=chat_messages,
                model=config.get("model"),
                temperature=temperature,
                timeout=int(timeout),
                response_format=response_format,
                max_tokens=max_tokens,
                top_p=top_p,
            ):
                if part.get("content"):
                    full_response += part["content"]
                    yield part["content"]
                if part.get("finish_reason"):
                    finish_reason = part["finish_reason"]
        except InternalServerError as exc:
            detail = "AI 服务内部错误，请稍后重试"
            response = getattr(exc, "response", None)
            if response is not None:
                try:
                    payload = response.json()
                    error_data = payload.get("error", {}) if isinstance(payload, dict) else {}
                    detail = error_data.get("message_zh") or error_data.get("message") or detail
                except Exception:
                    detail = str(exc) or detail
            else:
                detail = str(exc) or detail
            logger.error(
                "LLM stream internal error: model=%s user_id=%s detail=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail)
        except (
            httpx.RemoteProtocolError,
            httpx.ReadTimeout,
            APIConnectionError,
            APITimeoutError,
        ) as exc:
            if isinstance(exc, httpx.RemoteProtocolError):
                detail = "AI 服务连接被意外中断，请稍后重试"
            elif isinstance(exc, (httpx.ReadTimeout, APITimeoutError)):
                detail = "AI 服务响应超时，请稍后重试"
            else:
                detail = "无法连接到 AI 服务，请稍后重试"
            logger.error(
                "LLM stream failed: model=%s user_id=%s detail=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail) from exc
        except PermissionDeniedError as exc:
            detail = "AI 服务拒绝访问（可能被上游安全策略拦截），请稍后重试或更换可用 API 地址"
            logger.error(
                "LLM stream permission denied: model=%s user_id=%s detail=%s",
                config.get("model"),
                user_id,
                detail,
                exc_info=exc,
            )
            raise HTTPException(status_code=503, detail=detail) from exc
        finally:
            await client.aclose()

        if finish_reason == "length":
            logger.warning(
                "LLM response truncated: model=%s user_id=%s response_length=%d",
                config.get("model"),
                user_id,
                len(full_response),
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 响应因长度限制被截断（已生成 {len(full_response)} 字符），请缩短输入内容或调整模型参数",
            )

        if not full_response:
            logger.error(
                "LLM returned empty response: model=%s user_id=%s finish_reason=%s",
                config.get("model"),
                user_id,
                finish_reason,
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 未返回有效内容（结束原因: {finish_reason or '未知'}），请稍后重试或联系管理员",
            )

        await self.usage_service.increment("api_request_count")
        logger.info(
            "LLM streaming response success: model=%s user_id=%s chars=%d",
            config.get("model"),
            user_id,
            len(full_response),
        )

    async def generate(
        self,
        prompt: str,
        *,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> str:
        """兼容旧版接口的文本生成入口，统一走 get_llm_response。"""
        return await self.get_llm_response(
            system_prompt=system_prompt or "你是一位专业写作助手。",
            conversation_history=[{"role": "user", "content": prompt}],
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
            model_id=model_id,
        )

    @classmethod
    async def generate_detached(
        cls,
        prompt: str,
        *,
        session_factory=AsyncSessionLocal,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> str:
        """Resolve model configuration in a short session, then call the provider."""

        async with session_factory() as session:
            service = cls(session)
            config = await service._resolve_llm_config(
                user_id,
                stage=stage,
                model_id=model_id,
            )
        messages = [
            {"role": "system", "content": system_prompt or "你是一位专业写作助手。"},
            {"role": "user", "content": prompt},
        ]
        return await service._stream_and_collect_with_config(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
        )

    @classmethod
    async def generate_result_detached(
        cls,
        prompt: str,
        *,
        session_factory=AsyncSessionLocal,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        user_id: Optional[int] = None,
        timeout: float = 300.0,
        max_tokens: Optional[int] = None,
        response_format: Optional[str] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> AICallResult[str]:
        async with session_factory() as session:
            service = cls(session)
            config = await service._resolve_llm_config(
                user_id,
                stage=stage,
                model_id=model_id,
            )
        messages = [
            {"role": "system", "content": system_prompt or "你是一位专业写作助手。"},
            {"role": "user", "content": prompt},
        ]
        return await service._stream_and_collect_with_config_result(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
        )

    async def get_summary(
        self,
        chapter_content: str,
        *,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        system_prompt: Optional[str] = None,
        stage: str = "summary_memory",
        model_id: Optional[int] = None,
    ) -> str:
        if not system_prompt:
            prompt_service = PromptService(self.session)
            system_prompt = await prompt_service.get_prompt("extraction")
        if not system_prompt:
            logger.error("未配置名为 'extraction' 的摘要提示词，无法生成章节摘要")
            raise HTTPException(
                status_code=500, detail="未配置摘要提示词，请联系管理员配置 'extraction' 提示词"
            )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chapter_content},
        ]
        return await self._stream_and_collect(
            messages,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            stage=stage,
            model_id=model_id,
        )

    @classmethod
    async def get_summary_detached(
        cls,
        chapter_content: str,
        *,
        session_factory=AsyncSessionLocal,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        system_prompt: Optional[str] = None,
        stage: str = "summary_memory",
        model_id: Optional[int] = None,
    ) -> str:
        """在短事务内解析摘要提示词和模型配置，再执行外部调用。"""

        async with session_factory() as session:
            service = cls(session)
            resolved_prompt = system_prompt or await PromptService(session).get_prompt("extraction")
            if not resolved_prompt:
                logger.error("未配置名为 'extraction' 的摘要提示词，无法生成章节摘要")
                raise HTTPException(
                    status_code=500, detail="未配置摘要提示词，请联系管理员配置 'extraction' 提示词"
                )
            config = await service._resolve_llm_config(
                user_id,
                stage=stage,
                model_id=model_id,
            )

        messages = [
            {"role": "system", "content": resolved_prompt},
            {"role": "user", "content": chapter_content},
        ]
        return await service._stream_and_collect_with_config(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            stage=stage,
        )

    @classmethod
    async def get_summary_result_detached(
        cls,
        chapter_content: str,
        *,
        session_factory=AsyncSessionLocal,
        temperature: float = 0.2,
        user_id: Optional[int] = None,
        timeout: float = 180.0,
        system_prompt: Optional[str] = None,
        stage: str = "summary_memory",
        model_id: Optional[int] = None,
    ) -> AICallResult[str]:
        async with session_factory() as session:
            service = cls(session)
            resolved_prompt = system_prompt or await PromptService(session).get_prompt("extraction")
            if not resolved_prompt:
                raise HTTPException(
                    status_code=500, detail="未配置摘要提示词，请联系管理员配置 'extraction' 提示词"
                )
            config = await service._resolve_llm_config(
                user_id,
                stage=stage,
                model_id=model_id,
            )
        messages = [
            {"role": "system", "content": resolved_prompt},
            {"role": "user", "content": chapter_content},
        ]
        return await service._stream_and_collect_with_config_result(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            stage=stage,
        )

    async def _get_user_llm_config_record(self, user_id: Optional[int]):
        """统一校验并读取用户级 LLM 配置，禁止回退系统默认配置。"""
        if not user_id:
            logger.warning("缺少 user_id，拒绝回退到默认 LLM 配置")
            raise HTTPException(
                status_code=400,
                detail="缺少用户上下文，无法读取用户级 LLM 配置。系统默认 LLM 配置已禁用，请重新登录后在模型设置中保存用户级配置。",
            )

        config = await self.llm_repo.get_by_user(user_id)
        if not config:
            logger.warning("用户 %s 未配置用户级 LLM 设置", user_id)
            raise HTTPException(
                status_code=400,
                detail="请先在模型设置中保存用户级 LLM 配置。系统默认 LLM 配置已禁用。",
            )

        return config

    async def _stream_and_collect(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        response_format: Optional[str] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> str:
        config = await self._resolve_llm_config(user_id, stage=stage, model_id=model_id)
        return await self._stream_and_collect_with_config(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
        )

    async def _stream_and_collect_with_config(
        self,
        messages: List[Dict[str, str]],
        *,
        config: Dict[str, Any],
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        response_format: Optional[str] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
    ) -> str:
        result = await self._stream_and_collect_with_config_result(
            messages,
            config=config,
            temperature=temperature,
            user_id=user_id,
            timeout=timeout,
            response_format=response_format,
            max_tokens=max_tokens,
            top_p=top_p,
            stage=stage,
        )
        return result.value

    async def _stream_and_collect_with_config_result(
        self,
        messages: List[Dict[str, str]],
        *,
        config: Dict[str, Any],
        temperature: float,
        user_id: Optional[int],
        timeout: float,
        response_format: Optional[str] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        stage: str = "chapter_writing",
        provider_request_key: Optional[str] = None,
    ) -> AICallResult[str]:
        client = LLMClient(
            api_key=config["api_key"],
            base_url=config.get("base_url"),
            provider_type=config.get("provider_type"),
        )

        chat_messages = [ChatMessage(role=msg["role"], content=msg["content"]) for msg in messages]

        full_response = ""
        finish_reason = None
        usage = TokenUsage()

        logger.info(
            "Streaming LLM response: model=%s user_id=%s messages=%d",
            config.get("model"),
            user_id,
            len(messages),
        )

        # 单次模型调用层轻量重试：只处理上游临时故障，不重跑外层业务流程。
        try:
            for attempt in range(1, LLM_RETRY_MAX_ATTEMPTS + 1):
                full_response = ""
                finish_reason = None
                usage = TokenUsage()
                try:
                    async for part in client.stream_chat(
                        messages=chat_messages,
                        model=config.get("model"),
                        temperature=temperature,
                        timeout=int(timeout),
                        response_format=response_format,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        provider_request_key=provider_request_key,
                    ):
                        if part.get("content"):
                            full_response += part["content"]
                        if part.get("finish_reason"):
                            finish_reason = part["finish_reason"]
                        if isinstance(part.get("usage"), dict):
                            usage = TokenUsage.from_dict(part["usage"])
                    break
                except Exception as exc:
                    if attempt < LLM_RETRY_MAX_ATTEMPTS and self._is_retryable_llm_error(exc):
                        delay = self._llm_retry_delay_seconds(exc, attempt)
                        logger.warning(
                            "LLM stream retry: stage=%s provider=%s provider_type=%s model=%s "
                            "status_code=%s reason=%s error_type=%s user_id=%s attempt=%s/%s delay=%.2fs",
                            stage,
                            config.get("provider_name") or "unknown",
                            config.get("provider_type") or "unknown",
                            config.get("model"),
                            self._get_llm_error_status_code(exc) or "unknown",
                            self._safe_llm_error_reason(exc),
                            type(exc).__name__,
                            user_id,
                            attempt,
                            LLM_RETRY_MAX_ATTEMPTS,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    self._raise_llm_stream_error(exc, config, user_id, stage=stage)
        finally:
            await client.aclose()

        logger.debug(
            "LLM response collected: model=%s user_id=%s finish_reason=%s preview=%s",
            config.get("model"),
            user_id,
            finish_reason,
            full_response[:500],
        )

        if finish_reason == "length":
            logger.warning(
                "LLM response truncated: model=%s user_id=%s response_length=%d",
                config.get("model"),
                user_id,
                len(full_response),
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 响应因长度限制被截断（已生成 {len(full_response)} 字符），请缩短输入内容或调整模型参数",
            )

        if not full_response:
            logger.error(
                "LLM returned empty response: model=%s user_id=%s finish_reason=%s",
                config.get("model"),
                user_id,
                finish_reason,
            )
            raise HTTPException(
                status_code=500,
                detail=f"AI 未返回有效内容（结束原因: {finish_reason or '未知'}），请稍后重试或联系管理员",
            )

        await self.usage_service.increment("api_request_count")
        logger.info(
            "LLM response success: model=%s user_id=%s chars=%d",
            config.get("model"),
            user_id,
            len(full_response),
        )
        return AICallResult.from_config(
            full_response,
            config=config,
            usage=usage,
            stage=stage,
        )

    async def _resolve_llm_config(
        self,
        user_id: Optional[int],
        *,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> Dict[str, Optional[str]]:
        return await self._resolve_llm_config_with_policy(
            user_id,
            require_api_key=True,
            stage=stage,
            model_id=model_id,
        )

    async def _resolve_model_route(
        self,
        user_id: int,
        *,
        stage: str,
        capability: str,
        model_id: Optional[int] = None,
    ):
        if capability == "chat" and stage not in CHAT_STAGE_KEYS:
            raise HTTPException(status_code=400, detail=f"未知 AI 阶段：{stage}")
        if capability == "embedding" and stage not in EMBEDDING_STAGE_KEYS:
            raise HTTPException(status_code=400, detail=f"未知向量阶段：{stage}")

        model = None
        if model_id is not None:
            model = await self.ai_model_repo.get_owned(model_id, user_id)
            if not model:
                raise HTTPException(status_code=400, detail="选择的模型不存在或不属于当前用户")
        else:
            route = await self.stage_route_repo.get_by_stage(user_id, stage)
            model = route.model if route else None
            if not model:
                models = list(
                    await self.ai_model_repo.list_enabled_by_capability(user_id, capability)
                )
                default_flag = (
                    "is_default_embedding" if capability == "embedding" else "is_default_chat"
                )
                model = next((item for item in models if getattr(item, default_flag, False)), None)
                if models and not model:
                    section_name = "向量模型" if capability == "embedding" else "LLM 模型"
                    default_name = "当前使用模型" if capability == "embedding" else "主模型"
                    raise HTTPException(
                        status_code=400,
                        detail=f"请先在模型设置的 {section_name} 中勾选{default_name}。",
                    )

        if not model:
            return None
        if not model.is_enabled:
            raise HTTPException(status_code=400, detail=f"模型 {model.model_name} 已禁用")
        if not (model.capabilities_json or {}).get(capability):
            raise HTTPException(
                status_code=400, detail=f"模型 {model.model_name} 不支持 {capability}"
            )

        provider = model.provider
        if not provider or not provider.is_enabled:
            raise HTTPException(status_code=400, detail=f"模型 {model.model_name} 的供应商不可用")

        base_url = (provider.base_url or "").strip() or None
        api_key = decrypt(provider.api_key_encrypted)
        if not base_url:
            raise HTTPException(status_code=400, detail=f"供应商 {provider.name} 缺少 API URL")
        try:
            assert_safe_base_url(base_url, allow_private=settings.allow_private_llm_endpoints)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model.model_name,
            "model_id": model.id,
            "stage": stage,
            "provider_name": provider.name,
            "provider_type": provider.provider_type,
            "input_price_per_million": model.input_price_per_million,
            "output_price_per_million": model.output_price_per_million,
            "cached_input_price_per_million": model.cached_input_price_per_million,
            "cache_write_input_price_per_million": model.cache_write_input_price_per_million,
            "pricing_currency": model.pricing_currency,
        }

    async def _resolve_llm_config_with_policy(
        self,
        user_id: Optional[int],
        *,
        require_api_key: bool,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> Dict[str, Optional[str]]:
        if not user_id:
            logger.warning("缺少 user_id，拒绝回退到默认 LLM 配置")
            raise HTTPException(
                status_code=400,
                detail="缺少用户上下文，无法读取用户级 LLM 配置。系统默认 LLM 配置已禁用，请重新登录后在模型设置中保存用户级配置。",
            )

        routed = await self._resolve_model_route(
            user_id,
            stage=stage,
            capability="chat",
            model_id=model_id,
        )
        if routed:
            if (
                require_api_key
                and not routed.get("api_key")
                and routed.get("provider_type") != "ollama"
            ):
                raise HTTPException(
                    status_code=400, detail=f"阶段 {stage} 使用的供应商缺少 API Key"
                )
            return routed

        logger.warning("用户 %s 没有可用的 LLM 模型，stage=%s", user_id, stage)
        raise HTTPException(
            status_code=400,
            detail="请先在模型设置的 LLM 模型中启用模型，并勾选一个主模型。",
        )

    @staticmethod
    def _normalize_ollama_host(host: Optional[str]) -> Optional[str]:
        """归一化 Ollama host，避免误填 OpenAI 风格路径（如 /v1）。"""
        if host is None:
            return None

        normalized = host.strip().rstrip("/")
        if not normalized:
            return None

        removable_suffixes = ("/v1/models", "/v1/embeddings", "/v1")
        changed = True
        while changed:
            changed = False
            normalized_lower = normalized.lower()
            for suffix in removable_suffixes:
                if normalized_lower.endswith(suffix):
                    normalized = normalized[: -len(suffix)].rstrip("/")
                    changed = True
                    break

        return normalized or None

    @staticmethod
    def _extract_ollama_embed_vector(response: Any) -> Optional[List[float]]:
        """解析 /api/embed 响应，提取第一条向量。"""
        embeddings = (
            response.get("embeddings")
            if isinstance(response, dict)
            else getattr(response, "embeddings", None)
        )
        if not embeddings:
            return None
        first = embeddings[0] if isinstance(embeddings, list) else None
        if first is None:
            return None
        return first if isinstance(first, list) else list(first)

    @staticmethod
    def _extract_ollama_legacy_vector(response: Any) -> Optional[List[float]]:
        """解析 /api/embeddings（旧接口）响应。"""
        embedding = (
            response.get("embedding")
            if isinstance(response, dict)
            else getattr(response, "embedding", None)
        )
        if not embedding:
            return None
        return embedding if isinstance(embedding, list) else list(embedding)

    @staticmethod
    def _normalize_openai_embeddings_url(base_url: Optional[str]) -> Optional[str]:
        """将 OpenAI 兼容 base_url 规整为可直接 POST 的 /embeddings 端点。"""
        if not base_url:
            return None
        trimmed = base_url.strip().rstrip("/")
        if not trimmed:
            return None

        lowered = trimmed.lower()
        if lowered.endswith("/embeddings"):
            return trimmed
        if lowered.endswith("/v1"):
            return f"{trimmed}/embeddings"

        parsed = urlparse(trimmed)
        if parsed.path in {"", "/"}:
            return f"{trimmed}/v1/embeddings"
        return f"{trimmed}/embeddings"

    async def _request_ollama_embedding(
        self,
        client: Any,
        *,
        model: str,
        text: str,
        base_url: Optional[str],
    ) -> List[float]:
        """
        优先调用 Ollama 原生 /api/embed，若服务端较旧则回退 /api/embeddings。
        """
        if hasattr(client, "embed"):
            try:
                response = await client.embed(model=model, input=text)
                embedding = self._extract_ollama_embed_vector(response)
                if embedding:
                    return embedding
                logger.warning(
                    "Ollama /api/embed 返回空向量: model=%s base_url=%s", model, base_url
                )
            except Exception as exc:
                logger.warning(
                    "Ollama /api/embed 请求失败，尝试回退旧接口 /api/embeddings: model=%s base_url=%s error=%s",
                    model,
                    base_url,
                    exc,
                )

        try:
            response = await client.embeddings(model=model, prompt=text)
        except Exception as exc:  # pragma: no cover - 本地服务调用失败
            logger.error(
                "Ollama 嵌入请求失败: model=%s base_url=%s error=%s",
                model,
                base_url,
                exc,
                exc_info=True,
            )
            return []

        embedding = self._extract_ollama_legacy_vector(response)
        if not embedding:
            logger.warning(
                "Ollama /api/embeddings 返回空向量: model=%s base_url=%s", model, base_url
            )
            return []
        return embedding

    async def _resolve_embedding_route(
        self,
        *,
        user_id: Optional[int],
        stage: str,
        model_id: Optional[int],
    ) -> Dict[str, Any]:
        """在数据库短事务内解析用户的 embedding 路由。"""

        if not user_id:
            raise HTTPException(
                status_code=400,
                detail="缺少用户上下文，无法读取向量模型配置。系统默认向量配置已禁用，请重新登录后在模型设置中选择向量模型。",
            )

        routed = await self._resolve_model_route(
            user_id,
            stage=stage,
            capability="embedding",
            model_id=model_id,
        )
        if not routed:
            raise HTTPException(
                status_code=400,
                detail="请先在模型设置的向量模型中选择当前使用模型。系统默认向量配置已禁用。",
            )
        return routed

    @classmethod
    async def get_embedding_detached(
        cls,
        text: str,
        *,
        session_factory=AsyncSessionLocal,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
        stage: str = "rag_embedding",
        model_id: Optional[int] = None,
    ) -> List[float]:
        """短事务解析 embedding 路由，关闭会话后再等待外部响应。"""

        async with session_factory() as session:
            service = cls(session)
            routed = await service._resolve_embedding_route(
                user_id=user_id,
                stage=stage,
                model_id=model_id,
            )
        return await service._get_embedding_with_route(
            text,
            routed=routed,
            user_id=user_id,
            model=model,
        )

    @classmethod
    async def get_embedding_result_detached(
        cls,
        text: str,
        *,
        session_factory=AsyncSessionLocal,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
        stage: str = "rag_embedding",
        model_id: Optional[int] = None,
    ) -> AICallResult[List[float]]:
        async with session_factory() as session:
            service = cls(session)
            routed = await service._resolve_embedding_route(
                user_id=user_id,
                stage=stage,
                model_id=model_id,
            )
        return await service._get_embedding_with_route_result(
            text,
            routed=routed,
            user_id=user_id,
            model=model,
            stage=stage,
        )

    async def get_embedding(
        self,
        text: str,
        *,
        user_id: Optional[int] = None,
        model: Optional[str] = None,
        stage: str = "rag_embedding",
        model_id: Optional[int] = None,
    ) -> List[float]:
        """生成文本向量，用于章节 RAG 检索，支持 openai 与 ollama 双提供方。"""

        routed = await self._resolve_embedding_route(
            user_id=user_id,
            stage=stage,
            model_id=model_id,
        )
        return await self._get_embedding_with_route(
            text,
            routed=routed,
            user_id=user_id,
            model=model,
        )

    async def _get_embedding_with_route(
        self,
        text: str,
        *,
        routed: Dict[str, Any],
        user_id: Optional[int],
        model: Optional[str],
    ) -> List[float]:
        result = await self._get_embedding_with_route_result(
            text,
            routed=routed,
            user_id=user_id,
            model=model,
            stage=str(routed.get("stage") or "rag_embedding"),
        )
        return result.value

    async def _get_embedding_with_route_result(
        self,
        text: str,
        *,
        routed: Dict[str, Any],
        user_id: Optional[int],
        model: Optional[str],
        stage: str,
    ) -> AICallResult[List[float]]:
        """使用已解析的纯数据路由执行 embedding 网络调用。"""

        usage = TokenUsage()

        def result(value: List[float]) -> AICallResult[List[float]]:
            return AICallResult.from_config(
                value,
                config=routed,
                usage=usage,
                stage=stage,
            )

        user_embedding_model = routed["model"]
        user_embedding_base_url = routed.get("base_url")
        user_embedding_api_key = routed.get("api_key")
        user_llm_base_url = user_embedding_base_url
        user_llm_api_key = user_embedding_api_key
        user_embedding_provider_format = (
            "ollama" if routed.get("provider_type") == "ollama" else "openai"
        )

        provider = (
            user_embedding_provider_format
            if user_embedding_provider_format in {"openai", "ollama"}
            else "openai"
        )

        if provider not in {"openai", "ollama"}:
            logger.error("非法 embedding.provider 配置: %s", provider)
            raise HTTPException(
                status_code=500, detail="embedding.provider 仅支持 openai 或 ollama"
            )
        target_model = model or user_embedding_model
        if not target_model:
            logger.warning("用户 %s 未配置用户级向量模型", user_id)
            raise HTTPException(
                status_code=400,
                detail="请先在模型设置中补全用户级向量模型配置：向量 Model。系统默认向量配置已禁用。",
            )

        if provider == "ollama":
            if OllamaAsyncClient is None:
                logger.error("未安装 ollama 依赖，无法调用本地嵌入模型。")
                raise HTTPException(
                    status_code=500, detail="缺少 Ollama 依赖，请先安装 ollama 包。"
                )

            raw_base_url = user_embedding_base_url or user_llm_base_url
            if not raw_base_url:
                logger.warning("用户 %s 未配置用户级向量 API URL", user_id)
                raise HTTPException(
                    status_code=400,
                    detail="请先在模型设置中补全用户级向量模型配置：向量 API URL，或启用复用主模型 API URL。系统默认向量配置已禁用。",
                )
            base_url = self._normalize_ollama_host(raw_base_url)
            if raw_base_url and raw_base_url != base_url:
                logger.warning(
                    "检测到 Ollama 地址包含 OpenAI 风格路径，已自动修正: raw=%s normalized=%s",
                    raw_base_url,
                    base_url,
                )
            client = OllamaAsyncClient(host=base_url)
            embedding = await self._request_ollama_embedding(
                client,
                model=target_model,
                text=text,
                base_url=base_url,
            )
            if not embedding:
                return result([])
        else:
            api_key = user_embedding_api_key or user_llm_api_key
            base_url = user_embedding_base_url or user_llm_base_url
            if not base_url:
                logger.warning("用户 %s 未配置用户级向量 API URL", user_id)
                raise HTTPException(
                    status_code=400,
                    detail="请先在模型设置中补全用户级向量模型配置：向量 API URL，或启用复用主模型 API URL。系统默认向量配置已禁用。",
                )
            try:
                assert_safe_base_url(base_url, allow_private=settings.allow_private_llm_endpoints)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if api_key:
                client = AsyncOpenAI(api_key=api_key, base_url=base_url)
                try:
                    response = await client.embeddings.create(
                        input=text,
                        model=target_model,
                    )
                except Exception as exc:  # pragma: no cover - 网络或鉴权失败
                    logger.error(
                        "OpenAI 嵌入请求失败: model=%s base_url=%s user_id=%s error=%s",
                        target_model,
                        base_url,
                        user_id,
                        exc,
                        exc_info=True,
                    )
                    return result([])
                finally:
                    await client.close()
                if not response.data:
                    logger.warning(
                        "OpenAI 嵌入请求返回空数据: model=%s user_id=%s", target_model, user_id
                    )
                    return result([])
                embedding = response.data[0].embedding
                if getattr(response, "usage", None) is not None:
                    usage = normalize_openai_embedding_usage(response.usage)
            else:
                endpoint = self._normalize_openai_embeddings_url(base_url)
                if not endpoint:
                    logger.error("OpenAI 嵌入请求失败: 未配置可用 base_url，且未提供 API Key")
                    return result([])
                try:
                    async with httpx.AsyncClient(timeout=30.0) as client:
                        response = await client.post(
                            endpoint,
                            json={"input": text, "model": target_model},
                            headers={"Content-Type": "application/json"},
                        )
                        response.raise_for_status()
                        payload = response.json()
                except Exception as exc:  # pragma: no cover - 网络或协议失败
                    logger.error(
                        "OpenAI 无 Key 嵌入请求失败: model=%s endpoint=%s user_id=%s error=%s",
                        target_model,
                        endpoint,
                        user_id,
                        exc,
                        exc_info=True,
                    )
                    return result([])

                data = payload.get("data") if isinstance(payload, dict) else None
                if not data:
                    logger.warning(
                        "OpenAI 无 Key 嵌入请求返回空数据: model=%s endpoint=%s",
                        target_model,
                        endpoint,
                    )
                    return result([])
                first = data[0] if isinstance(data, list) else None
                if not isinstance(first, dict) or "embedding" not in first:
                    logger.warning(
                        "OpenAI 无 Key 嵌入响应结构异常: model=%s endpoint=%s",
                        target_model,
                        endpoint,
                    )
                    return result([])
                embedding = first["embedding"]
                raw_usage = payload.get("usage") if isinstance(payload, dict) else None
                if raw_usage is not None:
                    usage = normalize_openai_embedding_usage(raw_usage)

        if not isinstance(embedding, list):
            embedding = list(embedding)

        return result(embedding)

    async def _get_config_value(self, key: str) -> Optional[str]:
        record = await self.system_config_repo.get_by_key(key)
        if record:
            return record.value
        # 兼容环境变量，首次迁移时无需立即写入数据库
        env_key = key.upper().replace(".", "_")
        return os.getenv(env_key)
