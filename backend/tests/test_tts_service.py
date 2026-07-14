import base64
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.tts_service import (
    TTSConfigurationError,
    TTSService,
    TTSUpstreamError,
)


def _model(protocol="mimo_chat_audio", speed=1.0):
    return SimpleNamespace(
        model_name="mimo-v2.5-tts",
        capabilities_json={"tts": True},
        is_enabled=True,
        is_default_tts=True,
        tts_protocol=protocol,
        tts_voice="白桦" if protocol == "mimo_chat_audio" else "alloy",
        tts_speed=speed,
        provider=SimpleNamespace(
            base_url="http://127.0.0.1:8000/v1",
            api_key_encrypted="secret-key",
            is_enabled=True,
        ),
    )


def _make_wav(pcm: bytes = b"\x01\x00" * 500) -> bytes:
    """构造最小有效 wav（16-bit mono 24kHz PCM）；pcm 默认非零（有声），传全零可模拟静音。"""
    fmt_body = struct.pack("<HHIIHH", 1, 1, 24000, 48000, 2, 16)
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt_body)) + fmt_body
    data_chunk = b"data" + struct.pack("<I", len(pcm)) + pcm
    riff_size = 4 + len(fmt_chunk) + len(data_chunk)
    return b"RIFF" + struct.pack("<I", riff_size) + b"WAVE" + fmt_chunk + data_chunk


def _make_wav_raw(pcm: bytes, bits: int = 16, *, audio_format: int = 1, channels: int = 1, rate: int = 24000) -> bytes:
    """构造指定位深/格式的 wav（用于测试标准化）。"""
    block_align = channels * (bits // 8)
    byte_rate = rate * block_align
    fmt_body = struct.pack("<HHIIHH", audio_format, channels, rate, byte_rate, block_align, bits)
    return (
        b"RIFF" + struct.pack("<I", 4 + 8 + len(fmt_body) + 8 + len(pcm)) + b"WAVE"
        + b"fmt " + struct.pack("<I", len(fmt_body)) + fmt_body
        + b"data" + struct.pack("<I", len(pcm)) + pcm
    )


def _read_bits_per_sample(wav: bytes) -> int:
    offset = 12
    while offset + 8 <= len(wav):
        chunk_id = wav[offset:offset + 4]
        chunk_size = int.from_bytes(wav[offset + 4:offset + 8], "little")
        if chunk_id == b"fmt " and chunk_size >= 16:
            return int.from_bytes(wav[offset + 8 + 14:offset + 8 + 16], "little")
        offset += 8 + chunk_size + (chunk_size & 1)
    return 0


class FakeAsyncClient:
    response = None
    # 可选：按调用顺序的响应序列（优先于 response）；用尽或为空时回退 response。用于重试场景
    responses = None
    request = None

    def __init__(self, *, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def _next(self):
        if type(self).responses:
            return type(self).responses.pop(0)
        return type(self).response

    async def post(self, url, *, headers, json):
        type(self).request = {"url": url, "headers": headers, "json": json, "timeout": self.timeout}
        resp = self._next()
        if isinstance(resp, Exception):
            raise resp
        return resp

    def stream(self, method, url, *, headers, json):
        type(self).request = {
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": self.timeout,
        }
        return FakeResponseStream(self._next())


class FakeResponseStream:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    async def __aexit__(self, exc_type, exc, traceback):
        return False


@pytest.mark.asyncio
async def test_mimo_synthesis_uses_chat_audio_contract(monkeypatch):
    wav = _make_wav()
    encoded = base64.b64encode(wav).decode("ascii")
    FakeAsyncClient.response = httpx.Response(
        200,
        json={"choices": [{"message": {"audio": {"data": encoded}}}]},
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/chat/completions"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model(speed=1.2)))

    result = await service.synthesize(7, "第一段正文")

    assert result.content == wav
    assert result.media_type == "audio/wav"
    assert FakeAsyncClient.request["url"] == "http://127.0.0.1:8000/v1/chat/completions"
    payload = FakeAsyncClient.request["json"]
    assert payload["audio"] == {"format": "wav", "voice": "白桦"}
    assert payload["messages"][0]["role"] == "user"
    assert "有声书演播" in payload["messages"][0]["content"]
    assert payload["messages"][-1] == {"role": "assistant", "content": "第一段正文"}
    assert FakeAsyncClient.request["headers"]["Authorization"] == "Bearer secret-key"


@pytest.mark.asyncio
async def test_openai_speech_synthesis_returns_binary_audio(monkeypatch):
    FakeAsyncClient.response = httpx.Response(
        200,
        content=b"ID3mp3-data",
        headers={"content-type": "audio/mpeg"},
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/audio/speech"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_default_tts=AsyncMock(return_value=_model(protocol="openai_speech", speed=0.9))
    )

    result = await service.synthesize(7, "第二段正文")

    assert result.content == b"ID3mp3-data"
    assert result.media_type == "audio/mpeg"
    assert FakeAsyncClient.request["url"] == "http://127.0.0.1:8000/v1/audio/speech"
    assert FakeAsyncClient.request["json"] == {
        "model": "mimo-v2.5-tts",
        "input": "第二段正文",
        "voice": "alloy",
        "speed": 0.9,
        "response_format": "mp3",
    }


@pytest.mark.asyncio
async def test_synthesis_rejects_missing_default_configuration():
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=None))

    with pytest.raises(TTSConfigurationError, match="未配置默认语音朗读模型"):
        await service.synthesize(7, "正文")


@pytest.mark.asyncio
async def test_synthesis_rejects_invalid_model_or_provider():
    service = TTSService(AsyncMock())
    invalid = _model()
    invalid.provider.is_enabled = False
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=invalid))

    with pytest.raises(TTSConfigurationError, match="不可用"):
        await service.synthesize(7, "正文")


