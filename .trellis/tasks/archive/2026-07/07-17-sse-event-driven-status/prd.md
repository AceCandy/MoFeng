# SSE 章节状态改事件驱动（去每秒查DB轮询）

## Goal

L27 gap：novels.py:307 stream_chapter_status 仍 sleep(1.0) 轮询查DB（每秒），未改事件驱动。并发 UniqueConstraint✅ / 验证码 Redis✅ 已达成。需：SSE 改事件驱动（Celery 任务完成通知 / Redis pub-sub）。依赖 Celery 启用（记忆说 Celery 未集成，#18 是未来准备）。建议等 Celery 启用后处理，或用 Redis pub-sub 解耦。

## Requirements

- SSE 章节状态推送改事件驱动（Redis pub-sub），去每秒查 DB 轮询。详见 design.md。
- 前提修正：Celery 已集成（emotion/foreshadowing tasks），但章节生成是 async（LangGraph）非 Celery，故用 Redis pub-sub 解耦，不依赖 Celery 启用。

## Acceptance Criteria

- [x] stream_chapter_status（novels.py:307）去掉 asyncio.sleep(1.0) 轮询，改 Redis pub-sub subscribe 推送
- [x] 章节状态变更点（_set_chapter_generation_state + _mark_generation_failed + _mark_generation_failed_resume）publish 到 Redis channel
- [x] SSE subscribe 前查 DB 发初始态（pub-sub 消息丢失兜底）
- [x] Redis 不可用时 SSE 降级（回退轮询 or 前端重连），不阻塞生成流程
- [x] 真机 SSE 端到端验证通过（SQL 模拟状态变更+publish，覆盖 active[generating]+terminal[successful] 推送+终态关闭；完整 LLM 生成全流程同机制，留用户真机确认）
- [ ] （可选）stream_background_tasks（tasks.py:48）同方案改造去 1.5s 轮询

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
