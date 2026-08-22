# 升级前端框架主版本

## Goal

在安全基线和新工具链稳定后，迁移剩余前端框架主版本并保持现有用户行为。

## Requirements

- 基于前三批完成后的 `npm outdated` 清单确定剩余范围。
- 迁移 Vue Router 5、Pinia 4、marked 18 及其余尚未处理的直接依赖主版本。
- 按依赖逐项升级并运行聚焦回归，禁止一次性改完后再定位故障。
- 保持路由守卫、状态持久化、Markdown 消毒、编辑器和 AppShell 行为兼容。
- 仅做主版本迁移所需的最小代码调整，不重设计 UI 或重构相邻模块。

## Acceptance Criteria

- [ ] 所有剩余直接依赖处于最新兼容版本，任何例外均有 peer/运行时证据。
- [ ] `npm ci`、audit、API check、type-check、完整单测、lint、build 和 bundle budget 均通过。
- [ ] 路由、Pinia store、Markdown 渲染/消毒相关聚焦测试通过。
- [ ] 登录、AppShell、写作台编辑器浏览器冒烟通过，调试服务已关闭。

## Out of Scope

- 新功能、UI 重设计、后端依赖升级及与迁移无关的代码清理。

