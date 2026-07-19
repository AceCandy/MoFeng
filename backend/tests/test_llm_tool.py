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
    assert FakeAsyncClient.last_request["json"]["system"] == "system prompt"
    assert FakeAsyncClient.last_request["json"]["messages"] == [
        {"role": "user", "content": "hello"}
    ]
