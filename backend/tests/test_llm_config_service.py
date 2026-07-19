from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.schemas.llm_config import ProviderCreate
from app.services.llm_config_service import LLMConfigService


@pytest.mark.asyncio(loop_scope="session")
async def test_mask_api_key_keeps_only_suffix():
    service = LLMConfigService(AsyncMock())

    assert service._mask_api_key("sk-1234567890") == "******7890"
    assert service._mask_api_key("") is None
    assert service._mask_api_key(None) is None


@pytest.mark.asyncio(loop_scope="session")
async def test_pick_default_model_requires_capability():
    service = LLMConfigService(AsyncMock())
    models = [
        SimpleNamespace(id=1, model_name="embed", capabilities_json={"embedding": True}, is_enabled=True),
        SimpleNamespace(id=2, model_name="chat", capabilities_json={"chat": True}, is_enabled=True),
    ]

    selected = service._pick_default_model(models, capability="chat")

    assert selected.id == 2


def test_stage_capability_mapping():
    assert LLMConfigService.stage_capability("chapter_writing") == "chat"
    assert LLMConfigService.stage_capability("rag_embedding") == "embedding"


def test_stage_capability_rejects_unknown_stage():
    with pytest.raises(ValueError) as exc_info:
        LLMConfigService.stage_capability("unknown")

    assert "unknown AI stage" in str(exc_info.value)


def test_provider_create_defaults_to_chat_scope():
    payload = ProviderCreate(
        name="sub2api",
        provider_type="openai_compatible",
        base_url="https://api.example.com/v1",
    )

    assert payload.capabilities == {"chat": True, "embedding": False, "tts": False}


def test_provider_create_accepts_anthropic_with_custom_url():
    payload = ProviderCreate(
        name="Anthropic Proxy",
        provider_type="anthropic",
        base_url="https://anthropic-proxy.example/v1",
    )

    assert payload.provider_type == "anthropic"
    assert payload.base_url == "https://anthropic-proxy.example/v1"


@pytest.mark.asyncio(loop_scope="session")
async def test_get_provider_models_uses_saved_provider_type_for_custom_anthropic_url():
    service = LLMConfigService(AsyncMock())
    provider = SimpleNamespace(
        is_enabled=True,
        api_key_encrypted="anthropic-key",
        base_url="https://anthropic-proxy.example/v1",
        provider_type="anthropic",
    )
    service.provider_repo = SimpleNamespace(get_owned=AsyncMock(return_value=provider))
    service.get_available_models = AsyncMock(return_value=["claude-3-5-sonnet-20241022"])

    models = await service.get_provider_models(7, 3)

    assert models == ["claude-3-5-sonnet-20241022"]
    service.get_available_models.assert_awaited_once_with(
        api_key="anthropic-key",
        base_url="https://anthropic-proxy.example/v1",
        provider_type="anthropic",
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_get_anthropic_models_uses_custom_models_url(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"id": "claude-custom-sonnet"}]}

    class FakeAsyncClient:
        last_request = {}

        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def get(self, url, *, headers):
            FakeAsyncClient.last_request = {
                "url": url,
                "headers": headers,
                "timeout": self.timeout,
            }
            return FakeResponse()

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    service = LLMConfigService(AsyncMock())

    models = await service._get_anthropic_models(
        api_key="anthropic-key",
        base_url="https://anthropic-proxy.example/v1",
    )

    assert models == ["claude-custom-sonnet"]
    assert FakeAsyncClient.last_request["url"] == "https://anthropic-proxy.example/v1/models"
    assert FakeAsyncClient.last_request["headers"]["x-api-key"] == "anthropic-key"
    assert FakeAsyncClient.last_request["headers"]["anthropic-version"] == "2023-06-01"


def test_provider_to_read_exposes_provider_scope():
    provider = SimpleNamespace(
        id=1,
        user_id=7,
        name="vector",
        provider_type="openai_compatible",
        base_url="https://api.example.com/v1",
        api_key_preview="******1234",
        is_enabled=True,
        capabilities_json={"chat": False, "embedding": True},
    )

    read = LLMConfigService._provider_to_read(provider)

    assert read.capabilities == {"chat": False, "embedding": True, "tts": False}


@pytest.mark.asyncio(loop_scope="session")
async def test_upsert_stage_routes_rejects_disabled_model():
    service = LLMConfigService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_owned=AsyncMock(
            return_value=SimpleNamespace(
                model_name="disabled-chat",
                capabilities_json={"chat": True},
                is_enabled=False,
                provider=SimpleNamespace(is_enabled=True),
            )
        )
    )

    with pytest.raises(ValueError) as exc_info:
        await service.upsert_stage_routes(
            7,
            SimpleNamespace(
                routes=[SimpleNamespace(stage="chapter_writing", model_id=10)]
            ),
        )

    assert "disabled" in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="session")
