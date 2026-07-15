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

---

# Slice 6 实施清单：抽子组件 `ChapterFailedVersions.vue`

## 步骤

1. 新建 `ChapterFailedVersions.vue`：template 逐字搬失败区 DOM（`v-if` 条件留父标签）；script 收 status/failedVersionCards/generatingChapter/chapterNumber props + 逐字迁 `retryGenerateLabel` + emits(showVersionDetail/evaluateChapter/failedGenerateAction)；scoped style 含 failed-* 全部独占规则逐字（无共享选择器，整段搬迁）。
2. `useGenerationFailure.ts` 新增导出 `FailedVersionCard` interface + `GenerationStatus` type（producer 持有类型，避免子组件直引 @/api/novel）。纯增量。
3. 改 ChapterGenerating.vue：
   - template 失败区 → `<ChapterFailedVersions v-if="..." :status :failed-version-cards :generating-chapter :chapter-number @show-version-detail @evaluate-chapter @failed-generate-action />`（v-if 条件同原；v-else-if 链保持）
   - 新增 `import ChapterFailedVersions from './ChapterFailedVersions.vue'`
   - 删 `retryGenerateLabel` computed（orphan）
   - style：删失败区样式整段（L1019-1135，全部 failed-* 独占）
4. 复核：diff 只含子组件新建 + composable 2 类型导出 + 父 template/import/删 computed/删 style；失败区 template/script/style 与子组件逐字等价；handler handleFailedGenerateAction 留父（读 props，emit generateChapter），子组件 emit failedGenerateAction 意图。

## 验证（全绿）

- vue-tsc --noEmit → exit 0
- vitest run chapterGeneratingTiming.spec.ts → 7 绿
- vitest run（全量）→ 139 绿 0 失败（reader prefetch 用例本次亦通过）
- eslint 改动三文件 → 0 新增（仅父 1 预存 @/api/novel 警告；子组件用 GenerationStatus 类型规避了 @/api 直引）

## 结果

主组件 1330 → **1167**（−163）；子组件 200 行新增。diff（父+composable）28 insertions / 175 deletions，纯 template/script/style 迁移 + 类型导出 + orphan 清理。

## 非纯展示点处理（emit 拆分）

失败区含 `handleFailedGenerateAction`（showConfirm 副作用），非纯展示。决策：handler 留父（它本就读 props.status/props.chapterNumber、emit generateChapter，属父职责），子组件仅 emit `failedGenerateAction` 意图；showVersionDetail/evaluateChapter 由父转发。子组件维持"展示 + emit 意图"，confirm 业务逻辑不外泄至展示组件。

## 回滚点

`git checkout -- ChapterGenerating.vue frontend/src/composables/useGenerationFailure.ts && rm frontend/src/components/writing-desk/workspace/ChapterFailedVersions.vue`，无副作用。

## 提交边界

单 commit：`refactor(frontend): 抽 ChapterFailedVersions 子组件（#22 ChapterGenerating Slice 6）`。仅含 ChapterGenerating.vue + ChapterFailedVersions.vue + useGenerationFailure.ts + design.md + implement.md；不含 backend/app/services/tts_service.py（reader/TTS 会话残留）。

---

# Slice 7 实施清单：抽子组件 `ChapterStepInspector.vue`

## 步骤

1. 新建 `ChapterStepInspector.vue`：template 逐字搬节点详情面板 DOM（去 `v-if`，条件留父标签）；script 仅 `import type { ActiveStepDetails }` + 单 prop `activeStepDetails: ActiveStepDetails`（无 computed/emit/ref）；scoped style 含 inspector-card/-header/-title-group/-badge/-title/-subtitle/-meta + call-type/llm-usage/trace-status（共享三选择器）+ trace-status.is-failed + inspector-grids(+@media) + inspector-panel/panel-title/panel-code-wrapper/panel-code + `@keyframes fadeInInspector` 全部逐字搬迁。
2. 改 ChapterGenerating.vue：
   - template 节点详情面板 `<article v-if=...>` → `<ChapterStepInspector v-if="activeStepDetails && (!props.readOnly || activeStepKey)" :active-step-details="activeStepDetails" />`（v-if 条件同原；条件链 v-if→v-else-if→v-if 保持）
   - 新增 `import ChapterStepInspector from './ChapterStepInspector.vue'`
   - style：删 inspector/panel 整段（is-selected.is-done 之后到 panel-code）；删 `@keyframes fadeInInspector`（orphan）
   - **保留** `.chapter-console--read-only .chapter-console__inspector-card` 只读覆写（与 pipeline-card 共享选择器组，inspector-card 作子组件根继承父 data-v，仍命中）
3. 测试指针跟随：`uiAuditRegression.spec.ts` 的 `labels chapter trace details...` 用例，面板标签断言改读 `ChapterStepInspector.vue` 源码，逻辑引用断言仍指父。
4. 复核：diff 只含子组件新建 + 父 template/import/删 style + 测试指针；节点详情面板 template/style 与子组件逐字等价；activeStepDetails computed 留父（读 currentStepKey/activeTrace/STEP_DETAILS/失败分析）。

## 验证（全绿）

