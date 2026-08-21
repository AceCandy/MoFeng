# 收敛前端边界类型逃逸

## Goal

用可验证的领域类型收敛前端 API、工具函数、composable 与详情编辑链中已确认的 `any`，不改变运行时行为。

## Background

- 已确认的命中点分布在 `main.ts`、`utils/chapter.ts`、`generationTrace.ts`、`useWritingDeskOptimize.ts` 与 novel-detail 编辑链。
- 这些位置跨越外部输入与组件边界，不能用简单批量替换或更宽的断言掩盖。

## Requirements

- R1. 启动前建立本任务的精确 `any` 清单，区分可信内部类型与需要运行时收窄的外部输入。
- R2. 优先复用现有 DTO、组件契约和工具类型；只在没有可复用类型时新增最小本地类型。
- R3. 删除目标边界的显式/隐式 `any`，不得改成等价的无约束类型断言。
- R4. 保持 API 数据流、编辑交互、错误处理与渲染行为不变。
- R5. 本任务只拥有 API、utils、composable 与 novel-detail 数据流边界；遗留编辑器的 props/emits 迁移归下一子任务。

## Acceptance Criteria

- [ ] 规划清单内的 `any` 均被删除、收窄或以有证据的第三方边界隔离，并记录无法消除的例外。
- [ ] TypeScript 检查与目标 API/composable/detail 编辑测试通过。
- [ ] 不新增 `@ts-ignore`、`@ts-expect-error` 或无解释的双重断言来绕过类型系统。
- [ ] 用户可见编辑与生成行为无变化。

## Out of Scope

- 一次性清零全仓所有 `any`。
- 重写页面状态架构、生成流程或 API schema。
- 遗留编辑器 runtime `defineProps`/`defineEmits` 契约迁移。

## Notes

- 本任务按父任务顺序在 Pydantic v2 迁移完成后启动；若清单过大，应在启动前拆分而不是扩大单次 diff。
