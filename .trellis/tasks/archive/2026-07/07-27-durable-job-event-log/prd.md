# 建立 Durable Job 与 Event Log

## Goal

用 PostgreSQL 持久任务控制面和独立 worker 替换 Web 进程内长任务，并把状态通知升级为带 cursor 的可重放事件流。

## Background

- 路由创建 `BackgroundTask` 后用 FastAPI `BackgroundTasks.add_task` 执行，Web 进程重启会留下无人接管的 queued/running 记录：`backend/app/api/routers/writer.py:1668-1701,1744-1759`。
- 任务模型没有 lease、attempt 或 schedule 字段：`backend/app/models/background_task.py:13-40`。
- Redis publish 是 fire-and-forget；SSE/前端靠轮询兜底：`backend/app/services/event_bus.py:62-101,109-137`、`frontend/src/queries/tasks.ts:15-21`。

## Requirements

- JOB-1：持久 JobRun 支持 payload version、idempotency key、available time、attempt/max attempts、lease owner/expiry、heartbeat、cancel 和 dead-letter。
- JOB-2：多个 worker 使用原子 claim + fencing token，任何时刻最多一个有效 lease owner 能提交同一 attempt。该保证只覆盖数据库 outcome；外部调用使用独立 activity idempotency/ambiguity contract。
- JOB-3：worker crash、lease expiry 和进程优雅退出都有确定恢复语义；不可重试错误直接失败，可重试错误按 policy backoff。
- JOB-4：所有 state/progress/log transition 与 append-only JobEvent 在同一事务提交。
- JOB-5：SSE 从 PostgreSQL event cursor 读取，支持 `Last-Event-ID`、断线补发、去重、retention reset 和 owner scope。
- JOB-6：Redis 仅负责 wake-up；未配置、断线或重启时 worker scan/SSE poll 仍保证正确。
- JOB-7：API 只 enqueue 并返回 202/durable id；所有现有 `BackgroundTasks` 长任务迁入 registry/handler。
- JOB-8：任务 public event/error payload 使用白名单 schema，不包含 token、密钥或完整私有 prompt。
- JOB-9：现有 task list/detail/reminder 行为在兼容窗口保持，新增内部状态通过明确 mapping 映射到当前四态 UI。
- JOB-10：handler registry 强制声明 `transactional`、`idempotent_external` 或 `ambiguous_external`。外部 activity 写 durable intent/result；provider 不支持幂等且调用结果未知时进入 `needs_attention/dead_letter`，禁止自动盲重试。
- JOB-11：snapshot API 在同一数据库快照中返回 `snapshot_revision + resume_cursor`；workflow/project child job 统一写入一个授权明确的 stream。

## Dependencies

- 必须在 `07-27-explicit-database-bootstrap` 后实施，worker 不得继承隐式 migration/bootstrap。
- 为 projections 与 durable Chapter workflow 提供执行和事件基础设施。

## Acceptance Criteria

- [x] 两个 worker 并发 claim 同一任务时只有一个成功；过期 worker 使用旧 fencing token 不能提交。
- [x] 执行中强制终止 worker，lease 到期后另一 worker 接管；attempt、事件顺序和最终状态正确。
- [x] 同一 idempotency key 的重复 enqueue 返回同一 active/succeeded job，只产生一次 canonical DB outcome；外部调用按其声明的 activity 语义验证。
- [x] crash-after-external-call-before-result 分别验证 provider dedupe 和 ambiguous dead-letter，不把 DB fencing 误当外部 exactly-once。
- [x] retry/backoff、不可重试失败、max-attempt dead-letter 和 cancel 各有集成测试。
- [x] SSE 从旧 cursor 重连按序补齐；Redis 关闭时测试仍通过。
- [x] snapshot/cursor 并发边界测试证明 snapshot 后发生的事件不会遗漏或倒退；cursor reset 必须获取新 snapshot pair。
- [x] API 路由中不再使用 FastAPI `BackgroundTasks` 承载章节长任务。
- [x] AppShell 的现有 running/succeeded/failed reminder 契约不回归。

## Out Of Scope

- 不构建通用跨项目 SaaS 队列平台。
- 不引入 Temporal、Celery/Redis broker 或第二套 durable queue。
- 不在本子任务迁移完整 Chapter LangGraph；这里只提供 runtime 基础。
