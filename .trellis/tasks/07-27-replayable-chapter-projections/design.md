# Replayable Chapter Projections Design

## Canonical Write

定稿 command 在短事务内：

1. 校验 expected Chapter revision 和 selected version；
2. 写 selected content、增加 revision、状态置 `finalizing`；
3. append `ChapterFinalizationRequested` outbox；
4. append 对应 workflow/job event；
5. commit。

该事务不调用 LLM、embedding 或独立 session。

## Outbox

Outbox event 具有 aggregate identity、revision、event type/version、payload、created time。`(aggregate_type, aggregate_id, revision, event_type)` 唯一。消费状态不通过覆盖 event 本身表达；每个 projection 用自己的 checkpoint/status，允许多 consumer 独立重放。

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

summary LLM result 以 canonical revision + source content hash 唯一并先 commit。downstream execution row 通过依赖 result id 创建/claim；summary 处于 queued/running/retry/failed 时不创建可执行 downstream claim，避免消费未提交或旧结果。RAG chunk id 包含 revision 或 projection generation；新 generation 完成后原子切换 active revision，再删除旧 generation，避免先删后写形成空窗。

## Idempotency And Stale Events

- 每个 projection execution row 由唯一键 upsert/claim，并记录 dependency result ids；dependency revision 不匹配时拒绝执行。
- consumer 提交前再次比较 Chapter current revision；旧 revision 写入 staging 后不得成为 active。
- external call 返回后以 expected revision 短事务保存 result。
- crash-after-external-call 可能重复调用，但稳定 result key 和 upsert 保证最终结果唯一。

## Delete And Regenerate

删除/重新生成不直接跨 session 清派生表，而是提交 tombstone/superseded event。consumer 按 revision 删除或下线 memory、vector 和 foreshadowing artifacts。新 revision 与旧 tombstone 可以乱序到达，active revision guard 决定最终可见结果。

## Trace

trace 作为 read model 从 workflow/job step events 构建。敏感字段使用 allowlist/redaction；trace projection 失败不影响 workflow recovery。现有 trace 表可在兼容期作为 read target，恢复逻辑停止依赖它之后再收缩字段。

## Replay And Reconcile

- replay command 只创建/重置指定 projection execution，不改 canonical revision。
- reconcile 在单一事务中 `FOR UPDATE` 锁定 Chapter，比较 canonical current revision、tombstone/superseded、required projection status、dependency result revision 和 active artifact revision。只有它能更新 Chapter `successful`，并用唯一 event key追加 `ChapterFinalized` 与 workflow JobEvent；workflow 只观察，不重复 transition。
- dry-run 输出差异计数/identity，不输出正文、prompt、token 或 key。

## Rollback

consumer 可暂停而不丢 outbox。cutover 前 aggregate rollout owner/generation 与 worker lease fencing 在同一事务切换；先停止旧 owner claim 并 drain/expire lease，再启用新 consumer。回滚只改变 owner，不删除 outbox/status。
