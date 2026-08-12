# 技术设计

## 1. 边界

本任务只修改现有通用 modal、写作台进度/助手、三个触控目标及其测试。复用现有
`useDialogA11y`、CSS tokens、Vitest 和 Playwright，不新增 UI 基础设施。

## 2. 通用弹窗契约

`GlobalModalContainer` 挂载期间以 `active=ref(true)` 调用 `useDialogA11y`：

```text
trigger focus
  -> modal mounts
  -> focus explicit close button, otherwise first focusable, otherwise dialog box
  -> Tab / Shift+Tab stay inside dialog
  -> close / Escape emits close
  -> parent unmounts modal
  -> focus returns to trigger; body lock ref-count decrements
```

`role=dialog`、`aria-modal=true`、`aria-labelledby=<useId()>` 和 `tabindex=-1` 都属于 box；
overlay 仅处理遮罩点击。默认关闭按钮作为优先初始焦点。显式隐藏关闭按钮的调用方必须
已有可见等价命令，否则保持默认显示。

## 3. 写作台语义

- `ol > li` 保持列表层级；节点交互放入真实 button。waiting 仍渲染 button，但 disabled，
  从而不需要手写 Enter/Space 事件且不能触发 select。
- 失败节点的 retry button 继续是独立命令；外层节点 button 与 retry 不得形成嵌套按钮。
  当 retry 出现时，节点内容与 retry 作为同一 `li` 下的并列控件。
- `WDAssistantPanel` 将 `tabindex=0` 放在真正具有 `overflow-y:auto` 的 `.wd-ai__panel`，而非
  不滚动的 aside。

## 4. 触控与浏览器验收

只扩大目标按钮 hit area，不放大图标。使用既有组件选择器断言任务日志、AI 助手和口令
显示按钮的 bounding box。新增 `@axe-core/playwright` 仅作为 dev dependency；不在生产
bundle 中引入代码。

浏览器验收复用现有 fixture/登录路径，新增一个聚焦 U1 的 spec。axe 扫描限制在登录页、
写作台和任务日志 dialog，避免把本任务外的全站历史问题误纳入阻断范围。

## 5. 兼容与回滚

- props、slots、emits 和节点选择参数不变。
- 视觉仅可能出现默认关闭按钮和扩大的 hit area；颜色、排版、动画和布局保持既有 tokens。
- 可按单一 U1 提交回滚；没有数据、API 或数据库迁移。

