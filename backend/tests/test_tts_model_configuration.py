from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.schemas.llm_config import UserAIModelCreate
from app.schemas.llm_config import UserAIModelUpdate
from app.services.llm_config_service import LLMConfigService

ROOT = Path(__file__).resolve().parents[1]


def _tts_model_payload(**overrides):
    values = {
        "provider_id": 3,
        "display_name": "MiMo 朗读",
        "model_name": "mimo-v2.5-tts",
        "capabilities": {"chat": False, "embedding": False, "tts": True},
        "is_default_chat": False,
        "is_default_embedding": False,
        "is_default_tts": True,
        "tts_protocol": "mimo_chat_audio",
        "tts_voice": "白桦",
        "tts_speed": 1.0,
    }
    values.update(overrides)
    return values


def test_tts_model_requires_protocol_but_allows_runtime_voice():
    with pytest.raises(ValidationError):
        UserAIModelCreate(**_tts_model_payload(tts_protocol=None))

    payload = UserAIModelCreate(**_tts_model_payload(tts_voice=None))

    assert payload.tts_voice is None


@pytest.mark.parametrize("speed", [0.49, 2.01])
def test_tts_speed_must_stay_in_supported_range(speed):
    with pytest.raises(ValidationError):
        UserAIModelCreate(**_tts_model_payload(tts_speed=speed))


def test_tts_model_accepts_supported_protocol_and_configuration():
    payload = UserAIModelCreate(**_tts_model_payload())

    assert payload.tts_protocol == "mimo_chat_audio"
    assert payload.tts_voice == "白桦"
    assert payload.tts_speed == 1.0
    assert payload.is_default_tts is True


def test_capability_normalization_preserves_tts():
    assert LLMConfigService._normalize_capabilities({"tts": True}) == {
        "chat": False,
        "embedding": False,
        "tts": True,
    }


@pytest.mark.asyncio(loop_scope="session")
async def test_create_default_tts_locks_before_reading_provider():
    events = []
    session = AsyncMock()
    service = LLMConfigService(session)

    async def lock_user_configuration(user_id):
        events.append(("lock", user_id))

    async def get_owned(provider_id, user_id):
        events.append(("provider", user_id, provider_id))
        return SimpleNamespace(id=provider_id)

    async def add_model(model):
        model.id = 10
        return model

    service.model_repo = SimpleNamespace(
        lock_user_configuration=lock_user_configuration,
        add=add_model,
    )
    service.provider_repo = SimpleNamespace(get_owned=get_owned)
    service._normalize_default_flags = AsyncMock()

    await service.create_model(7, UserAIModelCreate(**_tts_model_payload()))

    assert events[:2] == [("lock", 7), ("provider", 7, 3)]


@pytest.mark.asyncio(loop_scope="session")
async def test_update_model_locks_before_reading_existing_model():
    events = []
    session = AsyncMock()
    service = LLMConfigService(session)
    model = SimpleNamespace(
        id=10,
        user_id=7,
        provider_id=3,
        display_name="MiMo 朗读",
        model_name="mimo-v2.5-tts",
        capabilities_json={"tts": True},
        context_window=None,
        is_default_chat=False,
        is_default_embedding=False,
        is_default_tts=True,
        tts_protocol="mimo_chat_audio",
        tts_voice="白桦",
        tts_speed=1.0,
        input_price_per_million=None,
        output_price_per_million=None,
        cached_input_price_per_million=None,
        cache_write_input_price_per_million=None,
        pricing_currency=None,
        is_enabled=True,
        sort_order=0,
    )

    async def lock_user_configuration(user_id):
        events.append(("lock", user_id))

    async def get_owned(model_id, user_id):
        events.append(("model", user_id, model_id))
        return model

    service.model_repo = SimpleNamespace(
        lock_user_configuration=lock_user_configuration,
        get_owned=get_owned,
    )
    service._normalize_default_flags = AsyncMock()

    await service.update_model(7, 10, UserAIModelUpdate(tts_voice="茉莉"))

    assert events[:2] == [("lock", 7), ("model", 7, 10)]


@pytest.mark.asyncio(loop_scope="session")
async def test_default_tts_model_clears_sibling_default():
    service = LLMConfigService(AsyncMock())
    selected = SimpleNamespace(
        id=10,
        capabilities_json={"tts": True},
        is_default_chat=False,
        is_default_embedding=False,
        is_default_tts=True,
        is_enabled=True,
    )
    sibling = SimpleNamespace(
        id=11,
        capabilities_json={"tts": True},
        is_default_chat=False,
        is_default_embedding=False,
        is_default_tts=True,
        is_enabled=True,
    )
    locked_models = AsyncMock(return_value=[selected, sibling])
    service.model_repo = SimpleNamespace(
        list_by_user=AsyncMock(return_value=[selected, sibling]),
        list_by_user_for_update=locked_models,
    )

    await service._normalize_default_flags(7, selected)

    assert selected.is_enabled is True
    assert sibling.is_default_tts is False
    assert sibling.is_enabled is True
    locked_models.assert_awaited_once_with(7)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_model_rejects_default_tts_model():
    service = LLMConfigService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_owned=AsyncMock(
            return_value=SimpleNamespace(
                id=10,
                model_name="mimo-v2.5-tts",
                is_default_chat=False,
                is_default_embedding=False,
                is_default_tts=True,
            )
        )
    )

    with pytest.raises(ValueError, match="语音朗读模型不能直接删除"):
        await service.delete_model(7, 10)


@pytest.mark.asyncio(loop_scope="session")
async def test_update_model_rejects_incomplete_tts_configuration():
    service = LLMConfigService(AsyncMock())
    model = SimpleNamespace(
        id=10,
        provider_id=3,
        display_name="旧模型",
        model_name="legacy-model",
        capabilities_json={"chat": True},
        context_window=None,
        is_default_chat=False,
        is_default_embedding=False,
        is_default_tts=False,
        tts_protocol=None,
        tts_voice=None,
        tts_speed=1.0,
        input_price_per_million=None,
        output_price_per_million=None,
        cached_input_price_per_million=None,
        cache_write_input_price_per_million=None,
        pricing_currency=None,
        is_enabled=True,
        sort_order=0,
    )
    service.model_repo = SimpleNamespace(
        lock_user_configuration=AsyncMock(),
        get_owned=AsyncMock(return_value=model),
    )

    with pytest.raises(ValueError, match="TTS 模型必须选择语音协议"):
        await service.update_model(
            7,
            10,
            UserAIModelUpdate(capabilities={"chat": False, "tts": True}),
        )


def test_alembic_baseline_includes_tts_columns():
    # schema 改由 alembic baseline 管理（替代 _ensure_schema_updates 过渡态，schema.sql 已随 PG 迁移删除），确认 baseline 含 tts 列
    baseline = (ROOT / "alembic" / "versions" / "a53385d06521_baseline.py").read_text(
        encoding="utf-8"
    )

    for column in ["is_default_tts", "tts_protocol", "tts_voice", "tts_speed"]:
        assert column in baseline
