# 统一 Node 与构建工具链

## Goal

将开发、CI、Docker 与类型定义统一到 Node 24 基线，并完成构建、测试和 TypeScript 工具链主版本迁移。

## Requirements

- 将 `engines.node`、CI 和部署构建镜像统一到满足所有目标依赖的 Node 24 最低版本。
- `@types/node` 跟随 Node 24，不升级到与真实运行时不匹配的 26。
- 迁移 Vite 8、Vitest 4、TypeScript 7、jsdom 30、`@vue/tsconfig` 及相关 plugins/vue-tsc。
- 检查 `npm-run-all2` 的唯一调用；原生 npm scripts 能保持行为时删除它，否则升级到兼容版本。
- 不降低 strict、测试覆盖要求或 bundle 预算。

## Acceptance Criteria

- [ ] 本地基线、CI、Docker、`engines.node` 和 `@types/node` 的 Node 主版本一致。
- [ ] 目标工具链均为最新兼容版本，peer/engine 检查无冲突。
- [ ] `npm ci`、audit、API check、type-check、完整单测、lint、build 和 bundle budget 均通过。
- [ ] Vite 开发服务可启动，登录、AppShell、写作台编辑器冒烟通过，服务已关闭。

## Out of Scope

- Vue Router、Pinia、marked 等应用框架主版本和业务功能变更。

