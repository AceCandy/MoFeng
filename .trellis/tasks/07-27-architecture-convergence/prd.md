# 架构问题全面收敛

## Goal

把章节生成到定稿的生命周期收敛为可恢复、可重放、可观测、契约单一的系统，并让 Web、worker、数据库启动和前端交互各自只有一个明确职责边界。

用户应获得的结果是：进程重启或通知断线不会丢任务；重试只产生一个 canonical DB outcome，无法判定的外部调用不会被盲目重放；生成、评审和一致性检查看到同一份上下文；memory、RAG 与伏笔可以重放修复；前后端状态不再依赖手工同步。

## Confirmed Facts

- 当前 LangGraph workflow 的恢复由应用手工重建 state 和 trace，定稿逻辑仍横跨 router、service、memory、RAG、伏笔与 trace：`backend/app/services/pipeline_orchestrator.py:200-797`、`backend/app/api/routers/writer.py:898-1206`。
- pipeline 与 writer 使用两套不同的评审上下文，字段和降级行为已经漂移：`backend/app/services/pipeline_orchestrator.py:2066-2090`、`backend/app/api/routers/writer.py:210-332`。
- Chapter 主事务提交前会调用向量删除，而向量服务自行创建 session 并提交，无法随主事务回滚：`backend/app/services/novel_service.py:758-809`、`backend/app/services/vector_store_service.py:249-273`。
- 长任务绑定 FastAPI `BackgroundTasks`；Redis Pub/Sub 是 fire-and-forget 通知，不是任务或事件事实源：`backend/app/api/routers/writer.py:1668-1701`、`backend/app/services/event_bus.py:62-81,109-120`。
- `Chapter` transport contract 在前端多个 API 模块重复维护：`frontend/src/api/novel.ts:309-335`、`frontend/src/api/admin.ts:66-85`。
- `init_db()` 在应用 lifespan 内混合建库、Alembic、管理员、系统配置、Prompt 和历史密钥处理：`backend/app/db/init_db.py:39-204`、`backend/app/main.py:56-62`。
- Redis Pub/Sub + SSE 是 2026-07-18 为降低轮询延迟主动引入的阶段性方案。本轮只撤销它的“事实源”职责，允许继续作为低延迟唤醒通道。
- Alembic 已是 schema source of truth；本轮不回退到手写 schema patch，只拆分 migration、bootstrap、readiness 和 runtime。

## Requirements

### R1 - Canonical Chapter Context

- 生成、评审、一致性检查必须从同一个版本化 Chapter context contract 派生输入。
- contract 必须定义字段来源、可见性裁剪、预算截断、RAG 缺失降级、provenance 和 source revision。
- durable workflow 必须持久化本次运行使用的 context snapshot 或稳定引用，恢复后不得静默切换输入。

### R2 - Durable Job And Event Log

- 所有超过 HTTP 请求生命周期的任务必须由独立 worker 从 PostgreSQL 领取，Web 进程只提交命令并返回 durable id。
- 任务必须支持 lease、heartbeat、过期回收、attempt、retry/backoff、dead-letter、取消和幂等键。
- 每次状态/进度变化必须追加持久事件；SSE 必须支持 cursor 重放和断线续传。
- Redis 可以负责通知“有新事件”，但任务正确性和 SSE 恢复不得依赖 Redis。

### R3 - Replayable Chapter Projections

- Chapter canonical write 与 outbox event 必须在同一数据库事务内提交。
- memory、RAG/pgvector、伏笔和用户可见 trace 必须成为有版本、可幂等重试、可重放的 projection。
- 删除、重新生成和重新定稿必须产生显式 revision/tombstone，不能在主事务中跨 session 删除派生数据。
- Chapter 在 required projections 完成前保持 `finalizing`；只有 projection reconciler 能在锁定 current revision 的事务内推进 `successful`。失败必须可见、可重试，不能伪装成成功。显式跳过的 projection 不计为失败。

### R4 - Durable Chapter Workflow

- 生成、评审、人工选版、定稿、projection 等待、节点重试和恢复必须由一个持久 workflow run 管理。
- workflow 使用稳定 run/thread id 和 PostgreSQL checkpoint；已有持久化成功 result 的 step 恢复时不得重复执行，外部结果不明时进入 reconcile 而非自动重放。
- 同一 project/chapter/revision 最多存在一个 active run；所有 command 都必须幂等。
- trace 变为 workflow/job event 的用户可见投影，不再承担恢复事实源。

### R5 - WritingDesk Statechart

