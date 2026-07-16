# design.md - 前端基线修复

## 1. build 失败修复（已完成）

**根因**（双重）：
1. PMR 子组件 import 无 `.vue` 扩展名（`from './FeedbackPanel'`）-- vite 默认 `resolve.extensions` 不含 `.vue`，resolve 失败。
2. 具名 import SFC（`import { Foo } from './Foo.vue'`）-- SFC `<script setup>` 只有默认导出，无具名导出。

**修复**：9 处加 `.vue` 扩展名 + 10 处具名改默认 import（PersonalModelRouting.vue + ProviderCard.vue）。连带修 vue-tsc 20 个 `Cannot find module` error（34->14）。

## 2. 剩余 14 vue-tsc error 修复策略（按类型分组）

| 组 | 文件:行 | error | 修复策略 |
|---|---|---|---|
| 类型收紧 | WDWorkspace.vue:25 | boolean\|undefined vs boolean | props 默认值或非空断言 |
| 类型收紧 | WDWorkspace.vue:392,393 | (n)=>boolean\|undefined vs (n)=>boolean | handler 返回值收紧或 props 标注 |
| 类型收紧 | ChapterPipeline.vue:75 | number\|null vs number | 非空守卫或默认值 |
| emit/props | PersonalModelRouting.vue:90 | Event vs MouseEvent | handler 参数类型标注 |
| emit/props | PersonalModelRouting.vue:93 | ModelPickerDialog props 不匹配 | emit 名 kebab-case 适配或 props 类型 |
| emit/props | NovelDetailShell.vue:54 | emit handler payload 类型 | handler 签名对齐 |
| Ref 类型 | WDWorkspace.vue:26 | BodyComponentExpose\|null vs Ref | shallowRef/Ref 类型标注 |
| never 推断 | useChapterReader.ts:182-185 | property on never | 变量类型注解（数组/对象类型断言） |
| overload | vite.config.ts:114 | defineConfig overload | vueDevToolsPlugin 返回 `Plugin[]` 类型 |

**原则**：仅类型修复，不改运行时行为。优先类型标注/守卫，非空断言 `!` 谨慎用（仅确认非空处）。

## 3. :global CSS warning 修复

main.css L4707-4708 `:global([data-theme='dark'])` / `:global(.dark)` 是 CSS Modules 语法，全局 CSS 不该用。Lightning CSS 不认。

**修复**：`:global([data-theme='dark'])` -> `[data-theme='dark']`（全局 CSS 直接用选择器，无需 :global）。`:global(.dark)` -> `.dark`（如有 .dark class）或删除（如无 .dark class）。看上下文定。

## 4. 验证流程修正

- 三件套定义补 `vite build`：vue-tsc --build / vitest run / eslint / **vite build**。
- vue-tsc 命令：`cd frontend && npx vue-tsc --build`（或绝对路径二进制 `frontend/node_modules/.bin/vue-tsc --build frontend/tsconfig.json`）。
- 沉淀 memory：三件套含 build + cd 前缀 + 假绿根因（漏 cd 跑 tsc help exit 0）。

## 5. 风险 + 回滚

- 类型修复可能改运行时（如非空断言掩盖真 null）-> 仅标注/守卫，断言谨慎。
- :global 改选择器可能影响 dark 主题样式 -> 手测 light/dark。
- 每 slice 独立 commit，revert 可回滚。
