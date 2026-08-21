# 收敛遗留编辑器组件契约

## Goal

把遗留编辑器组件的 runtime props、字符串 emits 与相邻契约类型化，使父子组件事件和 payload 可由 TypeScript 校验。

## Background

- 多个遗留编辑器仍使用 runtime `defineProps({...})` 和字符串数组 `defineEmits([...])`。
- 迁移只针对组件契约，不应借机重做编辑器 UI 或状态管理。

## Requirements

- R1. 启动前列出目标编辑器及其父组件调用点，确认每个 prop、event 与 payload 的现有行为。
- R2. 使用 Vue 类型化 `defineProps`/`defineEmits` 表达现有契约，复用已有领域类型。
- R3. 收敛仅因 props/emits 契约不明确产生的相邻 `any`。
- R4. 保持事件名称、触发时机、双向绑定与编辑行为兼容。
- R5. 本任务只拥有组件 props/emits 及其必要 payload 类型；API、utils、composable 与 novel-detail 数据流边界归前一子任务。

## Acceptance Criteria

- [ ] 目标编辑器不再使用字符串 emits 或无类型的 runtime props 契约。
- [ ] 所有父组件监听器与 payload 通过 TypeScript 检查。
- [ ] 目标编辑器组件测试通过，用户可见交互无变化。
- [ ] 未新增无约束断言或与当前行为无关的组件重构。

## Out of Scope

- 编辑器视觉重设计、状态管理迁移或统一全站表单框架。
- 不属于目标编辑器调用链的组件类型清理。
- 与 props/emits 契约无关的 API、工具函数、composable 或详情数据流 `any`。

## Notes

- 本任务按父任务顺序在前端边界类型任务完成后启动；启动前补精确组件清单和复杂任务规划材料。
