# Replayable Chapter Projections Design

## Canonical Write

定稿 command 在短事务内：

1. `SELECT ... FOR UPDATE` 锁定 Chapter，或执行 `UPDATE ... WHERE current_revision = expected_revision RETURNING`；
2. 校验 selected version，原子分配 revision，并持久化 immutable source snapshot/content hash；
3. 写 selected content、revision、状态 `finalizing` 与 required projection 配置快照；
4. append `ChapterFinalizationRequested` outbox；若存在 workflow correlation，同时通过既有 event service append workflow `JobEvent`；
5. commit。expected revision 冲突或唯一键冲突回滚并映射为领域 concurrency error。

该事务不调用 LLM、embedding 或独立 session。

## Outbox

Outbox event 具有 immutable event id、aggregate identity、revision、event type/version、payload fingerprint、created time。`(aggregate_type, aggregate_id, revision, event_type)` 唯一；相同 key 但 payload/version 不同视为 contract violation。payload 固定 typed child job 所需的 `job_type`、`payload_version`、idempotency identity 与 workflow stream identity，不复制正文。消费状态不覆盖 event 本身；每个 projection 用独立 result/checkpoint 记录，允许重放且保留 attempt 历史。

ChapterOutbox 只承载 aggregate-scoped 内部领域事实，不直接暴露给 SSE。consumer 通过现有 `JobService` 幂等创建 projection child `JobRun`；JobRun transition、projection status 与 public workflow `JobEvent` 由同一 application transaction 拥有。

## Durable Execution Ownership

projection 不实现新的 queue、claim、lease 或 retry loop。每个 projection 与 reconciler 都注册为 typed durable job handler，并使用现有 `JobRun` 的 `job_type/payload_version/idempotency_key`、`FOR UPDATE SKIP LOCKED` claim、lease、attempt、fencing token 和 executor generation。

projection result/checkpoint/artifact 表只保存领域状态：projection identity、source revision/hash、dependency result id、artifact generation、result/status 和 checkpoint。handler 进行外部调用前后使用短事务；result/status 提交同时校验完整 lease tuple、executor generation、expected revision/hash。条件更新影响 0 行时只记录 stale/fenced 诊断，不得激活 artifact。

## Projection DAG

```text
ChapterFinalizationRequested
  -> summary(project, chapter, revision)
       -> memory(...)
       -> rag(...)
       -> foreshadowing(...)
  -> trace(read model from workflow/job events)
  -> reconcile required statuses
       -> ChapterFinalized / successful
```

summary LLM result 以 immutable canonical revision + source content hash 唯一并先 commit。downstream child JobRun 通过 committed dependency result id 创建；claim 必须 join succeeded/current dependency，summary 处于 queued/running/retry_wait/failed/needs_attention 时不创建可执行 downstream job。RAG chunk id 包含 revision、projection generation 和 item key；新 generation 完成后在锁定 Chapter/current revision 的事务中条件切换 active generation，再异步清理旧 generation，避免先删后写形成空窗。

projection status 映射为：JobRun queued/running/retry_wait 对应同名非终态；succeeded 对应 projection succeeded；可安全跳过的 canonical 命令写 skipped；永久失败对应 failed；外部结果未知对应 needs_attention；revision/fencing 条件失败对应 stale。required gate 仅接受 succeeded，或该 revision 的 required 配置快照明确允许的 skipped。

## Idempotency And Stale Events

- child JobRun 使用既有原子 claim/lease/fencing；projection identity/result/artifact 使用数据库唯一键和 deterministic key upsert，不单独 claim。
- consumer 提交 result、status 或 active generation 时，在同一短事务锁定 Chapter 或使用 `current_revision/source_hash/not_tombstoned` 条件更新并检查 rowcount；旧 revision 只能保留为 staging/audit，不能 active。
- 每种 activity 先声明 side-effect class。`idempotent_external` 在调用前持久化 intent 与 provider request key；`ambiguous_external` 在可能已调用但无 durable result 时进入 needs_attention/dead-letter，禁止自动重放。
- memory、RAG、foreshadowing artifact key 至少包含 projection/project/chapter/revision/generation/item identity；upsert/delete 都按该 key 或精确 generation 执行，不按 chapter 无条件删除。

## Delete And Regenerate

删除/重新生成与 finalize 共用 canonical revision allocator，并提交指向精确 source revision/generation 的 tombstone/superseded event。Chapter current revision、tombstone watermark 与 `superseded_by` 决定合法状态；consumer 只能下线目标 generation。迟到 tombstone 不得删除更高 revision，迟到 finalize 不得越过 `current_revision == expected AND not_tombstoned` 条件激活。

## Trace

trace 作为 read model 从 workflow/job step events 构建。敏感字段使用 allowlist/redaction；trace projection 失败不影响 workflow recovery。现有 trace 表可在兼容期作为 read target，恢复逻辑停止依赖它之后再收缩字段。

## Replay And Reconcile

- replay command 只为指定 current/non-tombstoned revision 创建新的 fenced child JobRun attempt，不覆盖历史、不改 canonical revision；旧 revision 默认只允许 dry-run 或清理型 replay。
- reconciler 本身是 typed durable job。在单一事务中 `FOR UPDATE` 锁定 Chapter，比较 current revision/hash、tombstone/superseded、required 配置快照、projection status、dependency result revision 和 active artifact generation。只有 `status=finalizing AND revision=expected` 的条件转换成功时，才以 `(aggregate, revision, ChapterFinalized)` 唯一键追加 outbox 与 workflow JobEvent；重复 reconcile 幂等返回当前状态。
- dry-run/replay 强制管理员或内部服务身份、project scope、idempotency key、reason、批量/并发限制和审计记录。输出仅含 allowlisted identity、状态与差异计数，不输出正文、prompt、token、key 或 provider 原始错误。

## Observability And Operations

必须暴露 outbox age/backlog、各 projection queued/running/retry/failed/needs-attention/stale 数、lease reclaim、reconcile latency/success、artifact generation mismatch、外部调用 latency/cost 指标，并用 project/chapter/revision/job/event correlation id 输出结构化脱敏日志。发布 gate 定义 backlog、stuck、needs-attention 与 shadow diff 阈值，并有对应告警和 runbook 演练。

## Migration And Cutover

Alembic 只做 expand：新增 nullable/default-safe 列、表、唯一约束和索引，必要 backfill 分批且可重入；空库、当前库、并发 worker 和旧 binary 读取新 schema 都需验证。不可逆 canonical revision/outbox 不做破坏性 downgrade；代码回滚版本必须忽略未知 event version，并由 schema/readiness rollback floor 阻止不兼容 binary。

aggregate rollout marker 状态为 legacy/shadow/projection，owner + generation 在数据库中原子切换。shadow 复用同一 canonical input，但只有 legacy owner 写 active artifact；对比 identity/hash/status，连续观察窗口内零不可解释差异、backlog/告警达标后才 cutover。切换先停止旧 claim 并 drain/expire lease，再启用新 owner；回滚只切 owner，不删除 outbox/result。

## Rollback

consumer 可暂停而不丢 outbox。cutover 前 aggregate rollout owner/generation 与 worker executor generation/fencing 在同一事务切换；先停止旧 owner claim 并 drain/expire lease，再启用新 consumer。回滚只改变 owner，不删除 canonical revision、outbox、result/status 或 artifact generation。
