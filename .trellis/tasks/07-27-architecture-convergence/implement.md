# Architecture Convergence Execution Plan

## Gate 0 - Planning Review

- [ ] 父任务与七个子任务的 requirement、dependency、rollback 和 acceptance contract 完整。
- [ ] `research/durable-runtime-selection.md` 已记录选型与反证条件。
- [ ] 用户批准最新规划摘要后，只启动第一个 child；父任务保持 planning/integration owner。

## Phase 1 - Canonical Context

- [ ] 启动 `07-27-canonical-chapter-context`。
- [ ] 建立版本化 context contract、resolver 与 prompt adapters。
- [ ] pipeline/writer/consistency 切到同一 builder，保留独立纯映射的 shadow oracle。
- [ ] 用 contract/golden/fallback tests 验证后归档 child。
- Rollback：私有 builder 仅在旧视图 shadow 对比与其他入口 contract/wiring tests 完成后原子替换；失败时整体 git revert 该无 schema/数据迁移的发布变更，不长期维护双 DB 读取路径。

## Phase 2 - Explicit Database Bootstrap

- [ ] 启动 `07-27-explicit-database-bootstrap`。
- [ ] 拆出 create/migrate/bootstrap/readiness CLI 与 versioned data bootstrap。
- [ ] 更新 compose/deploy 顺序，API/worker runtime 只读校验。
- [ ] 验证空库、当前库、旧库、并发启动和重复 bootstrap。
- Rollback：部署脚本可临时调用兼容入口；不恢复多进程同时 mutation。

## Phase 3 - Durable Job And Event Log

- [ ] 启动 `07-27-durable-job-event-log`。
- [ ] Alembic 增加 JobRun lease/retry/idempotency 字段与 append-only JobEvent。
- [ ] 实现原子 claim、heartbeat、reaper、retry/dead-letter 和 worker 进程。
- [ ] 将 FastAPI BackgroundTasks 入口迁移为 enqueue；Redis 降为 wake-up。
- [ ] SSE 增加 cursor replay、retention/reset 与 owner authorization。
- [ ] 执行 worker kill/restart、双 worker claim、Redis-off、SSE reconnect 测试。
- Rollback：停止 worker、切回旧 executor 仅处理尚未由新 worker claim 的兼容任务。

## Phase 4 - Replayable Projections

- [ ] 启动 `07-27-replayable-chapter-projections`。
- [ ] 增加 Chapter revision/outbox/projection checkpoint/status schema。
- [ ] 将 finalize/delete/regenerate 的 memory、RAG、伏笔与 trace 写入 projection consumers。
- [ ] 移除主事务中的跨 session vector commit；加入 replay/reconcile 管理入口。
- [ ] 验证重复、乱序、失败重试、delete tombstone 和 backlog gate。
- Rollback：暂停 consumer，保留 outbox；旧同步路径只能在未 cutover aggregate 上启用。

## Phase 5 - Durable Chapter Workflow

- [ ] 启动 `07-27-durable-chapter-workflow`。
- [ ] 锁定与 `langgraph==1.2.2` 兼容的 PostgreSQL checkpointer。
- [ ] 将 pipeline/finalize 拆成可序列化、幂等 workflow nodes 与 command interrupt。
- [ ] 新建异步 start/status/command API，旧 endpoint 作为兼容 adapter。
- [ ] trace 改为 event projection，切断 trace-as-recovery。
- [ ] 执行三个 checkpoint 的进程终止/恢复、重复 command、LLM step 防重测试。
- Rollback：入口切回旧 workflow；新 run 继续由新 worker drain，不让两套 executor 争抢。

## Phase 6 - Generated Transport Contracts

- [ ] 启动 `07-27-generated-transport-contracts`。
- [ ] 导出确定性 OpenAPI artifact，接入 `openapi-typescript` script 与 CI drift gate。
- [ ] workflow/job/chapter DTO 改用 generated types，保留单一 domain mapper。
- [ ] 为 SSE event 增加 runtime decoder 与 schema version handling。
- [ ] 删除 `novel.ts`/`admin.ts` 重复 wire types并通过 type-check/tests。
- Rollback：生成物可回退到上一 schema commit；API adapter 保持字段兼容窗口。

## Phase 7 - WritingDesk Statechart

- [ ] 启动 `07-27-writing-desk-statechart`。
- [ ] 引入并锁定 XState 与 Vue binding，先建立 pure machine/model tests。
- [ ] 通过 actors 接入 Vue Query mutations、snapshot query 和 SSE decoder。
- [ ] 迁移生成/评审/选版/定稿/projection/retry/reconnect，移除散落 refs/watchers。
- [ ] 验证刷新恢复、断线补事件、重复点击、stale event、失败重试和 a11y 状态提示。
- Rollback：路由/feature flag 切回 legacy composables，server workflow 不回滚。

## Final Integration Gate

- [ ] 所有 child 均完成独立 quality check 和 spec update。
- [ ] PostgreSQL 集成测试覆盖 claim fencing、outbox atomicity、projection replay 和 checkpoint resume。
- [ ] 前后端集成覆盖 API → job → workflow → projection → SSE → statechart。
- [ ] `git diff` 仅包含七个子任务与必要 spec/deploy 变更；无缓存、密钥或调试产物。
- [ ] 明确记录未运行的测试及任何预存在失败，不越界修复。
- [ ] 最终 rollback drill 证明入口可回切且不会双执行。

## Validation Commands

实际命令以各 child 的 `implement.md` 和当时项目脚本为准。Java 约束不适用于本项目；Python/TypeScript 验证在每个 child 内按风险执行，不等到父任务末尾一次性补跑。

建议的全链路门禁：

```bash
cd backend && pytest tests/<child-focused-tests>
cd frontend && npm run type-check
cd frontend && npm run test:unit -- <child-focused-tests>
cd frontend && npm run lint
```

数据库并发与恢复验证必须使用 PostgreSQL/testcontainers；SQLite 不能证明 `SKIP LOCKED`、lease fencing、pgvector 或 Alembic 行为。
