# Architecture Convergence Design

## 1. First Principles

必须同时成立的事实：

1. PostgreSQL 是 Chapter canonical state 的事实源。
2. LLM、embedding 与进程执行都可能超时、重复或在响应前后崩溃。
3. “发过通知”不等于“状态已持久化”，“数据库里有任务行”也不等于“存在可接管的执行者”。
4. 派生数据可以最终一致，但必须知道它源自哪个 Chapter revision，并且能够重放到正确状态。
5. 前端只能消费服务端事实，不能靠本地布尔值猜测长流程走到哪一步。

因此目标不是给现有函数再包一层，而是建立三个清晰且不互相替代的事实边界：

- Chapter aggregate：正文、选版、revision 与生命周期事实。
- durable job/workflow state：执行、checkpoint、command、lease 与 retry 事实。
- append-only events：Chapter outbox 是 aggregate-scoped 内部领域事实；JobEvent 是 run/job-scoped 用户事件流。outbox 必须经 projection bridge 才能进入用户事件流，UI 不直接消费 outbox。

## 2. Target Topology

```text
HTTP API
  |  submit command / read snapshot
  v
Application command service ---- same PostgreSQL transaction ----+
  |                                                            |
  +--> Chapter aggregate / JobRun current state                 |
  +--> JobEvent append-only log                                 |
  +--> ChapterOutbox event -------------------------------------+

PostgreSQL claim + optional Redis wake-up
  |
  v
Independent worker
  +--> LangGraph PostgreSQL checkpoint (thread_id = workflow run id)
  +--> idempotent step result store
  +--> external LLM / embedding activities
  +--> projection consumers (memory / RAG / foreshadowing / trace)
  |
  +--> append JobEvent / projection status in PostgreSQL

SSE endpoint -- cursor reads JobEvent --> typed event decoder --> WritingDesk statechart
```

Redis 只缩短“数据库已有新事件”到消费者被唤醒的时间。轮询或 worker scan 是可靠后备，删除 Redis 后系统行为仍正确。

## 3. Runtime Selection

选择 PostgreSQL durable runtime，完整论证见 `research/durable-runtime-selection.md`。

LangGraph checkpointer 只保存 graph thread 状态，不替代 job queue。项目仍需实现 claim、lease、heartbeat、retry、dead-letter、command inbox 和事件日志。反过来，job queue 也不替代 graph checkpoint；二者分别解决“谁来执行”和“从哪里继续”。

自建 runtime 在 production cutover 前必须完成容量基线、2 倍目标负载、恢复 SLO、retention cleanup、备份恢复、指标告警和 kill/restart 演练。任何门禁失败，或新增需求超出当前短流程 command model，都必须暂停扩展并重新比较 Temporal，不能用继续加调度原语默认解决。

Temporal 的升级判断以能力触发，不以本轮进度触发。不得在本轮同时实现两套 control plane。

## 4. Core Contracts

### 4.1 Canonical Chapter Context

`ChapterContext` 是可序列化、版本化的 Pydantic contract，至少包含：

- `schema_version`
- `project_id`, `chapter_number`, `source_revision`
- writer-visible blueprint 与 chapter outline/mission
- previous chapter summary/tail 与 completed chapter summaries
- project memory、constitution、persona
- pending foreshadows、active plot threads
- related RAG chunks/summaries
- 每段的 provenance、truncation 与 fallback metadata

Context resolver 负责 DB/RAG 查询和预算策略；prompt adapters 只把同一 contract 渲染为 generation/review/consistency 所需视图。caller 不再自行查询或拼接业务字段。

每个 workflow run 在开始阶段持久化 context snapshot/hash。恢复沿用同一 snapshot；只有显式“以最新上下文重新开始”才创建新 revision/run。

### 4.2 JobRun

`JobRun` 是执行控制记录，概念字段为：

- identity：`id`, `job_type`, `payload_version`, `idempotency_key`, owner/project scope
- lifecycle：`queued`, `running`, `retry_wait`, `succeeded`, `failed`, `cancelled`, `dead_letter`
- scheduling：`available_at`, `attempt`, `max_attempts`, retry policy
- lease：`lease_owner`, `lease_expires_at`, `heartbeat_at`
- result/error：结构化 result、public error、internal error category
- linkage：workflow thread/run id、created/started/completed timestamps

数据库唯一约束保证同一 active idempotency key 不会创建第二个执行。claim 与 `running` event 在同一事务完成；worker 只能在持有有效 lease 时提交 transition。

