from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.services.llm_service import LLMService


def _disable_model_routes(service: LLMService) -> None:
    service.stage_route_repo = SimpleNamespace(get_by_stage=AsyncMock(return_value=None))
    service.ai_model_repo = SimpleNamespace(
        get_owned=AsyncMock(return_value=None),
        list_enabled_by_capability=AsyncMock(return_value=[]),
    )


@pytest.mark.asyncio
async def test_resolve_llm_config_rejects_missing_user_context():
    service = LLMService(AsyncMock())
    _disable_model_routes(service)

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_llm_config_with_policy(None, require_api_key=True)

    assert exc_info.value.status_code == 400
    assert "默认 LLM 配置已禁用" in exc_info.value.detail


@pytest.mark.asyncio
async def test_resolve_llm_config_requires_enabled_chat_model():
    service = LLMService(AsyncMock())
    _disable_model_routes(service)

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_llm_config_with_policy(7, require_api_key=True)

    assert exc_info.value.status_code == 400
    assert "LLM 模型" in exc_info.value.detail
    assert "基础 LLM" not in exc_info.value.detail


@pytest.mark.asyncio
async def test_resolve_llm_config_does_not_fallback_to_legacy_user_level_values():
    service = LLMService(AsyncMock())
    _disable_model_routes(service)
    service.llm_repo = SimpleNamespace(
        get_by_user=AsyncMock(
            return_value=SimpleNamespace(
                llm_provider_url="https://api.example.com/v1",
                llm_provider_api_key="test-key",
                llm_provider_model="gpt-test",
            )
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_llm_config_with_policy(9, require_api_key=True)

    assert exc_info.value.status_code == 400
    assert "LLM 模型" in exc_info.value.detail


@pytest.mark.asyncio
async def test_resolve_llm_config_requires_primary_chat_model_even_when_enabled_model_exists():
    service = LLMService(AsyncMock())
    provider = SimpleNamespace(
        name="Provider",
        provider_type="openai_compatible",
        base_url="https://api.example.com/v1",
        api_key_encrypted="test-key",
        is_enabled=True,
    )
    service.stage_route_repo = SimpleNamespace(get_by_stage=AsyncMock(return_value=None))
    service.ai_model_repo = SimpleNamespace(
        get_owned=AsyncMock(return_value=None),
        list_enabled_by_capability=AsyncMock(
            return_value=[
                SimpleNamespace(
                    id=15,
                    model_name="enabled-without-primary",
                    capabilities_json={"chat": True},
                    is_enabled=True,
                    is_default_chat=False,
                    provider=provider,
                )
            ]
        ),
    )
    service.llm_repo = SimpleNamespace(get_by_user=AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_llm_config_with_policy(7, require_api_key=True)

    assert exc_info.value.status_code == 400
    assert "主模型" in exc_info.value.detail


@pytest.mark.asyncio
async def test_resolve_llm_config_uses_stage_route_model():
    service = LLMService(AsyncMock())
    provider = SimpleNamespace(
        name="Stage Provider",
        provider_type="openai_compatible",
        base_url="https://api.stage.test/v1",
        api_key_encrypted="stage-key",
        is_enabled=True,
    )
    model = SimpleNamespace(
        id=42,
        model_name="stage-chat",
        capabilities_json={"chat": True},
        is_enabled=True,
        provider=provider,
    )
    service.stage_route_repo = SimpleNamespace(
        get_by_stage=AsyncMock(return_value=SimpleNamespace(model=model))
    )
    service.ai_model_repo = SimpleNamespace(
        get_owned=AsyncMock(return_value=None),
        list_enabled_by_capability=AsyncMock(return_value=[]),
    )
    service.llm_repo = SimpleNamespace(get_by_user=AsyncMock(return_value=None))

    config = await service._resolve_llm_config_with_policy(
        7,
        require_api_key=True,
        stage="chapter_writing",
    )

    assert config["model"] == "stage-chat"
    assert config["api_key"] == "stage-key"
    assert config["base_url"] == "https://api.stage.test/v1"
    assert config["stage"] == "chapter_writing"
    assert config["model_id"] == 42


@pytest.mark.asyncio
async def test_resolve_embedding_config_rejects_chat_only_route():
    service = LLMService(AsyncMock())
    provider = SimpleNamespace(
        name="Stage Provider",
        provider_type="openai_compatible",
        base_url="https://api.stage.test/v1",
        api_key_encrypted="stage-key",
        is_enabled=True,
    )
    model = SimpleNamespace(
        id=42,
        model_name="chat-only",
        capabilities_json={"chat": True, "embedding": False},
        is_enabled=True,
        provider=provider,
    )
    service.stage_route_repo = SimpleNamespace(
        get_by_stage=AsyncMock(return_value=SimpleNamespace(model=model))
    )
    service.ai_model_repo = SimpleNamespace(
        get_owned=AsyncMock(return_value=None),
        list_enabled_by_capability=AsyncMock(return_value=[]),
    )

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_model_route(7, stage="rag_embedding", capability="embedding")

    assert exc_info.value.status_code == 400
    assert "embedding" in exc_info.value.detail


@pytest.mark.asyncio
async def test_stream_and_collect_passes_provider_type_to_llm_client(monkeypatch):
    class FakeLLMClient:
        init_kwargs = {}

        def __init__(self, *, api_key, base_url, provider_type):
            self.init_kwargs = {
                "api_key": api_key,
                "base_url": base_url,
                "provider_type": provider_type,
            }
            FakeLLMClient.init_kwargs = self.init_kwargs

        async def stream_chat(self, **kwargs):
            yield {"content": "ok", "finish_reason": "stop"}

    service = LLMService(AsyncMock())
    service._resolve_llm_config = AsyncMock(
        return_value={
            "api_key": "anthropic-key",
            "base_url": "https://anthropic-proxy.example/v1",
            "model": "claude-3-5-sonnet-20241022",
            "provider_type": "anthropic",
        }
    )
    service.usage_service = SimpleNamespace(increment=AsyncMock())
    monkeypatch.setattr("app.services.llm_service.LLMClient", FakeLLMClient)

    response = await service._stream_and_collect(
        [{"role": "user", "content": "hello"}],
        temperature=0.2,
        user_id=7,
        timeout=30.0,
    )

    assert response == "ok"
    assert FakeLLMClient.init_kwargs == {
        "api_key": "anthropic-key",
        "base_url": "https://anthropic-proxy.example/v1",
        "provider_type": "anthropic",
    }


@pytest.mark.asyncio
async def test_get_embedding_does_not_fallback_to_legacy_user_level_values():
    service = LLMService(AsyncMock())
    _disable_model_routes(service)
    service.llm_repo = SimpleNamespace(
        get_by_user=AsyncMock(
            return_value=SimpleNamespace(
                llm_provider_url="https://api.example.com/v1",
                llm_provider_api_key="test-key",
                embedding_provider_url="https://api.example.com/v1",
                embedding_provider_api_key="test-key",
                embedding_provider_model="text-embedding-test",
                embedding_provider_format="openai",
            )
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.get_embedding("hello", user_id=9)

    assert exc_info.value.status_code == 400
    assert "向量模型" in exc_info.value.detail
    service.llm_repo.get_by_user.assert_not_awaited()