async def test_upsert_stage_routes_rejects_disabled_provider():
    service = LLMConfigService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_owned=AsyncMock(
            return_value=SimpleNamespace(
                model_name="provider-off",
                capabilities_json={"chat": True},
                is_enabled=True,
                provider=SimpleNamespace(is_enabled=False),
            )
        )
    )

    with pytest.raises(ValueError) as exc_info:
        await service.upsert_stage_routes(
            7,
            SimpleNamespace(
                routes=[SimpleNamespace(stage="chapter_writing", model_id=10)]
            ),
        )

    assert "provider disabled" in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_model_rejects_default_chat_model():
    service = LLMConfigService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_owned=AsyncMock(
            return_value=SimpleNamespace(
                id=10,
                model_name="main-chat",
                is_default_chat=True,
                is_default_embedding=False,
            )
        )
    )

    with pytest.raises(ValueError) as exc_info:
        await service.delete_model(7, 10)

    assert "主模型不能直接删除" in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_model_rejects_default_embedding_model():
    service = LLMConfigService(AsyncMock())
    service.model_repo = SimpleNamespace(
        get_owned=AsyncMock(
            return_value=SimpleNamespace(
                id=10,
                model_name="main-embedding",
                is_default_chat=False,
                is_default_embedding=True,
            )
        )
    )

    with pytest.raises(ValueError) as exc_info:
        await service.delete_model(7, 10)

    assert "当前向量模型不能直接删除" in str(exc_info.value)


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_model_removes_related_stage_routes_before_model():
    service = LLMConfigService(AsyncMock())
    model = SimpleNamespace(
        id=10,
        model_name="unused-chat",
        is_default_chat=False,
        is_default_embedding=False,
    )
    related_route = SimpleNamespace(model_id=10)
    other_route = SimpleNamespace(model_id=11)
    service.model_repo = SimpleNamespace(
        get_owned=AsyncMock(return_value=model),
        delete=AsyncMock(),
    )
    service.stage_route_repo = SimpleNamespace(
        list_by_user=AsyncMock(return_value=[related_route, other_route]),
        delete=AsyncMock(),
    )

    deleted = await service.delete_model(7, 10)

    assert deleted is True
    service.stage_route_repo.delete.assert_awaited_once_with(related_route)
    service.model_repo.delete.assert_awaited_once_with(model)
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="session")
async def test_delete_provider_removes_models_and_related_stage_routes():
    service = LLMConfigService(AsyncMock())
    provider = SimpleNamespace(id=3, name="sub2api")
    owned_model = SimpleNamespace(id=10, provider_id=3)
    other_model = SimpleNamespace(id=11, provider_id=4)
    related_route = SimpleNamespace(model_id=10)
    other_route = SimpleNamespace(model_id=11)
    service.provider_repo = SimpleNamespace(
        get_owned=AsyncMock(return_value=provider),
        delete=AsyncMock(),
    )
    service.model_repo = SimpleNamespace(
        list_by_user=AsyncMock(return_value=[owned_model, other_model]),
        delete=AsyncMock(),
    )
    service.stage_route_repo = SimpleNamespace(
        list_by_user=AsyncMock(return_value=[related_route, other_route]),
        delete=AsyncMock(),
    )

    deleted = await service.delete_provider(7, 3)

    assert deleted is True
    service.stage_route_repo.delete.assert_awaited_once_with(related_route)
    service.model_repo.delete.assert_awaited_once_with(owned_model)
    service.provider_repo.delete.assert_awaited_once_with(provider)
    service.session.commit.assert_awaited_once()


@pytest.mark.asyncio(loop_scope="session")
async def test_default_embedding_model_disables_other_embedding_models():
    service = LLMConfigService(AsyncMock())
    selected = SimpleNamespace(
        id=10,
        capabilities_json={"embedding": True},
        is_default_chat=False,
        is_default_embedding=True,
        is_enabled=True,
    )
    other_embedding = SimpleNamespace(
        id=11,
        capabilities_json={"embedding": True},
        is_default_chat=False,
        is_default_embedding=True,
        is_enabled=True,
    )
    chat_model = SimpleNamespace(
        id=12,
        capabilities_json={"chat": True},
        is_default_chat=True,
        is_default_embedding=False,
        is_enabled=True,
    )
    service.model_repo = SimpleNamespace(
        list_by_user=AsyncMock(return_value=[selected, other_embedding, chat_model])
    )

    await service._normalize_default_flags(7, selected)

    assert selected.is_enabled is True
    assert other_embedding.is_default_embedding is False
    assert other_embedding.is_enabled is False
    assert chat_model.is_default_chat is True
    assert chat_model.is_enabled is True