- vue-tsc --noEmit → exit 0
- vitest run chapterGeneratingTiming.spec.ts → 7 绿
- vitest run（全量）→ 139 绿 0 失败
- eslint 改动两文件 → 0 新增（仅父 1 预存 @/api/novel 警告；子组件 import `@/utils/generationTrace` 的 ActiveStepDetails 类型，非受限路径）

## 结果

主组件 1167 → **977**（−190）；子组件 206 行新增。diff（父）16 insertions / 202 deletions，纯 template/style 迁移 + import + orphan 清理；测试指针跟随 +4/-4 行。

## scoped 关键点

`.chapter-console__inspector-card` 是子组件根 → Vue「子组件根同时承载父级 data-v」→ 父级 `.chapter-console--read-only .chapter-console__inspector-card` 只读覆写不迁移仍命中（特异性 (0,4,0) > 子基样式 (0,2,0)）。本 slice 因此无需拆共享选择器组，比 Slice 5/6 更省事。

## 回滚点

`git checkout -- ChapterGenerating.vue frontend/src/components/__tests__/uiAuditRegression.spec.ts && rm frontend/src/components/writing-desk/workspace/ChapterStepInspector.vue`，无副作用。

## 提交边界

单 commit：`refactor(frontend): 抽 ChapterStepInspector 子组件（#22 ChapterGenerating Slice 7）`。仅含 ChapterGenerating.vue + ChapterStepInspector.vue + uiAuditRegression.spec.ts + design.md + implement.md；不含 backend/app/services/tts_service.py（reader/TTS 会话残留）。

---

# Slice 8 实施清单：抽 `composables/useChapterGenerationTrace.ts`

## 步骤

1. 新建 `useChapterGenerationTrace.ts`：逐字迁入 activeStepTraces/activeTrace/activeStepDetails 三 computed。签名收 props 子集 `{ generationTraces }` + TraceDeps（activeStepKey/currentStepKey/isFailureStatus/terminalFailedTrace/failureReason/failureScenario 透传引用）。返回 `{ activeStepDetails }`，activeStepTraces/activeTrace 内部中间量。import @/utils/generationTrace 的 13 符号 + ActiveStepDetails type（同原组件 activeStepDetails 用法）。
2. 改 ChapterGenerating.vue：
   - 删 activeStepTraces/activeTrace/activeStepDetails 三 computed 定义
   - `@/utils/generationTrace` 整段 import 删除（13 符号 + type 全随迁，组件无其他消费点）
   - 新增 `import { useChapterGenerationTrace } from '@/composables/useChapterGenerationTrace'`
   - 在 useGenerationPipeline 解构后插 `const { activeStepDetails } = useChapterGenerationTrace(props, { activeStepKey, currentStepKey, isFailureStatus, terminalFailedTrace, failureReason, failureScenario })`
3. 测试指针跟随：uiAuditRegression.spec.ts 3 用例（`uses real chapter generation traces...` / `does not show fabricated prompt...` / `labels chapter trace details...`）原 `source` 断言改读 `traceSource`（composable 源码）；`generationTraces?: ChapterGenerationTrace[]`（Props 仍在组件）保持 generatingSource。
4. 复核：三 computed 与原组件逐字等价；消费点（template activeStepDetails / ChapterStepInspector prop）零逻辑改动，解构同名。

## 验证（全绿）

- vue-tsc --noEmit → exit 0（TraceDeps 契约匹配：currentStepKey ComputedRef<string>，failureScenario {title,description}）
- vitest run chapterGeneratingTiming.spec.ts → 7 绿
- vitest run（全量）→ 141 绿 0 失败
- eslint 改动三文件 → 0 新增（仅父 1 预存 @/api/novel 警告；composable 不受限，同 useGenerationFailure）

## 实施偏差（已修正）

首次全量 vitest 1 失败：`uiAuditRegression.spec.ts:252 expect(generatingSource).toContain('const activeTrace = computed')`——rg 预扫描只搜了 traceUsesLlm/formatTraceActions，漏了第 3 个用例的 `const activeTrace`/`traceMetadata` 断言。补该用例指针跟随（→ traceSource）后全绿。教训：迁移 computed/符号前，rg 应覆盖**所有**指向被迁符号源码的测试断言（activeTrace/traceMetadata/兜底文案），不止主调用名。

## 结果

主组件 977 → **900**（−77）；composable 119 行新增。diff（父）8 insertions / 84 deletions，纯 computed 迁移 + import 整段迁走 + composable 调用；测试指针跟随 3 用例（+3 traceSource 声明 / 6 断言换源）。

## 回滚点

`git checkout -- ChapterGenerating.vue frontend/src/components/__tests__/uiAuditRegression.spec.ts && rm frontend/src/composables/useChapterGenerationTrace.ts`，无副作用。

## 提交边界

单 commit：`refactor(frontend): 抽 useChapterGenerationTrace composable（#22 ChapterGenerating Slice 8）`。仅含 ChapterGenerating.vue + useChapterGenerationTrace.ts + uiAuditRegression.spec.ts + design.md + implement.md；不含 backend/app/services/tts_service.py（reader/TTS 会话残留）。
