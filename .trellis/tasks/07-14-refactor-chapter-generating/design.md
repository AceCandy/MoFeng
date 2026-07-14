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

## <500 缺口（Slice 2 后评估）

| Slice | 主组件行数 |
|---|---|
| 起点 | 2261 |
| Slice 1 后 | 1762 |
| **Slice 2 后** | **1664** |

仍远 >500，按 Slice 3-7 继续推进，每会话一块。Slice 3（失败分析 composable，含 currentStepKey 54 行分支，中风险）是下一块；Slice 4-6 是纯展示子组件（低风险，scoped style 随迁）。具体边界推进到对应 slice 会话时在本文件追加契约表。
