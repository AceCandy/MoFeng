# Slice 1 实施清单：抽 `utils/generationTrace.ts`

> 首 slice。后续 slice（2 时序 / 3 失败分析 / 4-6 子组件 / 7 收尾）推进到对应会话时在本文件追加。

## 步骤

1. **新建** `frontend/src/utils/generationTrace.ts`：按 `design.md` 行号迁入常量（4 个）+ 类型（4 个）+ parse 工具（3）+ trace 工具（11）+ 格式化（9）。顶部加文件注释（来源、用途，非业务注释）。`import type { ChapterGenerationTrace } from '@/api/novel'`（trace 函数入参）+ `import { cleanVersionContent } from '@/utils/chapter'`（getTraceOutputText 用）。
2. **改 `ChapterGenerating.vue`**：
   - 删迁出符号（design.md 清单）
   - 顶部 `import { /* 迁出符号 */ } from '@/utils/generationTrace'`
   - 删 `import { cleanVersionContent ... }`（若组件内仅 getTraceOutputText 用，随迁 utils；确认组件无其他 cleanVersionContent 调用点再删）
   - 调用点（activeStepTraces/activeTrace/activeStepDetails/parsedStepPayload 等）零改动
3. **复核**：import 无遗漏、无重声明、无 orphan import。

## 验证（按序，任一红即停）

```bash
cd frontend && npx vue-tsc --noEmit                                              # exit 0
cd frontend && npx vitest run src/components/__tests__/chapterGeneratingTiming.spec.ts   # 7 绿
cd frontend && npx vitest run                                                   # 全绿
cd frontend && npx eslint src/components/writing-desk/workspace/ChapterGenerating.vue src/utils/generationTrace.ts  # 0 新增
```

## 独立复核（实施后）

- diff 只含：新建 utils + 组件「删符号 + 加 import + 可能删 cleanVersionContent import」，**无逻辑改动**
- `wc -l ChapterGenerating.vue` 下降 ~530（2261 → ~1730）
- 确认 utils 内函数逐字等价（无抄写偏差）

## 回滚点

任一验证红 → `git checkout -- ChapterGenerating.vue && rm frontend/src/utils/generationTrace.ts`，无副作用。

## 提交边界

单 commit：`refactor(frontend): 抽 generationTrace utils（#22 ChapterGenerating Slice 1）`。body 说明迁出符号 + 行数变化 + 三件套结果。三件套绿 + 复核通过后提交。

---

# Slice 2 实施清单：抽 `composables/useGenerationTiming.ts`

## 步骤

1. **新建** `frontend/src/composables/useGenerationTiming.ts`：按 `design.md` Slice 2 迁入状态（clockNow/localStartAt/timer）+ STAGE_CONFIG + 8 个时序 computed + 定时器 onMounted/onUnmounted + localStartAt 重置 watch。沿用 useChapterStatus 约定（props 子集 interface，不用 MaybeRefOrGetter）。返回 `{ elapsedText, etaText }`。
2. **删 2 死 computed**：`progressPercent`/`activeStageLabel`（全项目零引用，落在时序区内，零行为变化）。
3. **改 `ChapterGenerating.vue`**：删迁出符号 + 2 死 computed；`vue` import 去 `onUnmounted`；generationTrace import 去 `parseBackendTimestampToMs`；新增 composable import；onMounted 仅留 notifyWhenDone 读取；删 onUnmounted；插 `const { elapsedText, etaText } = useGenerationTiming(props)`。
4. **复核**：diff 只含删除 + composable 调用，无逻辑改动；composable 逐函数与原组件逐字等价。

## 验证（全绿）

- `vue-tsc --noEmit` → exit 0
- `vitest run chapterGeneratingTiming.spec.ts` → 7 绿
- `vitest run`（全量）→ 137 绿
- `eslint` 改动两文件 → 0 新增（1 预存 `@/api/novel` 警告，composable 不受限）

## 结果

主组件 1762 → **1664**（−98）；composable 110 行新增。集成测试 mount 主组件断言 DOM 全绿，运行时行为等价。

## 回滚点

