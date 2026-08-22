# 收敛遗留编辑器组件契约

## Goal

把蓝图编辑链和蓝图确认组件中遗留的 runtime props、字符串 emits 与 3 处相邻显式 `any` 改为可由 Vue/TypeScript 校验的现有契约，同时保持编辑、双向绑定、保存和蓝图生成行为不变。

## Background

- 蓝图编辑链为 `NovelDetailShell → BlueprintEditModal → 5 个数组编辑器`；前一子任务已把 section edit 事件收敛为 `unknown`，但本弹窗及子编辑器仍绕过组件契约检查。
- `BlueprintConfirmation` 已使用泛型 props/emits，但生成成功 payload 仍是 `any`；`useGenerateBlueprintMutation` 已返回生成别名 `BlueprintGenerationResponse`。
- 规划基线：`npm run type-check` 通过；`uiAuditRegression.spec.ts` 35 项通过。现有测试只钉住可访问性和动效源码，不验证 v-model 或保存 payload。
- 实施期聚焦测试确认五个数组编辑器会把 Vue reactive Proxy 直接交给 `structuredClone`，触发 `DataCloneError` 并阻断 emit；用户已批准在同一任务修复。

## In Scope

1. `BlueprintEditModal.vue`
   - `show/title/content/field` 改为泛型 props，保留现有默认值与 String/Object/Array 输入范围；唯一调用链始终传入且保存必需的 `field` 收紧为编译期必填。
   - `close/save` 改为类型化 emits；移除 `editableContent: any`。
2. 五个数组编辑器
   - `CharactersEditorEnhanced.vue`
   - `FactionsEditor.vue`
   - `RelationshipsEditor.vue`
   - `KeyLocationsEditor.vue`
   - `ChapterOutlineEditor.vue`
   - `modelValue` 与 `update:modelValue` 改为泛型契约，保留空数组默认、克隆、同步抑制、添加/删除和重排行为。
3. `BlueprintConfirmation.vue`
   - `blueprintGenerated` payload 复用 `BlueprintGenerationResponse`。
4. 只在编译器证明必要时调整两个直接父调用点 `NovelDetailShell.vue`、`InspirationMode.vue`；不得用 `any`、双重断言或忽略指令绕过不匹配。
5. 增加一个聚焦运行时测试，覆盖代表性的数组 v-model 克隆/emit 与弹窗保存 payload；保留现有 UI 静态回归。
6. 五个数组编辑器的 clone helper 在 `structuredClone` 拒绝 reactive Proxy 时回退到既有 JSON 克隆路径。

## Requirements

- R1. 七个目标组件不再包含 runtime-options `defineProps({...})`、字符串数组 `defineEmits([...])` 或清单内 3 处显式 `any`。
- R2. 复用 `ChapterOutline`、`Blueprint`/`BlueprintPatch` 与 `BlueprintGenerationResponse`；world-setting 内未生成字段继续使用组件本地最小接口，不新建公共类型目录。
- R3. props 的运行时默认值、事件名称、payload 字段名、触发时机与 v-model 名称保持不变；`field` 仅收紧编译期必填约束，不增加运行时默认值。
- R4. 深度 watch、同步抑制、角色 DNA、章节重排、弹窗关闭/保存和蓝图生成流程不得改写；clone helper 只增加 `structuredClone` 失败后的既有 JSON fallback。
- R5. 若完整类型化迫使修改前一任务拥有的 section/composable 数据边界，停止并返回规划；不得通过无约束断言伪造端到端安全。

## Acceptance Criteria

- [x] 目标 7 个组件的精确 `rg` 不再命中 runtime props、字符串 emits 或清单内显式 `any`。
- [x] `BlueprintEditModal` 的五个编辑分支与 fallback 输入在 `vue-tsc` 下通过，`save` 仍发出 `{ field, content }`。
- [x] `BlueprintEditModal` 不因字段专用 typed model 过滤或改写原数组元素，未编辑直接保存仍保留完整 payload。
- [x] 五个数组编辑器仍克隆输入、发出 `update:modelValue`，且至少一个代表性运行时测试证明不会直接修改原 prop。
- [x] 在环境提供 `structuredClone` 时，reactive Proxy 更新不再抛 `DataCloneError`，仍发出克隆后的数组。
- [x] `BlueprintConfirmation` 成功事件 payload 与 mutation 的 `BlueprintGenerationResponse` 一致，`InspirationMode` 监听器通过类型检查。
- [x] Scoped ESLint、聚焦 Vitest、`npm run type-check` 和 `npm run test:unit` 通过；独立复核无阻塞发现。

## Out of Scope

- 写作台中其他字符串 emits、`AppShell.vue` 组件 ref、`WDEvaluationDetailModal.vue` 与 `ChapterContent.vue` 的相邻债务。
- 编辑器视觉、文案、状态架构、交互流程或表单框架重构。
- API schema、生成 artifact、query/composable 架构或 novel-detail section 数据解码。
- 抽取通用 clone helper、通用编辑器基类或公共 types 目录。