@pytest.mark.asyncio
async def test_synthesis_maps_timeout_without_exposing_upstream(monkeypatch):
    FakeAsyncClient.response = httpx.ReadTimeout("upstream secret timeout")
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model()))

    with pytest.raises(TimeoutError, match="语音模型响应超时"):
        await service.synthesize(7, "不能写入日志的正文")


@pytest.mark.asyncio
async def test_mimo_synthesis_retries_after_timeout_then_succeeds(monkeypatch):
    # 首次上游超时、第二次成功：验证超时已纳入重试范围（原逻辑超时直接抛出不重试）
    wav = _make_wav()
    encoded = base64.b64encode(wav).decode("ascii")
    success = httpx.Response(
        200,
        json={"choices": [{"message": {"audio": {"data": encoded}}}]},
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/chat/completions"),
    )
    FakeAsyncClient.responses = [httpx.ReadTimeout("first attempt slow"), success]
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model()))

    result = await service.synthesize(7, "正文")

    assert result.content == wav
    assert result.media_type == "audio/wav"


@pytest.mark.asyncio
async def test_openai_synthesis_retries_after_timeout_then_succeeds(monkeypatch):
    success = httpx.Response(
        200,
        content=b"ID3mp3-data",
        headers={"content-type": "audio/mpeg"},
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/audio/speech"),
    )
    FakeAsyncClient.responses = [httpx.ReadTimeout("first attempt slow"), success]
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_default_tts=AsyncMock(return_value=_model(protocol="openai_speech"))
    )

    result = await service.synthesize(7, "正文")

    assert result.content == b"ID3mp3-data"
    assert result.media_type == "audio/mpeg"


