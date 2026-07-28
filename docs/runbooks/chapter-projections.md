# Chapter Projection Operations Runbook

## 1. 适用范围

本 runbook 用于章节 `summary`、`memory`、`rag`、`foreshadowing`、`trace`、
`reconcile` 与 `tombstone` 投影的监控、重放、shadow、cutover、rollback 和
outbox backlog 恢复，以及 superseded/tombstoned 制品的 retention 清理。

所有写操作必须由管理员执行，并遵守以下边界：

- 只通过管理 API 或 `python -m app.worker` 执行操作，不直接修改 rollout、
  revision、outbox、projection run、artifact generation 或 job lease 数据。
- `reason` 只写工单号和脱敏原因。不得写章节正文、prompt、访问 token、API key、
  provider 原始错误或用户隐私数据。
- dry-run 与 replay 必须使用不同的幂等键；同一幂等键只能重试完全相同的
  operator、mode、scope 和 reason。
- `needs_attention` 或 ambiguous external activity 必须先人工确认 provider 结果，
  禁止自动批量重放。
- canonical revision、outbox 和 projection history 是审计数据，不执行破坏性
  Alembic downgrade，不通过删除历史记录恢复服务。

## 2. 操作前检查

在 `backend/` 目录执行：

```bash
python -m app.db.cli db-check
python -m app.worker health
python -m app.worker metrics
```

只在以下条件全部满足时开始 replay 或 rollout：

1. `db-check` 成功，且没有 `schema_not_at_head`、`bootstrap_incomplete`、
   `bootstrap_contract_mismatch` 或 `binary_below_rollback_floor`。
2. worker health 为 healthy；没有未处理的 expired lease 或持续增长的 retry queue。
3. `chapter_projections.alerts` 中没有数据正确性告警。
4. rollout mutation 使用刚读取的 `generation` 与 `fencing_token`，不使用缓存值。
5. 目标数据库的 Alembic head 为 `f2a6c9d4e8b1`；该版本是 expand-only，禁止执行
   schema downgrade。

### 2.1 三类独立发布门禁

| 门禁 | 负责范围 | 校验方式 | 不可替代的约束 |
|---|---|---|---|
| Database binary rollback floor | schema/bootstrap 与 binary 兼容性 | `python -m app.db.cli db-check` | worker 或 chapter generation 正确，不能绕过 `binary_below_rollback_floor` |
| Worker executor generation | durable job claim、lease 与 worker fencing | `python -m app.worker health`，并按既有部署流程核对 `JOB_WORKER_GENERATION` | chapter rollout 切换不能激活错误 executor generation |
| Chapter rollout generation/fence | 单个 Chapter 的 legacy/projection active artifact owner | rollout GET 响应中的 `generation`、`fencing_token` | executor generation 正确，不能替代 aggregate CAS |

这三个 generation/fence 属于不同命名空间。任何一个门禁通过，都不表示另外两个已经
通过。当前没有通过 projection API 切换 worker executor generation 的操作面；必须使用
经过审核的 durable worker 部署流程。

## 3. Metrics 与告警

`python -m app.worker metrics` 输出 durable runtime 聚合值，并在
`chapter_projections` 下输出投影指标。不得将 metrics 输出扩展为正文、prompt、密钥、
访问 token 或 provider 原始错误。

