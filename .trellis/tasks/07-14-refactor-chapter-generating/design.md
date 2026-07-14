# 拆 ChapterGenerating.vue 设计：2261 → <500

parent `07-12-engineering-baseline` acceptance 第 4 项「5 大组件 <500 行」的 child。把 `frontend/src/components/writing-desk/workspace/ChapterGenerating.vue`（2261 行）按风险递增切多个独立可验证 slice 拆至 <500，运行时行为 100% 等价。范式沿用 parent Slice B/D（utils/composable + 子组件 + scoped style 随迁 + 测试指针跟随）。

## 组件结构（2261 行）

| 区 | 行 | 内容 |
|---|---|---|
| template | 2-259（~258） | pipeline 进度卡（步骤 ol + Tooltip + 节点重试）、失败区（候选版本网格 + 重新评审/重试）、草稿预览卡、节点详情面板（inspector：调用类型/LLM/输入/动作/产出）、footer actions（转入后台/取消/通知） |
| script | 261-1342（~1081） | Props(15)/emit(4)；时钟态（clockNow/localStartAt/timer）；step 选择（activeStepKey/selectStep）；常量（STAGE_CONFIG/PIPELINE_LABELS/STEP_DETAILS/TRACE_*_LABELS）；parse 工具；失败分析（currentStepKey ~54 行 + failureReason/failureScenario/failedVersionCards）；时序进度（elapsed/eta/progress/backendProgress/currentStageConfig）；trace 工具 + 格式化（~303 行）；activeStepDetails computed；stepState；动作（moveToBackground/handleFailedGenerateAction/cancelGeneration/toggleNotify）；watch×4 / onMounted/onUnmounted |
| style | 1344-2260（~916） | pipeline/dot/连线/badge、preview/strategy、inspector/panel-code、failed/version-card、actions、@media(max-width:833)、@keyframes（dot-ripple/blink-cursor/line-flow(-vertical)/fadeInInspector） |

## 测试网（强）

`chapterGeneratingTiming.spec.ts`（419 行，7 用例）是**集成测试**——`createApp(ChapterGenerating).mount` 后断言 DOM：

- trace `systemDuration` 展示（activeStepDetails → formatSystemDuration）
- 失败 trace 完整错误展示（failureReason/stepState aria-label）
- `evaluation_failed` 不复用旧成功 trace（currentStepKey/activeTrace）
- 失败卡片保留候选版本（failedVersionCards）
- evaluation 失败主操作 = 重新 AI 评审（retryGenerateLabel）
- 放弃草稿二次确认（handleFailedGenerateAction + globalAlert.showConfirm）
- 各阶段业务输出（formatDraft/AiReview/Refinement/ManualConfirmation）
- pipeline 标题顺序（pipelineSteps）

覆盖了 trace 格式化、失败分析、pipeline 步骤几乎全部核心逻辑。**拆分只要保持组件对外渲染行为，此测试即强回归网**（抽 utils/composable 后 mount 主组件仍验证）。

## Slice 划分（契约表）

| Slice | 形态 | 内容 | 行削减（估） | 风险 |
|---|---|---|---|---|
| **1** | utils 模块 `utils/generationTrace.ts` | trace 工具 + 格式化纯函数 + 常量 + 类型（精确清单见下） | ~530 | 极低（纯函数/常量迁移，零响应式） |
| **2** | composable `useGenerationTiming` | clockNow 定时器 + STAGE_CONFIG + elapsed/eta/progress/backendProgress/currentStageConfig/activeStageLabel | ~110 | 低 |
| **3** | composable `useGenerationFailure`（或并入 trace 模块） | failureReason/failureScenario/currentStepKey(54 行)/canRetryFromNode/failedVersionCards/terminalFailedTrace/isFailureStatus/stepState/stepExists | ~220 | 中（currentStepKey 分支多） |
| **4** | 子组件 `ChapterDraftPreview` | template 142-174 + preview/strategy style | ~80 | 低（纯展示） |
| **5** | 子组件 `ChapterFailedVersions` | template 88-140 + failed style + emit evaluateChapter/showVersionDetail | ~150 | 低（纯展示 + emit） |
| **6** | 子组件 `ChapterStepInspector` | template 176-237 + inspector style（props 收 activeStepDetails） | ~150 | 低（纯展示） |
| **7** | 余量收尾 | pipeline 步骤项 + footer actions，视余量并入主组件或再抽 | - | 中 |

