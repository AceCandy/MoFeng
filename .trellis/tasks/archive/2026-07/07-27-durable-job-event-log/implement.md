# Durable Job And Event Log Implementation Plan

## Steps

- [x] characterization tests 固定现有 BackgroundTask API、SSE 和 reminder 行为。
- [x] Alembic expand job lease/retry/idempotency 字段并新增 JobEvent；实现 legacy backfill。
- [x] 实现 repository + transition service，所有 state/event 原子写入。
- [x] 实现 claim/fencing、heartbeat、reaper、retry/dead-letter/cancel，以及强制 side-effect class 的 typed handler/activity intent-result registry。
- [x] 建立独立 worker entrypoint、graceful shutdown、health/metrics 和 deploy service。
- [x] 将 outline 与章节后处理从 FastAPI BackgroundTasks 迁入 registry。
- [x] SSE 改为 workflow/job stream DB cursor + Redis wake-up；snapshot 原子返回 revision/cursor，前端保留 polling fallback。
- [x] 加入 production readiness load/recovery/retention/alert gate；失败时停止 cutover 并重开 Temporal 选型。
- [x] shadow/feature flag cutover 后删除本任务产生的旧 executor orphan。

## Validation

```bash
cd backend
pytest tests/test_background_task_service.py tests/test_event_bus.py
pytest tests/test_durable_job_worker.py tests/test_job_event_stream.py
```

必须用 PostgreSQL integration test 验证 `SKIP LOCKED`、fencing、lease expiry、并发 enqueue、snapshot/cursor 边界和 cursor 顺序；必须包含真实 worker 进程 kill/restart，以及 crash-after-external-call 的 provider-dedupe/ambiguous-result 测试。前端运行 task reminder 相关 Vitest。

## Validation Record

- 最终集成复验（2026-07-31）：隔离 PostgreSQL schema 的 backend 全量 `605 passed`，覆盖 claim/fencing、lease 接管、真实进程 kill/restart、activity ambiguity、cursor/reset 与 Redis-off。
- Frontend Vitest `30 files / 263 tests` 通过，AppShell reminder 契约无回归。
- readiness 参数已确认：峰值并发 `20`、双倍演练 `40`、payload `1 MiB`、最长任务 `1800 s`、事件 retention `30 天/100 GiB`、恢复 SLO `300 s`、队列告警 `60 s`、event/projection lag 告警 `300 s`。
- 隔离 PostgreSQL 控制面以 `40` 个 durable jobs/worker 演练，`40/40` 成功，总耗时约 `0.6968 s`、完成 P95 约 `0.6714 s`；`40/40` 过期 lease 接管成功，恢复 P95 约 `0.6868 s`，低于 `300 s` SLO。该结果不代表真实 LLM/provider 吞吐。

## Rollback

- 入口 flag 可停止新任务进入 worker；已 claim 的新任务由 worker drain 完成。
- rollout owner marker、executor generation 和 lease fencing 在同一事务切换；先停止旧 claim，drain 或 expire 旧 lease，再允许新 owner。旧 executor 只处理仍持有其 generation 的 legacy row。
- JobEvent/新字段在兼容窗口保留，回滚代码忽略它们，不做破坏性 downgrade。
