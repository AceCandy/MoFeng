# AIMETA P=TTS合成服务_用户默认模型调用|R=MiMo与OpenAI语音协议|NR=不含播放与持久化|E=TTSService|X=internal|A=服务类|D=httpx,sqlalchemy|S=db,net|RD=./README.ai
import base64
import binascii
import json
from dataclasses import dataclass
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..repositories.ai_model_config_repository import UserAIModelRepository


class TTSConfigurationError(ValueError):
    """当前用户的语音朗读配置不可用。"""


class TTSUpstreamError(RuntimeError):
    """上游语音服务没有返回可播放音频。"""


@dataclass(frozen=True)
class SpeechAudio:
    content: bytes
    media_type: str


class TTSService:
    """使用当前用户唯一默认 TTS 模型合成单段语音。"""

    MAX_AUDIO_BYTES = 24 * 1024 * 1024
    MAX_UPSTREAM_RESPONSE_BYTES = 32 * 1024 * 1024

    def __init__(self, session: AsyncSession):
        self.model_repo = UserAIModelRepository(session)

    async def synthesize(
        self,
        user_id: int,
        text: str,
        voice: Optional[str] = None,
        speed: Optional[float] = None,
    ) -> SpeechAudio:
        model = await self.model_repo.get_default_tts(user_id)
        if not model:
            raise TTSConfigurationError("未配置默认语音朗读模型")
        provider = getattr(model, "provider", None)
        if (
            not model.is_enabled
            or not (model.capabilities_json or {}).get("tts")
            or not provider
            or not provider.is_enabled
        ):
            raise TTSConfigurationError("默认语音朗读模型不可用")
        if not provider.api_key_encrypted or not model.tts_protocol:
            raise TTSConfigurationError("默认语音朗读模型配置不完整")
        # 音色/倍速优先用运行时传入（朗读控件的全局偏好），缺省回退模型配置
        effective_voice = (voice or model.tts_voice or "").strip()
        if not effective_voice:
            raise TTSConfigurationError("未选择语音朗读音色")
        effective_speed = speed if speed is not None else float(model.tts_speed or 1.0)

        if model.tts_protocol == "mimo_chat_audio":
            return await self._synthesize_mimo(model, text, effective_voice, effective_speed)
        if model.tts_protocol == "openai_speech":
            return await self._synthesize_openai(model, text, effective_voice, effective_speed)
        raise TTSConfigurationError("默认语音朗读模型协议不受支持")

    @staticmethod
    def _headers(api_key: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    @classmethod
    async def _post_limited(cls, client: httpx.AsyncClient, url: str, **kwargs) -> tuple[bytes, str]:
        async with client.stream("POST", url, **kwargs) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > cls.MAX_UPSTREAM_RESPONSE_BYTES:
                raise TTSUpstreamError("语音模型响应过大")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(body) + len(chunk) > cls.MAX_UPSTREAM_RESPONSE_BYTES:
                    raise TTSUpstreamError("语音模型响应过大")
                body.extend(chunk)
            media_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
        return bytes(body), media_type

    @staticmethod
    def _is_wav(content: bytes) -> bool:
        return len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WAVE"

    @staticmethod
    def _is_mp3(content: bytes) -> bool:
        return content.startswith(b"ID3") or (
            len(content) >= 2 and content[0] == 0xFF and content[1] & 0xE0 == 0xE0
        )

    async def _synthesize_mimo(self, model, text: str, voice: str, speed: float) -> SpeechAudio:
        messages = []
        if speed != 1.0:
            messages.append(
                {"role": "user", "content": f"请以正常语速的 {speed:g} 倍朗读。"}
            )
        messages.append({"role": "assistant", "content": text})
        payload = {
            "model": model.model_name,
            "messages": messages,
            "audio": {"format": "wav", "voice": voice},
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                body, _ = await self._post_limited(
                    client,
                    f"{model.provider.base_url.rstrip('/')}/chat/completions",
                    headers=self._headers(model.provider.api_key_encrypted),
                    json=payload,
                )
            encoded = json.loads(body)["choices"][0]["message"]["audio"]["data"]
            if not encoded:
                raise TTSUpstreamError("语音模型未返回有效音频")
            audio = base64.b64decode(encoded, validate=True)
            if len(audio) > self.MAX_AUDIO_BYTES:
                raise TTSUpstreamError("语音模型响应过大")
            if not self._is_wav(audio):
                raise TTSUpstreamError("语音模型未返回有效音频")
            return SpeechAudio(content=audio, media_type="audio/wav")
        except httpx.TimeoutException as exc:
            raise TimeoutError("语音模型响应超时") from exc
        except httpx.HTTPError as exc:
            raise TTSUpstreamError("语音模型调用失败") from exc
        except TTSUpstreamError:
            raise
        except (KeyError, IndexError, TypeError, ValueError, binascii.Error) as exc:
            raise TTSUpstreamError("语音模型未返回有效音频") from exc

    async def _synthesize_openai(self, model, text: str, voice: str, speed: float) -> SpeechAudio:
        payload = {
            "model": model.model_name,
            "input": text,
            "voice": voice,
            "speed": speed,
            "response_format": "mp3",
        }
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                content, media_type = await self._post_limited(
                    client,
                    f"{model.provider.base_url.rstrip('/')}/audio/speech",
                    headers=self._headers(model.provider.api_key_encrypted),
                    json=payload,
                )
            if (
                len(content) > self.MAX_AUDIO_BYTES
                or media_type not in {"audio/mpeg", "audio/mp3"}
                or not self._is_mp3(content)
            ):
                raise TTSUpstreamError("语音模型未返回有效音频")
            return SpeechAudio(content=content, media_type="audio/mpeg")
        except httpx.TimeoutException as exc:
            raise TimeoutError("语音模型响应超时") from exc
        except httpx.HTTPError as exc:
            raise TTSUpstreamError("语音模型调用失败") from exc
