# Durable Chapter Runtime Selection

## Decision

本轮采用 **PostgreSQL durable job/event log + 独立 worker + LangGraph PostgreSQL checkpointer**。
Temporal 保留为达到明确升级条件后的替代控制面，不进入本轮基线。

选择依据不是改造工作量，而是核心一致性边界：MoFeng 的 Chapter、任务状态、trace、memory 与 pgvector 数据均已由同一个 PostgreSQL 承载。任务领取、领域写入、outbox 与事件追加可以共享事务；Temporal 的 workflow history 与业务数据库属于两个持久化系统，仍需额外的 outbox、幂等与补偿机制。

## Current Evidence

- 章节流水线已使用 LangGraph `StateGraph`，但 `compile()` 没有 checkpointer；恢复依赖应用代码删除 trace、重建 state 与 recovery graph：`backend/app/services/pipeline_orchestrator.py:340-423,386-397`。
- 长任务仍由 FastAPI `BackgroundTasks` 执行，DB 中虽有任务记录，Web 进程退出后没有其他执行者接管：`backend/app/api/routers/writer.py:1668-1701,1744-1759`。
- `BackgroundTask` 只有状态、进度、payload、结果和日志，没有 lease、attempt、heartbeat 或 next-run 语义：`backend/app/models/background_task.py:13-40`。
- Redis Pub/Sub 明确是可丢的轻量通知，发布失败静默，调用方依赖轮询兜底：`backend/app/services/event_bus.py:2-7,62-101,109-137`。
- LLM 重试只覆盖单次模型调用，不负责外层 workflow 恢复：`backend/app/services/llm_service.py:28-45,478-514`。
- 部署目前只有单 uvicorn worker、PostgreSQL 和可选 Redis，没有独立 worker 或 workflow control plane：`deploy/supervisord.conf:8-19`、`deploy/docker-compose.yml:1-103`。
- 当前依赖为 `langgraph==1.2.2`，尚未引入 PostgreSQL checkpointer：`backend/requirements.txt:17-25`。

## Comparison

| Dimension | Temporal Python | PostgreSQL + worker + LangGraph checkpoint |
| --- | --- | --- |
| Worker crash recovery | event history replay、activity heartbeat/retry 原生提供 | job lease、heartbeat、reaper 与 retry 由项目实现；graph state 由 checkpoint 恢复 |
| Idempotency | Activity 至少一次，业务副作用仍需幂等键 | worker 至少一次，业务副作用仍需幂等键；唯一约束可与业务写入同库 |
| Timers and signals | durable timer、Signal/Update/Schedule 为一等能力 | `available_at`、command/event row 自建；适合当前短流程和人工确认 |
| Transaction boundary | Temporal history 与业务 PostgreSQL 无法组成同一 ACID 事务 | job transition、domain write、outbox/event append 可在同一 PostgreSQL 事务内提交 |
| Observability | UI、history、visibility、metrics 体系成熟 | 复用现有 task/trace UI，但队列延迟、死信、replay 视图需建设 |
| Deployment | 新增 Temporal server/Cloud、namespace、worker 与独立故障域 | 复用 PostgreSQL，新增同镜像 worker 和显式 migrate/bootstrap step |
| Migration | 将现有 graph 拆成 deterministic Workflow + Activities，双系统迁移 | 保留 LangGraph 节点，先替换执行入口，再接 checkpoint 与 command resume |

## Required Capabilities For The Chosen Route

该选择只有在以下能力全部实现时才成立，不能把“数据库里有任务记录”误称为 durable runtime：

1. 原子 claim：`FOR UPDATE SKIP LOCKED` 或等价语义。
2. lease、heartbeat、过期回收与 worker 优雅退出。
3. attempt、错误分类、指数退避、最大重试和 dead-letter。
4. 业务幂等键与数据库唯一约束；外部 LLM/embedding 结果按 step key 缓存。
5. job state change 与 append-only `job_events` 同事务提交。
6. SSE 使用持久 cursor/`Last-Event-ID` 重放；Redis 只负责唤醒。
7. LangGraph PostgreSQL checkpoint 使用稳定 `thread_id`，恢复时不重新执行已持久化副作用。
8. worker、API 与 migration/bootstrap 进程职责分离。

## Production Readiness Gate

PostgreSQL 路线不得仅凭功能测试上线。cutover 前必须：

- 记录预期峰值、payload 大小、最长任务时长和 retention 预算；
- 以至少 2 倍目标负载验证 claim latency、event/projection lag 和数据库资源占用；
- 配置并验证 worker crash recovery SLO（上界由 lease + scan interval 决定）；
- 验证 queue/event/checkpoint retention cleanup、备份与恢复；
- 对 oldest queued age、expired lease、dead-letter、ambiguous external result、event lag 和 projection lag 建立告警；
- 完成 Redis-off、worker kill、DB reconnect 和 rolling deploy 演练。

若任一门禁不能满足，或为其他业务域新增复杂 durable timer/signal/schedule 原语，本轮选择必须重新审议，不允许默认继续扩展自建 control plane。

## Temporal Upgrade Triggers

出现任一条件时重新评估 Temporal，而不是继续扩展自建调度器：

- workflow 跨多个服务或语言运行；
- 需要天/周级 durable timers、大量 Signal/Update 或复杂 schedule；
- 需要控制面原生的 history、visibility、横向 worker failover 与审计 SLA；
- 自建 lease/reaper/retry/command 语义开始成为独立平台产品；
- 团队已接受并具备维护 Temporal Server/Cloud 的长期运维能力。

## Sources

- Temporal Workflow overview: https://docs.temporal.io/encyclopedia/workflow/workflow-overview
- Temporal Python failure detection: https://docs.temporal.io/develop/python/failure-detection
- Temporal Python message passing: https://docs.temporal.io/develop/python/workflows/message-passing
- Temporal visibility: https://docs.temporal.io/visibility
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph durable execution: https://docs.langchain.com/oss/python/langgraph/durable-execution
- LangGraph PostgreSQL checkpoint package: https://pypi.org/project/langgraph-checkpoint-postgres/

文档检索日期：2026-07-27。具体依赖版本必须在对应子任务实现前按 `langgraph==1.2.2` 的兼容矩阵重新锁定。
