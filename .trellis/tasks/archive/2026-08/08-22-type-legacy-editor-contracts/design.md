# 技术设计

## 变更边界

只迁移 7 个目标组件的现有 props/emits 契约，并在编译器要求时点改两个直接父调用点。重复的 clone/watch 逻辑保持各组件原状，不为一次迁移制造共享抽象。

## 契约矩阵

| 组件 | Props | Emits | 类型来源 |
| --- | --- | --- | --- |
| `BlueprintEditModal` | `show`、`title`、`content`、`field` | `close`、`save({ field, content })` | `BlueprintPatch` 字段值 + 本地编辑内容联合 |
| `ChapterOutlineEditor` | `modelValue` 默认 `[]` | `update:modelValue` | `ChapterOutline[]` |
| `RelationshipsEditor` | `modelValue` 默认 `[]` | `update:modelValue` | `Blueprint['relationships']` |
| `CharactersEditorEnhanced` | `modelValue` 默认 `[]` | `update:modelValue` | 本地 UI Character；`extra` 动态项为 `unknown` |
| `KeyLocationsEditor` | `modelValue` 默认 `[]` | `update:modelValue` | 本地 `KeyLocation[]` |
| `FactionsEditor` | `modelValue` 默认 `[]` | `update:modelValue` | 本地 `Faction[]` |
| `BlueprintConfirmation` | 现有 `aiMessage/projectId` | `blueprintGenerated`、`back` | `BlueprintGenerationResponse` |

## 兼容策略

- 数组编辑器使用 `withDefaults(defineProps<...>(), { modelValue: () => [] })` 和元组/调用签名 emits；现有本地数组及 watcher 不改。
- clone helper 先尝试 `structuredClone`，若 reactive Proxy 不可克隆则进入原有 JSON clone；不抽共享 helper，避免扩大迁移范围。
- `BlueprintEditModal` 保留当前 String/Object/Array 内容范围和打开时深拷贝。唯一调用链始终传入且保存必需的 `field` 标为编译期必填，不新增空串默认。Vue 模板不能按 `field` 收窄五个 v-model，因此使用局部、字段专用的 typed model；getter 只建立类型边界，不过滤数组，保存仍发送完整 `editableContent`。
- 蓝图生成成功事件直接引用 query 已返回的 `BlueprintGenerationResponse`，不复制 response shape。
- 不把 `BlueprintConfirmation` 的计时器、progress 或 mutation 流程纳入重构。

## 风险与回滚

- 最大风险是弹窗的宽内容联合与五个窄数组 v-model 之间缺少判别关联。局部 typed model 只服务模板类型且不得执行运行时过滤，以 `vue-tsc` 和未编辑数组原样保存测试为门禁；若必须修改 section/composable，返回 Phase 1。
- JSON fallback 延续原有兼容路径，只在 `structuredClone` 抛错时生效；合法普通对象输出不变。
- 所有改动不涉及数据和 API，可按单提交回滚。
