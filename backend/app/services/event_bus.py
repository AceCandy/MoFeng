# AIMETA P=事件总线_Redis pubsub 轻量通知|R=publish通知_subscribe channel|NR=不含业务逻辑查询|E=event_bus|X=internal|A=服务|D=redis|S=cache|RD=./README.ai
"""事件总线：基于 Redis pub-sub 的轻量通知。

publish 端在生成流程/后台任务状态变更后发出通知（只发 channel 信号，不发业务数据）；
SSE 端 subscribe channel，收到通知后再查 DB 推送完整快照。
Redis 不可用或未配置时 publish 静默跳过（不阻塞业务流程），subscribe 返回 None 由调用方回退轮询。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import redis.asyncio as aioredis

from ..core.config import settings

logger = logging.getLogger(__name__)

_CHANNEL_PREFIX = "chapter:status"
_BACKGROUND_TASK_CHANNEL_PREFIX = "task:status"

# fire-and-forget publish task 集合，避免 task 被 GC 回收（Python 推荐模式）。
_publish_tasks: set = set()

# 懒加载 async Redis 客户端单例；未配置或初始化失败为 None。
_async_client: Optional[aioredis.Redis] = None
_async_client_ready: bool = False


def chapter_status_channel(project_id: str, chapter_number: int) -> str:
    """单章状态变更通知 channel。"""
    return f"{_CHANNEL_PREFIX}:{project_id}:{chapter_number}"


def get_async_client() -> Optional[aioredis.Redis]:
    """懒加载 async Redis 客户端单例；未配置返回 None。

    客户端在首次命令时才真正建连，连接失败由调用方 try/except 捕获。
    """
    global _async_client, _async_client_ready
    if _async_client_ready:
        return _async_client
    _async_client_ready = True
    if not settings.redis_url:
        logger.info("未配置 REDIS_URL，事件总线禁用")
        return _async_client
    try:
        _async_client = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            socket_connect_timeout=2.0,
            socket_timeout=2.0,
        )
        logger.info("事件总线 Redis 客户端已初始化")
    except Exception as e:
        logger.warning(f"事件总线 Redis 客户端初始化失败: {e}")
        _async_client = None
    return _async_client


async def _safe_publish(client: aioredis.Redis, channel: str) -> None:
    """实际执行 publish，异常静默记录不外抛。"""
    try:
        await client.publish(channel, "1")
    except Exception as e:
        logger.warning(f"发布事件通知失败 channel={channel}: {e}")


async def publish_chapter_status(project_id: str, chapter_number: int) -> None:
    """发布章节状态变更通知（fire-and-forget，不阻塞生成流程）。

    Redis 不可用或未配置时静默跳过。
    """
    client = get_async_client()
    if client is None:
        return
    channel = chapter_status_channel(project_id, chapter_number)
    task = asyncio.create_task(_safe_publish(client, channel))
    _publish_tasks.add(task)
    task.add_done_callback(_publish_tasks.discard)


async def subscribe_chapter_status(
    project_id: str, chapter_number: int
) -> Optional[aioredis.client.PubSub]:
    """订阅单章状态变更 channel，返回 PubSub；Redis 不可用返回 None 供调用方回退轮询。

    调用方负责循环 get_message 并在结束时 await pubsub.aclose()。
    """
    client = get_async_client()
    if client is None:
        return None
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(chapter_status_channel(project_id, chapter_number))
    except Exception as e:
        logger.warning(f"订阅章节状态 channel 失败: {e}")
        await pubsub.aclose()
        return None
    return pubsub


def background_task_channel(user_id: int) -> str:
    """用户后台任务列表变更通知 channel（按 user_id 隔离）。"""
    return f"{_BACKGROUND_TASK_CHANNEL_PREFIX}:{user_id}"


async def publish_background_task(user_id: int) -> None:
    """发布后台任务列表变更通知（fire-and-forget，不阻塞业务流程）。

    Redis 不可用或未配置时静默跳过。
    """
    client = get_async_client()
    if client is None:
        return
    channel = background_task_channel(user_id)
    task = asyncio.create_task(_safe_publish(client, channel))
    _publish_tasks.add(task)
    task.add_done_callback(_publish_tasks.discard)


async def subscribe_background_task(user_id: int) -> Optional[aioredis.client.PubSub]:
    """订阅用户后台任务列表变更 channel，返回 PubSub；Redis 不可用返回 None 供调用方回退轮询。

    调用方负责循环 get_message 并在结束时 await pubsub.aclose()。
    """
    client = get_async_client()
    if client is None:
        return None
    pubsub = client.pubsub()
    try:
        await pubsub.subscribe(background_task_channel(user_id))
    except Exception as e:
        logger.warning(f"订阅后台任务 channel 失败: {e}")
        await pubsub.aclose()
        return None
    return pubsub
