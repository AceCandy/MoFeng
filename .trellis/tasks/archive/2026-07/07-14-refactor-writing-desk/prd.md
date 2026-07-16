# 拆 WritingDesk.vue（2009 行→<500）

## Goal

将 `frontend/src/views/WritingDesk.vue`（2009 行）拆分至 <500 行，运行时行为 100% 等价。属 parent `07-12-engineering-baseline` acceptance 第 4 项「5 大前端组件 <500 行」的子项。

## 现状

- 路径：`frontend/src/views/WritingDesk.vue`，2009 行（路由 `/novel/:id` 主页面）。
- 调用方：路由直接挂载。
- 测试覆盖：间接（依赖 WDWorkspace 等子组件的测试）。
- 职责：页面级组合——`WDSidebar` + `WDWorkspace` + `WDAssistantPanel` + 多 Modal（`WDEditChapterModal`/`WDGenerateOutlineModal`/推荐优化结果等）、drawer 管理（侧栏/助手栏开关与互斥）、章节选择（`selectedChapter`）、项目加载（`loadProject`/`refetchChapterIntoProject`）。

## Requirements

- 主组件降至 <500 行，抽出 composable（drawer 管理、章节/项目加载逻辑）与子组件（Modal 群）。
- 行为等价：drawer 开关与互斥、章节选择、项目加载、各 Modal 开关与回调不变。
- Vue scoped style 随 template 迁移。
- 三件套绿：`vue-tsc --noEmit` exit 0 / `vitest run` 全绿 / `eslint` 0 新增 error。
- 注意：WritingDesk 是 WDWorkspace 的父组件，改动不得破坏 WDWorkspace（已由 parent Slice B/D 抽过）的既有契约。

## Acceptance Criteria

- [ ] `WritingDesk.vue` < 500 行。
- [ ] 三件套全绿。
- [ ] 行为等价（drawer/章节选择/项目加载/Modal 流程手测或测试覆盖）。
- [ ] 抽出的子组件/composable 补 AIMETA 首行。

## Notes

- 复杂任务：`task.py start` 前补 `design.md` + `implement.md`。
- parent：`07-12-engineering-baseline`（acceptance 第 4 项）。
