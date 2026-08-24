# 技术设计：全局导航与设置体系收口

## 1. 设计目标

把全局账户菜单从“弹窗启动器”改成“路由入口”，并让设置、账户安全和管理功能各自拥有稳定页面。复用现有组件、查询与 API，不创建新的配置状态层，不修改后端合同。

## 2. 现状与根因

### 2.1 双宿主

`SettingsView` 既是 `/settings` 页面，又通过 `isModal` 嵌入 `AppShell` 的 `GlobalModalContainer`。外层 `AppShell` 因此重复持有保存、关闭、dirty 确认和组件 ref；弹窗模式还禁用了 URL 分区同步。

### 2.2 弹窗启动器集中在 AppShell

`AppShell` 同时异步加载 `SettingsView`、`AdminView`、`PromptUsageMap`、`PasswordManagement` 和 `TaskLogPanel`。前四项是稳定业务页面或表单，不应由全局壳拥有；任务日志是短时上下文反馈，继续保留弹窗。

### 2.3 基础与高级配置同权

现有四个能力分区的代码边界可复用，但导航没有表达优先级。首次配置作者和高级调优作者看到相同密度，阶段路由与定价抢占基础配置注意力。

## 3. 目标架构

```text
AppShell 账户菜单
├─ AI 设置          → /settings?tab=llm
├─ 账户与安全       → /account/security
├─ 管理后台(admin)  → /admin
└─ 退出登录

/settings (SettingsView，唯一宿主)
├─ 基础能力
│  ├─ 文本生成 llm
│  └─ 记忆检索 embedding
└─ 高级能力
   ├─ 语音朗读 tts
   └─ 阶段路由 routes

/account/security (AccountSecurityView)
└─ 复用 PasswordManagement，非 modal 模式

/admin (AdminView)
├─ 既有分区
└─ 提示词用量 prompt-usage → 复用 PromptUsageMap
```

## 4. 组件边界

### 4.1 AppShell

- 删除设置、管理、提示词用量和密码弹窗的状态、异步组件、ref、保存/关闭处理器及 Teleport 节点。
- 账户菜单项目通过 `router.push` 导航并关闭菜单。
- 保留用户菜单的 Escape、外部点击关闭和焦点恢复合同。
- 保留任务日志 `GlobalModalContainer`，不改变后台任务提醒语义。

这一步是主要删除收益：全局壳不再知道业务表单如何保存。

### 4.2 SettingsView

- 移除 `isModal` prop 和所有双宿主分支，始终作为路由页工作。
- 保留 `tab=llm|embedding|tts|routes` query 合同、roving tabindex、dirty 确认和 `beforeunload`。
- 将现有四分区呈现为“基础能力 / 高级能力”两组，不新增向导或状态机。
- 首屏继续复用 readiness 数据表达下一缺失步骤；不增加新的后端完成度字段。
- `AdminView` 同样移除 `isModal` 分支，始终作为 `/admin` 路由页工作。

### 4.3 模型选择

- 将 `ModelPickerDialog.vue` 重命名为 `ModelPickerPanel.vue`，移除 Teleport、dialog 语义和绝对浮层定位。
- 在对应供应商卡片之后内联展开，保留搜索、选择、保存、取消和 dirty 守卫。
- 触发按钮继续暴露 `aria-expanded` / `aria-controls`；关闭后焦点返回原触发按钮。
- 移除未声明的 `pending-tts-model-name` 传参，使用组件现有真实 props 作为唯一合同。

### 4.4 账户与安全

- 新建薄视图 `AccountSecurityView.vue`，只负责页面标题/布局并复用 `PasswordManagement`。
- 新增受认证路由 `/account/security`；不新增 store、API 或表单实现。
- `PasswordManagement` 统一使用非 modal 保存按钮；管理员强制改密状态继续来自 auth store。
- 路由守卫与登录成功跳转统一改为 `/account/security`；只有该路由允许处于 `mustChangePassword` 状态的管理员停留，完成改密后恢复正常导航。
- 将 PasswordManagement 中“管理员密码”等仅适合强制改密场景的文案改为普通用户也成立的账户安全文案。

### 4.5 管理后台

- `AdminView` 的 `MenuKey`、组件映射和分区列表增加 `prompt-usage`。
- 复用 `PromptUsageMap` 作为普通管理分区，通过 `/admin?tab=prompt-usage` 深链。
- `PromptUsageMap` 的“打开提示词编辑器”改为切到 `tab=prompts`，不再先关闭全局弹窗。

## 5. 配置分层

### 基础能力

- 供应商名称、连接凭据、文本主模型、记忆检索模型。
- readiness 优先说明当前缺失步骤，不创造新的完成度模型。

### 高级能力

- TTS 默认模型、阶段路由、模型定价。
- 阶段路由未覆盖时显示“继承主模型”，仅显式覆盖产生视觉强调。
- 自定义供应商类型与 Base URL 使用原生 `<details>` 按需展开；API Key 仍属于连接必需项，不隐藏。

### 不删除的合同

- 供应商 capability、默认 chat/embedding/TTS、`tts_protocol`、定价字段和 stage/model_id。
- TTS voice/speed 继续由章节朗读控件拥有。

## 6. 状态与数据流

- 所有配置查询和 mutation 继续经过 `useModelBundle`、Vue Query 和现有 `api/llm.ts`。
- 页面分区唯一来源为 `route.query.tab`；非法值回落 `llm`。
- 内联编辑状态继续由 `PersonalModelRouting` 及现有 composables 持有，不提升到 Pinia。
- 管理分区唯一来源为 `route.query.tab`；提示词用量复用 `useAdminPromptsQuery` 缓存。

## 7. 可访问性与响应式

- 账户菜单仍使用原生 button、`aria-expanded`、`aria-controls` 和 Escape 焦点恢复。
- 设置分区保留 ARIA tabs 键盘合同；两组只是视觉/语义分组，不嵌套第二套 tab。
- 模型面板关闭后聚焦触发按钮；dirty 状态触发的确认 dialog 继续复用 `globalAlert`。
- 移动端页面由单一文档/内容滚动所有者负责；不再存在设置 modal 与 picker modal 两层滚动。
- 保持 44px 最小触控目标和 WCAG 2.1 AA 对比度。

## 8. 兼容性与迁移

- `/settings` 与已有 query 值保持兼容；旧书签继续工作。
- `/admin` 既有 tab 值保持兼容，只增加 `prompt-usage`。
- 后端、数据库、OpenAPI 和生成类型不变。
- `SettingsView.isModal`、`AdminView.isModal`、`PasswordManagement.isModal` 的调用方清零后删除对应兼容分支；不保留无消费者接口。
- 旧 `/admin?tab=password` 不是有效分区且没有可兼容页面；登录和守卫直接迁移到 `/account/security`。
- 未接入运行时的 `shellNavigation.ts` 不在本任务删除，避免把死代码清理混入用户侧重构。

## 9. 方案取舍

- 不做设置向导：现有 readiness + 分组足以表达首次路径，向导会引入重复状态。
- 不建通用 SettingsShell：当前只有两个薄页面，共享抽象没有第二个真实消费者。
- 不把所有确认改成内联：删除和放弃修改属于必要高风险确认。
- 不删除低频字段：已确认定价、TTS 与路由均有运行时消费者；只降低展示层级。

## 10. 回滚

- 改动按“路由入口 → 页面宿主 → 内联模型面板 → 分层样式”分段提交/验证。
- 若模型面板交互出现回归，可独立回退该组件重命名与模板变化，不影响 AppShell 页面化。
- 无数据迁移，整体回滚只涉及前端文件。
