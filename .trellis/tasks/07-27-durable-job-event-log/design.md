# Durable Job And Event Log Design

## Storage

优先演进现有 task persistence，而不是并存两个用户任务真相。实现时通过 Alembic expand 表/字段，并提供 legacy row backfill/mapping。

`JobRun` current state 与 `JobEvent` history 分离：

- current row 用于高效 list、claim 和状态查询；
- append-only event 用于 SSE、审计和重建；
- transition service 是唯一同时写两者的入口。

JobEvent 使用全局 bigint cursor 和 stream-local sequence。standalone job 的 stream id 是 job id；workflow root/child/projection jobs 的用户可见 stream id 是 run id。`(stream_type, stream_id, sequence)` 唯一，cursor 只增不改。Chapter outbox 不是 SSE stream，只有 consumer 在更新 projection status 时追加的 JobEvent 才对 UI 可见。

## Claim And Fencing

worker transaction：

1. 选择 `queued/retry_wait` 且 `available_at <= now()`，或 lease 已过期的 `running` row；
2. `FOR UPDATE SKIP LOCKED`；
3. 增加 attempt/fencing token，写 lease owner/expiry；
4. append `job.started`/`job.reclaimed`；
5. commit 后执行 handler。

heartbeat 只在 token 匹配时延长 lease。success/failure/progress 同样带 token 条件，防止失去 lease 的旧 worker 覆盖新 owner。

## Handler Boundary

registry 以 `job_type + payload_version` 找到 typed handler，并强制声明 side-effect class：

- `transactional`：所有 outcome 在受 fencing 的 PostgreSQL 事务内完成；
- `idempotent_external`：先写 durable activity intent，使用 provider idempotency/request key，结果按 activity key upsert；
- `ambiguous_external`：provider 无法去重；调用后失去 lease或结果未知时不自动重放，转 `needs_attention/dead_letter` 由 reconciler/operator 判定。

handler 不接收 request/session 对象；每个短事务显式获取 session。fencing 只决定数据库提交权，不能宣称撤销外部副作用。

未知 payload version 进入 dead-letter，而不是猜测字段。

## Retry

错误映射为 retryable、permanent、cancelled。policy 定义最大 attempt、base/max delay 和 jitter。每次失败都持久化 public category；内部异常只进入安全日志，不进入 SSE payload。

## SSE

SSE endpoint 先授权 user/stream scope，再从 `cursor > last_id` 批量读取。snapshot endpoint 在同一只读事务中取得 current state 与当时最大可见 `resume_cursor`。无新事件时等待 Redis wake-up 或 timeout 后重查 DB。cursor 超出 retention 返回 typed reset，客户端必须重新获取新的 `snapshot_revision + resume_cursor` pair 后继续。

Redis payload 只包含非敏感 wake-up hint；即使重复或丢失都不改变结果。

## Compatibility

对外 `BackgroundTask` list/detail 暂时保留四态：`retry_wait` 映射 queued，`dead_letter` 映射 failed，cancelled 在 contract 扩展后再公开。旧轮询继续作为低频 fallback。

## Operations

提供 worker health、queue depth、oldest queued age、expired lease、retry/dead-letter/needs-attention、event lag 和 retention cleanup counters。管理操作（retry/cancel）自身也是带 idempotency key 的 command，并追加 event。cutover 前执行 2 倍目标负载与配置化 recovery SLO 演练；失败则重新评估 Temporal。
