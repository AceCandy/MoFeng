# 升级前端兼容依赖

## Goal

在不跨主版本的前提下，将所有前端直接依赖升级到最新兼容版本，缩小后续主版本迁移跨度。

## Requirements

- 基于安全修复任务完成后的 `npm outdated` 清单确定范围。
- 更新 Vue、Tailwind、TipTap、TanStack Query、Naive UI、ESLint、vue-tsc、Vite plugins 等同主版本依赖。
- 不升级 Vite 8、Vitest 4、TypeScript 7、Vue Router 5、Pinia 4、jsdom 30、marked 18 等主版本。
- 不修改业务行为；仅在新版本暴露真实兼容问题时做最小修复并留下聚焦回归检查。

## Acceptance Criteria

- [x] `npm outdated` 中不再存在可安全完成的同主版本直接依赖更新。
- [x] `npm audit` 为 0，锁文件可由 `npm ci` 复现。
- [x] API check、type-check、完整单测、lint、build 和 bundle budget 均通过。
- [x] 主版本依赖保持在后续任务边界内，未混入本批次。

## Out of Scope

- Node 基线、构建工具链主版本和框架主版本迁移。

## Verification

- 27 个直接依赖升级到当前主版本的最新兼容版本；TypeScript 5.8.3 → 5.9.3，Vue 3.5.22 → 3.5.41，TipTap 3.29.2 → 3.30.2。
- `npm ls --depth=0`：通过，无 invalid、peer 或 engine 冲突。
- `npm outdated --json`：仅剩 10 个后续主版本/工具链任务项目：`@types/node`、`@vue/tsconfig`、jsdom、marked、npm-run-all2、Pinia、TypeScript、Vite、Vitest、Vue Router。
- `npm ci` 与独立复核的 `npm ci --ignore-scripts`：均可从锁文件复现安装。
- `npm audit`、`npm audit --omit=dev`：均为 0。
- `npm run api:check`、`npm run type-check`、`npm run lint`：通过。
- `npm run test:unit`：44 个测试文件、348 个测试全部通过。
- `npm run build`：构建及硬预算通过；JS 总 gzip 565.09 KB，CSS 总 gzip 82.16 KB。
- `git diff --check` 与独立复核：通过；tracked diff 仅任务状态、`frontend/package.json` 和 `frontend/package-lock.json`。

## Unverified and Remaining Risk

- 未执行真实浏览器冒烟或生产部署验证；本批无产品源码修改，完整测试和构建门禁已覆盖约定范围。
- JS 总 gzip 565.09 KB 超过 560 KB 软预警线，但低于 600 KB 硬上限；本批不通过业务重构或抬阈值掩盖，留待后续批次持续比较。
