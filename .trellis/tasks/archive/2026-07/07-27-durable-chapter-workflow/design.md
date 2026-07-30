# Durable Chapter Workflow Design

## 1. Ownership Boundaries

| Fact | Sole owner | Reused mechanism |
| --- | --- | --- |
| Chapter正文、候选、revision、lifecycle | Chapter aggregate / projection reconciler | `Chapter`, `ChapterVersion`, `ChapterRevision`, outbox |
| 谁执行、lease、attempt、retry、fencing | durable JobRun | `BackgroundTask` + `JobService`；不新增第二套 job 表 |
| workflow phase、active slot、graph version、frozen context | `ChapterWorkflowRun` | 新增 domain orchestration current row |
| graph resume position | LangGraph PostgreSQL checkpointer | pinned vendor schema；不复用 trace/projection checkpoint |
| 外部/事务型 step intent/result | `JobActivity` | 扩展现有 activity API；不新增 step-result 表 |
| 人工命令 | `ChapterWorkflowCommand` | 新增 inbox，command id 唯一 |
| 用户事件与 SSE cursor | `JobEvent` workflow stream | `stream_type=workflow`, `stream_id=run_id` |
| 兼容 trace | JobEvent projector | 只读展示，不参与恢复 |

`run_id` 同时是 LangGraph `thread_id` 和 workflow event `stream_id`。root/dispatcher/projection child jobs 保留各自 job id，但 payload 和 stream 都引用同一 run id。

## 2. Persistent Model

### `ChapterWorkflowRun`

核心字段：

- identity：`id/run_id`, `user_id`, `project_id`, `chapter_id`, `chapter_number`, `base_revision`, unique `root_job_id`；
- version：`workflow_version`, `state_schema_version`, `row_revision`；
- context：`context_schema_version`, `context_snapshot`, `context_hash`, runtime input hash；
- current：`status`, `node_key`, `checkpoint_id`, public progress/error category；
- concurrency：`is_active`, `successor_run_id`, created/started/completed timestamps。

PostgreSQL partial unique index 覆盖 `(project_id, chapter_number, base_revision) WHERE is_active`。`is_active` 与状态受 CHECK 约束；`needs_attention` 仍为 active，防止通过新 start 绕过模糊 external outcome。

### `ChapterWorkflowCommand`

字段为 `command_id`, `run_id`, `type`, `payload_version`, payload, `actor_user_id`, `expected_run_revision`, `expected_chapter_revision`, `expected_checkpoint_id`, `status`, rejection code, created/applied timestamps。`command_id` 全局唯一；同一 command 重放返回已记录 outcome。

### JobRun status extension

新增内部 `waiting` 状态：释放 lease、不会被普通 claim 扫描；public task compatibility 暂映射为 `queued`，真实 phase 由 workflow snapshot 返回。状态对应关系：

| Workflow state | JobRun state | Active slot |
| --- | --- | --- |
| queued / executing nodes | queued, running, retry_wait | held |
| waiting_for_selection / projection_pending | waiting | held |
| needs_attention | needs_attention | held |
| successful | succeeded | released |
| failed | failed/dead_letter | released |
| cancelled / superseded | cancelled | released |

JobService 增加 fenced wait/resume transition，并通过单一 workflow transition adapter 在同一 transaction 同步 root JobRun、run、event 和 slot。现有 retry、activity ambiguity、cancel、success/failure paths 也调用该 adapter；不允许 handler 另行 commit run 状态。

## 3. Transaction And Lock Order

现有 projection lock order保持不变。workflow 新增顺序：

```text
worker/command/reconciler:
  root BackgroundTask -> ChapterWorkflowRun -> Chapter
  -> ChapterVersion(id ASC) -> existing finalize/projection order
```

- command 先无锁读取 run identity，再锁 root JobRun，随后重读并锁 run/Chapter；stale identity 失败关闭。
- worker 通过 `_require_lease` 先锁 root JobRun；transactional activity outcome writer 再锁 run/Chapter。
- start 尚无 root job：锁 Chapter，普通读取当前 active run；存在时直接返回，不在持有 Chapter 时反向锁其 BackgroundTask。不存在时在同一 transaction enqueue 新 root job并插入 run，唯一约束处理竞态。
- projection consumer/reconciler 不锁 workflow root job。projection 完成后的 workflow 唤醒由独立 resumer transaction 按 root JobRun→run→Chapter 顺序处理，避免 Chapter→BackgroundTask 反向边。
- checkpoint 由独立 Psycopg connection 写入，无法与 SQLAlchemy domain transaction 伪装成一个 ACID transaction；activity idempotency、command applied marker 和 stale-run reconciler负责跨边界恢复。

