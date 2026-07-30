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


@pytest.mark.asyncio(loop_scope="session")
async def test_detached_llm_call_closes_config_session_before_external_wait(monkeypatch):
    events: list[str] = []

    class SessionContext:
        async def __aenter__(self):
            events.append("session_enter")
            return AsyncMock()

        async def __aexit__(self, exc_type, exc, traceback):
            events.append("session_exit")

    def session_factory():
        return SessionContext()

    async def resolve_config(self, user_id, *, stage, model_id):
        events.append("resolve_config")
        return {"api_key": "test-key", "model": "test-model"}

    async def collect(self, messages, **kwargs):
        events.append("external_wait")
        return "ok"

    monkeypatch.setattr(LLMService, "_resolve_llm_config", resolve_config)
    monkeypatch.setattr(LLMService, "_stream_and_collect_with_config", collect)

    result = await LLMService.get_llm_response_detached(
        "system",
        [{"role": "user", "content": "hello"}],
        session_factory=session_factory,
        user_id=7,
    )

    assert result == "ok"
    assert events == ["session_enter", "resolve_config", "session_exit", "external_wait"]


@pytest.mark.asyncio(loop_scope="session")
async def test_detached_summary_closes_config_session_before_external_wait(monkeypatch):
    events: list[str] = []

    class SessionContext:
        async def __aenter__(self):
            events.append("session_enter")
            return AsyncMock()

        async def __aexit__(self, exc_type, exc, traceback):
            events.append("session_exit")

    def session_factory():
        return SessionContext()

    async def resolve_config(self, user_id, *, stage, model_id):
        events.append("resolve_config")
        return {"api_key": "test-key", "model": "test-model"}

    async def collect(self, messages, **kwargs):
        events.append("external_wait")
        return "summary"

    monkeypatch.setattr(LLMService, "_resolve_llm_config", resolve_config)
    monkeypatch.setattr(LLMService, "_stream_and_collect_with_config", collect)

    result = await LLMService.get_summary_detached(
        "chapter",
        session_factory=session_factory,
        system_prompt="summarize",
        user_id=7,
    )

    assert result == "summary"
    assert events == ["session_enter", "resolve_config", "session_exit", "external_wait"]


@pytest.mark.asyncio(loop_scope="session")
async def test_detached_embedding_closes_config_session_before_external_wait(monkeypatch):
    events: list[str] = []

    class SessionContext:
        async def __aenter__(self):
            events.append("session_enter")
            return AsyncMock()

        async def __aexit__(self, exc_type, exc, traceback):
            events.append("session_exit")

    def session_factory():
        return SessionContext()

    async def resolve_route(self, *, user_id, stage, model_id):
        events.append("resolve_route")
        return {"model": "test-model"}

    async def embed(self, text, **kwargs):
        events.append("external_wait")
        return [0.1, 0.2]

    monkeypatch.setattr(LLMService, "_resolve_embedding_route", resolve_route)
    monkeypatch.setattr(LLMService, "_get_embedding_with_route", embed)

    result = await LLMService.get_embedding_detached(
        "chapter",
        session_factory=session_factory,
        user_id=7,
    )

    assert result == [0.1, 0.2]
    assert events == ["session_enter", "resolve_route", "session_exit", "external_wait"]


@pytest.mark.asyncio(loop_scope="session")
async def test_openai_embedding_result_includes_real_usage_and_cost(monkeypatch):
    class FakeEmbeddings:
        async def create(self, **_kwargs):
            return SimpleNamespace(
                data=[SimpleNamespace(embedding=[0.1, 0.2])],
                usage=SimpleNamespace(prompt_tokens=25, total_tokens=25),
            )

    class FakeAsyncOpenAI:
        def __init__(self, **_kwargs):
            self.embeddings = FakeEmbeddings()

        async def close(self):
            return None

    monkeypatch.setattr("app.services.llm_service.AsyncOpenAI", FakeAsyncOpenAI)
    service = LLMService(AsyncMock())

    result = await service._get_embedding_with_route_result(
        "chapter",
        routed={
            "api_key": "test-key",
            "base_url": "https://api.example.test/v1",
            "model": "embedding-model",
            "model_id": 9,
            "provider_type": "openai_compatible",
            "input_price_per_million": "0.20",
            "output_price_per_million": None,
            "cached_input_price_per_million": None,
            "cache_write_input_price_per_million": None,
            "pricing_currency": "USD",
        },
        user_id=7,
        model=None,
        stage="rag_embedding",
    )

    assert result.value == [0.1, 0.2]
    assert result.usage.to_dict() == {
        "input_tokens": 25,
        "output_tokens": 0,
        "total_tokens": 25,
        "cached_input_tokens": 0,
        "cache_write_input_tokens": 0,
        "reasoning_tokens": 0,
        "is_complete": True,
    }
    assert result.cost_amount == "0.000005"
    assert result.cost_unknown_reason is None


