# 统一 Node 与构建工具链设计

## Boundary

本任务只修改 Node 基线、前端工具链依赖、npm 构建脚本和直接关联配置。产品运行时代码、Vue Router、Pinia、marked 与 UI 行为不在本批范围内。

## Runtime Baseline

- `engines.node` 设为 `^24.15.0`，匹配 jsdom 30 对 Node 24 的最低要求。
- 三个 GitHub Actions Node 配置与 Docker 前端构建镜像统一到 Node 24.15.0。
- `@types/node` 使用 24.x latest，`@tsconfig/node22` 替换为 `@tsconfig/node24`，`tsconfig.node.json` 同步更新 extends。

## Toolchain Versions

- Vite 8.2.2、Vitest 4.1.11、jsdom 30.0.1、`@vue/tsconfig` 0.9.1。
- TypeScript 保持 5.9.3：`openapi-typescript@7.13.0` latest 的 peer 范围为 `^5.x`，这是完整依赖树可接受的最新 TypeScript。
- 现有 `@vitejs/plugin-vue`、`@vitejs/plugin-vue-jsx`、vue-tsc 与 Vue DevTools plugin 已声明支持目标版本，无需为版本号制造无效改动。

## Build Script Simplification

仓库只有 `package.json` 的 `build` 使用 `run-p`，所有 CI/Docker 调用均为无额外参数的 `npm run build`。改为原生串行脚本：

`npm run type-check && npm run build-only && npm run build:budget`

由此删除 `npm-run-all2` 及其传递依赖。串行执行会略慢，但保持门禁顺序与失败语义，且不再维护单用途依赖。

## Compatibility and Rollback

- 保持 TypeScript strict、Vite config runtime test、完整单测和 bundle 硬预算不变。
- 每项配置随同一个工具链提交交付；出现无法兼容的主版本时回退该依赖及其必要配置，不使用 peer 绕过参数。
