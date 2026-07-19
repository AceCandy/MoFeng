"""章节状态事件总线（Redis pub-sub）单测 + SSE 事件驱动改造静态断言。

覆盖 L27 AC：
- event_bus：channel 命名、未配置 Redis 时 publish 静默/subscribe 返回 None、fire-and-forget task 异常吞掉。
- SSE：subscribe + get_message 替代每秒轮询、subscribe 前发初始态、降级 5s 轮询、aclose 退出。
- pipeline：三处状态变更 commit 后 publish。
"""
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services import event_bus

ROOT = Path(__file__).resolve().parents[1]
NOVELS_ROUTER_SOURCE = ROOT / "app/api/routers/novels.py"
PIPELINE_SOURCE = ROOT / "app/services/pipeline_orchestrator.py"
TASKS_ROUTER_SOURCE = ROOT / "app/api/routers/tasks.py"
BACKGROUND_TASK_SERVICE_SOURCE = ROOT / "app/services/background_task_service.py"


@pytest.fixture(autouse=True)
def _reset_event_bus():
    """每个测试前重置 event_bus 模块级单例状态，避免跨测试污染。"""
    event_bus._async_client = None
    event_bus._async_client_ready = False
    event_bus._publish_tasks.clear()
    yield
    event_bus._async_client = None
    event_bus._async_client_ready = False
    event_bus._publish_tasks.clear()


def _install_client(client):
    """直接注入已就绪的 mock 客户端，绕过懒加载。"""
    event_bus._async_client = client
    event_bus._async_client_ready = True


def test_chapter_status_channel_naming() -> None:
    assert event_bus.chapter_status_channel("p1", 3) == "chapter:status:p1:3"
    assert event_bus.chapter_status_channel("abc-9", 12) == "chapter:status:abc-9:12"


@pytest.mark.asyncio(loop_scope="session")
async def test_publish_silently_skips_when_redis_unavailable() -> None:
    """未配置 Redis（客户端为 None）时 publish 静默跳过，不抛异常、不创建 task。"""
    _install_client(None)
    await event_bus.publish_chapter_status("p1", 1)
    assert event_bus._publish_tasks == set()


@pytest.mark.asyncio(loop_scope="session")
async def test_publish_creates_fire_and_forget_task() -> None:
    """有 Redis 客户端时 publish 创建 fire-and-forget task，不阻塞调用方。"""
    client = MagicMock()
    client.publish = AsyncMock()
    _install_client(client)

    await event_bus.publish_chapter_status("p1", 1)
    await asyncio.sleep(0.05)  # 等 fire-and-forget task 跑完

    client.publish.assert_awaited_once_with("chapter:status:p1:1", "1")


@pytest.mark.asyncio(loop_scope="session")
async def test_publish_task_swallows_redis_error() -> None:
    """Redis publish 抛异常时被 _safe_publish 静默捕获，不外抛、不阻塞调用方。"""
    client = MagicMock()
    client.publish = AsyncMock(side_effect=ConnectionError("redis down"))
    _install_client(client)

    await event_bus.publish_chapter_status("p1", 1)
    await asyncio.sleep(0.05)
    # 到这里未抛异常即通过


@pytest.mark.asyncio(loop_scope="session")
async def test_subscribe_returns_none_when_redis_unavailable() -> None:
    """未配置 Redis 时 subscribe 返回 None，供 SSE 回退轮询。"""
    _install_client(None)
    result = await event_bus.subscribe_chapter_status("p1", 1)
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_subscribe_returns_pubsub_on_success() -> None:
    """有 Redis 时 subscribe 返回 PubSub 并完成 channel 订阅。"""
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    client = MagicMock()
    client.pubsub = MagicMock(return_value=pubsub)
    _install_client(client)

    result = await event_bus.subscribe_chapter_status("p1", 1)

    assert result is pubsub
    pubsub.subscribe.assert_awaited_once_with("chapter:status:p1:1")
    pubsub.aclose.assert_not_awaited()