`git checkout -- ChapterGenerating.vue && rm frontend/src/composables/useGenerationTiming.ts`，无副作用。

## 提交边界

单 commit：`refactor(frontend): 抽 useGenerationTiming composable（#22 ChapterGenerating Slice 2）`。body 说明迁出符号 + 删 2 死 computed + 行数变化 + 三件套结果。

---

# Slice 3 实施清单：抽 `composables/useGenerationFailure.ts`

## 边界调整

原计划含 currentStepKey，实施时发现它是横跨正常/失败的步骤状态机枢纽（被 activeStepTraces/activeTrace/activeStepDetails/currentStepIndex/stepState/canRetryFromNode/selectStep/stepTooltipText/watch 大量消费）。本 slice 缩边界为纯失败展示 5 符号，currentStepKey 系列留后续 useGenerationPipeline slice。理由：风险更低、命名准确、验证可靠。

## 步骤

1. 新建 `useGenerationFailure.ts`：迁入 isFailureStatus/terminalFailedTrace/failureReason/failureScenario/failedVersionCards + 内部 stepExists。签名收 props 子集 + pipelineSteps(ComputedRef) 入参。返回 6 符号（含 stepExists 供组件复用）。
2. 改 ChapterGenerating.vue：删 5 符号定义 + 组件内 stepExists + failedVersionCards；import 去 @/utils/chapter、@/utils/text，加 useGenerationFailure；插 composable 解构调用。
3. 复核：消费点（currentStepKey/activeTrace/activeStepDetails/stepTooltipText/canRetryFromNode）零逻辑改动，解构同名 .value 不变。

## 验证（全绿）

- vue-tsc --noEmit → exit 0
- vitest run chapterGeneratingTiming.spec.ts → 7 绿
- vitest run（全量）→ 137 绿
- eslint 改动两文件 → 0 新增（1 预存 @/api/novel 警告）

## 结果

主组件 1664 → **1559**（−105）；composable 151 行新增。diff 9 insertions / 114 deletions，纯符号迁移 + import 调整。

## 回滚点

`git checkout -- ChapterGenerating.vue && rm frontend/src/composables/useGenerationFailure.ts`，无副作用。

## 提交边界

单 commit：`refactor(frontend): 抽 useGenerationFailure composable（#22 ChapterGenerating Slice 3）`。

---

# Slice 4 实施清单：抽 `composables/useGenerationPipeline.ts`

## 步骤

1. 新建 `useGenerationPipeline.ts`：迁入 parsedStepPayload/isWaitingForManualConfirm/shouldShowManualConfirmBadge/currentStepKey/currentStepIndex/stepState/canRetryFromNode/stepTooltipText（逐字迁移）。签名收 props 子集 `{ status, generationStep, readOnly }` + `pipelineSteps: ComputedRef<PipelineStep[]>` + `failure: FailureAnalysis`（useGenerationFailure 返回子集 5 字段）。定义顺序按 design.md 依赖图。返回 5 符号（currentStepKey/stepState/canRetryFromNode/shouldShowManualConfirmBadge/stepTooltipText）。
2. 改 ChapterGenerating.vue：
   - 删 8 符号定义（currentStepKey/stepTooltipText/currentStepIndex/stepState/canRetryFromNode/isWaitingForManualConfirm/shouldShowManualConfirmBadge/parsedStepPayload）+ 死代码 completedSteps
   - import `@/utils/generationTrace` 去 `parseStepPayload`
   - 新增 `import { useGenerationPipeline } from '@/composables/useGenerationPipeline'`
   - 在 useGenerationFailure 解构之后插 `const { currentStepKey, stepState, canRetryFromNode, shouldShowManualConfirmBadge, stepTooltipText } = useGenerationPipeline(props, pipelineSteps, { isFailureStatus, terminalFailedTrace, stepExists, failureReason, failureScenario })`
3. 复核：消费点（selectStep/2 watch/activeStepTraces/activeTrace/activeStepDetails/template stepState 调用）零逻辑改动，解构同名 .value/调用不变；composable 逐函数与原组件字节等价。

## 验证（全绿）

