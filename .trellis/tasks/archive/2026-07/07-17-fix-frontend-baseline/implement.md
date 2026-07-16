# implement.md - 前端基线修复

## Slice 1: build import 修复（已完成）

- PersonalModelRouting.vue + ProviderCard.vue：9 处加 `.vue` 扩展名 + 10 处具名改默认 import
- verify: `vite build` 绿（`✓ built`，3180 modules）+ vue-tsc 34->14

## Slice 2: vite.config.ts overload（1 error）

- L114 defineConfig async 返回，vueDevToolsPlugin 返回 `false | Plugin`，类型不匹配
- 修复：loadVueDevToolsPlugin 返回类型标注 `Plugin | false`，或 defineConfig 返回类型断言
- verify: vue-tsc 14->13

## Slice 3: useChapterReader.ts never 推断（5 error）

- L182-185 property 'text'/'end'/'start' on never
- 修复：看 L180 附近变量类型注解（可能数组/对象缺类型断言导致 never）
- verify: vue-tsc ->8

## Slice 4: WDWorkspace.vue 类型收紧（4 error）

- L25 boolean|undefined vs boolean；L26 BodyComponentExpose|null vs Ref；L392/393 (n)=>boolean|undefined
- 修复：props 默认值/非空守卫 + Ref 类型标注 + handler 返回值收紧
- verify: vue-tsc ->4

## Slice 5: NovelDetailShell + ChapterPipeline + PMR 类型（4 error）

- NovelDetailShell.vue:54 emit handler payload
- ChapterPipeline.vue:75 number|null vs number
- PersonalModelRouting.vue:90 Event vs MouseEvent；:93 ModelPickerDialog props
- verify: vue-tsc ->0

## Slice 6: :global CSS warning

- main.css L4707-4708 `:global(...)` -> 标准选择器
- verify: `vite build` 无 :global warning

## Slice 7: 验证流程 + 收口

- 沉淀 memory：三件套含 build + cd 前缀 + 假绿根因
- 三件套 + build 全绿验证
- commit + finish-work

## 全局验证清单（每 slice）

- `vue-tsc --build frontend/tsconfig.json`（绝对路径二进制）error 数下降
- `vite build` 绿（Slice 1 后持续）
- `vitest run` 全绿
- `eslint` 改动文件 0 新增 error

## commit 策略

- Slice 1（build import）+ Slice 2-5（vue-tsc）+ Slice 6（:global）可合并 1-2 个 commit（基线修复语义内聚）
- Slice 7 memory 单独或随收口
