# AIMETA P=TTS合成API_当前用户语音代理|R=认证_错误映射_音频响应|NR=不含播放逻辑|E=route:POST_/api/tts/speech|X=http|A=语音代理|D=fastapi,sqlalchemy|S=net|RD=./README.ai
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.tts import SpeechRequest
from ...schemas.user import UserInDB
from ...services.tts_service import TTSConfigurationError, TTSService, TTSUpstreamError


router = APIRouter(prefix="/api/tts", tags=["Text to Speech"])


def get_tts_service(session: AsyncSession = Depends(get_session)) -> TTSService:
    return TTSService(session)


@router.post("/speech", response_class=Response)
async def synthesize_speech(
    payload: SpeechRequest,
    service: TTSService = Depends(get_tts_service),
    current_user: UserInDB = Depends(get_current_user),
) -> Response:
    try:
        audio = await service.synthesize(current_user.id, payload.text, payload.voice, payload.speed)
    except TTSConfigurationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except TimeoutError as exc:
        raise HTTPException(status_code=504, detail=str(exc)) from exc
    except TTSUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return Response(content=audio.content, media_type=audio.media_type)
