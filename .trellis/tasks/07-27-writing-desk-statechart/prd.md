# 重构 WritingDesk 为 Statechart

## Goal

用显式 statechart 统一 WritingDesk 的章节命令、长流程状态、SSE 重连、人工选版、定稿、projection pending 和失败重试，消除散落 ref/computed/watcher 对服务端生命周期的隐式推断。

## Background

- `WritingDesk.vue` 同时组合多个 chapter composable，并在本地维护 selected chapter、generation result、version index 与 generating chapter：`frontend/src/views/WritingDesk.vue:145-364`。
- 生成、状态流、选版、定稿和 retry 分布于 `useWritingDeskChapterGeneration`、`useWritingDeskProject`、`useWritingDeskConfirm` 等模块，缺少统一 transition contract。
- 当前 generation status 是手工 TypeScript union，异步 workflow/projection 状态扩展后更容易漂移：`frontend/src/api/novel.ts:309-335`。

## Requirements

- UI-1：采用 XState 与 Vue binding，定义可枚举 state、event、guard、actor 和 allowed commands；不手写另一套 ad-hoc reducer。
- UI-2：machine 至少覆盖 idle/loading/submitting/running/waiting-for-selection/finalizing/projection-pending/reconnecting/succeeded/failed/cancelled。
- UI-3：服务端 Chapter/run snapshot 与 generated transport types 是状态事实；Vue Query 继续拥有 server cache，machine 不复制完整项目/章节列表。
- UI-4：SSE event 先经过 runtime decoder，再按 run id、revision、cursor 去重并发送给 actor；stale/unknown event 不改变当前 run。
- UI-5：刷新页面、切换章节和 SSE 断线后从 snapshot + last cursor 恢复；不能依赖内存中的 `generatingChapter`。
- UI-6：重复 start/select/finalize/retry/cancel 由 guard 阻止，并由服务端幂等作为最终保护。
- UI-7：每个 failure state 明确允许的 retry/resume/cancel 操作和用户可见信息；projection failure 不伪装成 generation failure。
- UI-8：所有 API effect 通过现有 Vue Query mutations/queries actor 化；不从组件/composable 直接 fetch。
- UI-9：状态提示具备文本/ARIA 语义，不能只靠颜色；保留现有 task reminder 契约。

## Dependencies

- 依赖 durable workflow/job event API 和 generated transport contracts。
- 这是七个实现子任务中的最后一个，完成用户可见 cutover。

## Acceptance Criteria

- [ ] model tests 枚举每个 state/event 的合法与非法 transition，并覆盖 guard。
- [ ] 页面刷新后能恢复 waiting-for-selection、projection-pending 和 failed run。
- [ ] SSE 断线期间产生的事件通过 cursor 补齐；重复/乱序/stale revision event 不导致状态倒退。
- [ ] 双击 start/finalize/retry 只提交一个有效 command，UI 和服务端均可证明。
- [ ] Vue Query cache 是 Chapter/project 唯一 server cache；Pinia/statechart 未复制实体列表。
- [ ] 旧 generation composables 中的 lifecycle 布尔值和 watcher 在 cutover 后删除，无双状态源。
- [ ] type-check、Vitest、lint 和 WritingDesk 关键浏览器流程通过。

## Out Of Scope

- 不重做 WritingDesk 视觉设计、信息架构或无关组件。
- 不把全站状态迁入 XState。
- 不移除 Vue Query 或 AppShell task reminder。
