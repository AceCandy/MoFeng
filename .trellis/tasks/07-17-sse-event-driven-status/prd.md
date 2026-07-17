# SSE 章节状态改事件驱动（去每秒查DB轮询）

## Goal

L27 gap：novels.py:307 stream_chapter_status 仍 sleep(1.0) 轮询查DB（每秒），未改事件驱动。并发 UniqueConstraint✅ / 验证码 Redis✅ 已达成。需：SSE 改事件驱动（Celery 任务完成通知 / Redis pub-sub）。依赖 Celery 启用（记忆说 Celery 未集成，#18 是未来准备）。建议等 Celery 启用后处理，或用 Redis pub-sub 解耦。

## Requirements

- TBD

## Acceptance Criteria

- [ ] TBD

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
