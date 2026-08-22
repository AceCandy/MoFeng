# 实施计划

1. 锁定清单与基线
   - 对研究材料列出的 13 个文件运行精确 `rg`；确认目标仍为 24 个显式 `any`。
   - 复跑 `npm run type-check` 与现有 58 个聚焦测试。
   - Gate：命中和基线与 `research/frontend-any-inventory.md` 一致。

2. 收窄纯 TypeScript 边界
   - `main.ts` 收窄 DOM target。
   - `api/novel.ts`、`generationTrace.ts` 将动态 metadata 改为 unknown 字典。
   - `useVersionResolver.ts`、`useChapterGenerationTrace.ts` 对类型检查暴露的 metadata 读取增加最小守卫。
   - `chapter.ts` 将评审解析结果改为 unknown 字典；补对象、二次编码、数组、空值和非法 JSON 测试。
   - `useWritingDeskOptimize.ts` 收窄评审字段和异常。
   - 新增 `useWritingDeskOptimize.spec.ts`，锁定合法载荷的 mutation 请求和 malformed 载荷阻断。
   - Gate：chapter/generationTrace 聚焦测试与 type-check 通过。

3. 收窄 novel-detail 数据流
   - 四个 section 的 edit value、`useShellBlueprintEdit` 缓存/入口改为 unknown。
   - `WorldSettingSection` 增加最小本地守卫；`ChaptersSection` 收窄评审条目；`sectionIcons` 使用 `Component`。
   - 不修改 `BlueprintEditModal` 或其子编辑器。
   - Gate：目标 `rg` 无类型 `any` 命中，type-check 通过。

4. 质量门禁
   - `cd frontend && npm run type-check`
   - `cd frontend && npx vitest run src/utils/__tests__/chapter.spec.ts src/utils/__tests__/generationTrace.spec.ts src/composables/__tests__/useWritingDeskOptimize.spec.ts src/components/__tests__/uiAuditRegression.spec.ts`
   - 对所有改动 TS/Vue 文件运行 scoped ESLint。
   - `cd frontend && npm run test:unit`
   - `git diff --check` 与 Trellis context validate。

5. 独立复核与规范同步
   - 复核 24 个命中分类、外部值读取前守卫、合法载荷兼容和未触及排除项。
   - 更新 frontend type-safety 中已完成的热点说明；记录实际验证与未验证项。
   - 回滚点：若需要修改遗留编辑器、生成 artifact 或请求/交互契约，返回 Phase 1。