| Alert code | 精确触发条件 | 首要处理 |
|---|---|---|
| `chapter_outbox_backlog` | 当前非 legacy finalize outbox 缺少对应 summary run，数量大于 0 | 检查 worker health；按第 7 节定位并 dry-run，确认后逐条 replay |
| `chapter_outbox_stuck` | 最老 backlog age 大于 300 秒 | 视为 dispatcher/worker 故障，先恢复 worker，再处理 backlog |
| `chapter_projection_needs_attention` | projection job 为 `needs_attention`，或 ambiguous activity 数量大于 0 | 停止自动重试，人工确认外部调用结果和 provider request key |
| `chapter_projection_dead_letter` | projection job `dead_letter` 数量大于 0 | 修复永久错误或配置后 dry-run；确认 scope/current revision 后 replay |
| `chapter_projection_expired_lease` | running projection job 的 lease 已过期 | 检查 worker heartbeat；等待 reclaim/终态，禁止同时创建重复 replay |
| `chapter_projection_retry_stuck` | 最老 `retry_wait` projection job age 大于 300 秒 | 检查 provider、available_at 与 active worker generation |
| `chapter_projection_shadow_failed` | shadow 有失败观察、窗口结束但成功样本不足，或 unexplained diff 大于 0 | 禁止 cutover；根据当前状态 rollback 到 shadow 或 legacy |
| `chapter_projection_stale` | 当前 projection run 中存在 `stale` | 核对是否为预期 supersede/tombstone；异常增长时检查 revision/fence 漂移 |
| `chapter_projection_generation_mismatch` | active run 的 revision/hash 与 Chapter canonical identity 不一致 | 立即停止 cutover/replay；排空非终态任务后 rollback owner，并保留现场审计 |
| `chapter_projection_cost_unknown` | projection AI usage 中存在 cost envelope 不完整或 pricing/usage 未知 | 检查 `ai_cost_unknown_counts`；补齐 pricing 或 provider usage，禁止用估算值回填 |
| `chapter_projection_usage_incomplete` | projection AI usage 中存在 `usage_complete=false` | 检查 provider usage 适配；在观测窗口内继续增长时禁止 cutover |
| `chapter_projection_external_failed` | external activity 的 `failed` 或 `retryable_failed` 数量大于 0 | 检查分类、provider 与 retry queue；先收敛失败，再评估 cutover |

关键恢复指标：

- `outbox_backlog` 回到 0，`outbox_oldest_age_seconds` 为空。
- `projection_expired_lease_count` 回到 0。
- `ambiguous_external` 回到 0，或每条均有人工处置记录。
- `generation_mismatch` 回到 0。
- shadow 的 `failed_observations` 与 `shadow_diff.unexplained_count` 均为 0，且
  `gate_ready` 为 true。
- 从进入 shadow 时保存的 metrics 基线起，`ai_usage_incomplete_count`、
  `ai_cost_unknown_count`、external `failed` 和 `retryable_failed` 均无新增。

metrics 只统计 `idempotent_external` 与 `ambiguous_external` activity。AI 调用同时输出
`ai_usage_record_count`、token totals、`ai_usage_incomplete_count`、
`ai_cost_known_count`、`ai_cost_unknown_count`、按币种分组的 `ai_cost_totals`，以及固定枚举的
`ai_cost_unknown_counts`。未知 activity status 归入 `unknown`，未知 cost reason 归入 `other`，
避免把 provider 或租户自由文本暴露为高基数指标。

只有同时存在 `cost_known=true`、`cost_amount` 和 `cost_currency` 的记录才进入成本汇总；
缺金额或币种的异常 envelope 归入 `cost_envelope_invalid`。不同币种不得相加。调用次数、
字符数和 `max_tokens` 都不是成本。进入 shadow 前保存累计基线；cutover 时比较增量，而不是
要求不可删除的历史累计值归零。观测窗口内只要 unknown/incomplete 增长，或发布预算无法由
已知币种成本验证，就必须停止 cutover。

## 4. Projection Ownership 与 Activity

| Projection | Durable side-effect class | Dependency / activity key | Active artifact 或状态 owner |
|---|---|---|---|
| `summary` | `ambiguous_external` | 无上游 projection；`summary_generation` | `Chapter.real_summary`、summary run result；成功后派生 downstream runs |
| `memory` | `ambiguous_external` | active/succeeded summary；`memory_{field}` | `CharacterState`、`ChapterSnapshot` 与 memory projection metadata |
| `rag` | `ambiguous_external` | 同 execution mode 的 succeeded summary；`rag_embedding` | `RagChunk`、`RagSummary` generation |
| `foreshadowing` | `ambiguous_external` | summary；activity key 来自每个 compute request | 非手工 `Foreshadowing` 与 status history |
| `trace` | `transactional` | 无外部 activity；聚合 workflow `JobEvent` | projection run 的 event counts result |
| `reconcile` | `transactional` | 所有 required projections succeeded 且 active mode 一致 | 唯一负责 `finalizing -> successful` 与 `ChapterFinalized` outbox |
| `tombstone` | `transactional` | immutable tombstone/superseded event | 只停用事件指定 revision/generation 的 artifact 与旧 active runs |