预估：Slice 1-3（utils/composable）砍 ~860，主组件 ~1400；Slice 4-7（子组件）再砍 ~530+，主组件 → <500。单 slice 独立可验证，跨会话推进。

---

## Slice 1 详述：抽 `utils/generationTrace.ts`

### 边界

纯函数 + 常量 + 类型，**零响应式依赖**。从组件 script 迁出，组件 `import { ... } from '@/utils/generationTrace'` 调用。template 零改动，行为等价。与 `utils/chapter.ts`（cleanVersionContent）/`utils/text.ts` 同级。

### 迁出符号（精确行号 → utils）

**常量**：`STEP_DETAILS`(414-511)、`PIPELINE_LABELS`(324-343)、`TRACE_CALL_TYPE_LABELS`(391-407)、`TRACE_STATUS_LABELS`(409-412)

**类型**：`StepDetail`(364-369)、`ParsedStepPayload`(371-375)、`TraceMetadata`(377)、`ActiveStepDetails`(379-389)

**parse 工具**：`parseStepPayload`(513-531)、`parseBackendTimestampToMs`(533-542)、`normalizePipelineStepKey`(550-558)

**trace 工具**：`isPlainTraceObject`(883-885)、`traceMetadata`(887-889)、`resolveTraceDurationMs`(891-905)、`formatSystemDuration`(907-923)、`traceUsesLlm`(925-937)、`formatTraceValue`(939-943)、`formatTracePayload`(945-953)、`firstTextValue`(955-962)、`toDisplayVersionNumber`(964-970)、`getTraceOutputPayload`(972-975)、`getTraceOutputText`(977-982)

**格式化**：`formatDraftGenerationOutputs`(984-987)、`formatAiReviewOutputs`(989-1051)、`formatReviewRefinementOutputs`(1053-1062)、`formatManualConfirmationOutputs`(1064-1076)、`formatModelCall`(1078-1093)、`formatTraceInputs`(1095-1108)、`formatTraceActions`(1110-1145)、`formatTraceOutputs`(1147-1178)、`resolveTraceCallType`(1180-1186)

### 留组件（依赖 props / 响应式）

- computed：`activeStepTraces`(867)、`activeTrace`(872)、`activeStepDetails`(1188-1242)——用 utils 函数组装
- 失败分析：`parsedStepPayload`(544)、`isFailureStatus`(546)、`stepExists`(560)、`terminalFailedTrace`(562)、`failureReason`(566)、`failureScenario`(608)、`currentStepKey`(669-723)、`failedVersionCards`(738)
- 步骤：`pipelineSteps`(345)、`currentStepIndex`(755)、`completedSteps`(760)、`stepTooltipText`(725)、`stepState`(1244)、`selectStep`(308)、`shouldShowManualConfirmBadge`(666)
- 时序（Slice 2 再抽）、动作、watch/lifecycle

### 输入依赖（被迁出符号引用的组件符号 → 反向 import）

`activeStepDetails`/`activeTrace` 等 computed 调用迁出的 format/工具函数 → 组件 import 这些函数。`normalizePipelineStepKey`/`parseBackendTimestampToMs` 被组件多处用（activeStepTraces/currentStepKey/时序）→ import。无循环依赖（utils 不 import 组件）。

### 等价性

逐字迁移，函数签名 / 返回值 / 常量值不变。组件 import 后调用点解析到 utils，运行时等价。`chapterGeneratingTiming` 7 用例全绿验证（mount 主组件断言 DOM，行为不变）。

### 验证

- `cd frontend && npx vue-tsc --noEmit`（import 解析 + 类型）
- `cd frontend && npx vitest run src/components/__tests__/chapterGeneratingTiming.spec.ts` → 8 绿
- `cd frontend && npx vitest run` → 全绿
- `cd frontend && npx eslint src/components/writing-desk/workspace/ChapterGenerating.vue src/utils/generationTrace.ts` → 0 新增

### 回滚

`git checkout -- ChapterGenerating.vue && rm frontend/src/utils/generationTrace.ts`，无数据/迁移影响。

---

## Slice 2 详述：抽 `composables/useGenerationTiming.ts`

### 边界

