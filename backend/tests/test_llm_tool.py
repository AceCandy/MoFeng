from types import SimpleNamespace

import pytest

from app.utils import llm_tool
from app.utils.llm_tool import ChatMessage, LLMClient


@pytest.mark.asyncio(loop_scope="session")
async def test_anthropic_stream_chat_uses_custom_messages_url(monkeypatch):
    class FakeStreamResponse:
        def raise_for_status(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def aiter_lines(self):
            yield 'data: {"type":"content_block_delta","delta":{"type":"text_delta","text":"你好"}}'
            yield 'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"}}'

    class FakeAsyncClient:
        last_request = {}

        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def stream(self, method, url, *, headers, json):
            FakeAsyncClient.last_request = {
                "method": method,
                "url": url,
                "headers": headers,
                "json": json,
                "timeout": self.timeout,
            }
            return FakeStreamResponse()

    monkeypatch.setattr(llm_tool.httpx, "AsyncClient", FakeAsyncClient)
    client = LLMClient(
        api_key="anthropic-key",
        base_url="https://anthropic-proxy.example/v1",
        provider_type="anthropic",
    )

    chunks = [
        chunk
        async for chunk in client.stream_chat(
            messages=[
                ChatMessage(role="system", content="system prompt"),
                ChatMessage(role="user", content="hello"),
            ],
            model="claude-3-5-sonnet-20241022",
            temperature=0.2,
            max_tokens=1024,
            timeout=30,
            provider_request_key="workflow-provider-key",
        )
    ]

    assert chunks == [
        {"content": "你好", "finish_reason": None},
        {"content": None, "finish_reason": "end_turn"},
    ]
    assert FakeAsyncClient.last_request["method"] == "POST"
    assert FakeAsyncClient.last_request["url"] == "https://anthropic-proxy.example/v1/messages"
    assert FakeAsyncClient.last_request["headers"]["x-api-key"] == "anthropic-key"
    assert FakeAsyncClient.last_request["headers"]["anthropic-version"] == "2023-06-01"
    assert FakeAsyncClient.last_request["headers"]["Idempotency-Key"] == ("workflow-provider-key")
    assert FakeAsyncClient.last_request["json"]["system"] == "system prompt"
    assert FakeAsyncClient.last_request["json"]["messages"] == [
        {"role": "user", "content": "hello"}
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_openai_stream_chat_preserves_usage_only_final_chunk(monkeypatch):
    class FakeStream:
        def __init__(self):
            self._chunks = [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(content="完成"),
                            finish_reason="stop",
                        )
                    ],
                    usage=None,
                ),
                SimpleNamespace(
                    choices=[],
                    usage=SimpleNamespace(
                        prompt_tokens=12,
                        completion_tokens=4,
                        total_tokens=16,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=3),
                        completion_tokens_details=SimpleNamespace(reasoning_tokens=2),
                    ),
                ),
            ]

        def __aiter__(self):
            self._iterator = iter(self._chunks)
            return self

        async def __anext__(self):
            try:
                return next(self._iterator)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

    class FakeCompletions:
        payload = None

        async def create(self, **payload):
            FakeCompletions.payload = payload
            return FakeStream()

    class FakeAsyncOpenAI:
        def __init__(self, **_kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

        async def close(self):
            return None

    monkeypatch.setattr(llm_tool, "AsyncOpenAI", FakeAsyncOpenAI)
    client = LLMClient(
        api_key="openai-key",
        base_url="https://openai-proxy.example/v1",
        provider_type="openai_compatible",
    )

    chunks = [
        chunk
        async for chunk in client.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="gpt-test",
            provider_request_key="workflow-provider-key",
        )
    ]

    assert FakeCompletions.payload["stream_options"] == {"include_usage": True}
    assert FakeCompletions.payload["extra_headers"] == {"Idempotency-Key": "workflow-provider-key"}
    assert chunks == [
        {"content": "完成", "finish_reason": "stop"},
        {
            "content": None,
            "finish_reason": None,
            "usage": {
                "input_tokens": 12,
                "output_tokens": 4,
                "total_tokens": 16,
                "cached_input_tokens": 3,
                "cache_write_input_tokens": 0,
                "reasoning_tokens": 2,
                "is_complete": True,
            },
        },
    ]


@pytest.mark.asyncio(loop_scope="session")
async def test_anthropic_stream_usage_is_cumulative_not_additive(monkeypatch):
    class FakeStreamResponse:
        def raise_for_status(self):
            return None

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        async def aiter_lines(self):
            yield (
                'data: {"type":"message_start","message":{"usage":'
                '{"input_tokens":10,"output_tokens":0,'
                '"cache_read_input_tokens":4,"cache_creation_input_tokens":2}}}'
            )
            yield 'data: {"type":"message_delta","delta":{},"usage":{"output_tokens":1}}'
            yield (
                'data: {"type":"message_delta","delta":{"stop_reason":"end_turn"},'
                '"usage":{"output_tokens":2}}'
            )

    class FakeAsyncClient:
        def __init__(self, *, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return False

        def stream(self, method, url, *, headers, json):
            return FakeStreamResponse()

    monkeypatch.setattr(llm_tool.httpx, "AsyncClient", FakeAsyncClient)
    client = LLMClient(api_key="anthropic-key", provider_type="anthropic")

    chunks = [
        chunk
        async for chunk in client.stream_chat(
            messages=[ChatMessage(role="user", content="hello")],
            model="claude-test",
        )
    ]

    assert chunks[-1] == {
        "content": None,
        "finish_reason": "end_turn",
        "usage": {
            "input_tokens": 16,
            "output_tokens": 2,
            "total_tokens": 18,
            "cached_input_tokens": 4,
            "cache_write_input_tokens": 2,
            "reasoning_tokens": 0,
            "is_complete": True,
        },
    }
