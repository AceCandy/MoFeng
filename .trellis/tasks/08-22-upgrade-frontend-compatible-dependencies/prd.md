# 升级前端兼容依赖

## Goal

在不跨主版本的前提下，将所有前端直接依赖升级到最新兼容版本，缩小后续主版本迁移跨度。

## Requirements

- 基于安全修复任务完成后的 `npm outdated` 清单确定范围。
- 更新 Vue、Tailwind、TipTap、TanStack Query、Naive UI、ESLint、vue-tsc、Vite plugins 等同主版本依赖。
- 不升级 Vite 8、Vitest 4、TypeScript 7、Vue Router 5、Pinia 4、jsdom 30、marked 18 等主版本。
- 不修改业务行为；仅在新版本暴露真实兼容问题时做最小修复并留下聚焦回归检查。

## Acceptance Criteria

- [ ] `npm outdated` 中不再存在可安全完成的同主版本直接依赖更新。
- [ ] `npm audit` 为 0，锁文件可由 `npm ci` 复现。
- [ ] API check、type-check、完整单测、lint、build 和 bundle budget 均通过。
- [ ] 主版本依赖保持在后续任务边界内，未混入本批次。

## Out of Scope

- Node 基线、构建工具链主版本和框架主版本迁移。

