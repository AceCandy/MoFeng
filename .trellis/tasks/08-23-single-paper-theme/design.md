# 统一为单一暖纸浅色主题：技术设计

## Boundaries

改动限定在前端主题启动、共享导航、受夜色规则影响的页面/组件、全局样式、视觉合同测试与设计文档。不改变路由、数据流或业务组件边界。

## Theme Bootstrap

- 在 `frontend/index.html` 的 `<html>` 上静态设置 `data-theme="light"`。
- 从 `frontend/src/main.ts` 删除 `ThemePreference`、存储键、解析函数、`matchMedia` 监听与 `setupTheme()` 调用。
- 从 `AppShell.vue` 删除主题状态/切换/同步逻辑、按钮与系统主题监听；保留其他 mounted/unmounted 清理。
- 旧 localStorage 值成为无害的未读取数据，不增加一次性迁移代码。

## Style Convergence

所有替换复用现有 token：

| 夜色职责 | 暖纸替代 |
| --- | --- |
| 页面大底 `night-bg*` | `--md-background` / `--md-surface-dim` |
| 侧栏与工具带 `night-surface*` | `--md-surface-container-low` / `--md-surface-container` |
| 夜色正文/辅文 | `--md-on-surface` / `--md-on-surface-variant` |
| 夜色发线 | `--md-outline-variant` / `--md-outline` |
| 夜色朱砂 | `--md-miaohong` / `--md-miaohong-strong` / `--md-btn-seal-text` |
| 夜色深影 | `--md-elevation-paper-1` / `--md-elevation-paper-2` |

页面处理：

1. 首页保留 Hero 结构、目标卡、进度和骑缝签，将背景、文字、进度和装饰改为纸色层级；删除仅在黑底上成立的暖光晕。
2. 登录/注册保留双栏与表单纸卡，页底和 `AuthIntro` 改用标准纸色 token；删除 `auth-night.css` 的局部浅色重映射，需要的认证页公共布局样式归入现有认证样式文件。
3. 写作台保留三栏/抽屉布局和稿纸层级，将页底、项目顶栏、章节侧栏、主工具带与助手面板换成可区分的纸色层级，不改尺寸和交互。
4. 删除 `tokens.css` 的 `--md-night-*` 和暗色 token block；删除各全局/局部 `[data-theme='dark']` 覆盖，保留浅色基础规则。

## Compatibility And Accessibility

- 保留 `data-theme="light"` 以继续命中现有浅色选择器，避免一次扩大到所有样式选择器。
- 根节点明确 `color-scheme: light`，保证原生表单控件与单主题一致。
- 不修改 DOM 布局和业务事件；删除主题按钮后检查顶栏宽度、焦点顺序与辅助名称。
- 纸色上的文字、边框、状态和主操作继续以 WCAG 2.1 AA 为底线；不以阴影或颜色作为唯一状态信号。

## Tests And Contracts

- 调整 `global-modal-accessibility.spec.ts` 为单一浅色环境，保留弹层无障碍覆盖。
- 更新 `uiAuditRegression.spec.ts`、`readGlobalCss.spec.ts` 等静态合同：断言单主题入口、无夜色 token 引用、无暗色选择器，并检查浅色对比度。
- 更新 `DESIGN.md` 的夜色章节与 `.trellis/spec/frontend` 中的主题合同，与代码同步提交。

## Rollback

改动是纯前端样式/启动收敛，不涉及数据迁移。回滚时整体回退该任务提交即可；旧本地存储值从未被删除，不影响旧版恢复。
