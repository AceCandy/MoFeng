# Replayable Chapter Projections Implementation Plan

## Steps

- [x] 固定现有 finalize/delete/regenerate characterization tests、派生数据 ownership map，以及每类 activity 的 transactional/idempotent_external/ambiguous_external 分类。
- [x] 设计并验证 expand-only Alembic：Chapter revision/source hash/required snapshot、outbox、projection result/checkpoint/artifact generation、rollout marker 与审计 schema；明确 backfill、索引/锁预算、旧新 binary 兼容和 rollback floor。
- [x] 实现带 Chapter `FOR UPDATE`/expected-revision CAS 的 canonical command transaction 与 outbox repository（flush only），覆盖并发冲突、rollback 和 immutable source hash。
- [x] 将 projection/reconciler 注册为现有 durable runtime 的 typed child JobRun handler；固定 payload version/idempotency/workflow stream，禁止新增 claim/lease/retry loop。
- [x] 先实现 summary projection/result cache、activity intent 与 dependency gate，再迁 memory、RAG、foreshadowing 和 trace；所有提交校验 JobRun fencing + revision/hash。
- [x] 将 vector 写入改为 deterministic staging generation + conditional active revision，并移除 adapter 内 commit/session ownership 及按 chapter 无条件删除。
- [x] 实现 required 状态矩阵与 typed reconciler、Chapter successful 原子 transition，以及带 authz/idempotency/audit/rate limit 的 replay/dry-run CLI。
- [x] 迁移 delete/regenerate 为精确 generation 的 tombstone/superseded events，覆盖乱序、迟到和 retention cleanup。
- [x] 接入 backlog/stuck/needs-attention/stale/reconcile/external-call 指标、脱敏日志、告警与 runbook。
- [x] 以 aggregate rollout marker 做 legacy -> shadow -> projection；定义 diff/hash 阈值和观察窗口，验证 owner/generation fencing、lease drain 与 cutover/rollback，并将旧同步副作用严格限制为 legacy owner 的 rollback 路径。

## Validation

```bash
cd backend
TEST_POSTGRES_URL=<postgresql+asyncpg-url> .venv/bin/python -m pytest -q

cd ../frontend
npm run lint
npm run type-check
npm run test:unit
npm run build
```

2026-07-31 最终集成复验：隔离 PostgreSQL schema 的 backend 全量 `603 passed`，
frontend Vitest `30 files / 263 tests`，lint、type-check、production build 与 bundle
budget 通过。64 条 warning 均来自既有 Pydantic v1 兼容写法和 passlib `crypt` 弃用。
14 个真实并发/跨进程用例在完整的 59 表随机 schema 中通过；初始化故障注入确认
schema 不残留，全量结束后 public 业务表与 `test_*` schema 均为 0（仅保留
`job_executor_controls` 基础行）。

PostgreSQL integration tests 必须覆盖：

- 空库/当前库 migration、并发 migration/worker、旧新 binary compatibility 与 rollback floor；
- canonical rollback、并发 revision CAS、双 worker claim、lease expiry/reclaim、失效 fencing token 与独立 OS worker kill/restart；
- summary dependency commit、迟到旧 revision、tombstone/regenerate 乱序、reconciler 并发与唯一 finalized event；
- provider dedupe 与 ambiguous-result needs-attention、每类 artifact crash-after-side-effect、vector active generation 原子切换；
- replay authz/idempotency/audit/rate limit、stale replay、retention cleanup；
- shadow diff、owner/generation cutover/rollback、outbox backlog 恢复以及指标/告警触发与恢复。

SQLite/mock 只能覆盖纯逻辑，不能作为 locking、lease、migration、event ordering 或恢复证据。现有 router 静态测试只在行为 owner 改变时更新，不为通过测试保留错误边界。

## Rollback

- 暂停 consumer，outbox 保留等待恢复。
- rollout marker + owner/generation 决定某个 Chapter revision 由旧同步 path 或新 projections 写 active artifact，禁止双 owner；切换前 drain/expire lease。
- canonical revision/outbox 不做破坏性 downgrade；回滚 binary 必须兼容新 schema、忽略未知 event version 并遵守 readiness rollback floor。
- 已提交的新 revision/result/artifact generation 保留；回滚只切 owner，replay/reconcile 用于修复 backlog，不让旧路径重做已拥有的副作用。