时序相关状态 + computed + 定时器生命周期，依赖仅 props 子集（`chapterNumber`/`status`/`generationProgress`/`generationStartedAt`/`statusUpdatedAt`）。沿用 `useChapterStatus` 约定：composable 收 `props`（子集 interface），不用 `MaybeRefOrGetter`。返回 `{ elapsedText, etaText }` 供模板消费，其余时序中间量对本 composable 私有。

### 迁出符号（→ composable）

- 状态：`clockNow`/`localStartAt`/`timer`
- 常量：`STAGE_CONFIG`
- computed：`parsedGenerationStartedAt`/`parsedStatusUpdatedAt`/`startTimestamp`/`elapsedSeconds`/`backendProgress`/`currentStageConfig`/`etaText`/`elapsedText`
- 生命周期：定时器 onMounted（仅 setInterval）+ onUnmounted（clearInterval）
- watch：`[chapterNumber, status, generationStartedAt]` → 重置 localStartAt（`immediate: true`）

### 删除（死代码，全项目零引用）

- `progressPercent`（computed，从未被读）
- `activeStageLabel`（computed，从未被读；依赖 `currentStepKey`，本属 Slice 3 范畴）

抽时序时顺带删除这两个落在时序区内的死 computed，零运行时行为变化（git 可追溯）。

### 留组件

- `notifyWhenDone` ref + 其 onMounted（读 localStorage）+ toggleNotify + status→showSuccess watch（均非时序）
- 其余失败分析/pipeline/inspector 逻辑

### 组件 import 调整

- `vue`：去 `onUnmounted`（组件不再用，定时器清理随 composable）
- `@/utils/generationTrace`：去 `parseBackendTimestampToMs`（随 parsed* 迁入 composable，组件不再直接用）
- 新增 `import { useGenerationTiming } from '@/composables/useGenerationTiming'`

### 等价性 / 验证

逐字迁移 + 删 2 死 computed。`chapterGeneratingTiming` 7 用例（mount 主组件断言 DOM）全绿验证行为等价。vue-tsc exit 0 / 全量 vitest 137 绿 / eslint 0 新增（1 预存 `@/api/novel` 警告，composable 不受限）。

---

## Slice 3 详述：抽 `composables/useGenerationFailure.ts`

### 边界（相对原计划的调整）

原计划把 `currentStepKey`（54 行分支）纳入本 slice。深入依赖图后发现 `currentStepKey` 是**横跨正常/失败的步骤状态机枢纽**——被 `activeStepTraces`/`activeTrace`/`activeStepDetails`/`currentStepIndex`/`stepState`/`canRetryFromNode`/`selectStep`/`stepTooltipText`/2 个 watch 几乎整个 script 消费。强行抽走会牵动大半个组件、命名失真（并非"失败分析"）、风险升到中高。

故本 slice **只抽纯失败展示** 5 符号（依赖闭合于 props 子集 + utils），`currentStepKey` 系列状态机留后续 slice（建议命名 `useGenerationPipeline`，风险更高值得独占注意力）。按 CLAUDE.md「风险更低/diff 更小优先」。

### 迁出符号（→ composable）

- `isFailureStatus`、`terminalFailedTrace`、`failureReason`、`failureScenario`、`failedVersionCards`（5 符号逐字迁移）
- `stepExists`（failureReason 依赖它判断步骤键合法性；composable 内自建，同时返回供组件 currentStepKey 复用）

### composable 签名

`useGenerationFailure(props: GenerationFailureProps, pipelineSteps: ComputedRef<PipelineStep[]>)`。第二参数 pipelineSteps 是对 useChapterStatus「只收 props」范式的唯一偏离——failureReason 的 stepExists 分支需要步骤键集合，而 pipelineSteps 随 status 变化不可硬编码。注释已说明。

### 留组件（步骤状态机，后续 slice）

`pipelineSteps`、`parsedStepPayload`、`currentStepKey`、`currentStepIndex`、`stepState`、`canRetryFromNode`、`retryGenerateLabel`、`selectStep`、`stepTooltipText`、`completedSteps`、`activeStepTraces`/`activeTrace`/`activeStepDetails`、watch/lifecycle。这些消费 composable 返回的 isFailureStatus/terminalFailedTrace/failureReason/failureScenario/stepExists（解构同名，.value 引用零改动）。

### 组件 import 调整