fencing 只能保护数据库提交，不能撤销已发生的外部调用。handler 必须声明 side-effect class：纯事务型、provider-supported idempotent external、或 ambiguous external。前两类使用 durable intent/result key；第三类若在调用后、结果持久化前失去 lease，进入 `needs_attention/dead_letter` 并由 reconcile 决定，禁止自动盲重试。

### 4.3 JobEvent And SSE Cursor

`JobEvent` 是 append-only 记录：全局递增 cursor、stream-local sequence、event type、schema version、public payload、created time。current `JobRun` 是日志的查询投影，不是唯一历史。

用户可见 stream 明确只有一条：standalone job 使用 `stream_type=job, stream_id=job_id`；Chapter workflow 及其 projection child jobs 使用 `stream_type=workflow, stream_id=run_id`。Chapter outbox consumer 在更新 projection status 的同一事务中追加 workflow JobEvent。全局 cursor 决定跨来源顺序，`(stream_id, sequence)` 防重。

SSE：

- 接受 `Last-Event-ID` 或显式 cursor；
- 先从 PostgreSQL 补齐 cursor 后事件，再进入 wait/poll；
- Redis 只唤醒读取，不直接承载 payload；
- 以 event id 去重，按 owner scope 授权；
- snapshot API 在一个只读事务中返回 `snapshot_revision + resume_cursor`；客户端只从该 cursor 之后续传。
- 有明确 retention 和“cursor 已过期，重新取 snapshot”的事件；reset 后必须重新取得一对新的 snapshot/cursor，不能沿用旧 revision。

### 4.4 Chapter Outbox And Projections

Chapter canonical transaction 追加版本化领域事件，例如：

- `ChapterDraftGenerated`
- `ChapterVersionSelected`
- `ChapterFinalizationRequested`
- `ChapterFinalized`
- `ChapterRevisionSuperseded`
- `ChapterDeleted`

事件具有 `(project_id, chapter_number, revision, event_type)` 幂等键。每个 projection 维护 checkpoint/status，并用 `(projection_name, aggregate_id, revision)` 唯一约束防重。

projection 分类：

- required：影响下一章可靠上下文的 summary/memory/RAG/foreshadowing；完成前 Chapter 保持 `finalizing`。
- skipped：用户通过明确 contract 跳过，例如 `skip_vector_update`；记录为 skipped，不视为成功执行。
- trace：从 workflow/job events 生成用户可见 read model，不参与恢复。

projection 失败不会回滚已提交的 canonical content，但会阻止 lifecycle 进入 `successful`，并提供独立重试/replay。projection reconciler 是唯一 lifecycle owner：它在同一事务锁定 Chapter revision、验证没有 superseded/tombstone、检查所有 required status、更新 `successful`，并追加唯一 `ChapterFinalized`/workflow event。workflow 只观察该结果并结束 run。

### 4.5 Durable Chapter Workflow

一个 `ChapterWorkflowRun` 绑定一个 root `JobRun`，并以 `run_id` 作为 LangGraph `thread_id` 和 workflow event stream correlation id；projection child job 保留自己的 job id，但写入同一 workflow stream。graph 负责：

1. resolve/freeze context
2. plan/direct
3. generate candidate versions
4. review/evaluate
5. interrupt and wait for version command
6. finalize canonical revision + outbox
7. wait/reconcile required projections
8. observe reconciler-confirmed success and finish run

人工操作通过持久 command inbox 进入；command 带 idempotency key 和 expected revision。节点输出以 `(run_id, node_key, attempt/input_hash)` 持久化，恢复优先读取已完成结果，避免重复 LLM 成本和副作用。

旧 trace recovery 在兼容期只读；完成 checkpoint 切换后不再删除 trace 来决定恢复位置。

### 4.6 Transport Contracts

FastAPI `app.openapi()` 导出确定性 schema，`openapi-typescript` 生成 `frontend/src/api/generated/schema.d.ts`。生成物提交仓库，CI 重跑并检查 clean diff。

边界分层：

- generated transport types：HTTP wire DTO 的唯一 TypeScript 定义；
- `src/api/*`：URL、method、timeout、auth 和 `requestJson` 调用；
- domain mapper：仅当 UI 需要 camelCase/判别联合/运行时解码时存在；
- `queries/*`：Vue Query cache 与 mutation，不复制 DTO。

SSE payload 除静态生成类型外，必须在入口用 `unknown` + runtime decoder 校验。