## 4. Graph V1

```text
queued
  -> freeze_context
  -> plan_and_direct
  -> generate_candidates
  -> review_candidates
  -> persist_candidates
  -> waiting_for_selection (interrupt)
  -> finalize_revision
  -> projection_pending (interrupt/wait)
  -> observe Chapter current revision successful
  -> successful
```

失败可进入 `retry_wait`, `needs_attention`, `failed` 或 `cancelled`。graph registry 按 `workflow_version` 编译并保留旧 definition，breaking node/state change新增版本，不原地改变运行中 thread 的 node 名或 state shape。

checkpoint state 只包含 schema/version、run id、node key、context/activity/result references、hash、selected version id、command marker和必要标量。`AsyncSession`、ORM、LLM client、service、`EnhancedWritingFlow`、完整 prompt/正文不进入 checkpoint。完整 frozen context 存 run row；候选/评审内部结果存 private `JobActivity.result_payload`，checkpoint只引用 key/hash。

## 5. Activity Contract

每个 activity key 在 root job 范围内使用：

```text
wf:<node_key>:<logical_input_sha256>
```

root job 已提供 run scope，因此 key 不重复拼入 run id；完整 input hash、workflow version和非敏感 provenance 写入 request metadata。key 冲突但 canonical request不同必须失败关闭。

- pure node：只计算并 checkpoint，不建 activity。
- transactional node：`complete_activity(..., outcome_writer=...)` 在持有有效 root lease/fence 的 transaction 内原子写 domain outcome、activity result 和 JobEvent。
- idempotent external：先写 intent，向 provider传稳定 request key，结果落 activity后 checkpoint。
- ambiguous external：先写 intent；response 与 result commit 间崩溃后 run/JobRun 原子进入 `needs_attention`，普通 recovery 不再调用 provider。

workflow handler 仍声明最保守的默认 side-effect class；扩展 `JobExecutionContext.begin_activity` 允许每个 activity显式声明三个既有 class，存储和 metrics 以 activity 自身 class 为准。不得新增另一套 activity model。

生成候选按候选 ordinal 分 activity；review/post-review 按稳定 stage 分 activity，避免一个大 activity 使已完成模型调用全部失去可复用粒度。事务型候选持久化和 finalize 同样写 activity result，数据库 commit 后、checkpoint 前崩溃可直接读取 result继续。

## 6. Checkpointer Lifecycle

锁定 MIT 许可的 `langgraph-checkpoint-postgres==3.1.0`；其 `langgraph-checkpoint>=4.1,<5` 与 `langgraph==1.2.2` 的约束已通过 wheel metadata核对。部署构建固定 `langgraph-checkpoint==4.1.1`、`orjson==3.11.9`、`psycopg[binary]==3.3.4` 与 `psycopg-pool==3.3.1`，CPython 3.11 Linux wheel解析及真实 PostgreSQL smoke 已通过。worker使用 `AsyncPostgresSaver`，每次 invoke传：

```python
{"configurable": {"thread_id": run_id}}
```

vendor `checkpoint_migrations`, `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` 由项目 Alembic expand revision创建，并记录 pinned package要求的 migration versions。新表为空时用普通索引替代 vendor 的 concurrent setup步骤。worker/API 只验证 schema，永不调用 `setup()`；`db-check` 比对 Alembic head、表结构和 pinned checkpoint migration version。

checkpointer 使用由 SQLAlchemy URL 结构化派生的 Psycopg DSN，不做字符串替换。测试连接必须与 SQLAlchemy session 指向同一随机 PostgreSQL schema/database，并验证不会 fallback到 `public`。

## 7. Command Handshake

1. API 验证 owner 和 envelope，按 root JobRun→run→Chapter 锁序判断 expected revisions/checkpoint。
2. accepted command 与 `workflow.command.accepted` event 原子写入；waiting root 原子 requeue。重复 command返回相同记录。
3. handler claim 后加载 pending command及当前 checkpoint。只有 expected checkpoint匹配才调用 `Command(resume=...)`；pending prepare 允许提交时的 Chapter revision，或由当前 command 自身形成的精确后置状态。
4. graph state写入 `last_applied_command_id` 后产生新 checkpoint；同 thread runtime验证 marker 后才回调 command applied。`select` 后置状态必须是 expected Chapter revision 恰好加一且 selected version 与 payload一致，`retry_projection` 必须保持 revision不变。
5. 若崩溃发生在 checkpoint后、command applied前，重启允许从上述精确后置状态重新 prepare，并从 checkpoint marker只补写 inbox状态；绝不向下一个 interrupt重复 resume。selected version或revision漂移时 prepare/apply均失败关闭。