- WritingDesk 必须用显式 statechart 管理命令、SSE、重连、选版、定稿、projection pending、失败与重试。
- 服务端数据继续由 TanStack Vue Query 管理；statechart 不得复制一套长期 server cache。
- 刷新页面后必须能从 workflow snapshot + event cursor 恢复交互状态。

### R6 - Generated Transport Contracts

- FastAPI OpenAPI 必须是 transport schema 的唯一事实源，并生成受版本控制的 TypeScript 类型。
- 手写 API 方法只保留 URL/HTTP 调用和明确的 domain mapping seam，不得重复声明后端 DTO。
- CI 必须检测 OpenAPI 或生成物漂移；SSE/event payload 必须有 schema 与运行时 decoder。

### R7 - Explicit Database Bootstrap

- schema migration、一次性数据 bootstrap、管理员初始化、Prompt seed、readiness 与 app runtime 必须拆为显式命令/进程。
- API 和 worker 启动不得执行 schema/data mutation；只允许安全检查、只读 readiness 和缓存预热。
- 新库、当前库、旧版已 stamp 库的升级路径必须可重复执行并可审计。

### R8 - Controlled Migration

- 每个子任务使用 expand/backfill/cutover/contract 的可回滚迁移；禁止一次提交删除旧恢复路径和旧 API。
- 兼容窗口内必须能通过 feature flag 或 adapter 回退，且新旧路径不得同时执行同一副作用。
- 不得顺手修复与本架构任务无关的既有测试失败或邻接技术债。
- durable runtime 上线前必须通过 production readiness gate；若容量、恢复 SLO、retention、告警或故障演练不达标，则停止扩展自建 control plane 并重新评估 Temporal。

## Delivery Order

1. `07-27-canonical-chapter-context`
2. `07-27-explicit-database-bootstrap`
3. `07-27-durable-job-event-log`
4. `07-27-replayable-chapter-projections`
5. `07-27-durable-chapter-workflow`
6. `07-27-generated-transport-contracts`
7. `07-27-writing-desk-statechart`

父任务只拥有总体契约、依赖顺序和最终集成验收，不直接承载业务代码实现。

## Acceptance Criteria

- [ ] AC1：统一 context contract 的 contract/golden tests 证明 pipeline、writer、consistency 对同一 source revision 使用同形上下文，且 RAG 关闭时降级确定。
- [ ] AC2：worker 在任务执行中被终止后，lease 过期可由另一 worker 接管；同一幂等键只产生一次 canonical DB outcome。外部 provider 不支持幂等且结果不明时进入人工处理，不盲目重放。
- [ ] AC3：SSE 使用旧 cursor 重连能按序补齐缺失事件；关闭 Redis 后仍正确，仅实时性下降。
- [ ] AC4：Chapter 定稿事务失败时不产生可消费 outbox；projection 失败后可重放，重复重放不产生重复 memory、vector 或伏笔记录。
- [ ] AC5：workflow 能在生成后、人工选版前、projection 处理中三个检查点分别重启恢复；已持久化完成的 LLM/DB step 不重复，crash-after-provider-response 的模糊结果进入 reconcile。
- [ ] AC6：WritingDesk 刷新、断网重连、重复点击、节点重试、定稿失败和 projection pending 均由合法 statechart transition 处理。
- [ ] AC7：后端 schema 改动后未更新生成物会使 CI 失败；`novel.ts` 与 `admin.ts` 不再各自声明 `Chapter` wire DTO。
- [ ] AC8：API 与 worker 在空库或 schema 落后时 fail readiness，但不会自行 migration/bootstrap；显式命令可完成新库和升级库初始化。
- [ ] AC9：切换完成后，FastAPI request 进程内不再运行章节长任务，trace 不再作为恢复事实源，Redis 不再作为事件事实源。
- [ ] AC10：每个子任务独立通过其测试与回滚门禁，最终集成测试覆盖 API → job → workflow → projection → SSE → statechart 全链路。
- [ ] AC11：durable runtime 记录预期峰值并通过至少 2 倍目标负载演练；恢复延迟满足显式配置的 SLO，queue age、expired lease、dead-letter、event/projection lag 和 retention cleanup 均有指标与告警。任一门禁失败即重新打开 Temporal 选型。

## Out Of Scope

- 将整个产品改造成通用 event-sourced system。
- 替换 PostgreSQL、pgvector、FastAPI、Vue Query 或现有 HTTP wrapper。
- 本轮引入 Temporal control plane；升级条件记录在 research 中。
- 与七个子任务无关的页面重设计、性能微调、死代码清理或既有静态测试修复。