所有外部 activity 先持久化 intent/request key。HTTP 429/5xx 分类为 retryable，HTTP 4xx
与无效输入/结果分类为 permanent；其它未知异常进入 ambiguous/`needs_attention`，不能盲重放。
所有 active artifact 写入前都必须重新验证 canonical revision/hash/generation、rollout
owner/generation/fencing token 与 job lease fencing。

## 5. Dry-run 与 Replay

允许的 projection name：

```text
summary memory rag foreshadowing trace reconcile
```

先执行 dry-run：

```bash
python -m app.worker projection-dry-run \
  --operator-user-id 1001 \
  --project-id 11111111-1111-1111-1111-111111111111 \
  --chapter-id 42 \
  --revision 17 \
  --projection-name memory \
  --idempotency-key INC-1234-memory-r17-dry-run-1 \
  --reason "INC-1234 provider recovered" \
  --outbox-event-id 22222222-2222-2222-2222-222222222222
```

只有 stdout JSON 返回 `status: "eligible"` 时才能 replay。replay 使用新的幂等键：

```bash
python -m app.worker projection-replay \
  --operator-user-id 1001 \
  --project-id 11111111-1111-1111-1111-111111111111 \
  --chapter-id 42 \
  --revision 17 \
  --projection-name memory \
  --idempotency-key INC-1234-memory-r17-replay-1 \
  --reason "INC-1234 provider recovered" \
  --outbox-event-id 22222222-2222-2222-2222-222222222222
```

成功 replay 返回 `status: "queued"`、`projection_run_id` 与 `job_id`。失败只在 stderr
输出稳定 error code。单个管理员每分钟最多 10 次 dry-run/replay audit；不要通过更换管理员
绕过限流。

常见拒绝码：

| Error/reason code | 含义与处理 |
|---|---|
| `operator_not_found` / `operator_not_authorized` | 使用真实 active admin，禁止共用或伪造 operator id |
| `projection_scope_not_found` / `projection_revision_not_found` | project、chapter、revision 或 finalize outbox 不属于同一 scope |
| `stale_revision` / `tombstoned_revision` | 不重放旧 revision；回到 current canonical command |
| `canonical_identity_mismatch` / `outbox_revision_mismatch` | 停止操作并核对 immutable lineage，禁止手工修表 |
| `rollout_owner_mismatch` | 该 Chapter 仍由 legacy owner 控制，先完成 rollout 决策 |
| `projection_in_progress` | 已有 queued/running/retry_wait run，等待其终态 |
| `summary_dependency_missing` | 先恢复同 revision/mode 的 active succeeded summary |
| `summary_replay_requires_new_finalize` | successful revision 的 summary 不直接 replay，必须创建新的 finalize revision |
| `required_projection_gate_not_satisfied` | required projections 未全部成功且 active，不能 reconcile |
| `idempotency_key_conflict` | 幂等键已用于不同 mode/scope/reason；核对请求后使用新的明确 key |
| `rate_limit_exceeded` | 停止批量操作，等待一分钟窗口并重新评估范围 |

## 6. Shadow、Drain、Cutover 与 Rollback

管理 API prefix：

```text
/api/admin/chapter-projections
```

请求必须携带管理员 Bearer 凭据。凭据由密钥管理工具注入，不写入工单、脚本、日志或
runbook 示例。先读取当前状态：

```text
GET /api/admin/chapter-projections/rollouts/{chapter_id}?project_id={project_id}
```

所有 mutation body 都包含最新状态响应中的 CAS 值：

```json
{
  "project_id": "11111111-1111-1111-1111-111111111111",
  "chapter_id": 42,
  "expected_generation": 1,
  "expected_fencing_token": 0,
  "reason": "INC-1234 projection rollout"
}
```

### 6.1 状态与合法边

| State | Active owner | 正向迁移 | Rollback |
|---|---|---|---|
| `legacy` | `legacy` | `legacy -> shadow` | 无 |
| `shadow` | `legacy` | `shadow -> draining` | `shadow -> legacy` |
| `draining` | `legacy` | `draining -> projection` | `draining -> shadow` |
| `projection` | `projection` | 无 | `projection -> legacy`，按 manifest 精确恢复 legacy artifact |