- `@/utils/chapter`：整行删（cleanVersionContent + formatChapterGenerationError 随 failureReason/failedVersionCards 迁出，组件无其他消费点）
- `@/utils/text`：整行删（countNonWhitespaceChars 随 failedVersionCards 迁出）
- 新增 `import { useGenerationFailure } from '@/composables/useGenerationFailure'`
- `@/utils/generationTrace`：parseStepPayload/normalizePipelineStepKey 保留（parsedStepPayload/currentStepKey/activeStepTraces 仍用）

### 等价性 / 验证

逐字迁移，消费点零逻辑改动（解构同名）。chapterGeneratingTiming 7 用例（mount 主组件断言 DOM，覆盖 failureReason/failureScenario/failedVersionCards/currentStepKey）全绿验证运行时等价。vue-tsc exit 0 / 全量 vitest 137 绿 / eslint 0 新增（1 预存 `@/api/novel` 警告，composable 不受限）。

---

## Slice 4 详述：抽 `composables/useGenerationPipeline.ts`

### 边界

抽**步骤状态机**——把 pipeline 步骤集、当前步骤键推导（currentStepKey 55 行分支）、步骤运行态（stepState/canRetryFromNode）、tooltip 文案（stepTooltipText）整体迁入 composable。这是 design.md 原计划的中风险块；现状（1559 行）下大头仍是 currentStepKey，必须抽走才能显著推进 <500。

### 迁出符号（→ composable）

- `parsedStepPayload`（computed，仅 currentStepKey 消费，composable 内部，不返回）
- `isWaitingForManualConfirm` + `shouldShowManualConfirmBadge`（仅后者返模板）
- `currentStepKey`（computed，55 行分支逐字迁移；返回，组件 active*computed 与 2 个 watch 复用）
- `currentStepIndex`（computed，仅 composable 内 stepState 用，不返回）
- `stepState`（函数，逐字迁移；返回，模板 + 组件 selectStep 复用）
- `canRetryFromNode`（函数，逐字迁移；返回）
- `stepTooltipText`（函数，逐字迁移；返回）

### 删除（死代码，全项目零引用，已 rg 确认）

- `completedSteps`（computed，仅 L450 定义无消费点）—— 按 Slice 2 删 progressPercent/activeStageLabel 先例顺带删

### composable 签名

`useGenerationPipeline(props: GenerationPipelineProps, pipelineSteps: ComputedRef<PipelineStep[]>, failure: FailureAnalysis)`。

- `GenerationPipelineProps`：props 子集 `{ status, generationStep, readOnly }`
- `pipelineSteps`：复用组件现有 computed（同时是 useGenerationFailure 的输入；为唯一叶节点，留组件避免循环依赖）
- `failure`：useGenerationFailure 返回的子集 `{ isFailureStatus, terminalFailedTrace, stepExists, failureReason, failureScenario }`——currentStepKey 需要 isFailureStatus/terminalFailedTrace/stepExists 定位失败节点，stepTooltipText 需要 failureReason/failureScenario。这是对「只收 props」范式的较大偏离，但语义合理：步骤状态机天然需要"失败发生在哪一步"。注释说明。

返回 `{ currentStepKey, stepState, canRetryFromNode, shouldShowManualConfirmBadge, stepTooltipText }`。

### 留组件（依赖 activeStepKey 组件状态 / trace 展示 / 动作）

`pipelineSteps`、`selectStep`（写 activeStepKey，调 composable 的 stepState）、`activeStepKey` ref、watch×2（currentStepKey→activeStepKey / readOnly→activeStepKey）、`activeStepTraces`/`activeTrace`/`activeStepDetails`（消费 currentStepKey + activeStepKey）、`retryGenerateLabel`、`previewParagraphs`/`previewModeLabel`、actions、status→notify watch、onMounted。这些消费 composable 返回的 currentStepKey/stepState（解构同名，.value/调用零改动）。

### 组件 import 调整

- `@/utils/generationTrace`：去 `parseStepPayload`（随 parsedStepPayload 迁入 composable，组件不再直接用）。STEP_DETAILS/PIPELINE_LABELS/normalizePipelineStepKey/trace* 保留（activeStepDetails/activeStepTraces 仍用）。
- 新增 `import { useGenerationPipeline } from '@/composables/useGenerationPipeline'`

