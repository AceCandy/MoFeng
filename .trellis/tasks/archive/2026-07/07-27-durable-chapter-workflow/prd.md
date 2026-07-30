# 构建 Durable Chapter Workflow

## Goal

把章节生成、评审、人工选版、定稿、projection 等待、节点重试和恢复收敛到一个 PostgreSQL 持久化的 LangGraph workflow run。Web 进程只提交命令和读取快照；独立 worker 可以在进程终止、滚动发布和通知断线后继续同一 run，且已经持久化的外部结果和 canonical 写入不会被盲目重复。

## Confirmed Facts

- 章节生成入口现已返回 `202 + BackgroundTask`，但 durable handler 仍把整段内存 LangGraph 包成一个 `ambiguous_external` activity；图没有 checkpointer，失败后仍依赖 trace 重建 state：`backend/app/api/routers/writer.py:95-177`、`backend/app/services/chapter_generation_task_runner.py:37-98`、`backend/app/services/pipeline_orchestrator.py:204-427`。
- 当前 `PipelineGraphState` 含不可可靠序列化的运行时对象，部分 review 副作用没有进入 State/trace，节点内部还自行 commit Chapter、trace 和候选版本：`backend/app/services/pipeline_orchestrator.py:403-439`、`backend/app/services/pipeline_orchestrator.py:965-1620`。
- durable runtime 已提供唯一 JobRun current row、lease/fencing、版本化 handler、`JobActivity` intent/result、workflow `JobEvent` stream 和 ambiguous-result 停止语义：`backend/app/models/background_task.py:13-91`、`backend/app/models/job.py:27-165`、`backend/app/services/job_service.py:221-408,480-985`。
- canonical finalize 已原子写入 Chapter revision、immutable outbox 和 dispatcher job；required projection 由既有 reconciler 唯一推进 Chapter `successful`：`backend/app/services/chapter_projection_service.py:185-390`、`backend/app/services/chapter_projection_runtime.py:577-663`、`backend/app/services/chapter_projection_rollout.py:1360-1377`。
- finalize 当前会生成新的 workflow stream id，若直接复用会把生成 run 与 projection 事件拆成两条流：`backend/app/services/chapter_projection_service.py:216-220,319-375`。
- 项目固定 `langgraph==1.2.2`，尚未引入 PostgreSQL checkpointer 或 Psycopg 3；runtime 不允许自行建表或 migration：`backend/requirements.txt:1-25`、`.trellis/spec/backend/database-guidelines.md`。

## Requirements

- WF-1：每个 run 使用稳定 `run_id == LangGraph thread_id == workflow stream_id`，绑定 user、project、chapter、base revision、一个 root JobRun、workflow schema version，以及冻结后的 canonical context snapshot/hash。
- WF-2：graph 明确覆盖 context freeze、plan/direct、generate candidates、review、persist candidates、wait-for-selection、finalize、wait-for-projections 和 terminal state；checkpoint 只保存版本化、可序列化的 ID、hash 和状态，不保存 session、client、ORM 对象、prompt 正文或运行时 service。
- WF-3：使用已核验兼容范围的 `langgraph-checkpoint-postgres==3.1.0`，并在实施 Gate 0 锁定其 Psycopg 3 direct/transitive build。worker/process 重启后从相同 thread checkpoint 恢复；运行中的旧 workflow version 必须由对应 graph definition 继续处理。若依赖解析、目标平台 wheel 或运行验证失败，停止实现并重开设计，禁止退回内存 checkpointer。
- WF-4：复用现有 `JobActivity` 作为唯一 step intent/result 账本。每个有副作用 step 使用稳定 node/input identity；已成功的 activity 直接复用。事务型 outcome 与 activity result 原子提交；外部 response 未持久化的模糊窗口进入 `needs_attention`，不得自动重放。
- WF-5：人工 `select`、`retry`、`retry_external`、`retry_projection`、`cancel` 通过持久 command inbox 进入，携带 command id、payload version、expected run revision、expected Chapter revision 和 expected checkpoint。重复 command 返回同一结果；stale command 以 `409` 拒绝并返回当前 run snapshot。
- WF-6：同一 project/chapter/base revision 最多一个 active run。queued/running/retry/wait/finalize/projection/needs-attention 均占 active slot；只有 successful/failed/cancelled/superseded 释放。自动 retry 沿用 run；terminal 后的显式 retry 只有在没有 successor 时才能原子重取 slot，否则返回 successor。
- WF-7：run 与 root JobRun 的 wait、resume、retry、needs-attention、cancel 和 terminal transition，以及相应 JobEvent，必须由同一 service-owned PostgreSQL transaction 提交。等待人工选择或 projection 时释放 worker lease，不能依靠长 lease 或进程内 task 存活。
- WF-8：trace 只从 workflow/job events 投影用于兼容展示；新 run 不读取、删除或重放 trace 来决定恢复位置。清空或暂停 trace projection 不得影响 checkpoint recovery。
- WF-9：HTTP start 返回 `202 + run snapshot/link`；snapshot、command 和现有 workflow-scoped SSE 构成新 API。现有 generate/finalize/select endpoint 在兼容窗口只做 adapter，不执行第二套 workflow 或创建第二条 stream。
- WF-10：finalize 必须沿用 run id 写 outbox/dispatcher/projection child jobs。workflow 只观察既有 projection reconciler 将同一 current revision 标记为 `successful`，不得自行写该 Chapter transition；projection failed 可以从该阶段显式重试，无需重跑生成。
- WF-11：错误按 node、retryability 和 public category 表达。`needs_attention` 保留 active slot；原 ambiguous activity 永久保留且不可重置。只有带 actor 审计及 `acknowledge_possible_duplicate=true` 的 `retry_external` 才能以 command id 派生一个新的 activity intent，或由 cancel 终止；同一命令重放不得创建第二个 retry intent。系统不接受人工注入的未知 provider result。
- WF-12：checkpoint schema 只能由 Alembic/显式 migration 安装，API/worker 不得调用 checkpointer `setup()` 变更 schema。`db-check` 验证 pinned checkpointer schema version；terminal run 的 checkpoint 和 command/activity 私有 payload 按明确 retention policy 清理，activity identity/status 与 AI usage/cost audit 保留。
- WF-13：切换使用 expand/drain/cutover/contract。旧 `chapter_generation` jobs 先 drain 或由兼容 worker 接管；新旧 executor 不得同时对同一 Chapter 执行副作用。二进制回滚保留新表和 checkpoint 数据，并继续 drain 已创建的新 run。

