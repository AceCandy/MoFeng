# Durable Chapter Workflow Implementation Plan

## Gate 0 - Dependency And Contract Preflight

- [x] 以已选 `langgraph-checkpoint-postgres==3.1.0` 为基线，用 wheel/source核验 `langgraph==1.2.2` 与 Psycopg 3的精确兼容矩阵，锁定 direct/transitive builds并记录许可证/目标平台wheel可用性；真实PostgreSQL smoke失败即停止并重开设计，禁止 memory fallback。
- [x] 固化 Graph V1 node/state/command/event schema及 legacy node映射；为 run、root JobRun、Chapter、projection分别标注唯一事实源。
- [x] 为 workflow锁序、waiting semantics、ambiguous manual retry和checkpointer Alembic ownership补充 backend spec；实现前不得保留相互冲突的“可能自动重调 provider”描述。

## Phase 1 - Expand Persistence

- [x] 新增 `ChapterWorkflowRun`、`ChapterWorkflowCommand` ORM/schema/repository，partial active unique、status/check约束、command idempotency和root job FK。
- [x] Alembic expand revision创建 workflow表与 pinned vendor checkpoint四表/版本行；加入模型/schema/索引收敛测试，downgrade拒绝破坏已有 workflow history。
- [x] 扩展 `db-check` 验证 checkpointer schema/version和binary rollback floor；API/worker static test禁止调用 `AsyncPostgresSaver.setup()`。
- [x] 为随机 PostgreSQL schema/database同时配置 asyncpg和Psycopg search path；故障注入证明建表/seed/连接失败仍清理命名空间与连接。

## Phase 2 - Extend The Existing Durable Runtime

- [x] `JobService`/repository加入 internal `waiting`、fenced wait/resume及claim排除；public compatibility把 waiting映射为 queued。
- [x] 让 activity可显式声明既有 side-effect class；canonical request不一致时失败关闭；`complete_activity`支持同 transaction的 fenced `outcome_writer`。
- [x] 建立唯一 workflow transition adapter，使 retry/wait/resume/ambiguity/cancel/success/failure与run状态、active slot、JobEvent原子同步。
- [x] 为 ambiguous activity实现仅由审计 command触发的 retry_external/cancel；原row不可变，新intent由command id稳定派生并要求possible-duplicate acknowledgement；普通 worker reclaim、retry和graph replay均不得重调 provider。
- [x] 单元/PostgreSQL测试覆盖 stale fence、activity replay、waiting无claim、atomic transition、并发 active slot和既有 projection job无回归。

## Phase 3 - Build Workflow Core

- [x] 实现 start service：锁 Chapter，返回已有 active run或原子创建 run + workflow stream + root JobRun；冻结请求/runtime input identity。
- [x] 建立版本化 serializable Graph V1 state和graph registry；接入 `AsyncPostgresSaver`、稳定 thread id及旧 version routing。
- [x] 将 canonical context分为 base freeze与retrieval activity，持久化 snapshot/hash；checkpoint只保存reference/hash。
- [x] 把现有 plan/generate/review/post-review拆成 pure或typed activities；候选 ordinal/stage使用稳定 activity key，完整结果保持private。
- [x] 用 transactional activity原子持久化候选版本；移除新 workflow对trace重建、`clear_from_node`和不可序列化 runtime object的依赖。
- [x] 实现 graph interrupt、root wait outcome和同一 thread resume；worker handler不得在人工/projection等待期间持有lease。
  - [x] Graph V1 完整拓扑使用显式 runtime bindings；选版与 projection 节点使用真实 `interrupt()`，同一 PostgreSQL thread 可跨 saver 恢复且不重跑前序节点。
  - [x] worker 将 `JobWaitOutcome` 作为一等执行结果，以当前 fence 提交 root wait/run/event并释放 lease，之后不再提交 success。
  - [x] 装配 production context/model/candidate persistence bindings并注册精确的 `chapter_workflow/v1` handler；真实 PostgreSQL 集成测试证明生产装配只写一份候选并释放 selection wait lease。
  - [x] 装配 command/finalize/projection bindings；新 workflow start API入口保持关闭，未实现节点失败关闭，禁止空 binding fallback。

## Phase 4 - Commands And Recovery

- [x] 实现 command service/envelope、expected run/Chapter/checkpoint验证、accepted/rejected/applied event和duplicate replay。
  - [x] 严格 command envelope、owner与 expected run/Chapter/checkpoint 锁内验证；accepted/rejected 持久审计、waiting root/run 原子 requeue、同 command id replay 与并发 stale command 已覆盖真实 PostgreSQL 测试。
  - [x] ambiguous retry_external/cancel 补齐 applied/rejected 审计事件；manual retry 仅复制 hash-only canonical provider identity，非规范私有 payload 失败关闭。
  - [x] select/retry_projection 的 applied result 由 checkpoint marker handshake 持久化；普通 retry 仍归下一项的确定失败规则。
- [x] 实现 command checkpoint marker handshake；注入 checkpoint后/inbox apply前崩溃，证明只补状态不重复resume。
- [x] 实现 running/waiting cancel、automatic retry、terminal explicit retry/successor规则及 allowed-command snapshot；区分确定失败 `retry` 与 ambiguous `retry_external`，拒绝人工注入provider result。
- [x] 实现 stale-run reconciler和稳定 reason codes，覆盖 JobRun/run/checkpoint/Chapter/projection不一致矩阵。

## Phase 5 - Finalize And Projection Bridge