### 6.2 进入 Shadow

调用：

```text
POST /api/admin/chapter-projections/rollouts/enter-shadow
```

在通用 body 上增加观察配置：

```json
{
  "project_id": "11111111-1111-1111-1111-111111111111",
  "chapter_id": 42,
  "expected_generation": 1,
  "expected_fencing_token": 0,
  "reason": "INC-1234 start shadow observation",
  "observation_seconds": 3600,
  "required_observations": 10
}
```

示例窗口不是全局政策，应按变更风险设定。进入 shadow 后 owner 仍为 legacy；shadow
artifact 不得 active。持续 GET 状态并检查 metrics，直到：

- 观察窗口结束；
- `successful_observations >= required_observations`；
- `failed_observations == 0`；
- 最新观察 revision 等于 Chapter current revision 且 outcome 为 `match`；
- `shadow_diff.unexplained_count == 0`；
- `gate_ready == true`。

任一条件失败，禁止进入 drain。调用 rollback 可从 shadow 返回 legacy，保留审计与 inactive
shadow artifact。

### 6.3 Prepare Cutover / Drain

使用最新 CAS 调用：

```text
POST /api/admin/chapter-projections/rollouts/prepare-cutover
```

服务会再次检查 gate，并拒绝存在同 Chapter 的 queued/running/retry_wait
`chapter_finalize` 或 `chapter_projection_*` job，错误码为 `rollout_jobs_not_drained`。
不要取消或直接改 lease；等待任务完成、失败或被 worker reclaim。成功后状态为 `draining`，
owner 仍为 legacy，fencing token 已变化，下一步必须重新 GET。

### 6.4 Complete Cutover

使用 draining 状态的最新 CAS 调用：

```text
POST /api/admin/chapter-projections/rollouts/complete-cutover
```

服务再次验证 gate 与 drain，然后在同一事务提升 shadow artifact、保存 rollback manifest，
并切换为 `owner=projection,state=projection`。响应后立即执行 metrics 与 rollout GET；如出现
generation mismatch、stale 激增或 active artifact 差异，停止新操作并进入 rollback。

### 6.5 Rollback

使用当前状态最新 CAS 调用：

```text
POST /api/admin/chapter-projections/rollouts/rollback
```

rollback 同样要求没有非终态 Chapter job：

- `shadow -> legacy`：停止 shadow 观察，legacy artifact 保持 active。
- `draining -> shadow`：恢复观察态，修复差异后重新评估 gate。
- `projection -> legacy`：严格按 cutover 保存的 manifest 恢复 legacy artifact；manifest
  缺失、revision/generation 漂移或跨 Chapter 数据都会拒绝。

rollback 只切 owner 和 active artifact，不删除 canonical revision、outbox、projection result、
inactive artifact generation 或 transition audit。

## 7. Outbox Backlog 恢复

先保存 metrics 时间点和告警代码，再用只读数据库连接定位当前 backlog。查询只返回 correlation
id，不读取 payload 或正文：

```sql
SELECT
    event.id AS outbox_event_id,
    event.project_id,
    event.chapter_id,
    event.revision,
    event.created_at
FROM chapter_outbox_events AS event
JOIN chapters AS chapter
  ON chapter.id = event.chapter_id
LEFT JOIN chapter_projection_runs AS summary
  ON summary.chapter_id = event.chapter_id
 AND summary.revision = event.revision
 AND summary.projection_name = 'summary'
 AND summary.source_hash = chapter.source_hash
WHERE event.event_type = 'ChapterFinalizationRequested'
  AND COALESCE(event.payload ->> 'execution_mode', '') <> 'legacy'
  AND event.revision = chapter.current_revision
  AND summary.id IS NULL
ORDER BY event.created_at, event.id;
```

恢复顺序：

1. 确认 worker healthy；若不 healthy，先恢复 active executor generation 的 worker。
2. 对每条记录执行 `summary` dry-run，并显式传入 `outbox_event_id`。
3. 只对 `eligible` 记录逐条 replay；每条使用不同 replay 幂等键，遵守每分钟 10 次限流。
4. 观察新 `job_id` 进入终态；不要在 queued/running/retry_wait 时创建第二次 replay。
5. 重跑 metrics，直到 backlog 为 0、oldest age 清空，且没有 generation mismatch、
   needs-attention 或 dead-letter。
