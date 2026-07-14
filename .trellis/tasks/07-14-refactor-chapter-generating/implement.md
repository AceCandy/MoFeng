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
