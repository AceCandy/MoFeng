# Architecture Convergence Execution Plan

## Gate 0 - Planning Review

- [x] 父任务与七个子任务的 requirement、dependency、rollback 和 acceptance contract 完整。
- [x] `research/durable-runtime-selection.md` 已记录选型与反证条件。
- [x] 用户批准最新规划摘要后，按依赖顺序执行并归档七个 child。

## Phase 1 - Canonical Context

- [x] 启动并归档 `07-27-canonical-chapter-context`。
- [x] 建立版本化 context contract、resolver 与 prompt adapters。
- [x] pipeline/writer/consistency 切到同一 builder，保留独立纯映射的 shadow oracle。
- [x] 用 contract/golden/fallback tests 验证后归档 child。
- Rollback：私有 builder 仅在旧视图 shadow 对比与其他入口 contract/wiring tests 完成后原子替换；失败时整体 git revert 该无 schema/数据迁移的发布变更，不长期维护双 DB 读取路径。

## Phase 2 - Explicit Database Bootstrap

- [x] 启动并归档 `07-27-explicit-database-bootstrap`。
- [x] 拆出 create/migrate/bootstrap/readiness CLI 与 versioned data bootstrap。
- [x] 更新 compose/deploy 顺序，API/worker runtime 只读校验。
- [x] 验证空库、当前库、旧库、并发启动和重复 bootstrap。
- Rollback：部署脚本可临时调用兼容入口；不恢复多进程同时 mutation。

## Phase 3 - Durable Job And Event Log

- [x] 启动并归档 `07-27-durable-job-event-log`。
- [x] Alembic 增加 JobRun lease/retry/idempotency 字段与 append-only JobEvent。
- [x] 实现原子 claim、heartbeat、reaper、retry/dead-letter 和 worker 进程。
- [x] 将 FastAPI BackgroundTasks 入口迁移为 enqueue；Redis 降为 wake-up。
- [x] SSE 增加 cursor replay、retention/reset 与 owner authorization。
- [x] 执行 worker kill/restart、双 worker claim、Redis-off、SSE reconnect 测试。
- Rollback：停止 worker、切回旧 executor 仅处理尚未由新 worker claim 的兼容任务。

## Phase 4 - Replayable Projections

- [x] 启动并归档 `07-27-replayable-chapter-projections`。
- [x] 增加 Chapter revision/outbox/projection checkpoint/status schema。
- [x] 将 finalize/delete/regenerate 的 memory、RAG、伏笔与 trace 写入 projection consumers。
- [x] 移除主事务中的跨 session vector commit；加入 replay/reconcile 管理入口。
- [x] 验证重复、乱序、失败重试、delete tombstone 和 backlog gate。
- Rollback：暂停 consumer，保留 outbox；旧同步路径只能在未 cutover aggregate 上启用。

## Phase 5 - Durable Chapter Workflow

- [x] 启动并归档 `07-27-durable-chapter-workflow`。
- [x] 锁定与 `langgraph==1.2.2` 兼容的 PostgreSQL checkpointer。
- [x] 将 pipeline/finalize 拆成可序列化、幂等 workflow nodes 与 command interrupt。
- [x] 新建异步 start/status/command API，旧 endpoint 作为兼容 adapter。
- [x] trace 改为 event projection，切断 trace-as-recovery。
- [x] 执行三个 checkpoint 的进程终止/恢复、重复 command、LLM step 防重测试。
- Rollback：入口切回旧 workflow；新 run 继续由新 worker drain，不让两套 executor 争抢。

## Phase 6 - Generated Transport Contracts

- [x] 启动并归档 `07-27-generated-transport-contracts`。
- [x] 导出确定性 OpenAPI artifact，接入 `openapi-typescript` script 与 CI drift gate。
- [x] workflow/job/chapter DTO 改用 generated types，保留单一 domain mapper。
- [x] 为 SSE event 增加 runtime decoder 与 schema version handling。
- [x] 删除 `novel.ts`/`admin.ts` 重复 wire types并通过 type-check/tests。
- Rollback：生成物可回退到上一 schema commit；API adapter 保持字段兼容窗口。

## Phase 7 - WritingDesk Statechart