## Dependencies

- canonical Chapter context、explicit database bootstrap、durable job/event log 和 replayable Chapter projections 已完成并构成本任务的强制契约。
- 本任务完成后冻结 workflow OpenAPI/event shape，供 generated transport contracts 与 WritingDesk statechart 消费。

## Acceptance Criteria

- [ ] AC1：在候选生成完成、等待选版和 projection pending 三个位置分别终止真实 worker 进程，重启后用同一 run/thread 从对应 checkpoint 继续。
- [ ] AC2：重复 start/select/retry/cancel 不重复已成功的 LLM result、候选版本、canonical revision、outbox 或 projection；activity 调用次数和数据库唯一结果均有断言。
- [ ] AC3：crash-after-provider-response-before-result 对 ambiguous external 转为 `needs_attention` 并持续占 active slot；worker 重启和普通 retry 均不再次调用 provider。原 ambiguous row保持不变；只有带重复调用确认的 `retry_external` 创建一个 command-derived intent并恰好再调用一次，同一 command重放不增加调用或intent；cancel不调用 provider。
- [ ] AC4：stale run/revision/checkpoint command 返回 `409 + current snapshot`，不消费 command、不覆盖 successor，也不推进旧 checkpoint。
- [ ] AC5：同章并发 start 只创建一个 active run/root JobRun/thread；另一请求返回同一 durable identity。cancel/failed/retry/superseded 与 JobRun transition 原子释放或重取 slot。
- [ ] AC6：等待状态没有有效 worker lease；select command 和 projection resumer 能持久 requeue。Web、Redis 或 worker 进程重启不影响 run 最终进度，只影响唤醒延迟。
- [ ] AC7：finalize outbox、dispatcher 和全部 projection child jobs 使用 start 时的 run id/workflow stream；只有 projection reconciler 能把 Chapter/current revision 推进为 `successful`。
- [ ] AC8：删除全部 generation trace 或暂停 trace projector 后，checkpoint resume、command 去重和 terminal outcome 仍通过；兼容 trace 仅可由 JobEvent 重建。
- [ ] AC9：旧 generate/finalize/select adapters 与新 API 指向同一 run，返回一致 Chapter lifecycle；旧 pending jobs drain 期间不存在双 executor。
- [ ] AC10：空库/current 库迁移包含 pinned checkpointer 的完整 schema/version；API/worker 启动不执行 DDL，schema 漂移时 readiness fail closed，二进制回滚保留数据。
- [ ] AC11：stale-run reconciler 能检测并安全收敛人为制造的 JobRun/run/checkpoint/Chapter 不一致；并发 start/command/finalize/reconcile 测试遵守既有 JobRun→Chapter 和 projection aggregate 锁序且无死锁。
- [ ] AC12：retention 只清理超过保留期的 terminal thread checkpoint与私有 command/activity payload，不触碰 active、needs-attention、current Chapter、outbox、activity identity/status、AI usage/cost 或 projection audit；重复清理幂等且不遗留测试 schema/连接。

## Out Of Scope

- 不引入 Temporal、跨服务 workflow 或第二套 lease/retry/event control plane。
- 不重写 LLM prompt、review 算法、候选评分、memory/RAG/伏笔 projection 算法。
- 不让 workflow history/checkpoint 成为 Chapter canonical data，也不把 projection checkpoint 冒充 LangGraph checkpoint。
- 不在本子任务完成 generated TypeScript contracts 或 WritingDesk statechart；只冻结其后续所需的后端契约。
- 不把已完成的 legacy trace 历史转换成伪造 LangGraph checkpoint；兼容期只 drain 旧 job 并保留只读展示。
- 不提供人工录入/伪造未知 provider response 的接口；外部平台若未来支持按 request id 查询结果，另行设计可信 reconcile adapter。