`select`, `retry`, `retry_external`, `cancel`, `retry_projection` 共用 envelope。普通 `retry` 只处理有确定失败结果的 node，不能匹配 ambiguous activity。

`retry_external` 必须携带 `acknowledge_possible_duplicate=true`。原 ambiguous `JobActivity` 保持不可变；系统以 canonical command id 和 logical step input 派生新的 activity key/provider request key，并在 request metadata记录 `logical_step_key`、`manual_retry_command_id` 与被替代 activity。相同 command重放命中同一新 intent，不能再生成一条。若新调用再次 ambiguous，再次停止并要求新的显式 command。系统不允许人工写入一个无法验证来源的 provider result。

## 8. Finalize And Projection Integration

`ChapterFinalizeSubmissionService` 拆出不 commit 的 prepare/apply boundary，legacy `submit()` 继续包装 commit/publish。`ChapterProjectionService.create_finalize` 接受外部 `workflow_stream_id`：新 workflow必须传 `run_id`，legacy caller才允许生成兼容 id。

finalize transactional activity在 root lease fence 下锁 Chapter/versions，验证 selected version、base/current revision和 source hash，然后原子写 canonical revision、outbox、dispatcher job与 activity result。dispatcher及所有 projection child jobs继承相同 workflow stream。

workflow进入 `projection_pending` 后释放 lease。既有 projection reconciler仍是 Chapter `successful` 的唯一 writer。worker maintenance resumer观察 run target revision与 Chapter current revision：成功则 requeue root；失败保持 pending并暴露 `retry_projection`；superseded/tombstoned则终止旧 run。resumer不重做 projection outcome。

## 9. Snapshot, API And Trace

新增后端契约：

- `POST /api/writer/chapter-workflows`：start/return existing，202；
- `GET /api/writer/chapter-workflows/{run_id}`：Chapter + run + allowed commands + `resume_cursor` snapshot；
- `POST /api/writer/chapter-workflows/{run_id}/commands`：accepted 202，stale 409并携 current snapshot；
- 事件继续使用 `/api/tasks/events?stream_type=workflow&stream_id=<run_id>`。

旧 generate endpoint转发 start并继续返回 root `BackgroundTaskResponse`。旧 finalize/select在 active workflow存在时转为 select command；无新 run的 legacy Chapter仍走旧 finalize adapter直到 drain结束。`from_node_key` 只映射到合法 retry command或 legacy drain，不再删除新 run trace。

trace projector以 `(run_id, JobEvent.cursor)` 幂等生成现有展示 row；新 workflow不读取 trace。事件 payload保持 allowlist，不记录 prompt、正文、token、密钥或内部异常。

## 10. Reconciliation And Retention

stale-run reconciler比较 root JobRun、run row、latest checkpoint metadata、Chapter current revision和projection status，按稳定 reason code处理：

- expired running lease交给既有 job reaper；
- checkpoint已应用 command但 inbox仍 pending时补记 applied；
- projection pending且 Chapter successful时 requeue；
- Chapter revision已变更时 supersede/cancel旧 run；
- root terminal与run active不一致时在同一 transaction修复slot，无法证明安全则 `needs_attention`；
- checkpoint缺失/版本未知时 fail closed，不从 trace猜 state。

retention只选择超过配置保留期的 terminal run；再次锁定并确认没有 successor依赖、不是 active/needs-attention/current projection目标后，删除该 thread checkpoints并清空可清理的command/activity私有payload。command/activity identity、状态、actor、AI usage/cost audit继续保留；outbox、Chapter revisions、JobEvents和projection审计仍按各自契约保留。

## 11. Rollout And Rollback

1. Expand：依赖、ORM表、vendor checkpoint表、waiting transition、API/handler均上线但新 start关闭。
2. Verify：在隔离 PostgreSQL运行 checkpoint、command和kill/restart测试；新 worker同时注册 legacy与workflow payload versions。
3. Drain/Cutover：停止创建 legacy generation jobs，切换 executor generation并让兼容 worker drain/reassign旧 queued jobs；确认无旧 active lease后开启workflow start。
4. Contract：至少一个发布窗口和生产演练后，删除 trace recovery/router orchestration；旧 graph version继续保留到其 run全部 terminal+retention。

回滚先关闭新 start并把旧 adapter设为入口；已经创建的新 run仍由兼容 worker drain。不得把已持久化候选、revision或outbox交给旧 executor重做。schema和checkpoint保留，binary rollback必须通过 rollback-floor/readiness检查。
