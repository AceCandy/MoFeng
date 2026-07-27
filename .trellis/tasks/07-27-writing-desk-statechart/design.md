# WritingDesk Statechart Design

## Ownership

```text
Vue Query: Project / Chapter / Workflow snapshot server cache
XState actor: 当前交互状态、run correlation、pending command、last cursor
Vue refs: 纯展示状态（drawer/modal/focus），不表达服务端 lifecycle
```

machine context 不保存完整 Chapter/NovelProject；通过 typed selectors 读取 query snapshot。切换 chapter 会停止旧 event subscription/actor，创建或 rehydrate 新 actor。

## State Model

顶层处理 `booting`, `ready`, `reconnecting`, `fatal`。`ready` 内嵌 workflow states：

- idle
- submitting
- running
- waitingForSelection
- finalizing
- projectionPending
- succeeded
- failed（带 failure kind 与 allowed retry target）
- cancelled

服务端 snapshot 是 reconciliation event，可以纠正本地 transient state；revision 较旧的 snapshot/event 被 guard 拒绝。

## Events And Actors

- UI commands：START、SELECT_VERSION、FINALIZE、RETRY_NODE、RETRY_PROJECTION、CANCEL。
- server events：RUN_SNAPSHOT、JOB_EVENT、STREAM_DISCONNECTED、CURSOR_RESET。
- actors：Vue Query mutation promise、snapshot refetch、SSE subscription。

mutation success 不直接猜测终态，只记录 command accepted并等待 snapshot/event。mutation error 转为 typed command failure，不覆盖已知 server run state。

## Rehydration

路由/章节选择后：

1. query 原子 run snapshot，响应同时包含 `snapshot_revision + resume_cursor`；
2. 创建 machine snapshot；
3. 只从该 `resume_cursor` 之后订阅 SSE，并按全局 cursor/stream sequence 去重；
4. cursor expired 时丢弃旧 resume boundary，重新 fetch 一对新的 snapshot/cursor，再继续。

last cursor 可以保存在当前 view/session；它不是业务事实，丢失后全量 snapshot 仍可恢复。

## Testing

- pure machine transition table/model tests；
- actor tests 使用 fake query/mutation/SSE；
- component integration 验证 rendered controls 与 allowed commands；
- browser test 验证 refresh、disconnect、duplicate click 和 stale event。

## Rollout

新 statechart 在 feature flag 下先读取同一 query/SSE shadow snapshot，不提交 command；比较派生状态。cutover 后只保留一套 command owner。legacy composables 延迟一个发布窗口删除。

## Rollback

路由/feature flag 切回 legacy composables；durable backend workflow 继续运行，旧 UI 通过 compatibility snapshot/status adapter 展示。不能让两套 UI 同时提交 command。
