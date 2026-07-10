import base64
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
            base_url="https://api.example.com/v1",
            api_key_encrypted="secret-key",
            is_enabled=True,
        ),
    )


class FakeAsyncClient:
    response = None
    request = None

    def __init__(self, *, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    async def post(self, url, *, headers, json):
        type(self).request = {"url": url, "headers": headers, "json": json, "timeout": self.timeout}
        if isinstance(type(self).response, Exception):
            raise type(self).response
        return type(self).response

    def stream(self, method, url, *, headers, json):
        type(self).request = {
            "method": method,
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": self.timeout,
        }
        return FakeResponseStream(type(self).response)


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
    encoded = base64.b64encode(b"RIFF\x00\x00\x00\x00WAVEdata").decode("ascii")
    FakeAsyncClient.response = httpx.Response(
        200,
        json={"choices": [{"message": {"audio": {"data": encoded}}}]},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model(speed=1.2)))

    result = await service.synthesize(7, "第一段正文")

    assert result.content == b"RIFF\x00\x00\x00\x00WAVEdata"
    assert result.media_type == "audio/wav"
    assert FakeAsyncClient.request["url"] == "https://api.example.com/v1/chat/completions"
    payload = FakeAsyncClient.request["json"]
    assert payload["audio"] == {"format": "wav", "voice": "白桦"}
    assert payload["messages"][-1] == {"role": "assistant", "content": "第一段正文"}
    assert "1.2" in payload["messages"][0]["content"]
    assert FakeAsyncClient.request["headers"]["Authorization"] == "Bearer secret-key"


@pytest.mark.asyncio
async def test_openai_speech_synthesis_returns_binary_audio(monkeypatch):
    FakeAsyncClient.response = httpx.Response(
        200,
        content=b"ID3mp3-data",
        headers={"content-type": "audio/mpeg"},
        request=httpx.Request("POST", "https://api.example.com/v1/audio/speech"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_default_tts=AsyncMock(return_value=_model(protocol="openai_speech", speed=0.9))
    )

    result = await service.synthesize(7, "第二段正文")

    assert result.content == b"ID3mp3-data"
    assert result.media_type == "audio/mpeg"
    assert FakeAsyncClient.request["url"] == "https://api.example.com/v1/audio/speech"
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
async def test_synthesis_rejects_empty_or_invalid_audio(monkeypatch):
    FakeAsyncClient.response = httpx.Response(
        200,
        json={"choices": [{"message": {"audio": {"data": ""}}}]},
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
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
    request = httpx.Request("POST", "https://api.example.com/v1/audio")
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
        request=httpx.Request("POST", "https://api.example.com/v1/chat/completions"),
    )
    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = TTSService(AsyncMock())
    service.model_repo = SimpleNamespace(get_default_tts=AsyncMock(return_value=_model()))

    with pytest.raises(TTSUpstreamError, match="响应过大"):
        await service.synthesize(7, "正文")
