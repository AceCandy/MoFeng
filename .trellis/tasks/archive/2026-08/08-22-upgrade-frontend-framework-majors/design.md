# 前端框架主版本升级设计

## Boundary

本任务只升级 Vue Router、Pinia、marked 及 Pinia 4 新增的直接 peer。保持现有路由表、store 边界、Markdown 展示和 UI 结构不变，不引入文件路由、持久化插件或共享 Markdown 抽象。

## Dependency Migration

1. marked 16.4.2 → 18.0.10：保留 `marked.parse`、`marked.setOptions` 与 DOMPurify 净化边界；用现有评审面板测试确认常规 Markdown 渲染和危险 HTML 清理。
2. Pinia 3.0.4 → 4.0.3：新增运行时依赖 `@vue/devtools-api@8.2.1`；项目已是 ESM，两个 store 和测试中的 `setActivePinia(createPinia())` 不需要迁移。
3. Vue Router 4.6.4 → 5.2.0：项目未使用合并进 Router 5 的文件路由功能；仅把全局守卫从弃用的 `next()` 回调改为返回重定向/`undefined`，保持恢复会话、鉴权、管理员与密码重置顺序不变。

## Compatibility Contracts

- `marked.parse` 的任何 HTML 输出都必须经过 DOMPurify，禁止因升级绕开消毒。
- `useAuthStore` 继续拥有 token/user，本任务不改变 localStorage 行为；服务端缓存仍归 Vue Query。
- 导航守卫成功路径返回 `undefined`，拒绝路径返回与现有 `next(...)` 相同的 route location。
- 不使用 `--force` 或 `--legacy-peer-deps`；npm 必须正常解析所有 peer。

## Rollback

每个依赖按 marked → Pinia → Vue Router 顺序单独安装并执行聚焦回归。任一步失败时仅回退该依赖、必要 peer 和直接代码调整；完整门禁通过后再作为一个框架迁移提交交付。
