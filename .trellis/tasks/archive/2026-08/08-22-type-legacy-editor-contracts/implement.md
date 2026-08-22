# 实施计划

1. 锁定基线与清单
   - 复核 7 个目标组件及两个直接父调用点。
   - 记录 runtime props、字符串 emits 和 3 处显式 `any`。
   - Gate：`npm run type-check` 与现有 `uiAuditRegression.spec.ts` 通过。
2. 迁移五个数组编辑器
   - generic props + typed `update:modelValue`；复用 `ChapterOutline`/`Blueprint`，其余保留本地接口。
   - `CharactersEditorEnhanced.extra` 改为 unknown 字典扩展。
   - clone helper 在 `structuredClone` 拒绝 reactive Proxy 时回退到既有 JSON clone。
   - Gate：Scoped ESLint + type-check。
3. 迁移弹窗与蓝图确认事件
   - 类型化 `BlueprintEditModal` props/emits/本地内容；保持五分支和 fallback。
   - `BlueprintConfirmation` 复用 `BlueprintGenerationResponse`。
   - 编译器若暴露父监听器问题，只在直接父组件点改；若越过任务边界则返回规划。
4. 补聚焦回归
   - 新增代表性数组编辑器 v-model 克隆/emit 测试和弹窗 save payload 测试。
   - 测试环境保留原生 `structuredClone`，证明 Proxy fallback 生效而非通过 stub 绕过。
   - 复跑 `uiAuditRegression.spec.ts`。
5. 最终门禁
   - `npm run type-check`
   - 对改动 TS/Vue/测试运行 scoped ESLint。
   - 聚焦 Vitest 后运行 `npm run test:unit`。
   - 目标 `rg`、`git diff --check`、Trellis validate、独立只读复核。
