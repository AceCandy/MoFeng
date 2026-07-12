from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.api.routers.tts import synthesize_speech
from app.schemas.tts import SpeechRequest
from app.services.tts_service import SpeechAudio, TTSConfigurationError, TTSUpstreamError


@pytest.mark.asyncio
async def test_tts_router_returns_raw_audio_response():
    service = SimpleNamespace(
        synthesize=AsyncMock(return_value=SpeechAudio(content=b"wave", media_type="audio/wav"))
    )

    response = await synthesize_speech(
        SpeechRequest(text="正文"),
        service=service,
        current_user=SimpleNamespace(id=7),
    )

    assert response.body == b"wave"
    assert response.media_type == "audio/wav"
    service.synthesize.assert_awaited_once_with(7, "正文", None, None)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (TTSConfigurationError("未配置默认语音朗读模型"), 409),
        (TTSUpstreamError("语音模型调用失败"), 502),
        (TimeoutError("语音模型响应超时"), 504),
    ],
)
async def test_tts_router_maps_service_errors(error, status_code):
    service = SimpleNamespace(synthesize=AsyncMock(side_effect=error))

    with pytest.raises(Exception) as exc_info:
        await synthesize_speech(
            SpeechRequest(text="正文"),
            service=service,
            current_user=SimpleNamespace(id=7),
        )

    assert exc_info.value.status_code == status_code
    assert "secret" not in str(exc_info.value.detail)


def test_speech_request_rejects_empty_and_oversized_text():
    with pytest.raises(ValueError):
        SpeechRequest(text="")

    with pytest.raises(ValueError):
        SpeechRequest(text="字" * 2501)
