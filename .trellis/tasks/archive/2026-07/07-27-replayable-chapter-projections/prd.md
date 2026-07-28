# 建立 Replayable Chapter Projections

## Goal

把 summary、memory、RAG/pgvector、伏笔和用户 trace 从 Chapter 主事务中的脆弱副作用，收敛为由 transactional outbox 驱动、按 revision 幂等且可重放的派生投影。

## Background

- Chapter 删除在主 session commit 前调用向量删除，向量服务又在独立 session 中 commit；主事务失败时派生数据不能回滚：`backend/app/services/novel_service.py:758-809`、`backend/app/services/vector_store_service.py:249-273`。
- 定稿 router 同时负责选版、正文、summary LLM、memory、RAG、伏笔、trace 与多次状态更新：`backend/app/api/routers/writer.py:898-1206`。
- `FinalizeService` 只覆盖部分派生写回，无法独立表达整个定稿和恢复语义：`backend/app/services/finalize_service.py:158-309`。

## Requirements

- PROJ-1：每次 canonical Chapter finalize/regenerate/delete 通过 PostgreSQL 行锁或 expected-revision CAS 原子分配单调 revision，并在同一事务写入 immutable source snapshot/content hash、lifecycle 与 versioned outbox event；并发冲突必须显式失败或重读，不得静默覆盖。
- PROJ-2：outbox payload 只包含稳定 identity/revision 和必要 metadata；consumer 从 canonical source 加载内容，避免复制完整正文成为第二事实源。
- PROJ-3：每个 projection execution 是现有 durable runtime 中的 typed child `JobRun`；`JobRun`/transition service 继续唯一拥有 claim、lease、attempt、retry、fencing 与 `JobEvent`，projection 表只保存领域 identity、result、dependency、status/checkpoint 和 artifact generation，不得形成第二套执行控制面。
- PROJ-4：consumer 以 `(projection, project, chapter, revision)` 和稳定 artifact key 幂等；claim 与所有 result/status commit 必须校验 `JobRun` lease tuple/fencing token，并在同一短事务使用 expected revision 条件写。失效 worker 或旧 revision 的 affected rows 为 0 时转 stale/superseded，不得激活结果。
- PROJ-5：projection DAG 明确依赖：summary result 以 immutable canonical revision + content hash 版本化；需要它的 memory/RAG/foreshadowing 只有在该 result committed 后才能创建或 claim typed child job。依赖失败、歧义或重试不推进下游 checkpoint；trace 从 job/workflow events 派生。
- PROJ-6：删除/替换产生精确指向 revision/generation 的 tombstone/superseded event；tombstone 自身单调且幂等，迟到事件只能下线目标 generation，旧 revision 不得覆盖或删除新 revision。
- PROJ-7：projection 状态至少区分 queued/running/retry_wait/succeeded/failed/skipped/stale/needs_attention；required projection 只有 succeeded 或由 canonical command 显式授权的 skipped 才满足 gate。required 未满足前 Chapter 保持 `finalizing`；typed reconciler job 是唯一 `successful` transition owner，并在锁定 current revision、排除 tombstone/superseded 后同事务更新 lifecycle 与追加唯一 event。workflow 只观察结果。
- PROJ-8：提供按 event、chapter revision 和 projection name 的 dry-run/replay/reconcile；命令必须校验管理员/内部权限与 project scope，携带幂等键、操作者和原因，限制批量范围/并发，并以 allowlist 输出审计结果。replay 新建 fenced attempt，不覆盖历史，也不得让旧 revision 成为 active。
- PROJ-9：repository/projection adapter 只 flush，不创建独立 session 或 commit；application service/worker handler 拥有短事务及 rollback/冲突映射，外部 LLM/embedding 调用不持有 DB transaction。
- PROJ-10：summary、embedding、memory、RAG 和 foreshadowing 逐项声明 `transactional`、`idempotent_external` 或 `ambiguous_external`。外部调用前持久化 activity intent/request key；provider 不支持幂等且结果未知时进入 `needs_attention/dead_letter`，禁止自动盲重放。
- PROJ-11：ChapterOutbox 是 aggregate-scoped 内部事实，不直接作为 SSE；outbox 消费、typed child JobRun transition、projection status 与 workflow-scoped public `JobEvent` 的幂等键和事务 owner 必须明确。
- PROJ-12：上线前必须有 outbox/projection lag、retry/dead-letter/needs-attention、stale、reconcile、外部调用耗时/成本指标和告警；aggregate rollout marker/owner/generation 的 shadow、cutover、drain 与回滚门槛可验证。

## Dependencies

- 依赖 `07-27-durable-job-event-log` 的 worker、retry 和事件基础设施。
- 使用 `07-27-canonical-chapter-context` 的 revision/snapshot 语义。
- 为 durable Chapter workflow 的 finalize/projecting 阶段提供 contract。

## Acceptance Criteria

- [x] canonical transaction rollback 时没有可消费 outbox event；commit 时 event 与 revision 同时可见。
- [x] finalize/regenerate/delete 并发时 revision 仍单调，冲突不会丢失 canonical write；consumer 的 revision/hash 条件提交不能被 TOCTOU 绕过。
- [x] 每个 projection 复用 typed child JobRun，在重复投递、双 worker、lease 接管、失效 fencing token 和 crash-after-side-effect 情况下只有一个 active outcome，且没有独立 claim/retry loop。
- [x] summary/memory/RAG/foreshadowing 的依赖顺序和 required/skipped/failed 状态可查询。
- [x] summary failure/retry、并发 downstream claim 和 revision supersede 测试证明下游只消费 committed current summary result。
- [x] 删除后重放 tombstone 能清理指定 revision 的派生数据；旧 finalize event 不能复活它。
- [x] projection 失败时 Chapter 不显示 `successful`，修复后 replay 可继续完成且无需重新生成正文。
- [x] reconciler 与 regenerate/delete 并发时，旧 revision 不能被标记 successful，且只追加一次 finalized event。
- [x] `VectorStoreService`/projection adapter 不再创建隐藏事务或自行 commit。
- [x] provider dedupe 与 ambiguous-result 故障注入分别证明可安全重试和禁止盲重放；每类 artifact 的稳定 key 保证重复执行不产生重复 active 数据。
- [x] 管理员或内部 CLI 可授权、限流、幂等且可审计地 dry-run/replay；越权、过大范围和 stale revision 被拒绝且不泄露正文或敏感 metadata。
- [x] 空库/当前库 migration、旧新 binary 兼容、shadow diff、owner fencing cutover、回滚与 outbox backlog 恢复均达到发布门槛；告警演练能发现 stuck/lag/needs-attention。

## Out Of Scope

- 不把整个业务数据库改造成 event sourcing。
- 不保证外部 LLM/embedding exactly-once；通过结果缓存和幂等写入实现 effectively-once outcome。
- 不在本子任务迁移完整 Chapter workflow 或前端交互。