@pytest.mark.asyncio(loop_scope="session")
async def test_ollama_embedding_result_marks_usage_unknown(monkeypatch):
    class FakeOllamaClient:
        def __init__(self, *, host):
            self.host = host

    monkeypatch.setattr("app.services.llm_service.OllamaAsyncClient", FakeOllamaClient)
    service = LLMService(AsyncMock())
    service._request_ollama_embedding = AsyncMock(return_value=[0.3, 0.4])

    result = await service._get_embedding_with_route_result(
        "chapter",
        routed={
            "api_key": None,
            "base_url": "http://localhost:11434",
            "model": "nomic-embed-text",
            "model_id": 10,
            "provider_type": "ollama",
            "input_price_per_million": "0",
            "pricing_currency": "USD",
        },
        user_id=7,
        model=None,
        stage="rag_embedding",
    )

    assert result.value == [0.3, 0.4]
    assert result.usage.is_complete is False
    assert result.cost_amount is None
    assert result.cost_unknown_reason == "usage_unavailable"


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_llm_config_rejects_missing_user_context():
    service = LLMService(AsyncMock())
    _disable_model_routes(service)

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_llm_config_with_policy(None, require_api_key=True)

    assert exc_info.value.status_code == 400
    assert "默认 LLM 配置已禁用" in exc_info.value.detail


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_llm_config_requires_enabled_chat_model():
    service = LLMService(AsyncMock())
    _disable_model_routes(service)

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_llm_config_with_policy(7, require_api_key=True)

    assert exc_info.value.status_code == 400
    assert "LLM 模型" in exc_info.value.detail
    assert "基础 LLM" not in exc_info.value.detail


@pytest.mark.asyncio(loop_scope="session")
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


@pytest.mark.asyncio(loop_scope="session")
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


@pytest.mark.asyncio(loop_scope="session")
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
        input_price_per_million=2,
        output_price_per_million=8,
        cached_input_price_per_million=0.5,
        cache_write_input_price_per_million=None,
        pricing_currency="USD",
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
    assert config["input_price_per_million"] == 2
    assert config["output_price_per_million"] == 8
    assert config["pricing_currency"] == "USD"


@pytest.mark.asyncio(loop_scope="session")
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


@pytest.mark.asyncio(loop_scope="session")
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

        async def aclose(self) -> None:
            pass

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


@pytest.mark.asyncio(loop_scope="session")
async def test_stream_and_collect_retries_transient_concurrency_limit(monkeypatch):
    class FakeLLMClient:
        attempts = 0

        def __init__(self, *, api_key, base_url, provider_type):
            pass

        async def aclose(self) -> None:
            pass

        async def stream_chat(self, **kwargs):
            FakeLLMClient.attempts += 1
            if FakeLLMClient.attempts == 1:
                raise RuntimeError("Concurrency limit exceeded for account, please retry later")
            yield {"content": "ok", "finish_reason": "stop"}

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    service = LLMService(AsyncMock())
    service._resolve_llm_config = AsyncMock(
        return_value={
            "api_key": "test-key",
            "base_url": "https://api.example.test/v1",
            "model": "chat-model",
            "provider_type": "openai_compatible",
        }
    )
    service.usage_service = SimpleNamespace(increment=AsyncMock())
    monkeypatch.setattr("app.services.llm_service.LLMClient", FakeLLMClient)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    response = await service._stream_and_collect(
        [{"role": "user", "content": "hello"}],
        temperature=0.2,
        user_id=7,
        timeout=30.0,
    )

    assert response == "ok"
    assert FakeLLMClient.attempts == 2
    assert len(sleep_calls) == 1