- vue-tsc --noEmit → exit 0
- vitest run chapterGeneratingTiming.spec.ts → 7 绿
- vitest run（全量）→ 全绿
- eslint 改动两文件 → 0 新增（1 预存 @/api/novel 警告）

## 回滚点

`git checkout -- ChapterGenerating.vue && rm frontend/src/composables/useGenerationPipeline.ts`，无副作用。

## 结果

主组件 1559 → **1455**（−104）；composable 166 行新增。diff 15 insertions / 119 deletions，纯符号迁移 + import 调整 + 删 completedSteps 死代码。

## 验证（全绿）

- vue-tsc --noEmit → exit 0（FailureAnalysis 契约匹配）
- vitest run chapterGeneratingTiming.spec.ts → 7 绿
- vitest run（全量）→ 138 绿
- eslint 改动两文件 → 0 新增（1 预存 @/api/novel 警告，composable 不受限）

## 实施偏差（已修正）

首次跑 timing 7 用例全挂：`useGenerationPipeline is not defined`——Edit 时插了解构调用却漏了配套 import 行。vue-tsc 未捕获（script setup 对未声明标识符宽松），运行时集成测试立刻抓到。补 import 后全绿。教训：新增 composable 调用时，import 行与解构块须同批 Edit。

## 提交边界

单 commit：`refactor(frontend): 抽 useGenerationPipeline composable（#22 ChapterGenerating Slice 4）`。

---

# Slice 5 实施清单：抽子组件 `ChapterDraftPreview.vue`

## 步骤

1. 新建 `ChapterDraftPreview.vue`：template 逐字搬草稿预览卡 DOM（去 `v-else-if`，条件留父标签）；script 收 `chapterContentPreview` prop + 逐字迁 `previewParagraphs`/`previewModeLabel`；scoped style 含骨架（border/radius/bg/shadow/padding/h4）+ 独占规则逐字 + 自带 `@keyframes blink-cursor` + reduced-motion cursor。
2. 改 ChapterGenerating.vue：
   - template 草稿预览卡 → `<ChapterDraftPreview v-else-if="!props.readOnly" :chapter-content-preview="props.chapterContentPreview" />`
   - 新增 `import ChapterDraftPreview from './ChapterDraftPreview.vue'`
   - 删 `previewParagraphs`/`previewModeLabel` computed
   - style：border/padding/h4 三处共享选择器删 preview-card；删 preview 独占段；reduced-motion 删 cursor selector；删 `@keyframes blink-cursor`（orphan）
3. 复核：diff 只含子组件新建 + 父删 template/script/style + import + 共享选择器拆分；template/script/style 三段与子组件逐字等价；条件链 v-if→v-else-if→v-if 不变。

## 验证（全绿）

- vue-tsc --noEmit → exit 0
- vitest run chapterGeneratingTiming.spec.ts → 7 绿
- vitest run（全量）→ 除 useChapterReader 1 个 pre-existing 失败外 138 绿（reader 失败属 reader 会话残留，非本 slice 引入，不在范围）
- eslint 改动两文件 → 0 新增（1 预存 @/api/novel 警告）

## 结果

主组件 1455 → **1330**（−125）；子组件 164 行新增。diff 7 insertions / 132 deletions，纯 template/script/style 迁移 + 共享选择器拆分 + orphan 清理。

## 范式确立点（首个子组件 slice）

- scoped style 随迁：父 `<style scoped>` 选不到子组件元素 → 子组件自带 scoped style，卡片骨架重复声明（两处维护，scoped 固有代价）。
- @keyframes 自带：scoped 给 keyframes 名加 data-v hash → 子组件引用父 keyframes 失配，必须自带 `@keyframes blink-cursor`。
- 条件链保留：`v-else-if` 留在父的子组件标签上，保持「失败区 → 草稿预览 → 节点详情」三段条件。

## 提交边界

单 commit：`refactor(frontend): 抽 ChapterDraftPreview 子组件（#22 ChapterGenerating Slice 5）`。仅含 ChapterGenerating.vue + ChapterDraftPreview.vue + design.md + implement.md；不含 useChapterReader.ts/.spec.ts（reader 会话残留）。
