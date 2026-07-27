# Durable Chapter Workflow Design

## Run Identity

`run_id` 是 API、LangGraph thread、workflow event stream 和前端 correlation identity；root JobRun/child jobs 保留独立 job id并引用 run id。数据库 partial unique constraint 覆盖 active states 的 `(project_id, chapter_number, base_revision)`；run payload 记录 workflow schema version 与 frozen context reference/hash。

active states 为 queued/running/retry_wait/waiting_for_selection/finalizing/projection_pending/cancelling；terminal states 为 successful/failed/cancelled/superseded。run 与 root JobRun 的 active/terminal transition、event append 和 unique-slot release 在同一事务。自动 retry 不释放；exhausted/permanent failure 释放。terminal user retry 仅在不存在 successor run 时原子重新占用 slot，否则转向 successor。stale-run reconciler 比较 run、JobRun、checkpoint 和 Chapter revision。

## Graph

```text
queued
  -> context_frozen
  -> planning/directing
  -> generating
  -> reviewing
  -> waiting_for_selection (interrupt)
  -> finalizing (canonical revision + outbox)
  -> projection_pending
  -> observe Chapter successful
  -> run successful

any executable state -> retry_wait / failed / cancelled
```

`waiting_for_selection` 不占 worker lease。select command 入库并唤醒 job，LangGraph Command/resume 使用 checkpoint 继续。

## Node Contract

每个 node 接收/返回 versioned serializable state。外部对象（AsyncSession、LLM client、ORM model）不进入 checkpoint。

有副作用 node 使用：

- `step_key = run_id + node_key + logical_input_hash`
- execution/result row unique key
- external call 前持久化 intent，返回后短事务写 result
- replay 时已有 completed result 直接复用

LLM exactly-once 无法保证；crash-after-response-before-persist 可能再次调用。通过 provider request id（若支持）、step key、成本事件和 deterministic DB outcome 降低风险，并在文档中明确语义。

## Command Inbox

command envelope：`command_id`, `run_id`, `type`, `expected_revision`, `payload_version`, payload, actor, created time。唯一 command id 防重。worker 在同一事务标记 consumed 并 append event；stale command 记录 rejected event。

## API

- start：创建/返回 run，202。
- snapshot：Chapter + run current state + allowed commands + last event cursor。
- command：select version、retry node/projection、cancel。
- event stream：所有 root/child/projection 用户事件写入 `workflow/run_id` 的 durable JobEvent stream；Chapter outbox 不直接暴露。

旧 `/advanced/generate` 在兼容期转发 start，并用明确 contract 表达异步，不在 request 内等待。若必须保持旧同步 response，则只作为限期 compatibility polling adapter，不能执行 workflow 本体。

## Recovery

job runtime 负责重新分配执行，checkpointer 负责 graph state，step result store 负责副作用 outcome 防重，Chapter/outbox 负责领域一致性。四者通过 run id/revision 关联，但不互相冒充事实源。外部调用仍遵循 job activity class；ambiguous result 不因 graph replay 自动重做。

reconciler 检测 JobRun terminal、checkpoint state、Chapter lifecycle 和 projection status 不一致，追加诊断 event并提供安全修复命令。

## Versioning And Deployment

运行中的 workflow 按 workflow schema version 路由到兼容 graph definition。部署不得修改旧 history 无法 replay 的 node 名/shape；breaking graph change 新增 version。contract 阶段只在旧 run drain 或 migration 后删除旧 graph。

## Rollback

入口 flag 可停止新 run 使用新 graph。rollout generation 与 root lease fencing 同事务切换，先停止旧 claim并 drain/expire，再启用新 owner。已创建的新 run 由兼容 worker drain；旧 pipeline 不领取带新 workflow version 的 job，避免同一 Chapter 双执行。