### 依赖顺序（自顶向下，无循环）

```
pipelineSteps(props)            ← 留组件
useGenerationFailure(props, pipelineSteps) → failure
useGenerationPipeline(props, pipelineSteps, failure)
  ├ parsedStepPayload
  ├ currentStepKey ← parsedStepPayload + pipelineSteps + failure.{isFailureStatus,terminalFailedTrace,stepExists}
  ├ currentStepIndex ← pipelineSteps + currentStepKey
  ├ stepState ← currentStepKey + currentStepIndex
  ├ canRetryFromNode ← stepState
  └ stepTooltipText ← stepState + failure.{failureReason,failureScenario}
```

currentStepKey 不依赖 stepState；stepState 依赖 currentStepKey/currentStepIndex——单向，无循环。

### 等价性 / 验证

逐字迁移（currentStepKey/stepState/canRetryFromNode/stepTooltipText 与原组件字节等价），消费点解构同名。chapterGeneratingTiming 7 用例（mount 主组件断言 DOM，覆盖 currentStepKey/stepState/activeTrace/失败卡片/pipeline 标题顺序）全绿验证运行时等价。vue-tsc exit 0 / 全量 vitest / eslint 0 新增（1 预存 `@/api/novel` 警告，composable 不受限）。

### 风险

中。currentStepKey 55 行分支多，抄写偏差即改变步骤状态机。强回归网覆盖；逐字迁移 + 独立复核（逐函数比对）兜底。

---

## Slice 5 详述：抽子组件 `ChapterDraftPreview.vue`

### 边界

把"正常生成中"草稿预览卡（template `chapter-console__preview-card` 整块 + 专属 `previewParagraphs`/`previewModeLabel` computed + preview/strategy scoped style）整体抽成纯展示子组件。首个子组件 slice，确立 template/script/style 三段同迁范式。

### 迁出（→ 子组件）

- template：草稿预览卡 DOM（逐字搬迁；`v-else-if="!props.readOnly"` 条件留在父的子组件标签上，保持「失败区 v-if → 草稿预览 v-else-if → 节点详情 v-if」条件链）
- script：`previewParagraphs`/`previewModeLabel`（逐字迁移；子组件收 `chapterContentPreview` prop，逻辑内聚，无对外依赖）
- style（scoped）：preview-card/header/body/cursor/strategy 独占规则（逐字）+ 卡片骨架（border/radius/bg/shadow/padding/h4，源自父 3 处共享选择器）+ `@keyframes blink-cursor` + reduced-motion cursor

### scoped 关键点（首个子组件踩到的范式坑）

1. 父 `<style scoped>` 选不到子组件元素 → 子组件必须自带 scoped style，含卡片骨架（与父其余 card 重复声明，两处维护，系 scoped 子组件固有代价，与 ChapterToolbar 范式一致）。
2. `.chapter-console__cursor { animation: blink-cursor }` → Vue scoped 给 keyframes 名加 data-v hash，子组件引用父 keyframes 会失配 → 子组件**自带 `@keyframes blink-cursor`**。

### 父组件 import 调整

- 新增 `import ChapterDraftPreview from './ChapterDraftPreview.vue'`

### 父组件 style 清理（共享选择器拆 preview-card + orphan）

- border 共享组（7 card）：删 `.chapter-console__preview-card,`
- padding 共享组（5 card）：删 `.chapter-console__preview-card,`
- h4 共享组：`.chapter-console__pipeline-card h4, .chapter-console__preview-card h4` → `.chapter-console__pipeline-card h4`
- reduced-motion：删 `.chapter-console__cursor` selector（保留 pipeline dot）
- `@keyframes blink-cursor`：删除（引用随 `.cursor` 迁出后成 orphan，本次改动产生，按 CLAUDE.md 清理自身 orphan）

### 等价性 / 验证

template/script/style 逐字搬迁，子组件骨架补全与父原值一致。chapterGeneratingTiming 7 用例（mount 主组件）全绿验证主组件渲染不破。**草稿预览卡本身无 spec 覆盖**（timing 用例均为失败/评审/pipeline 场景），等价性靠逐字搬迁 + 主组件 mount 不报错双保险；样式细节（光标动画等）需人工目视。vue-tsc exit 0 / 全量 vitest 除 reader pre-existing 失败外 138 绿 / eslint 0 新增（1 预存 @/api/novel 警告）。

