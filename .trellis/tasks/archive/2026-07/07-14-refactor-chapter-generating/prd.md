# 拆 ChapterGenerating.vue（2261 行→<500）

## Goal

将 `frontend/src/components/writing-desk/workspace/ChapterGenerating.vue`（2261 行）拆分至 <500 行，运行时行为 100% 等价。属 parent `07-12-engineering-baseline` acceptance 第 4 项「5 大前端组件 <500 行」的子项。

## 现状

- 路径：`frontend/src/components/writing-desk/workspace/ChapterGenerating.vue`，2261 行。
- 调用方：`useChapterStatus.ts`（动态分发）、`WDWorkspace.vue`。
- **测试覆盖：有** `frontend/src/components/__tests__/chapterGeneratingTiming.spec.ts`（5 大中唯一有专门测试者，安全网较好）。
- 职责：章节生成进度控制台——步骤管道（`selectStep`/`stepTooltipText`）、流式输出展示、失败重试（`handleFailedGenerateAction`）、转入后台/取消/完成通知（`moveToBackground`/`cancelGeneration`/`toggleNotify`）。

## Requirements

- 主组件降至 <500 行，抽出内聚子组件 / composable。
- 行为等价：步骤管道交互、流式输出、失败/后台/取消/通知均不变。
- Vue scoped style 随 template 迁移。
- 三件套绿：`vue-tsc --noEmit` exit 0 / `vitest run` 全绿（含 `chapterGeneratingTiming` 不回归）/ `eslint` 0 新增 error。

## Acceptance Criteria

- [ ] `ChapterGenerating.vue` < 500 行。
- [ ] 三件套全绿（`chapterGeneratingTiming` 测试不回归）。
- [ ] 行为等价（流式/管道/失败重试/通知手测或测试覆盖）。
- [ ] 抽出的子组件补 AIMETA 首行。

## Notes

- 复杂任务：`task.py start` 前补 `design.md` + `implement.md`。
- parent：`07-12-engineering-baseline`（acceptance 第 4 项）。
- 已有测试是优势，可优先从测试覆盖的时序/交互块切入。
