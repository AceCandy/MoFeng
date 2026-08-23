# 实施计划

## 1. 建立回归合同

- 在现有 UI 审计回归测试中加入账户菜单、页面身份和旧视觉残留的最小断言。
- 先运行目标测试，确认新断言能复现当前缺陷。

验证：`npm run test:unit -- src/components/__tests__/uiAuditRegression.spec.ts`

## 2. 修复共享 AppShell

- 将账户触发器和四个菜单动作改为原生按钮，补 `aria-expanded`、`aria-controls`、Escape 与焦点恢复。
- 删除旧项目上下文 scoped 样式块，不添加新 override。

验证：目标单元测试；桌面项目详情、写作台、管理详情的账户键盘路径与 axe 对比度。

## 3. 清退旧视觉残留

- 登录页删除“印”和对应样式。
- 工作台改进度文案并删除进度端点装饰。
- 写作台侧栏删除状态方印的 DOM、映射和样式。
- 项目概览把状态缩写改为“完成/待补”。

验证：目标单元测试；登录、工作台、写作台、项目详情的双视口截图/DOM 检查。

## 4. 补齐页面身份

- 工作台、灵感页、写作台真实章节标题、独立设置页补正确 `h1`；设置弹窗保持 `h2`。
- 路由复用 `meta.label` 更新 `document.title`，补登录/注册 label。

验证：目标单元测试；逐路由检查 heading 与标签页标题。

## 5. 静态质量门

在 `frontend/` 运行：

1. `npm run type-check`
2. `npm run lint`
3. `npm run test:unit`
4. `npm run build-only`
5. `npm run build:budget`
6. `node ../.agents/skills/impeccable/scripts/detect.mjs --json src`

CSS 必须保持在 26KB 硬上限内，detector 应返回 `[]`。

## 6. 独立复核与浏览器验收

- 独立只读复核变更与规格一致性，再由主流程核对关键出处。
- 启动一次本地调试服务，批量检查 9 个主路由的 1440×900 与 412×915：稳定状态 axe、页面级横向溢出、页面 h1/title、账户菜单键盘路径。
- 如发现问题，集中修复一次并最多再确认一次；结束前关闭服务和浏览器会话，删除临时产物。

## 风险文件与回滚点

- `AppShell.vue`：共享面最大；先验证账户菜单，再验证三个项目上下文路由。
- `SettingsView.vue`：路由/弹窗双用；两种上下文都要检查标题层级。
- `WDSidebar.vue`：删除状态装饰不能影响章节选择与状态 Tooltip。
- `router/index.ts`：仅添加 label/title 行为，认证守卫保持逐行不变。