### 风险

低-中。纯展示，但 scoped 骨架重复声明 + keyframes 自带是首个子组件 slice 的范式确立点，抄写偏差（骨架属性漏抄/keyframes 漏带）即视觉走样。逐字核对兜底。

---

## Slice 6 详述：抽子组件 `ChapterFailedVersions.vue`

### 边界

把"失败状态展示区域"（template `chapter-console__failed-container` 整块 + 专属 `retryGenerateLabel` computed + failed-* scoped style）整体抽成子组件。比 Slice 5 更简单：failed-* 选择器全部独占，无共享选择器需拆分。

### 迁出（→ 子组件）

- template：失败区 DOM 逐字搬迁（`v-if` 失败条件留父的子组件标签，保持「失败区 v-if → 草稿预览 v-else-if → 节点详情 v-if」条件链）
- script：`retryGenerateLabel` computed（仅本区用，逐字迁移）
- style（scoped）：failed-container/failed-versions(-head/-kicker)/failed-actions/danger-action/failed-version-grid/-card/-title/-meta/-preview/-action + `@media(max-width:833px) failed-versions-head` 全部独占规则逐字搬迁

### 非纯展示点（emit 拆分）

失败区含 `handleFailedGenerateAction`（`globalAlert.showConfirm` 二次确认副作用 + 向上 emit `generateChapter`），非纯展示。拆分方案：**handler 留父组件**（它读 props.status/props.chapterNumber，本就属于父），子组件只 emit `failedGenerateAction` 意图事件；`showVersionDetail`/`evaluateChapter` 由父转发。子组件保持"展示 + emit 意图"，confirm 业务逻辑不外泄。

### 子组件契约

- props：`status`（GenerationStatus|null）、`failedVersionCards`（FailedVersionCard[]）、`generatingChapter`（number|null）、`chapterNumber`（number|null）
- emits：`showVersionDetail[index]`、`evaluateChapter`、`failedGenerateAction`
- 内部 computed：`retryGenerateLabel`（从 status 派生）

### 类型导出（composable producer 持有，沿用 ActiveStepDetails 范式）

`useGenerationFailure.ts` 新增导出 `FailedVersionCard`（候选版本卡片结构）+ `GenerationStatus`（= Chapter['generation_status']，避免子组件直接 import @/api/novel 触发 no-restricted-imports）。纯增量，零行为变化。

### 父组件 import 调整

- 新增 `import ChapterFailedVersions from './ChapterFailedVersions.vue'`
- 删 `retryGenerateLabel` computed（orphan，随迁子组件）

### scoped 关键点

failed-* 全部独占（不在 border/padding/h4 共享选择器组），整段搬迁无需拆分。`.md-btn` 等全局类来自 main.css，scoped 子组件内仍生效（子组件渲染的元素带 data-v-child，`.chapter-console__failed-actions[data-v-child] .md-btn[data-v-child]` 命中）。

### 等价性 / 验证

template/script/style 逐字搬迁 + emit 拆分（handler 留父）。chapterGeneratingTiming 7 用例（含失败卡片 failedVersionCards、evaluation 失败主操作 retryGenerateLabel、放弃草稿二次确认 handleFailedGenerateAction）全绿验证运行时等价——失败区是 timing 测试网覆盖最密的部分。vue-tsc exit 0 / 全量 vitest **139 绿 0 失败**（reader prefetch 用例本次亦通过）/ eslint 0 新增（仅父 1 预存 @/api/novel 警告）。

### 风险

低。失败区是 timing 测试网重点覆盖对象（4/7 用例直接断言失败区 DOM/行为），回归网最强。

---

## Slice 7 详述：抽子组件 `ChapterStepInspector.vue`

### 边界

把"节点详情面板"（template `chapter-console__inspector-card` 整块 + inspector/panel scoped style）抽成纯展示子组件。`activeStepDetails`（重型 computed，依赖 currentStepKey/activeTrace/STEP_DETAILS/失败分析等）留父，作 prop 透传。沿用 Slice 5/6 的 scoped 三段同迁范式。

### 迁出（→ 子组件）