@pytest.mark.asyncio
async def test_synthesis_rejects_empty_or_invalid_audio(monkeypatch):
    FakeAsyncClient.response = httpx.Response(
        200,
        json={"choices": [{"message": {"audio": {"data": ""}}}]},
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/chat/completions"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model()))

    with pytest.raises(TTSUpstreamError, match="未返回有效音频"):
        await service.synthesize(7, "正文")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("protocol", "content", "headers"),
    [
        (
            "mimo_chat_audio",
            {"choices": [{"message": {"audio": {"data": base64.b64encode(b"not-wav").decode("ascii")}}}]},
            {},
        ),
        ("openai_speech", b"not-mp3", {"content-type": "audio/mpeg"}),
    ],
)
async def test_synthesis_rejects_invalid_audio_format(monkeypatch, protocol, content, headers):
    request = httpx.Request("POST", "http://127.0.0.1:8000/v1/audio")
    FakeAsyncClient.response = (
        httpx.Response(200, json=content, headers=headers, request=request)
        if isinstance(content, dict)
        else httpx.Response(200, content=content, headers=headers, request=request)
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_default_tts=AsyncMock(return_value=_model(protocol=protocol))
    )

    with pytest.raises(TTSUpstreamError, match="未返回有效音频"):
        await service.synthesize(7, "正文")


@pytest.mark.asyncio
async def test_synthesis_rejects_oversized_upstream_response(monkeypatch):
    encoded = base64.b64encode(b"RIFF\x00\x00\x00\x00WAVEdata").decode("ascii")
    FakeAsyncClient.response = httpx.Response(
        200,
        json={"choices": [{"message": {"audio": {"data": encoded}}}]},
        headers={"content-length": str(TTSService.MAX_UPSTREAM_RESPONSE_BYTES + 1)},
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/chat/completions"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model()))

    with pytest.raises(TTSUpstreamError, match="响应过大"):
        await service.synthesize(7, "正文")


def test_wav_validation_rejects_silent_and_truncated():
    # 有效 wav（有声、完整）通过
    assert TTSService._is_valid_wav(_make_wav()) is True
    # 完整但静音（PCM 全零）→ 拒绝
    assert TTSService._is_valid_wav(_make_wav(pcm=b"\x00" * 1000)) is False
    # data chunk 被截断（实际数据少于声明，总长仍达标）→ 拒绝
    big = _make_wav(pcm=b"\x01\x00" * 600)
    assert TTSService._is_valid_wav(big[:-200]) is False


@pytest.mark.asyncio
async def test_synthesis_rejects_silent_wav_after_retry(monkeypatch):
    # 上游偶发返回"完整但静音"的 wav：校验失败 → 重试一次 → 仍静音 → 报错（前端走浏览器兜底）
    silent = _make_wav(pcm=b"\x00" * 1000)
    encoded = base64.b64encode(silent).decode("ascii")
    FakeAsyncClient.response = httpx.Response(
        200,
        json={"choices": [{"message": {"audio": {"data": encoded}}}]},
        request=httpx.Request("POST", "http://127.0.0.1:8000/v1/chat/completions"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model()))

    with pytest.raises(TTSUpstreamError, match="未返回有效音频"):
        await service.synthesize(7, "正文")


def test_normalize_wav_converts_high_bit_depth_to_pcm16():
    # 24-bit wav → 16-bit PCM（非零样本，过静音检测；pcm 足够大以过最小字节校验）
    wav24 = _make_wav_raw(b"\x00\x01\x02" * 500, bits=24)
    normalized = TTSService._normalize_to_pcm16_wav(wav24)
    assert TTSService._is_valid_wav(normalized)
    assert _read_bits_per_sample(normalized) == 16

    # 32-bit wav → 16-bit PCM
    wav32 = _make_wav_raw(b"\x00\x01\x02\x03" * 750, bits=32)
    normalized32 = TTSService._normalize_to_pcm16_wav(wav32)
    assert TTSService._is_valid_wav(normalized32)
    assert _read_bits_per_sample(normalized32) == 16

    # 16-bit 标准输入透传后仍是有效 16-bit wav
    assert _read_bits_per_sample(TTSService._normalize_to_pcm16_wav(_make_wav())) == 16