@pytest.mark.asyncio(loop_scope="session")
async def test_stream_and_collect_result_keeps_only_successful_attempt_usage(monkeypatch):
    class FakeLLMClient:
        attempts = 0
        provider_request_keys = []

        def __init__(self, *, api_key, base_url, provider_type):
            pass

        async def aclose(self) -> None:
            pass

        async def stream_chat(self, **kwargs):
            FakeLLMClient.attempts += 1
            FakeLLMClient.provider_request_keys.append(kwargs.get("provider_request_key"))
            if FakeLLMClient.attempts == 1:
                yield {
                    "content": "discarded",
                    "finish_reason": None,
                    "usage": {
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "total_tokens": 120,
                        "cached_input_tokens": 0,
                        "cache_write_input_tokens": 0,
                        "reasoning_tokens": 0,
                        "is_complete": True,
                    },
                }
                raise RuntimeError("Concurrency limit exceeded, please retry later")
            yield {"content": "ok", "finish_reason": "stop"}
            yield {
                "content": None,
                "finish_reason": None,
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 2,
                    "total_tokens": 12,
                    "cached_input_tokens": 4,
                    "cache_write_input_tokens": 0,
                    "reasoning_tokens": 1,
                    "is_complete": True,
                },
            }

    async def fake_sleep(_delay):
        return None

    service = LLMService(AsyncMock())
    service.usage_service = SimpleNamespace(increment=AsyncMock())
    monkeypatch.setattr("app.services.llm_service.LLMClient", FakeLLMClient)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    result = await service._stream_and_collect_with_config_result(
        [{"role": "user", "content": "hello"}],
        config={
            "api_key": "test-key",
            "base_url": "https://api.example.test/v1",
            "model": "chat-model",
            "model_id": 8,
            "provider_type": "openai_compatible",
            "input_price_per_million": "2.00",
            "output_price_per_million": "8.00",
            "cached_input_price_per_million": "0.50",
            "cache_write_input_price_per_million": None,
            "pricing_currency": "USD",
        },
        temperature=0.2,
        user_id=7,
        timeout=30.0,
        stage="summary_memory",
        provider_request_key="workflow-provider-key",
    )

    assert result.value == "ok"
    assert result.usage.to_dict() == {
        "input_tokens": 10,
        "output_tokens": 2,
        "total_tokens": 12,
        "cached_input_tokens": 4,
        "cache_write_input_tokens": 0,
        "reasoning_tokens": 1,
        "is_complete": True,
    }
    assert result.cost_amount == "0.000030"
    assert result.cost_currency == "USD"
    assert result.cost_unknown_reason is None
    assert FakeLLMClient.attempts == 2
    assert FakeLLMClient.provider_request_keys == [
        "workflow-provider-key",
        "workflow-provider-key",
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_stream_and_collect_does_not_retry_non_retryable_errors(monkeypatch):
    class FakeLLMClient:
        attempts = 0

        def __init__(self, *, api_key, base_url, provider_type):
            pass

        async def aclose(self) -> None:
            pass

        async def stream_chat(self, **kwargs):
            FakeLLMClient.attempts += 1
            raise RuntimeError("invalid API Key")
            yield {"content": "", "finish_reason": None}

    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    service = LLMService(AsyncMock())
    service._resolve_llm_config = AsyncMock(
        return_value={
            "api_key": "bad-key",
            "base_url": "https://api.example.test/v1",
            "model": "chat-model",
            "provider_type": "openai_compatible",
        }
    )
    monkeypatch.setattr("app.services.llm_service.LLMClient", FakeLLMClient)
    monkeypatch.setattr("asyncio.sleep", fake_sleep)

    with pytest.raises(RuntimeError, match="invalid API Key"):
        await service._stream_and_collect(
            [{"role": "user", "content": "hello"}],
            temperature=0.2,
            user_id=7,
            timeout=30.0,
        )

    assert FakeLLMClient.attempts == 1
    assert sleep_calls == []


@pytest.mark.asyncio(loop_scope="session")
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