- template：节点详情面板 DOM 逐字搬迁（`v-if="activeStepDetails && (!props.readOnly || activeStepKey)"` 条件留父的子组件标签，保持「失败区 v-if → 草稿预览 v-else-if → 节点详情 v-if」条件链）
- script：无业务逻辑迁移——子组件仅 `import type { ActiveStepDetails }` + 单 prop `activeStepDetails: ActiveStepDetails`（9 字段全 string）。零 computed/emit/ref，纯展示。
- style（scoped）：inspector-card/-header/-title-group/-badge/-title/-subtitle/-meta + call-type/llm-usage/trace-status（共享三选择器，全 inspector 独占）+ trace-status.is-failed + inspector-grids(+@media) + inspector-panel/panel-title/panel-code-wrapper/panel-code + `@keyframes fadeInInspector` 全部逐字搬迁

### scoped 关键点（本 slice 比 Slice 5/6 更省事之处）

父级 `.chapter-console--read-only .chapter-console__inspector-card`（只读覆写 border-radius:0/box-shadow:none，与 pipeline-card 共享选择器组）**不迁移、保留在父**。理由：`.chapter-console__inspector-card` 是子组件根元素，Vue scoped CSS 规则「子组件根节点同时承载父级 data-v」→ 父级该后代选择器编译为 `.chapter-console--read-only[data-v-parent] .chapter-console__inspector-card[data-v-parent]`，子根继承 data-v-parent 仍命中。特异性：只读覆写 (0,4,0) > 子组件基样式 (0,2,0)，覆写仍生效。故本 slice 无需像 Slice 5 拆共享选择器组——直接整段迁出，父只读覆写天然兼容。

inspector/panel/call-type/llm-usage/trace-status 选择器全部 inspector 独占（不在 border/padding/h4 共享组），整段搬迁无需拆分。

### 父组件 import 调整

- 新增 `import ChapterStepInspector from './ChapterStepInspector.vue'`

### 测试指针跟随（uiAuditRegression.spec.ts）

`labels chapter trace details by action...` 用例原读 `ChapterGenerating.vue` 源码断言面板标签「输入材料/实际动作/产出结果/调用类型/LLM 调用」。这些文本随 Slice 7 迁入子组件 → 断言改为读 `ChapterStepInspector.vue` 源码（`inspectorSource`）；逻辑引用 `traceUsesLlm`/`formatTraceActions` 仍在父 activeStepDetails computed，断言仍指 `source`。语义不变，仅换读源目标。沿用 Slice 1 在同文件的指针跟随先例（L253-254/L269 注释）。

### 等价性 / 验证

template/style 逐字搬迁 + 单 prop 透传 + 测试指针跟随。chapterGeneratingTiming 7 用例（mount 主组件断言 DOM，activeStepDetails 经 formatSystemDuration/formatTrace* 组装）全绿验证运行时等价。vue-tsc exit 0 / 全量 vitest **139 绿 0 失败** / eslint 0 新增（仅父 1 预存 @/api/novel 警告，子组件用 `@/utils/generationTrace` 的 ActiveStepDetails 类型，非受限路径）。

### 风险

低。纯展示，无业务逻辑迁移。**唯一理论等价点（无 spec 覆盖）**：只读模式下 inspector-card 的 border-radius:0/box-shadow:none 覆写靠 Vue「子组件根继承父 data-v」机制生效——属 CSS 行为，timing 测试断言 DOM 不覆盖样式细节，需人工目视只读回溯场景的节点详情面板边框/阴影。

---

## <500 缺口（Slice 7 后评估）

| Slice | 主组件行数 |
|---|---|
| 起点 | 2261 |
| Slice 1 后 | 1762 |
| Slice 2 后 | 1664 |
| Slice 3 后 | 1559 |
| Slice 4 后 | 1455 |
| Slice 5 后 | 1330 |
| Slice 6 后 | 1167 |
| **Slice 7 后** | **977** |

节点详情面板已抽出。主组件 977 行，仍 >500，需继续拆分：pipeline 进度卡（步骤 ol + Tooltip + 节点重试，~80 行 template + 大量 pipeline/dot/连线/badge style）与 footer actions（~20 行）是剩余可抽的展示块；script 区（activeStepDetails/activeTrace/activeStepTraces/pipelineSteps/selectStep/动作/watch）仍是主体，可考虑抽 `useChapterGenerationTrace` composable 收 trace 组装逻辑。每会话一块。
