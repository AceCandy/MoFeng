# 实施计划

## 1. 安全合同与正确性

- [x] 为系统配置敏感键分类和响应脱敏先写后端失败测试。
- [x] 修改 schema/service，更新 OpenAPI 与生成 TypeScript 类型。
- [x] 修改管理配置 UI 的状态展示与“留空保留”编辑语义。
- [x] 修复 `WDSidebar` 完成态优先级并补最小回归测试。
- 验证：相关 Pytest、API contract check、WDSidebar/Vitest、TypeScript 类型检查。
- 回滚点：安全合同改动独立提交前 diff 可单批撤销；不得以回滚为由恢复秘密回显。

## 2. 核心移动路径与管理详情

- [x] 共享详情导航加入 chapters、URL 同步、普通用户移动 topbar/H1/CTA。
- [x] 新增管理员详情 query，统一普通/管理员 `novel` 数据源。
- [x] 修复写作台互斥抽屉、关闭态 inert/aria-hidden 与横向溢出。
- [x] 章节移动列表按钮补可访问名称，滚动区补键盘入口。
- 验证：组件/查询测试；390×844 浏览器检查 `scrollWidth`、抽屉焦点、章节入口、管理计数。
- 回滚点：共享详情与写作台分别保持可独立撤销。

## 3. 数据保护与业务动作

- [x] 扩展 `useDialogA11y` 背景 inert，并覆盖现有删除弹窗。
- [x] 设置页阶段路由的 tab/路由离开/beforeunload 脏状态保护。
- [x] Prompt 选择、管理 tab、路由离开的脏状态保护。
- [x] 用户启停确认和可访问名称。
- [x] 灵感重开复用项目删除 mutation，失败不清空；工作台 CTA 文案/去向共用状态判定。
- 验证：对应 Vitest、静态回归测试和浏览器取消/确认路径。

## 4. 相关视觉 polish

- [x] 修复词笺、今日目标、删除操作、风险提示、更新时间等报告定位的 AA 对比度。
- [x] 移动阶段路由压缩为可展开分组。
- [x] 管理统计加载态用占位符/骨架，统一 H1/H2 与滚动区 tabindex。
- [x] 只使用现有 token 和组件，检查无偶然样式漂移。
- 验证：桌面+移动一次成批截图，axe，Impeccable detector。

## 5. 集成复核

- [x] 运行前端相关 Vitest、`npm run type-check`、`npm run lint`。
- [x] 运行相关后端 Pytest，不执行无必要的数据库全量套件。
- [x] 运行 `npm run api:check`；若 schema 变更，确认 OpenAPI 与生成类型已同步。
- [x] 浏览器逐页检查 9 个路由的桌面/390px、键盘、控制台、横向溢出、加载/错误/确认状态。
- [x] 运行一次 Impeccable detector，独立审查 source diff；清理截图、socket、临时服务和本地产物。
- [x] `git status --short` 只包含任务文档、审查报告和本任务直接修改文件。

## 验证记录

- 2026-08-23：`npm run lint`、`npm run type-check`、`npm run api:check` 通过；全量 Vitest 44 个文件、357 项通过；相关后端 Pytest 61 项通过。
- 桌面与 390×844 已回归九个目标路由；注册功能在当前环境关闭，`/register` 按配置重定向到 `/login`，因此真实注册表单仅由合同测试覆盖。
- 逐页 axe 未发现违规；Impeccable detector 结果为空。浏览器回归未发现新增控制台错误，灵感页一次 409 走既有冲突恢复路径。
