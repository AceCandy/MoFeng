# SSE 章节状态改事件驱动 - 技术方案

## 现状

- `novels.py:307 stream_chapter_status`：每秒轮询 DB（`asyncio.sleep(1.0)`），JSON 快照去重后推送；前端写作台单章状态依赖此 SSE。
- `tasks.py:48 stream_background_tasks`：每 1.5 秒轮询 DB（`asyncio.sleep(1.5)`），全局任务日志角标依赖此 SSE。**同样轮询问题，建议同方案改造**。
- 章节生成是 async（`pipeline_orchestrator.PipelineOrchestrator.generate_chapter` 用 LangGraph `graph.ainvoke`），**非 Celery**（Celery 仅用于 emotion/foreshadowing 后台任务）。
- Redis 已用（`cache_service.CacheService`，同步 `redis.from_url` 客户端，仅 get/set 情感曲线/任务状态，**无 pub-sub**）。

## 目标

SSE 改事件驱动（Redis pub-sub），去掉每秒查 DB 轮询。

## 方案：Redis pub-sub

### channel 设计

- `chapter:status:{project_id}:{chapter_number}`：单章状态变更 channel。
- publish 内容：章节状态快照 JSON（与当前 `get_chapter_schema` 返回结构一致，前端零适配）。

### publish 点（pipeline_orchestrator.py）

章节状态在此三处变更，均加 publish：

- `_set_chapter_generation_state`（L809）：进度/步骤/状态（generating/evaluating/selecting/finalizing）变更时 publish。
- `_mark_generation_failed`（L667）：status=failed 时 publish。
- `_mark_generation_failed_resume`（L323）：resume 失败 status=failed 时 publish。

publish 在 async 生成流程内调用，用 `asyncio.create_task` 或 `to_thread` 非阻塞发出（不等待订阅者）。

### SSE subscribe 改造（stream_chapter_status, novels.py:307）

1. 初始：查 DB 一次，发初始状态快照（覆盖 subscribe 前的状态）。
2. 订阅 `chapter:status:{project_id}:{chapter_number}` Redis channel，收到事件即推送。
3. 去掉 `asyncio.sleep(1.0)` 轮询循环。
4. 终态（waiting_for_confirm/successful/failed/evaluation_failed）收到后 break 关闭 SSE。

### Redis 客户端

- 现有 `cache_service` 用同步 `redis.from_url`。
- pub-sub subscribe 是阻塞长连接，需 `redis.asyncio` 客户端（async subscribe）。
- 建议：新增 async Redis 客户端（`redis.asyncio.from_url`）专用于 pub-sub；publish 可复用同步客户端（在 to_thread）或 async 客户端。

## 风险

- **Redis 不可用**：SSE 降级。方案：subscribe 失败时回退轮询（保留 sleep 但拉长间隔，如 5s），或前端检测断开重连。需明确降级策略。
- **pub-sub 消息丢失**：subscribe 前 publish 的事件丢失。DB 初始态查询兜底（subscribe 前先查 DB 发初始状态）。
- **影响核心功能**：章节生成状态推送是写作台核心体验，需真实环境验证生成全流程（generating->evaluating->selecting->finalizing->successful/failed）状态推送正确。
- **publish 非阻塞**：确保 publish 不阻塞生成流程（生成是 async，publish 用 fire-and-forget）。

## 依赖

- Redis 必须可用（`settings.redis_url` 配置）。当前 cache_service 在 Redis 不可用时禁用缓存；SSE 需明确降级策略。
- 不依赖 Celery（章节生成是 async，publish 在 async 流程内）。

## 验证清单

- [ ] publish 点覆盖所有状态变更（generating/evaluating/selecting/finalizing/successful/failed/evaluation_failed）。
- [ ] SSE subscribe 收到事件即推送，无轮询。
- [ ] subscribe 前查 DB 发初始态（消息丢失兜底）。
- [ ] Redis 断开降级（回退轮询 or 前端重连）。
- [ ] 真实章节生成全流程状态推送正确（写作台 SSE 实时更新）。
- [ ] `stream_background_tasks`（tasks.py:48）同方案改造（可选，同轮询问题）。

## 实施步骤（建议拆分）

1. 新增 async Redis pub-sub 封装（`app/services/event_bus.py` 或扩展 cache_service）：publish + subscribe。
2. pipeline_orchestrator 三处状态变更加 publish。
3. stream_chapter_status 改 subscribe + DB 初始态兜底 + 降级。
4. 真实环境验证生成全流程。
5. （可选）stream_background_tasks 同方案改造。