@pytest.mark.asyncio(loop_scope="session")
async def test_subscribe_returns_none_and_closes_pubsub_on_connection_error() -> None:
    """subscribe 建连失败时返回 None 并 aclose pubsub，避免连接泄漏。"""
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock(side_effect=ConnectionError("redis down"))
    pubsub.aclose = AsyncMock()
    client = MagicMock()
    client.pubsub = MagicMock(return_value=pubsub)
    _install_client(client)

    result = await event_bus.subscribe_chapter_status("p1", 1)

    assert result is None
    pubsub.aclose.assert_awaited_once()


# ---------------- SSE 事件驱动改造静态断言 ----------------


def _novels_source() -> str:
    return NOVELS_ROUTER_SOURCE.read_text(encoding="utf-8")


def _pipeline_source() -> str:
    return PIPELINE_SOURCE.read_text(encoding="utf-8")


def _tasks_source() -> str:
    return TASKS_ROUTER_SOURCE.read_text(encoding="utf-8")


def _background_task_service_source() -> str:
    return BACKGROUND_TASK_SERVICE_SOURCE.read_text(encoding="utf-8")


def test_sse_stream_replaced_polling_with_pubsub_subscribe() -> None:
    """stream_chapter_status 改事件驱动：subscribe channel + get_message，去掉每秒轮询。"""
    source = _novels_source()
    assert "subscribe_chapter_status(project_id, chapter_number)" in source
    assert "pubsub.get_message(" in source
    assert "asyncio.sleep(1.0)" not in source


def test_sse_emits_initial_state_before_subscribe() -> None:
    """subscribe 前查 DB 发初始态，兜底 pub-sub 订阅前的消息丢失。"""
    source = _novels_source()
    initial_fetch = source.index("await fetch_payload()")
    subscribe_call = source.index("await subscribe_chapter_status")
    assert initial_fetch < subscribe_call


def test_sse_falls_back_to_polling_when_redis_unavailable() -> None:
    """Redis 不可用时 SSE 回退 5s 轮询查 DB。"""
    source = _novels_source()
    assert "pubsub is None" in source
    assert "asyncio.sleep(5.0)" in source


def test_sse_falls_back_to_polling_on_pubsub_disconnect() -> None:
    """运行中 Redis 断连（get_message 异常）时回退轮询，不靠异常断开 SSE。"""
    source = _novels_source()
    assert "redis_disconnected" in source
    assert "async def poll_loop" in source
    assert "async for evt in poll_loop():" in source


def test_sse_closes_pubsub_on_exit() -> None:
    """事件驱动循环退出时在 finally 中 aclose pubsub，避免连接泄漏。"""
    source = _novels_source()
    assert "finally:" in source
    assert "await pubsub.aclose()" in source


def test_pipeline_publishes_chapter_status_on_state_changes() -> None:
    """三处状态变更（_set/_mark_failed/_mark_failed_resume）commit 后 publish 通知。"""
    source = _pipeline_source()
    assert "from ..services.event_bus import publish_chapter_status" in source
    assert (
        source.count("await publish_chapter_status(project_id, chapter_number)") >= 3
    )


# ---------------- 后台任务事件总线（方案 B 扩展） ----------------


def test_background_task_channel_naming() -> None:
    assert event_bus.background_task_channel(1) == "task:status:1"
    assert event_bus.background_task_channel(42) == "task:status:42"


@pytest.mark.asyncio(loop_scope="session")
async def test_publish_background_task_silently_skips_when_redis_unavailable() -> None:
    """未配置 Redis 时 publish 静默跳过，不抛异常、不创建 task。"""
    _install_client(None)
    await event_bus.publish_background_task(1)
    assert event_bus._publish_tasks == set()


