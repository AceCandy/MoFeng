from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from app.schemas.llm_config import UserAIModelCreate, UserAIModelUpdate
from app.services.llm_config_service import LLMConfigService


def _chat_model_payload(**overrides):
    values = {
        "provider_id": 3,
        "display_name": "Chat Model",
        "model_name": "chat-model",
        "capabilities": {"chat": True, "embedding": False, "tts": False},
        "input_price_per_million": "2.5",
        "output_price_per_million": "8",
        "cached_input_price_per_million": "0.5",
        "cache_write_input_price_per_million": None,
        "pricing_currency": " usd ",
    }
    values.update(overrides)
    return values


def test_model_pricing_schema_preserves_decimal_and_normalizes_currency() -> None:
    payload = UserAIModelCreate(**_chat_model_payload())

    assert payload.input_price_per_million == Decimal("2.5")
    assert payload.output_price_per_million == Decimal("8")
    assert payload.pricing_currency == "USD"


@pytest.mark.parametrize(
    "overrides",
    [
        {"input_price_per_million": "-0.1"},
        {"pricing_currency": "US"},
        {"pricing_currency": "12$"},
    ],
)
def test_model_pricing_schema_rejects_invalid_values(overrides) -> None:
    with pytest.raises(ValidationError):
        UserAIModelCreate(**_chat_model_payload(**overrides))


@pytest.mark.asyncio(loop_scope="session")
async def test_model_pricing_round_trips_through_create_and_update_service() -> None:
    session = AsyncMock()
    service = LLMConfigService(session)

    async def add_model(model):
        model.id = 10
        return model

    service.provider_repo = SimpleNamespace(get_owned=AsyncMock(return_value=SimpleNamespace(id=3)))
    service.model_repo = SimpleNamespace(
        add=add_model,
        lock_user_configuration=AsyncMock(),
    )
    service._normalize_default_flags = AsyncMock()

    created = await service.create_model(7, UserAIModelCreate(**_chat_model_payload()))
    model = service._normalize_default_flags.await_args.args[1]
    service.model_repo.get_owned = AsyncMock(return_value=model)
    updated = await service.update_model(
        7,
        10,
        UserAIModelUpdate(
            input_price_per_million=None,
            output_price_per_million="9.25",
            pricing_currency="eur",
        ),
    )

    assert created.input_price_per_million == Decimal("2.5")
    assert created.pricing_currency == "USD"
    assert updated.input_price_per_million is None
    assert updated.output_price_per_million == Decimal("9.25")
    assert updated.pricing_currency == "EUR"