- [x] 启动并归档 `07-27-writing-desk-statechart`。
- [x] 引入并锁定 XState 与 Vue binding，先建立 pure machine/model tests。
- [x] 通过 actors 接入 Vue Query mutations、snapshot query 和 SSE decoder。
- [x] 迁移生成/评审/选版/定稿/projection/retry/reconnect，移除散落 refs/watchers。
- [x] 验证刷新恢复、断线补事件、重复点击、stale event、失败重试和 a11y 状态提示。
- Rollback：路由/feature flag 切回 legacy composables，server workflow 不回滚。

## Final Integration Gate

- [x] 所有 child 均完成独立 quality check 和 spec update。
- [x] PostgreSQL 集成测试覆盖 claim fencing、outbox atomicity、projection replay 和 checkpoint resume。
- [x] 分层集成覆盖 API → job → workflow → projection → SSE → statechart。
- [x] 任务相关 diff 仅包含本任务修复与验收记录；工作树另有未由本任务产生的 `.agents/`、`.claude/` 工具目录变更，未纳入本任务；无缓存、密钥或调试产物。
- [x] 已记录未运行门禁和既有弃用 warning，未越界修复。
- [x] 最终 rollback drill 证明入口可回切且不会双执行。
- [ ] 生产 readiness：记录预期峰值/载荷轮廓，通过至少 2 倍目标负载与显式恢复 SLO 演练。

## Integration Evidence (2026-07-31)

- Backend: 基于隔离 PostgreSQL schema 的全量测试 `605 passed`；包含空库/current/legacy migration、并发 bootstrap、claim/fencing、独立进程 kill/restart、cursor/reset、outbox/projection replay、checkpoint resume 与 rollback 覆盖。
- Frontend: ESLint、`vue-tsc`、OpenAPI/generated ownership 门禁通过；Vitest `30 files / 263 tests` 通过。
- Browser: Playwright WritingDesk workflow 桌面/移动端 `20 passed`；由 Playwright 管理的 WebServer 已退出。
- Python: 本轮受影响文件 Ruff 通过，mypy 配置范围 `20 source files` 通过；Black 对这些文件仍报告仓库原有格式差异，未运行全文件格式化以避免无关 diff。
- Readiness 参数已确认并写入 `backend/app/core/config.py`、`backend/env.example`、`deploy/.env.example` 与 Compose：峰值并发 `20`、双倍演练并发 `40`、payload `1 MiB`、最长任务 `1800 s`、事件 retention `30 天/100 GiB`、恢复 SLO `300 s`、队列告警 `60 s`、event/projection lag 告警 `300 s`。
- Durable runtime 控制面演练（隔离 PostgreSQL，40 个 durable jobs/40 个 worker）：`40/40` 成功，总耗时约 `0.6968 s`，完成 P95 约 `0.6714 s`；`40/40` 过期 lease 接管成功，恢复 P95 约 `0.6868 s`，低于 `300 s` SLO。该演练验证 durable control plane，不等同于真实 LLM/provider 吞吐演练。
- Retention、payload 上限、queue/event/projection lag、expired lease、dead-letter 和 retention budget 告警均有定向测试与 worker metrics 输出；未修改或迁移用户现有数据库。
- 既有非阻断项：全量测试报告 `73` 条 Pydantic v1 兼容/passlib `crypt` 弃用 warning。

## Residual Risks / Rollout Preconditions

- 本轮 AC11 只证明 durable control plane 的 2x synthetic load、lease recovery、指标和告警；真实 LLM/provider 吞吐、provider 费用和模型侧限流仍需在独立发布窗口验证。
- `JOB_MAX_DURATION_SECONDS` 与 `JOB_RECOVERY_SLO_SECONDS` 当前是显式 readiness profile 和 metrics 输出；它们不隐式改变 provider timeout、lease 或 retry 策略。
- `retained_event_bytes` 是 `JobEvent.payload` 的 PostgreSQL 存储字节数信号，不是完整 relation/index 的物理占用；需要容量预算时应另做备份/恢复和表膨胀演练。
- legacy router/trace recovery adapter 仍处于兼容窗口；必须在发布窗口观察、回切演练和数据审计完成后，单独执行 contract 删除，不能在本次收尾中提前删除。

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