- [x] 拆分 finalize prepare/commit boundary，给 `create_finalize`增加已有 workflow stream参数；legacy submit行为保持兼容。
- [x] finalize transactional activity在 root fence下验证 expected revision并原子写 selected content、revision、outbox、dispatcher和activity result。
- [x] 断言 dispatcher、summary/downstream/reconciler jobs全部继承 `run_id` stream；workflow自身不写 Chapter successful。
- [x] 实现无长lease的 projection resumer及 `retry_projection` command，处理 success/failed/superseded/tombstone。
- [x] 按 root JobRun→run→Chapter与既有 projection aggregate锁序增加确定性并发等待队列/无死锁测试。

## Phase 6 - API, Compatibility And Observability

- [x] 新增 start/snapshot/command Pydantic contracts、service DI和writer routes；owner授权、404同形、stale 409 current snapshot完整测试。
- [x] generate/finalize/select adapters路由到同一 run；旧 job drain期间保留 legacy handler，不允许双 executor。
- [x] 将 generation trace改为 JobEvent cursor幂等投影；新 run删除trace或暂停projector仍可完整恢复。
  - [x] PostgreSQL 覆盖原子回滚、幂等重放、删除后重建、隐私白名单、malformed event、双连接锁竞争与 retention watermark；定向回归 5 passed。
  - [x] 相关 Ruff、Black、Mypy、compileall 与 `git diff --check` 通过；既有 readiness/migration 大测试文件的 I001 不在本项扩大处理。
- [x] 增加 workflow state/age、waiting duration、command rejection、needs-attention、checkpoint/projection lag和reconciler修复 metrics/alerts。
- [x] 实现 terminal workflow retention与幂等 cleanup；只删除checkpoint/私有payload，保护 active、needs-attention、current revision、activity identity、AI usage/cost、outbox和审计。

## Phase 7 - Rollout And Contract

- [x] 新 start默认关闭；隔离数据库shadow、真实进程kill/restart、Redis-off与rolling-worker本地演练已通过，入口保持关闭。
- [x] 本地切换 executor generation，旧 queued job安全reassign、旧 running lease受fence保护；数据库断言同章active run与有效root lease均为1，stale outcome未写入。
- [ ] 一个发布窗口后删除新路径不再使用的router编排和trace recovery；保留仍有active run的Graph V1及legacy payload handler。
- [x] 冻结 OpenAPI/JobEvent shape，作为 generated transport contracts子任务输入。

## Validation

```bash
cd backend
pytest tests/test_chapter_workflow_migration.py tests/test_database_readiness.py
pytest tests/test_chapter_workflow_graph.py tests/test_chapter_workflow_commands.py
pytest tests/test_chapter_workflow_start.py tests/test_chapter_workflow_reconciliation.py
pytest tests/test_chapter_workflow_activities.py tests/test_chapter_workflow_persistence.py
pytest tests/test_chapter_workflow_projection_bridge.py tests/test_chapter_workflow_retention.py
pytest tests/test_durable_job_runtime.py tests/test_durable_job_worker.py tests/test_job_event_stream.py
pytest tests/test_chapter_projection_outbox.py tests/test_chapter_projection_runtime.py tests/test_chapter_projection_rollout_integration.py
pytest tests/test_chapter_context_contract.py tests/test_chapter_context_resolver.py tests/test_pipeline_context_restore.py
pytest tests/test_pipeline_langgraph_refactor_static.py tests/test_confirm_finalize_router_static.py
pytest

cd ../frontend
npm run lint
npm run type-check
npm run test:unit
npm run build
npm run check:bundle-budget
```

最终集成复验（2026-07-31）：隔离 PostgreSQL schema 的 backend 全量
`603 passed`，本任务聚焦回归 `15 passed`；provider 透传、AC8、真实进程
kill/restart、Redis-off 与 executor generation rolling 均包含在全量结果中。
Frontend ESLint、TypeScript、production build 和 bundle budget 通过，Vitest
`30 files / 263 tests`，Playwright desktop/mobile `20 passed`；仅保留 64 条既有
Pydantic/passlib 弃用 warning。

Mypy 配置范围 20 个文件、dirty Python Ruff、compileall 和
`git diff --check` 均通过。dirty Python Black 共检查 71 个文件，继续
排除三个既有大文件 `app/core/config.py`、`app/api/routers/writer.py`、
`app/services/chapter_projection_rollout.py`，不在本任务制造全文件格式化
churn。最终 PostgreSQL 只读审计确认：临时数据库 0、`test_*` schema 0、
测试连接 0；配置业务库 `users=1`，业务任务 `failed=1, succeeded=4`，
无测试 worker 残留。

三个恢复点必须使用真实 PostgreSQL checkpoint和独立OS worker进程执行 terminate/restart；mock graph、共享savepoint或静态源码断言不能单独证明durable execution。并发锁测试使用随机隔离schema/独立连接，并验证无 `test_*` schema、public业务行、临时数据库、构建目录或调试进程残留。

## Review Gates

- [x] 独立实现审查：事实源、transaction ownership、锁序、activity ambiguity、command handshake、migration/runtime DDL边界。
- [x] 独立测试审查：每条 AC有非同义反复的行为测试；kill/restart与deadlock证据来自真实连接/进程。
- [x] Spec更新后执行全量 backend/frontend门禁；只记录既有弃用warning，不顺手处理。
- [x] 按 Trellis Phase 3.4单独展示提交计划并取得用户批准；禁止 push。

## Rollback

- 关闭新 start并切 legacy adapter；新 workflow worker/graph versions继续 drain现有run。
- 不删除workflow/checkpoint schema，不调用 destructive downgrade；用 `db-check` rollback floor阻止旧binary误读。
- 不把已有candidate/revision/outbox交给legacy path重做；ambiguous/needs-attention run保持fenced直到显式处理。
