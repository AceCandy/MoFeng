# 遗留编辑器契约清单

## 目标命中

- `BlueprintEditModal.vue:90-102`：runtime props、字符串 emits、`ref<any>`；父调用为 `NovelDetailShell.vue:61-68`。
- `CharactersEditorEnhanced.vue:365,369-376`：动态 extra `any`、runtime props、字符串 emits。
- `FactionsEditor.vue:55-62`、`RelationshipsEditor.vue:57-64`、`KeyLocationsEditor.vue:55-62`、`ChapterOutlineEditor.vue:47-54`：runtime props + 字符串 emits。
- `BlueprintConfirmation.vue:155-158`：`blueprintGenerated` payload 为 `any`；父调用为 `InspirationMode.vue:161-168`，mutation 已返回 `BlueprintGenerationResponse`。

## 行为钉点

- 五个数组编辑器均在 prop → local 时深拷贝，并在 local 深度变化时发出 `update:modelValue`；同步窗口由 `syncing + nextTick` 抑制回环。
- 五个 clone helper 对 reactive Proxy 直接调用 `structuredClone` 会抛 `DataCloneError`；应捕获后进入现有 JSON fallback。
- `ChapterOutlineEditor` 删除后从 1 开始重排 `chapter_number`。
- `CharactersEditorEnhanced` 的 DNA 字段更新会立即 emit，新增角色初始化完整 DNA。
- `BlueprintEditModal` 打开时克隆 `content`，关闭发 `close`，保存发 `{ field, content }`。
- `BlueprintConfirmation` mutation 成功后等待完成动画再发 `blueprintGenerated(response)`。

## 类型来源

- `api/novel.ts` 已导出 `Blueprint`、`BlueprintPatch`、`ChapterOutline`、`BlueprintGenerationResponse`。
- 生成 `Blueprint.characters` 为 unknown 字典数组，`relationships` 为 `Relationship[]`，`chapter_outline` 为 `ChapterOutline[]`；world-setting 为 unknown 字典。

## 排除项

- 写作台其他字符串 emits，以及 `AppShell`、评审弹窗和章节内容 catch 命中。
- 现有 `uiAuditRegression.spec.ts` 只覆盖目标组件的可访问性/动效源码，不证明 runtime payload。
