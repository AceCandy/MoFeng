# 升级前端框架主版本

## Goal

在安全基线和新工具链稳定后，迁移剩余前端框架主版本并保持现有用户行为。

## Requirements

- 基于前三批完成后的 `npm outdated` 清单确定剩余范围：Vue Router 5.2.0、Pinia 4.0.3、marked 18.0.10。
- Pinia 4 将 `@vue/devtools-api` 改为必需 peer，直接引入其最新兼容版本 8.2.1。
- 按依赖逐项升级并运行聚焦回归，禁止一次性改完后再定位故障。
- 保持路由守卫、状态持久化、Markdown 消毒、编辑器和 AppShell 行为兼容。
- 仅做主版本迁移所需的最小代码调整，不重设计 UI 或重构相邻模块。

## Acceptance Criteria

- [x] 所有剩余直接依赖处于最新兼容版本，任何例外均有 peer/运行时证据。
- [x] `npm ci`、audit、API check、type-check、完整单测、lint、build 和 bundle budget 均通过。
- [x] 路由、Pinia store、Markdown 渲染/消毒相关聚焦测试通过。
- [x] 登录、AppShell、写作台编辑器浏览器冒烟通过，调试服务已关闭。

## Out of Scope

- 新功能、UI 重设计、后端依赖升级及与迁移无关的代码清理。
- TypeScript 6/7 与 `@types/node` 26；继续执行上一子任务已批准的 peer/真实运行时版本例外。

## Technical Evidence

- Vue Router 5 官方迁移说明确认：未使用 `unplugin-vue-router`/文件路由时无破坏性变化；现有 `next()` 守卫仍兼容但已弃用，迁移为返回值语义。
- Pinia 4 仅有 ESM-only 与显式 `@vue/devtools-api` peer 两项技术性破坏；项目本身是 ESM，现有 `defineStore`、`createPinia`、`setActivePinia` 用法均受支持。
- marked 17/18 的破坏性变化集中在 tokenizer/renderer token 形状与尾部空行；项目只调用 `marked.parse`/`setOptions`，并在输出边界使用 DOMPurify。
