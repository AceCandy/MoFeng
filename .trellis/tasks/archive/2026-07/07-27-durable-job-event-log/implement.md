# Durable Job And Event Log Implementation Plan

## Steps

- [ ] characterization tests 固定现有 BackgroundTask API、SSE 和 reminder 行为。
- [ ] Alembic expand job lease/retry/idempotency 字段并新增 JobEvent；实现 legacy backfill。
- [ ] 实现 repository + transition service，所有 state/event 原子写入。
- [ ] 实现 claim/fencing、heartbeat、reaper、retry/dead-letter/cancel，以及强制 side-effect class 的 typed handler/activity intent-result registry。
- [ ] 建立独立 worker entrypoint、graceful shutdown、health/metrics 和 deploy service。
- [ ] 将 outline 与章节后处理从 FastAPI BackgroundTasks 迁入 registry。
- [ ] SSE 改为 workflow/job stream DB cursor + Redis wake-up；snapshot 原子返回 revision/cursor，前端保留 polling fallback。
- [ ] 加入 production readiness load/recovery/retention/alert gate；失败时停止 cutover 并重开 Temporal 选型。
- [ ] shadow/feature flag cutover 后删除本任务产生的旧 executor orphan。

## Validation

```bash
cd backend
pytest tests/test_background_task_service.py tests/test_event_bus.py
pytest tests/test_durable_job_worker.py tests/test_job_event_stream.py
```

必须用 PostgreSQL integration test 验证 `SKIP LOCKED`、fencing、lease expiry、并发 enqueue、snapshot/cursor 边界和 cursor 顺序；必须包含真实 worker 进程 kill/restart，以及 crash-after-external-call 的 provider-dedupe/ambiguous-result 测试。前端运行 task reminder 相关 Vitest。

## Rollback

- 入口 flag 可停止新任务进入 worker；已 claim 的新任务由 worker drain 完成。
- rollout owner marker、executor generation 和 lease fencing 在同一事务切换；先停止旧 claim，drain 或 expire 旧 lease，再允许新 owner。旧 executor 只处理仍持有其 generation 的 legacy row。
- JobEvent/新字段在兼容窗口保留，回滚代码忽略它们，不做破坏性 downgrade。
