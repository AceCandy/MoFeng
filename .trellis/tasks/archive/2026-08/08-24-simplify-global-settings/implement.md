# 实施计划：全局导航与设置体系收口

## 1. 导航与路由

- [x] 在 `router/index.ts` 增加 `/account/security`，复用 app layout 与认证守卫。
- [x] 新建薄视图 `AccountSecurityView.vue`，复用 `PasswordManagement` 非 modal 模式。
- [x] 将登录后的强制改密跳转和全局守卫从不存在的 `/admin?tab=password` 改为 `/account/security`，并验证完成改密后解除限制。
- [x] 清理 PasswordManagement 中仅面向管理员的占位文案，使普通用户账户安全入口成立。
- [x] 在 `AdminView.vue` 增加 `prompt-usage` 分区并接入 `PromptUsageMap`。
- [x] 将 `PromptUsageMap` 的编辑跳转改为 `/admin?tab=prompts`。
- [x] 将 `AppShell.vue` 的 AI 设置、账户安全、管理后台入口改为路由导航。
- [x] 从账户菜单删除独立“提示词用量”入口。

验证：普通/管理员菜单项目与路由正确；刷新、前进、后退保持页面和分区。

## 2. 删除全局业务弹窗宿主

- [x] 删除 `AppShell.vue` 中 Settings/Admin/PromptUsage/Password 的异步导入、状态、refs、保存/关闭处理器和 Teleport 节点。
- [x] 保留任务日志弹窗、用户菜单 Escape/焦点恢复、退出登录行为。
- [x] 删除因上述改动形成的无用样式/import；若 `settings-modal.css` 无消费者，删除文件及 `main.css` import。
- [x] 移除 `SettingsView.isModal`、`AdminView.isModal` 与 `PasswordManagement.isModal` 无消费者分支。

验证：DOM 中不出现“个人设置”业务 dialog；任务日志 dialog 回归不变。

## 3. 设置页面分层

- [x] 在 `SettingsView.vue` 中把 llm/embedding 归为基础能力，tts/routes 归为高级能力，保留原 section ID 和 URL query。
- [x] 复用现有 readiness 数据突出下一个缺失步骤，不新增向导状态。
- [ ] 将自定义供应商类型/Base URL 放入原生 `<details>`；保留名称、API Key 和启用所需操作。（Base URL 当前必填且无可靠预设，隐藏会破坏首次配置，审查后不实施。）
- [x] 删除重复“新增供应商”主入口。
- [x] 收敛供应商启停入口，保留一个主要路径。
- [x] 阶段路由默认文案改为“继承主模型”，仅强调显式覆盖。

验证：基础配置可在单页面层级完成；低频配置仍可访问且 API payload 不变。

## 4. 模型选择内联化

- [x] 将 `ModelPickerDialog.vue` 重命名为 `ModelPickerPanel.vue` 并更新引用/测试。
- [x] 删除 Teleport、dialog/overlay 语义和浮层定位，改为供应商卡片后的内联区域。
- [x] 保留搜索、动态 aria-label、选择、保存、取消和 dirty 关闭保护。
- [x] 为触发按钮补齐/保留 `aria-expanded`、`aria-controls`，关闭后恢复焦点。
- [x] 移除 `pending-tts-model-name` 无效传参并确认控制台无 Vue warning。

验证：文本、embedding、TTS 三种模型选择均工作；无第二层业务 dialog、无接口警告。

## 5. 测试更新

- [x] 扩展账户菜单测试：普通/管理员可见项、提示词用量移除、路由跳转、无设置弹窗宿主。
- [x] 扩展 `ui-p1-regression.spec.ts`：从账户菜单进入 `/settings` 和 `/admin`。
- [x] 增加 `/settings?tab=embedding` 刷新及前进/后退验证，非法 tab 回落 llm。
- [x] 增加未保存修改取消/确认路径。
- [x] 增加 ModelPickerPanel 打开、Escape/取消、dirty 保护、焦点恢复和动态 ARIA 名称测试。
- [ ] 增加账户安全密码表单的最小验证与成功路径测试。（本轮沿用既有表单实现，未新增后端成功路径 E2E。）
- [x] 增加强制改密路由守卫测试：登录/直接导航均进入 `/account/security`，成功改密后可离开。
- [x] 保留 `ttsSettings`、`modelRoutingHelpers`、`RoutingStagesPanel` 的 TTS/阶段路由合同。

## 6. 质量门

- [x] 运行相关 Vitest：导航、设置、TTS、模型路由、阶段路由、密码。
- [x] 运行设置/导航相关 Playwright，桌面与 Pixel 7 一次完成。
- [x] 对 `/settings`、`/account/security`、`/admin?tab=prompt-usage` 做 axe 核验。
- [x] 运行 `npm run type-check`。
- [x] 运行 `npm run lint`。
- [x] 运行 `npm run build`，确认 CSS/JS budget 通过。
- [x] 独立复核 diff：无后端/API/数据库变化，无遗留 modal 状态或无用 import。

## 风险与回滚点

- `AppShell.vue` 删除范围大但逻辑集中；先完成路由入口再删除弹窗状态，确保始终有可用入口。
- `ModelPickerDialog` 改为内联是最高交互风险点，单独验证后再做视觉分层。
- `SettingsView` query 和 dirty guard 必须先有回归测试，再删除 modal 分支。
- 若移动端内联面板过长，优先使用页面内折叠，不回退到嵌套 modal。

## 明确不做

- 不新增依赖、store、通用设置框架或向导状态机。
- 不修改后端、OpenAPI、数据库或模型路由算法。
- 不删除 `shellNavigation.ts` 等不影响本次用户结果的既有死代码。