@pytest.mark.asyncio(loop_scope="session")
async def test_publish_background_task_creates_fire_and_forget_task() -> None:
    """有 Redis 客户端时 publish 创建 fire-and-forget task，不阻塞调用方。"""
    client = MagicMock()
    client.publish = AsyncMock()
    _install_client(client)

    await event_bus.publish_background_task(7)
    await asyncio.sleep(0.05)

    client.publish.assert_awaited_once_with("task:status:7", "1")


@pytest.mark.asyncio(loop_scope="session")
async def test_subscribe_background_task_returns_none_when_redis_unavailable() -> None:
    """未配置 Redis 时 subscribe 返回 None，供 SSE 回退轮询。"""
    _install_client(None)
    result = await event_bus.subscribe_background_task(1)
    assert result is None


@pytest.mark.asyncio(loop_scope="session")
async def test_subscribe_background_task_returns_pubsub_on_success() -> None:
    """有 Redis 时 subscribe 返回 PubSub 并完成 channel 订阅。"""
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock()
    pubsub.aclose = AsyncMock()
    client = MagicMock()
    client.pubsub = MagicMock(return_value=pubsub)
    _install_client(client)

    result = await event_bus.subscribe_background_task(9)

    assert result is pubsub
    pubsub.subscribe.assert_awaited_once_with("task:status:9")
    pubsub.aclose.assert_not_awaited()


@pytest.mark.asyncio(loop_scope="session")
async def test_subscribe_background_task_returns_none_and_closes_pubsub_on_connection_error() -> None:
    """subscribe 建连失败时返回 None 并 aclose pubsub，避免连接泄漏。"""
    pubsub = MagicMock()
    pubsub.subscribe = AsyncMock(side_effect=ConnectionError("redis down"))
    pubsub.aclose = AsyncMock()
    client = MagicMock()
    client.pubsub = MagicMock(return_value=pubsub)
    _install_client(client)

    result = await event_bus.subscribe_background_task(9)

    assert result is None
    pubsub.aclose.assert_awaited_once()


# ---------------- 后台任务 SSE 事件驱动改造静态断言 ----------------


def test_tasks_sse_replaced_polling_with_pubsub_subscribe() -> None:
    """stream_background_tasks 改事件驱动：subscribe channel + get_message，替代固定轮询。"""
    source = _tasks_source()
    assert "subscribe_background_task(current_user.id)" in source
    assert "pubsub.get_message(" in source
    assert "async def fetch_payload" in source
    assert "def build_event(payload" in source


def test_tasks_sse_emits_initial_state_before_subscribe() -> None:
    """subscribe 前查 DB 发初始态，兜底 pub-sub 订阅前的消息丢失。"""
    source = _tasks_source()
    initial_fetch = source.index("await fetch_payload()")
    subscribe_call = source.index("await subscribe_background_task")
    assert initial_fetch < subscribe_call


def test_tasks_sse_falls_back_to_polling_when_redis_unavailable() -> None:
    """Redis 不可用时 SSE 回退 1.5s 轮询查 DB。"""
    source = _tasks_source()
    assert "pubsub is None" in source
    assert "asyncio.sleep(1.5)" in source


def test_tasks_sse_falls_back_to_polling_on_pubsub_disconnect() -> None:
    """运行中 Redis 断连（get_message 异常）时回退轮询，不靠异常断开 SSE。"""
    source = _tasks_source()
    assert "redis_disconnected" in source
    assert "async def poll_loop" in source
    assert "async for evt in poll_loop():" in source


def test_tasks_sse_closes_pubsub_on_exit() -> None:
    """事件驱动循环退出时在 finally 中 aclose pubsub，避免连接泄漏。"""
    source = _tasks_source()
    assert "finally:" in source
    assert "await pubsub.aclose()" in source


def test_background_task_service_publishes_on_state_changes() -> None:
    """5 处状态变更（create/append_log/mark_running/mark_succeeded/mark_failed）commit 后 publish 通知。"""
    source = _background_task_service_source()
    assert "from .event_bus import publish_background_task" in source
    assert source.count("await publish_background_task(task.user_id)") >= 5
