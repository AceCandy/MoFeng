# 修复章节实时进度停滞

## Goal

章节工作流运行时，页面应随最新 SSE cursor 推进生成节点，不需要刷新页面才能从“整理前文”切换到后续阶段。

## Background

- 后端会为每个 activity 提交新的 `ChapterWorkflowRun.node_key`、`row_revision` 和 workflow 事件。
- 相邻的 `activity.succeeded` 与下一节点 `activity.started` 可能只间隔约 50ms。
- `useChapterWorkflowActor` 当前会为每个新 cursor 发起 current lookup，并只接纳最后发起的请求：`frontend/src/composables/useChapterWorkflowActor.ts:447`、`:570`。
- actor 的 lookup port 使用同一 Vue Query key：`frontend/src/queries/chapterWorkflow.ts:221`。项目锁定的 `@tanstack/query-core@5.100.10` 会复用同 key 的在途请求，因此“最后发起”的 lookup 仍可能得到前一次旧快照。
- 刷新页面会发起全新的 current lookup，所以能立即显示数据库中的最新节点。

## Requirements

- 同一 scope 的 workflow lookup 在任意时刻最多有一个实际请求在途。
- lookup 在途期间若收到更新 cursor，当前请求结束后必须补查一次，以收敛到最新 workflow 快照。
- 多个在途期间的唤醒可以合并，但不能漏掉最后一次唤醒。
- 保留现有 scope、connection epoch、run identity 和 row revision 防旧快照保护。
- 重复 cursor 不得触发无意义补查。
- 不改变后端事件协议、生成流程、进度节点映射或页面视觉结构。

## Acceptance Criteria

- [x] 快速连续收到两个新 cursor，且第一次 lookup 返回旧节点时，actor 会自动再查一次并应用最新节点，无需刷新页面。
- [x] lookup 在途期间收到多个新 cursor，只追加一次必要的后续 lookup，不形成请求风暴。
- [x] 重复 cursor、迟到结果、scope 切换、reset/reconnect 的现有保护继续通过测试。
- [x] 章节生成进度相关聚焦测试、TypeScript 类型检查和相关 lint 通过。

## Out of Scope

- 修改 durable workflow 或 JobEvent 的后端写入逻辑。
- 修改章节详情 query key、trace 投影或候选正文刷新逻辑。
- 调整生成进度组件的文案、布局或节点数量。

## Technical Notes

- 优先在 `useChapterWorkflowActor` 的唤醒协调处修复根因，复用现有 lookup 与状态机，不增加依赖或新抽象层。
- 回归测试需要模拟真实 Vue Query 的同-key在途复用，或等价地覆盖“lookup 在途时 cursor 再推进”的行为，不能只使用彼此独立的 mock Promise。
