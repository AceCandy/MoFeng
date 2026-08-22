# 前端边界 `any` 清单

## 基线

- TypeScript：`cd frontend && npm run type-check` 通过。
- 聚焦测试：chapter、generationTrace、uiAuditRegression 共 `58 passed`。
- `useWritingDeskOptimize` 当前没有直接测试；现有 `useWritingDeskChapterOps.spec.ts` 提供可复用的 mutation mock 模式。
- 完整 `frontend/src` 文字扫描用于划定边界；测试中的 `expect.any(...)`、CSS `anywhere` 和注释不计入类型命中。

## 本任务目标：13 个文件，24 个命中

| 文件与位置 | 数量 | 边界 | 最小收窄 |
| --- | ---: | --- | --- |
| `src/main.ts:68` | 1 | DOM `EventTarget` | `HTMLElement` 运行时判断 |
| `src/api/novel.ts:254` | 1 | 后端 version metadata | `Record<string, unknown>` |
| `src/utils/chapter.ts:252,260` | 2 | `JSON.parse` 评审载荷 | unknown 字典 + 调用方字段守卫 |
| `src/utils/generationTrace.ts:25` | 1 | 生成 trace metadata | `Record<string, unknown>`；复用现有对象守卫 |
| `src/composables/useWritingDeskOptimize.ts:100,125` | 2 | mutation 异常 | unknown + `instanceof Error` |
| `src/composables/useShellBlueprintEdit.ts:40,43` | 2 | 内部编辑事件/缓存 | unknown，止于下一任务的遗留 modal 边界 |
| `src/components/novel-detail/CharactersSection.vue:85,98` | 2 | edit emit | unknown |
| `src/components/novel-detail/OverviewSection.vue:183,254` | 2 | edit emit | unknown |
| `src/components/novel-detail/ChaptersSection.vue:707` | 1 | 评审 JSON 条目 | unknown 字典 + 展示字段收窄 |
| `src/components/novel-detail/ChapterOutlineSection.vue:86,90` | 2 | edit emit | unknown |
| `src/components/novel-detail/sectionIcons.ts:16` | 1 | Vue 动态组件 | `Component` |
| `src/components/novel-detail/RelationshipsSection.vue:92,97` | 2 | edit emit | unknown |
| `src/components/novel-detail/WorldSettingSection.vue:132,137,142,145,165` | 5 | 后端动态字典、列表、edit emit | unknown 字典 + 本地对象/字符串守卫 |

## 可复用证据

- `api/novel.ts` 已将 `BlueprintPatch`、`ChapterGenerationTrace` 暴露为生成 schema 索引别名；生成的 trace metadata 本身就是 unknown 字典。
- `generationTrace.ts:isPlainTraceObject` 已集中收窄 trace metadata，后续字段读取已有 `typeof`/数组检查。
- `ShellContent.vue` 的 edit payload 已是 `unknown`；各 section 与 `useShellBlueprintEdit` 应与其对齐。
- `BlueprintPatch[keyof BlueprintPatch]` 已定义最终保存内容类型，无需复制蓝图字段。
- Vue 提供 `Component` 类型，可直接替代图标表的 `any`。

## 实施期补充影响面

- `useVersionResolver.ts`：`ChapterVersion.metadata` 与 trace metadata 改为 unknown 字典后，原有嵌套字段读取需局部对象守卫。
- `useChapterGenerationTrace.ts`：trace metadata 的 `summary` 在展示前需字符串守卫。
- 两处由 `vue-tsc` 暴露，未新增显式 `any`，但属于原始类型定义变化的直接消费者。

## 明确排除并记录的相邻命中

- 下一子任务遗留编辑器契约：`BlueprintEditModal.vue`、`CharactersEditorEnhanced.vue`、`BlueprintConfirmation.vue` 等 runtime props/emits 或编辑值。
- 其他不在本子任务描述内的组件：`AppShell.vue` 的组件 ref、`WDEvaluationDetailModal.vue` 的评审条目断言、`ChapterContent.vue` 的 catch 变量。
- 这些位置不在本任务中顺带修改；父任务最终复核或其所属子任务必须继续追踪。
