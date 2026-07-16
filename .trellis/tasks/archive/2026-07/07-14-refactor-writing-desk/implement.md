# WritingDesk 拆分执行计划

## Slice 1：5 payload 纯函数去重

### 步骤

1. **改 import 块** `WritingDesk.vue` L303-308：`@/utils/chapter` 加 5 名（字母序）
   - decodeJsonStringFragment / extractJsonField / normalizeOptimizeResult / parseEvaluationPayload / tryParseOptimizerPayload
   - → verify: `rg -n "from '@/utils/chapter'" src/views/WritingDesk.vue` 含 5 名

2. **删本地副本** L877-979（tryParseOptimizerPayload … parseEvaluationPayload 连续块）
   - 保留 L865-875（recommendedOptimizedParagraphs/WordCount computed）
   - 保留 L981 watch
   - → verify: `rg -n "^const (tryParseOptimizerPayload|decodeJsonStringFragment|extractJsonField|normalizeOptimizeResult|parseEvaluationPayload)" src/views/WritingDesk.vue` EXIT=1（无声明，仅调用点）

3. **vue-tsc**：`cd frontend && npx vue-tsc --noEmit` → EXIT=0

4. **vitest**：`cd frontend && npx vitest run` → 全绿（重点 wdWorkspaceLockedChapter）

5. **eslint**：`cd frontend && npx eslint src/views/WritingDesk.vue` → 0 新增 error/warning

6. **行数**：`wc -l frontend/src/views/WritingDesk.vue` → ~1910

7. **独立复核**：`git diff src/views/WritingDesk.vue` 确认仅 import 加 5 名 + 删 L877-979，无其他改动

8. **提交 + 推送**：commit message `refactor(frontend): 去 WritingDesk payload 纯函数重复（#22 WritingDesk Slice 1）`

9. **更新 design.md** Slice 1 行标 ✅ + 实际行数；更新 memory mofeng-audit-progress

### Review gate

- 5 函数逐字等价已 design.md 验证；实施后 git diff 复核仅删本地副本 + 加 import。
- spec L333 resolveRecommendedVersionIndex 留本地，断言不破。

### Rollback

单文件改动（WritingDesk.vue），`git checkout src/views/WritingDesk.vue` 即回滚。

### 后续 slice（每会话一块）

见 design.md roadmap（Slice 2-9+）。每 slice 仿 NovelDetailShell：rg 预扫消费点 + spec 断言 → 抽 composable/子组件 → 指针跟随 → 三件套 → 独立复核 → 提交推送 → 更新 design/memory。
