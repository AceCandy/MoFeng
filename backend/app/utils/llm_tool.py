# -*- coding: utf-8 -*-
# AIMETA P=LLM工具_大模型调用辅助|R=请求构建_响应解析|NR=不含业务逻辑|E=LLMTool|X=internal|A=工具类|D=httpx|S=net|RD=./README.ai
"""LLM 工具封装，支持 OpenAI 兼容与 Anthropic Messages API。"""

import json
import os
from dataclasses import asdict, dataclass
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx
from openai import AsyncOpenAI

from .ai_telemetry import normalize_anthropic_usage, normalize_openai_usage


@dataclass
class ChatMessage:
    role: str
    content: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


class LLMClient:
    """异步流式调用封装，按供应商类型选择协议。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        provider_type: Optional[str] = None,
    ):
        self._provider_type = (provider_type or "openai_compatible").strip().lower()
        if self._provider_type == "anthropic":
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            self._base_url = base_url or os.environ.get("ANTHROPIC_API_BASE") or "https://api.anthropic.com/v1"
        else:
            key = api_key or os.environ.get("OPENAI_API_KEY")
            self._base_url = base_url or os.environ.get("OPENAI_API_BASE")
        if not key:
            raise ValueError("缺少 API Key 配置，请在数据库或环境变量中补全。")

        self._api_key = key
        self._client = None
        if self._provider_type != "anthropic":
            # 重试统一交给 LLMService 控制，避免 SDK 隐式重试叠加导致等待时间不可控。
            self._client = AsyncOpenAI(api_key=key, base_url=self._base_url, max_retries=0)

    @staticmethod
    def _anthropic_messages_url(base_url: Optional[str]) -> str:
        trimmed = (base_url or "https://api.anthropic.com/v1").strip().rstrip("/")
        lowered = trimmed.lower()
        if lowered.endswith("/messages"):
            return trimmed
        if lowered.endswith("/v1"):
            return f"{trimmed}/messages"
        return f"{trimmed}/v1/messages"

    @staticmethod
    def _to_anthropic_payload(
        messages: List[ChatMessage],
        *,
        model: Optional[str],
        temperature: Optional[float],
        top_p: Optional[float],
        max_tokens: Optional[int],
    ) -> Dict[str, object]:
        system_parts: List[str] = []
        anthropic_messages: List[Dict[str, str]] = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            role = message.role if message.role in {"user", "assistant"} else "user"
            anthropic_messages.append({"role": role, "content": message.content})

        payload: Dict[str, object] = {
            "model": model or os.environ.get("MODEL", "claude-3-5-sonnet-20241022"),
            "messages": anthropic_messages,
            "stream": True,
            "max_tokens": max_tokens or 4096,
        }
        if system_parts:
            # Anthropic 将 system prompt 放在顶层字段，不作为 message role 发送。
            payload["system"] = "\n\n".join(system_parts)
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        return payload

    async def _stream_anthropic_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str],
        temperature: Optional[float],
        top_p: Optional[float],
        max_tokens: Optional[int],
        timeout: int,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        url = self._anthropic_messages_url(self._base_url)
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }
        payload = self._to_anthropic_payload(
            messages,
            model=model,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )

        cumulative_usage: Dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    line = raw_line.strip()
                    if not line.startswith("data:"):
                        continue
                    data = line.removeprefix("data:").strip()
                    if not data or data == "[DONE]":
                        continue
                    event = json.loads(data)
                    event_type = event.get("type")
                    if event_type == "message_start":
                        message = event.get("message") or {}
                        usage = message.get("usage") or {}
                        if isinstance(usage, dict):
                            cumulative_usage.update(usage)
                            yield {
                                "content": None,
                                "finish_reason": None,
                                "usage": normalize_anthropic_usage(cumulative_usage).to_dict(),
                            }
                    elif event_type == "content_block_delta":
                        delta = event.get("delta") or {}
                        text = delta.get("text")
                        if text:
                            yield {"content": text, "finish_reason": None}
                    elif event_type == "message_delta":
                        delta = event.get("delta") or {}
                        finish_reason = delta.get("stop_reason")
                        usage = event.get("usage") or {}
                        normalized_usage = None
                        if isinstance(usage, dict) and usage:
                            cumulative_usage.update(usage)
                            normalized_usage = normalize_anthropic_usage(cumulative_usage).to_dict()
                        if finish_reason or normalized_usage is not None:
                            chunk: Dict[str, Any] = {
                                "content": None,
                                "finish_reason": finish_reason,
                            }
                            if normalized_usage is not None:
                                chunk["usage"] = normalized_usage
                            yield chunk
                    elif event_type == "error":
                        error = event.get("error") or {}
                        raise RuntimeError(error.get("message") or "Anthropic API error")

    async def stream_chat(
        self,
        messages: List[ChatMessage],
        model: Optional[str] = None,
        response_format: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: int = 120,
        **kwargs,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if self._provider_type == "anthropic":
            async for chunk in self._stream_anthropic_chat(
                messages=messages,
                model=model,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
                timeout=timeout,
            ):
                yield chunk
            return

        payload = {
            "model": model or os.environ.get("MODEL", "gpt-3.5-turbo"),
            "messages": [msg.to_dict() for msg in messages],
            "stream": True,
            "timeout": timeout,
            "stream_options": {"include_usage": True},
            **kwargs,
        }
        if response_format:
            payload["response_format"] = {"type": response_format}
        if temperature is not None:
            payload["temperature"] = temperature
        if top_p is not None:
            payload["top_p"] = top_p
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens

        stream = await self._client.chat.completions.create(**payload)
        async for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if not chunk.choices:
                if usage is not None:
                    yield {
                        "content": None,
                        "finish_reason": None,
                        "usage": normalize_openai_usage(usage).to_dict(),
                    }
                continue
            choice = chunk.choices[0]
            if not choice.delta and usage is None:
                continue
            result: Dict[str, Any] = {
                "content": choice.delta.content if choice.delta else None,
                "finish_reason": choice.finish_reason,
            }
            if usage is not None:
                result["usage"] = normalize_openai_usage(usage).to_dict()
            yield result

    async def aclose(self) -> None:
        """关闭底层 AsyncOpenAI 客户端，释放连接池。"""
        if self._client is not None:
            await self._client.close()
            self._client = None
