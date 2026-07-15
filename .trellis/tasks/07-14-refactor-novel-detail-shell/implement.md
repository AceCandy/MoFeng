# 执行清单 — NovelDetailShell 拆分

## Slice 1：抽 `sectionIcons.ts`（section 导航图标）

> 目标：script-only 纯数据抽取，验证拆分范式 + 三件套流程；零运行时行为变化。

- [ ] 1. 创建 `frontend/src/components/novel-detail/sectionIcons.ts`：逐字搬迁 `getSectionIcon` + 8 个 SVG 函数组件 + `Record<SectionKey, any>`；`SectionKey = AllSectionType` 从 `@/api/novel` import type；导出 `getSectionIcon`。
- [ ] 2. 改 `NovelDetailShell.vue`：删 L390-444（`getSectionIcon` 整块），加 `import { getSectionIcon } from '@/components/novel-detail/sectionIcons'`（放在 `BlueprintEditModal` import 后、`@/assets/blueprint.css` 前，与组件 import 分组一致）。template L117 零改动。
- [ ] 3. **验证**：
  - `wc -l` 确认 1662 → ~1608。
  - `cd frontend && npx vue-tsc --noEmit`（exit 0）。
  - `cd frontend && npx vitest run`（全绿，重点看 uiAuditRegression + novelDetailHeading）。
  - `cd frontend && npx eslint src/components/novel-detail/sectionIcons.ts src/components/shared/NovelDetailShell.vue`（0 新增）。
- [ ] 4. 独立复核 diff（逐字搬迁、surgical、无副作用扩散）。
- [ ] 5. 更新 `design.md` Slice 1 小节补实际行数/验证结果。
- [ ] 6. commit + push（无 Co-Authored-By）。
- [ ] 7. 更新 memory `mofeng-audit-progress.md` + `MEMORY.md` 索引。

### 回滚点

每步均为独立 Edit/Write，任一验证失败可直接 revert 对应改动。整体可 `git checkout -- <files>` 回到 1662 基线。