### 4.7 WritingDesk Statechart

采用 XState statechart 管理交互 actor，Vue Query 仍是服务端实体缓存。machine snapshot 只保存 UI/workflow correlation 信息，例如 selected chapter、run id、last event cursor、pending command。

状态至少覆盖：`idle`、`submitting`、`running`、`waiting_for_selection`、`finalizing`、`projection_pending`、`succeeded`、`failed`、`reconnecting`。服务端 snapshot/event 驱动 transition；非法/过期 event 通过 run id + revision 被忽略。

页面刷新先加载 query snapshot，再用 cursor 恢复 actor；重复点击由 machine guard 和服务端 idempotency 双重约束。

## 5. Transaction Boundaries

- Router 不 commit；application/service 拥有事务。
- repository/projection adapter 只 flush，不自行 commit。
- canonical mutation、outbox、JobEvent 必须同 session/transaction。
- 外部 LLM/embedding 调用期间不持有长事务。输入先固化，外部结果返回后用 expected revision + idempotency key 短事务提交。
- pgvector 写入由 projection worker 的事务拥有；禁止 `VectorStoreService` 创建隐藏 session 并 commit。
- publish Redis 永远发生在 commit 后，失败只影响唤醒延迟。

## 6. Database Startup Boundary

进程职责拆分：

- `db-create`：仅本地/首次安装可选，连接 `postgres` 创建目标数据库。
- `db-migrate`：只运行 `alembic upgrade head`。legacy database 只有匹配已登记 baseline schema fingerprint 才能显式 adopt/stamp；未知结构 fail closed。
- `db-bootstrap`：按版本执行默认配置、Prompt seed、管理员初始化等显式数据动作。
- API/worker runtime：校验安全配置和 schema head，执行只读 cache preload，不 mutation。
- liveness：进程存活；readiness：DB 可达、schema 在 head、必要依赖可用。

部署先执行 migrate/bootstrap one-shot，再启动 API/worker。历史 API key 明文加密应进入受版本管理的数据迁移，不再在每次 app 启动扫描。

## 7. Migration And Rollback

所有子任务遵循：

1. Expand：增加新表/字段/adapter，不删除旧行为。
2. Backfill：迁移已有任务、trace 或 bootstrap version；可重复执行。
3. Shadow/dual-read：新路径产出可比对结果，但同一副作用只有一个 owner。
4. Cutover：rollout owner marker 与 lease fencing 在同一数据库事务切换；先停止旧 claim、drain/expire 已有 lease，再启用新 owner，最后切 API/worker/UI。
5. Contract：观测一个发布窗口后删除旧路径和重复 contract。

回滚只切换入口和读取路径，不回滚已经提交的 canonical Chapter revision。新事件/字段必须允许旧版本 reader 忽略未知类型。

## 8. Key Risks And Controls

| Risk | Control |
| --- | --- |
| worker crash 后重复副作用 | lease fencing + durable intent/result；provider idempotency；ambiguous external 禁止盲重试并进入人工 reconcile |
| checkpoint 与业务状态分叉 | stable run/thread id；transition transaction 中记录 expected revision；reconciler 检测 |
| outbox backlog 导致下一章上下文陈旧 | required projection gate；队列延迟/失败可观测；人工 replay |
| SSE cursor 泄露其他用户事件 | owner-scoped query 与授权；public payload whitelist |
| event payload 或 trace 泄密 | schema allowlist；不记录 token、密钥和未裁剪敏感配置 |
| 双路径迁移重复执行 | 单一 idempotency key；feature flag 只选择一个 executor |
| DB migration 与多进程竞争 | explicit one-shot migration，runtime readiness 只读 |
| 大规模重构难回滚 | 子任务逐个 cutover、独立验收、旧 adapter 延迟删除 |
| 自建 runtime 演化成平台 | production readiness gate；容量/SLO/告警不达标或新增复杂 timer/signal 即重新评估 Temporal |

## 9. Architecture Decision Reversals

- 重新打开 Redis SSE 决策：不是否定事件驱动推送，而是补上阶段性方案缺少的 durable cursor 和事实源。Redis 保留 wake-up 价值。
- OpenAPI codegen：此前多次建议但未接入 scripts/CI；本轮在 workflow API 稳定后一次收敛，避免生成后继续手工漂移。
- Alembic：schema 所有权已经正确；本轮只移除 runtime 对 migration/bootstrap 的隐式执行，不重做 baseline。
