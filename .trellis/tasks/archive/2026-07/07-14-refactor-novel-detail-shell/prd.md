# 拆 NovelDetailShell.vue（1662 行→<500）

## Goal

将 `frontend/src/components/shared/NovelDetailShell.vue`（1662 行）拆分至 <500 行，运行时行为 100% 等价。属 parent `07-12-engineering-baseline` acceptance 第 4 项「5 大前端组件 <500 行」的子项。

## 现状

- 路径：`frontend/src/components/shared/NovelDetailShell.vue`，1662 行。
- 调用方：`AdminNovelDetail.vue`、`NovelDetail.vue`。
- **测试覆盖：无**（codegraph 未发现覆盖测试）。
- 职责：小说详情外壳——section 动态分发（`sectionComponents[activeSection]`/`switchSection`/`loadSection`/`reloadSection`）、蓝图编辑 Modal（`handleSectionEdit`/`handleSave`/`startAddChapter`，经 `BlueprintEditModal` + `updateBlueprintMutation`）、侧栏开关、写作台跳转（`goToWritingDesk`）、`isAdmin` 只读分支。

## Requirements

- 主组件降至 <500 行，抽出 composable（section 分发、加载逻辑）与子组件（侧栏、编辑 Modal 群）。
- 行为等价：section 切换与懒加载、蓝图字段编辑保存、新增章节、侧栏、跳转、管理员只读分支不变。
- Vue scoped style 随 template 迁移。
- 三件套绿：`vue-tsc --noEmit` exit 0 / `vitest run` 全绿 / `eslint` 0 新增 error。
- 因无既有测试，首块拆分前先补关键路径测试或固化手测清单。
- 注意：section 动态分发模式与 WDWorkspace `currentComponent` 类似。

## Acceptance Criteria

- [ ] `NovelDetailShell.vue` < 500 行。
- [ ] 三件套全绿。
- [ ] 行为等价（section 切换/蓝图编辑/新增章节/跳转/管理员分支手测或测试覆盖）。
- [ ] 抽出的子组件/composable 补 AIMETA 首行。

## Notes

- 复杂任务：`task.py start` 前补 `design.md` + `implement.md`。
- parent：`07-12-engineering-baseline`（acceptance 第 4 项）。