6. 执行一次 rollout GET，确认 owner/state/generation/fence 未被恢复操作意外改变。

## 8. Retention Preview 与 Purge

retention 只允许清理已 supersede/tombstone revision 的失活 `rag` 或非手工
`foreshadowing` 制品。canonical revision、outbox、projection run、手工伏笔、active
制品、`legacy` generation 与 retention audit 永不由该命令删除。

先使用 active admin 执行 preview：

```bash
python -m app.worker projection-retention-preview \
  --operator-user-id 1001 \
  --project-id 11111111-1111-1111-1111-111111111111 \
  --chapter-number 42 \
  --revision 16 \
  --artifact-generation 33333333-3333-3333-3333-333333333333 \
  --artifact-kind rag \
  --idempotency-key INC-1234-rag-r16-preview-1 \
  --reason "INC-1234 retention review" \
  --max-rows 500
```

只有 stdout 返回 `status: "eligible"`，且 `candidate_rows` 与工单预期一致时才能 purge。
purge 必须使用新的幂等键，但保持相同的 project/chapter/revision/generation/kind 与
`max_rows`：

```bash
python -m app.worker projection-retention-purge \
  --operator-user-id 1001 \
  --project-id 11111111-1111-1111-1111-111111111111 \
  --chapter-number 42 \
  --revision 16 \
  --artifact-generation 33333333-3333-3333-3333-333333333333 \
  --artifact-kind rag \
  --idempotency-key INC-1234-rag-r16-purge-1 \
  --reason "INC-1234 retention review" \
  --max-rows 500
```

服务按精确 `ChapterRevision.id + revision + projection_name + artifact_generation` 锁定 run，
再锁定失活候选并检查同 scope 是否出现 active 制品。DELETE 仍携带 project、chapter、
revision、generation、inactive，以及 foreshadowing 的 `is_manual=false` 条件；删除行数变化会
整体 rollback 并返回 `artifact_state_changed`。completed purge 由目标唯一约束防止重复执行，
每次 preview、成功 purge 或拒绝都会保留审计。单个管理员每分钟最多 10 次 retention 操作。

常见拒绝码：

| Error/reason code | 含义与处理 |
|---|---|
| `operator_not_found` / `operator_not_authorized` | 使用真实 active admin；停用账号不可操作 |
| `revision_not_found` | project、chapter number 与 revision 未定位到同一 revision |
| `legacy_generation_protected` / `current_generation_protected` | 目标仍受 legacy/current 保护，不得清理 |
| `revision_not_retirable` | revision 不是 `superseded` 或 `tombstoned` |
| `active_projection_run` / `projection_in_progress` / `active_artifacts` | 等待任务终态或 owner 切换；禁止强删 |
| `retention_batch_too_large` | 缩小精确 scope 或提高经审核的 `max_rows` 后重新 preview |
| `no_inactive_artifacts` / `artifact_generation_already_purged` | 无可清理行或该目标已完成 purge；不要换 key 重复删除 |
| `artifact_state_changed` | preview 与 DELETE 间状态变化，事务已回滚；重新读取并 preview |
| `idempotency_key_conflict` | key 已用于不同 mode/scope/reason；核对后使用新 key |
| `rate_limit_exceeded` | 停止批量操作，等待一分钟窗口 |

## 9. 故障处置原则

- `rollout_cas_mismatch`：重新 GET，重新判断，不把旧请求原样重试。
- `rollout_jobs_not_drained`：等待非终态 job 收敛；检查 worker health、expired lease 和 retry age。
- shadow gate reason：修复对应观察条件；不得覆盖 diff 或手工增加 observation count。
- ambiguous external：核对 provider request key 和上游结果；未确认前保持 `needs_attention`。
- stale/tombstone：保留历史。迟到事件只能停用其自身 target revision/generation。
- binary rollback：`e7c9a1b2d3f4` 与 head `f2a6c9d4e8b1` 都保留 canonical/audit 数据；
  F2 `downgrade()` 会明确拒绝。只部署通过 `db-check` rollback floor 的 binary，禁止删除
  projection、AI usage 或 retention audit tables。
