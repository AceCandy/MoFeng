# 收敛前端边界类型逃逸

## Goal

收敛前端 API、工具函数、composable 与 novel-detail 数据流中已确认的 24 个显式 `any`，让外部数据在使用前经过运行时收窄，让内部组件事件保留未知性而不绕过类型系统，同时保持正常数据下的编辑、优化、滚动和渲染行为不变。

## Background

- 父任务前三项已完成；本任务是第 4 项，后续第 5 项单独负责遗留编辑器的 runtime props/emits 契约。
- 精确清单覆盖 13 个原始 `any` 文件；实施时类型检查确认 `useVersionResolver.ts` 与 `useChapterGenerationTrace.ts` 是 metadata 的直接消费者，需同步增加读取守卫，详见 `research/frontend-any-inventory.md`。
- `frontend/src` 的完整文字扫描还发现遗留编辑器、AppShell ref、写作台错误处理等相邻命中；它们不属于本任务，已记录而不顺带修改。
- 规划基线：`npm run type-check` 通过；chapter、generationTrace、uiAuditRegression 共 58 个测试通过。

## Requirements

- R1. 删除清单内 24 个显式 `any`；不得改成 `as any`、双重断言、`@ts-ignore` 或 `@ts-expect-error`。
- R2. DOM 事件、JSON 评审载荷、trace/version metadata 与 world-setting 动态数据使用 `unknown`、`Record<string, unknown>` 及最小运行时守卫；无效形状不得触发属性访问异常。
- R3. 复用生成的 `BlueprintPatch`、`ChapterGenerationTrace` 和现有领域接口；Vue 图标表使用 `Component`，不新增公共类型目录、通用解码框架或依赖。
- R4. novel-detail 展示组件的 `edit` 事件与 `useShellBlueprintEdit` 内部缓存使用 `unknown` 传递，不替遗留 `BlueprintEditModal`/编辑器伪造已验证类型；该终端契约留给下一子任务。
- R5. `parseEvaluationPayload` 与优化 composable 只接受对象形状，使用前收窄推荐版本、评审摘要和版本评审字典；合法载荷的版本选择、请求字段和用户提示保持不变。
- R6. 保持滚动条状态、trace 展示、章节评审、蓝图编辑和错误回退的用户可见行为不变；不修改 API schema、生成 artifact、查询架构或页面布局。
- R7. `ChapterVersion.metadata` 与 trace metadata 改为 unknown 字典后，其两个直接消费者必须在读取嵌套字段或摘要前完成收窄。

## Acceptance Criteria

- [ ] `research/frontend-any-inventory.md` 中 13 个目标文件的 `rg` 门禁不再命中类型位置的 `any`，且相邻排除项仍未被顺带修改。
- [ ] 评审 JSON 的对象、二次编码对象、数组、空值和非法 JSON 有聚焦测试；合法推荐版本仍生成相同优化请求。
- [ ] trace/version metadata、world-setting 列表和 novel-detail 评审结果在 TypeScript 下以 `unknown` 开始，并在读取字段前完成收窄。
- [ ] `npm run type-check`、目标 Vitest、Scoped ESLint 与前端完整单元测试通过。
- [ ] diff 不包含生成 artifact、依赖、遗留编辑器契约或用户可见交互变更，且独立复核无阻塞发现。

## Out of Scope

- 一次性清零全仓所有 `any`，或处理本任务研究材料列出的相邻命中。
- `BlueprintEditModal.vue`、`CharactersEditorEnhanced.vue` 等遗留编辑器 runtime props/emits；由下一子任务负责。
- 重写评审解析体系、页面状态架构、生成流程、API schema 或 OpenAPI/TypeScript artifact。
- 修复与类型收窄无关的 UI、错误文案、日志或格式问题。
