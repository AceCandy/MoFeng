# 建立 Replayable Chapter Projections

## Goal

把 summary、memory、RAG/pgvector、伏笔和用户 trace 从 Chapter 主事务中的脆弱副作用，收敛为由 transactional outbox 驱动、按 revision 幂等且可重放的派生投影。

## Background

- Chapter 删除在主 session commit 前调用向量删除，向量服务又在独立 session 中 commit；主事务失败时派生数据不能回滚：`backend/app/services/novel_service.py:758-809`、`backend/app/services/vector_store_service.py:249-273`。
- 定稿 router 同时负责选版、正文、summary LLM、memory、RAG、伏笔、trace 与多次状态更新：`backend/app/api/routers/writer.py:898-1206`。
- `FinalizeService` 只覆盖部分派生写回，无法独立表达整个定稿和恢复语义：`backend/app/services/finalize_service.py:158-309`。

## Requirements

- PROJ-1：每次 canonical Chapter finalize/regenerate/delete 产生单调 revision，并在同一事务追加 versioned outbox event。
- PROJ-2：outbox payload 只包含稳定 identity/revision 和必要 metadata；consumer 从 canonical source 加载内容，避免复制完整正文成为第二事实源。
- PROJ-3：summary、memory、RAG、foreshadowing、trace 各有独立 projection identity、status、attempt、last error 与 checkpoint。
- PROJ-4：consumer 以 `(projection, project, chapter, revision)` 唯一键幂等；重复、并发和 worker crash 不得生成重复记录。
- PROJ-5：projection DAG 明确依赖：summary result 以 canonical revision + content hash 版本化；需要它的 memory/RAG/foreshadowing 只有在该 result committed 后才能 claim。依赖失败/重试不推进下游 checkpoint；trace 从 job/workflow events 派生。
- PROJ-6：删除/替换使用 revisioned tombstone；旧 revision 的迟到 consumer 不得覆盖新 revision。
- PROJ-7：required projections 完成前 Chapter 保持 `finalizing`；projection reconciler 是唯一 `successful` transition owner，并在锁定 current revision、排除 tombstone/superseded 后同事务更新 lifecycle 与追加唯一 event。workflow 只观察结果。显式 `skip_vector_update` 记录为 skipped。
- PROJ-8：提供按 event、chapter revision 和 projection name 的 replay/reconcile 能力，并能检测 missing/stale projection。
- PROJ-9：projection adapter 不自行 commit；worker/application service 拥有短事务，外部 LLM/embedding 调用不持有 DB transaction。

## Dependencies

- 依赖 `07-27-durable-job-event-log` 的 worker、retry 和事件基础设施。
- 使用 `07-27-canonical-chapter-context` 的 revision/snapshot 语义。
- 为 durable Chapter workflow 的 finalize/projecting 阶段提供 contract。

## Acceptance Criteria

- [ ] canonical transaction rollback 时没有可消费 outbox event；commit 时 event 与 revision 同时可见。
- [ ] 每个 projection 在重复投递、双 worker 并发和 crash-after-side-effect 情况下结果唯一。
- [ ] summary/memory/RAG/foreshadowing 的依赖顺序和 required/skipped/failed 状态可查询。
- [ ] summary failure/retry、并发 downstream claim 和 revision supersede 测试证明下游只消费 committed current summary result。
- [ ] 删除后重放 tombstone 能清理指定 revision 的派生数据；旧 finalize event 不能复活它。
- [ ] projection 失败时 Chapter 不显示 `successful`，修复后 replay 可继续完成且无需重新生成正文。
- [ ] reconciler 与 regenerate/delete 并发时，旧 revision 不能被标记 successful，且只追加一次 finalized event。
- [ ] `VectorStoreService`/projection adapter 不再创建隐藏事务或自行 commit。
- [ ] 管理员或内部 CLI 可 dry-run reconcile，再按 project/chapter/revision 定向 replay。

## Out Of Scope

- 不把整个业务数据库改造成 event sourcing。
- 不保证外部 LLM/embedding exactly-once；通过结果缓存和幂等写入实现 effectively-once outcome。
- 不在本子任务迁移完整 Chapter workflow 或前端交互。
