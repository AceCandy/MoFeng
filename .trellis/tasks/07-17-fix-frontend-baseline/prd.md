# 前端基线修复（vue-tsc error + build 失败 + :global）

## Goal

修复前端基线破损，恢复 `vite build` + `vue-tsc --build` + 三件套全绿，并修正验证流程避免假绿。属 parent `07-12-engineering-baseline` 范围。来源：#28 Phase 1 验证时暴露。

## 现状

#28 Phase 1 验证暴露前端基线破损（git stash 验证全部 pre-existing）：

1. **vite build 失败**（已修）：PMR 子组件 import 用无 `.vue` 扩展名（`from './FeedbackPanel'`），vite 默认 `resolve.extensions` 不含 `.vue`，resolve 失败；且用具名 import SFC（`import { Foo } from './Foo.vue'`），但 SFC `<script setup>` 只有默认导出无具名导出。共 9 处无扩展名 + 10 处具名 import（PersonalModelRouting.vue + ProviderCard.vue）。
2. **vue-tsc 34 error**：build 修复连带修 20（PMR `Cannot find module` 等），**剩 14 error** 分布 6 文件：
   - `vite.config.ts(114)` defineConfig overload（vueDevToolsPlugin 返回 false|Plugin）
   - `PersonalModelRouting.vue(90)` Event vs MouseEvent；`(93)` ModelPickerDialog props 类型（emit kebab-case）
   - `NovelDetailShell.vue(54)` emit handler payload 类型
   - `WDWorkspace.vue(25/26/392/393)` boolean|undefined vs boolean；BodyComponentExpose|null vs Ref
   - `ChapterPipeline.vue(75)` number|null vs number
   - `useChapterReader.ts(182-185)` property on never（类型推断）
3. **main.css `:global()` warning**（L4707-4708）：CSS Modules 语法误用，Lightning CSS 不认（build warning 不 fail 但需修）。
4. **验证流程假绿**：历史 PMR/NovelDetailShell/WDWorkspace 收口「vue-tsc 0 / 三件套绿」是假绿--vue-tsc 漏 `cd frontend` 跑全局 tsc help（exit 0 误判）+ 三件套从未含 `vite build`。

## Requirements

- `vite build` 绿（已修 import，待验证 :global 不阻塞）。
- `vue-tsc --build` 0 error（剩 14 待修）。
- `vite build` 无 `:global` warning。
- 三件套 + build 全绿：`vue-tsc --build` 0 / `vitest run` 全绿 / `eslint` 0 新增 error / `vite build` 绿。
- 修正验证流程：三件套含 `vite build`，vue-tsc 命令带 `cd frontend` 前缀（或绝对路径二进制）。
- 行为等价：类型修复不改运行时行为（仅类型收紧/标注）。

## Acceptance Criteria

- [x] `vite build` 绿（`✓ built`）。
- [x] `vue-tsc --build` 0 error。
- [x] `vite build` 无 `:global` warning。
- [x] `vitest run` 全绿 / `eslint` 0 新增 error。
- [x] 验证流程文档化（三件套 + build + cd 前缀），沉淀 memory 避免假绿重现。

## Notes

- 复杂任务：`task.py start` 前补 `design.md`（14 error 分组修复策略）+ `implement.md`（逐 error 清单）。
- parent：`07-12-engineering-baseline`。
- build import 修复已完成（待随任务 commit）；剩余 14 error + :global 待修。
