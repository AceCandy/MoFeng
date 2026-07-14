# AIMETA P=TTS合成服务_用户默认模型调用|R=MiMo与OpenAI语音协议|NR=不含播放与持久化|E=TTSService|X=internal|A=服务类|D=httpx,sqlalchemy|S=db,net|RD=./README.ai
import base64
import binascii
import json
import logging
import struct
from dataclasses import dataclass
from typing import Optional

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.crypto import decrypt
from ..core.ssrf import assert_safe_base_url
from ..repositories.ai_model_config_repository import UserAIModelRepository


logger = logging.getLogger(__name__)


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
    # 有效 wav 最小字节数：仅 wav 头（约 44 字节）而无 PCM 数据视为空音频
    MIN_AUDIO_BYTES = 1000

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
        try:
            assert_safe_base_url(provider.base_url, allow_private=settings.allow_private_llm_endpoints)
        except ValueError as exc:
            raise TTSConfigurationError(str(exc)) from exc
        if not provider.api_key_encrypted or not model.tts_protocol:
            raise TTSConfigurationError("默认语音朗读模型配置不完整")
        # 音色/倍速优先用运行时传入（朗读控件的全局偏好），缺省回退模型配置
        effective_voice = (voice or model.tts_voice or "").strip()
        if not effective_voice:
            raise TTSConfigurationError("未选择语音朗读音色")
        effective_speed = speed if speed is not None else float(model.tts_speed or 1.0)

        if model.tts_protocol == "mimo_chat_audio":
            return await self._synthesize_mimo(model, text, effective_voice)
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

    @classmethod
    def _is_valid_wav(cls, audio: bytes) -> bool:
        # 既校验 wav 头与最小字节数，又校验 data chunk 完整性，并拒绝"完整但静音"的音频
        if not cls._is_wav(audio) or len(audio) < cls.MIN_AUDIO_BYTES:
            return False
        if not cls._wav_data_complete(audio):
            return False
        return cls._wav_has_signal(audio)

    @staticmethod
    def _wav_data_complete(audio: bytes) -> bool:
        offset = 12  # 跳过 "RIFF" + size + "WAVE" 头
        while offset + 8 <= len(audio):
            chunk_id = audio[offset:offset + 4]
            chunk_size = int.from_bytes(audio[offset + 4:offset + 8], "little")
            if chunk_id == b"data":
                return len(audio) >= offset + 8 + chunk_size
            offset += 8 + chunk_size + (chunk_size & 1)  # 奇数大小需补 1 字节 padding
            if chunk_size == 0:
                break
        return False

    @staticmethod
    def _wav_has_signal(audio: bytes) -> bool:
        # 拦截"完整但静音"的音频：定位 data chunk，存在非零样本才算有效
        offset = 12
        while offset + 8 <= len(audio):
            chunk_id = audio[offset:offset + 4]
            chunk_size = int.from_bytes(audio[offset + 4:offset + 8], "little")
            if chunk_id == b"data":
                return any(audio[offset + 8:offset + 8 + chunk_size])
            offset += 8 + chunk_size + (chunk_size & 1)
        return False

    @classmethod
    def _normalize_to_pcm16_wav(cls, audio: bytes) -> bytes:
        """标准化为 16-bit PCM wav：解析 fmt/data，PCM 转 16-bit，重写标准 wav。
        MiMo 偶发返回浏览器 <audio> 无法播放的 wav（24/32-bit 或非标准 chunk），
        统一重写为标准 16-bit PCM 后 <audio> 才能正常播放。"""
        audio_format = 1
        num_channels = 1
        sample_rate = 24000
        bits_per_sample = 16
        pcm = b""
        offset = 12
        while offset + 8 <= len(audio):
            chunk_id = audio[offset:offset + 4]
            chunk_size = int.from_bytes(audio[offset + 4:offset + 8], "little")
            body = offset + 8
            if chunk_id == b"fmt " and chunk_size >= 16:
                audio_format = int.from_bytes(audio[body:body + 2], "little") or 1
                num_channels = int.from_bytes(audio[body + 2:body + 4], "little") or 1
                sample_rate = int.from_bytes(audio[body + 4:body + 8], "little") or 24000
                bits_per_sample = int.from_bytes(audio[body + 14:body + 16], "little") or 16
            elif chunk_id == b"data":
                pcm = audio[body:body + chunk_size]
            offset += 8 + chunk_size + (chunk_size & 1)
        if not pcm:
            return audio
        pcm16 = cls._pcm_to_16bit(pcm, audio_format, bits_per_sample)
        if audio_format != 1 or bits_per_sample != 16:
            logger.info(
                "MiMo wav 标准化为 pcm16: format=%d channels=%d rate=%d bits=%d",
                audio_format, num_channels, sample_rate, bits_per_sample,
            )
        byte_rate = sample_rate * num_channels * 2
        block_align = num_channels * 2
        fmt_body = struct.pack("<HHIIHH", 1, num_channels, sample_rate, byte_rate, block_align, 16)
        return (
            b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt_body) + 8 + len(pcm16)) + b"WAVE"
            + b"fmt " + struct.pack("<I", len(fmt_body)) + fmt_body
            + b"data" + struct.pack("<I", len(pcm16)) + pcm16
        )

    @staticmethod
    def _pcm_to_16bit(pcm: bytes, audio_format: int, bits_per_sample: int) -> bytes:
        """把 PCM 数据转成 16-bit 有符号小端。"""
        if audio_format == 3 and bits_per_sample == 32:
            # IEEE float32 → 16-bit PCM
            out = bytearray()
            for i in range(0, len(pcm) - 3, 4):
                val = struct.unpack("<f", pcm[i:i + 4])[0]
                clamped = -1.0 if val < -1.0 else (1.0 if val > 1.0 else val)
                out += int(clamped * 32767).to_bytes(2, "little", signed=True)
            return bytes(out)
        if bits_per_sample == 16:
            return pcm[: len(pcm) // 2 * 2]
        if bits_per_sample == 8:
            # 8-bit unsigned (0-255) → 16-bit signed
            out = bytearray()
            for sample in pcm:
                out += ((sample - 128) << 8).to_bytes(2, "little", signed=True)
            return bytes(out)
        if bits_per_sample == 24:
            # 24-bit signed → 16-bit signed（右移 8 位）
            out = bytearray()
            for i in range(0, len(pcm) - 2, 3):
                val = int.from_bytes(pcm[i:i + 3], "little", signed=True)
                out += (val >> 8).to_bytes(2, "little", signed=True)
            return bytes(out)
        if bits_per_sample == 32:
            # 32-bit signed → 16-bit signed（右移 16 位）
            out = bytearray()
            for i in range(0, len(pcm) - 3, 4):
                val = int.from_bytes(pcm[i:i + 4], "little", signed=True)
                out += (val >> 16).to_bytes(2, "little", signed=True)
            return bytes(out)
        return pcm[: len(pcm) // 2 * 2]

    async def _synthesize_mimo(self, model, text: str, voice: str) -> SpeechAudio:
        # MiMo TTS 契约：语气指令放 user 消息、待朗读原文放 assistant 消息；
        # 该端点不接受 system 角色（上游返回 4xx）。
        messages = [
            {
                "role": "user",
                "content": (
                    "你是一位顶级有声书演播艺术家。请朗读提供的文本：\n"
                    "1. 感情饱满，语调随情节起伏——紧张处提速上扬，舒缓处放慢沉静；\n"
                    "2. 区分旁白与对白：旁白叙述有温度，对白贴合角色情绪与性格；\n"
                    "3. 善用停顿、气息与重音制造戏剧张力。"
                ),
            },
            {"role": "assistant", "content": text},
        ]
        payload = {
            "model": model.model_name,
            "messages": messages,
            "audio": {"format": "wav", "voice": voice},
        }
        url = f"{model.provider.base_url.rstrip('/')}/chat/completions"
        headers = self._headers(decrypt(model.provider.api_key_encrypted))
        try:
            # 上游偶发返回截断/空 wav（HTTP 流不完整），完整性校验不过则重试一次
            for attempt in range(2):
                async with httpx.AsyncClient(timeout=60.0) as client:
                    body, _ = await self._post_limited(client, url, headers=headers, json=payload)
                encoded = json.loads(body)["choices"][0]["message"]["audio"]["data"]
                audio = base64.b64decode(encoded, validate=True) if encoded else b""
                if len(audio) > self.MAX_AUDIO_BYTES:
                    raise TTSUpstreamError("语音模型响应过大")
                if self._is_valid_wav(audio):
                    return SpeechAudio(
                        content=self._normalize_to_pcm16_wav(audio),
                        media_type="audio/wav",
                    )
                logger.warning(
                    "MiMo 返回无效/截断音频，字节数=%d attempt=%d", len(audio), attempt + 1
                )
            raise TTSUpstreamError("语音模型未返回有效音频")
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
                    headers=self._headers(decrypt(model.provider.api_key_encrypted)),
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
