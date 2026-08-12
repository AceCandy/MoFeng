# 补齐 scoped task SSE 纵深校验

## Goal

完成增量审计 T1，让客户端在处理 `task` SSE 事件前复核事件内 task 的 stream scope，
防止未来服务端、代理或 fixture 漂移把其他流的任务写入当前状态。

## Requirements

- `decodeBackgroundTaskEvent(payload, expectedScope?)` 在既有 version/cursor/task shape 校验
  后，复用 `matchesStreamScope` 校验 `task.stream_type` 和 `task.stream_id`。
- 有 expected scope 时必须完全匹配；不匹配返回
  `{ kind: 'malformed', reason: 'scope' }` 且不得调用 `onTask`。
- 无 expected scope 时继续允许任意合法 scoped task，保持全局任务流兼容性。
- `decodeBackgroundTaskStreamMessage` 的 task 分支传递 expected scope；不新增错误类型、
  reducer 状态或重连策略。
- 契约规范明确 snapshot 顶层 scope 与 task 事件内 task scope 的不同校验位置。

## Out Of Scope

- 不修改服务端查询、SSE schema、OpenAPI、generated types 或 API 路径。
- 不改变现有同 scope snapshot 恢复和 polling fallback 策略。

## Acceptance Criteria

- [ ] 匹配 expected scope 的 task event 被接受；stream type 或 stream id 任一不同均以
  `reason: 'scope'` 拒绝。
- [ ] 无 expected scope 的全局流仍接受合法 scoped task。
- [ ] 被拒绝事件不调用 `onTask`，既有同 scope snapshot 恢复仍携带原 expected scope。
- [ ] focused task tests、前端 lint、type-check 和 unit tests 通过。
- [ ] transport contract 与实现、测试一致，`git diff --check` 通过。

