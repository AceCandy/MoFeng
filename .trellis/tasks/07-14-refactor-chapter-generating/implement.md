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
