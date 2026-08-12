# 通用弹窗与写作台可访问性

## Goal

完成增量审计 U1：让通用弹窗、章节生成进度和写作台助手在键盘、触控与读屏场景下
满足 WCAG 2.1 AA，同时保持现有视觉身份、业务事件和响应式布局不变。

## Background

- `GlobalModalContainer` 当前把 dialog role 放在遮罩层，标题未关联，手写 ESC 与 body
  overflow，缺少初始焦点、焦点陷阱和关闭后恢复。
- `ChapterPipeline` 以 `li role=button` 模拟按钮，waiting 节点仍可触发点击。
- `WDAssistantPanel` 的独立滚动区域不可通过键盘聚焦。
- 任务日志、AI 助手和口令显示按钮缺少统一的 44x44 CSS px 自动化验收。
- 项目当前未安装 `@axe-core/playwright`，需要作为开发依赖加入以执行设计指定的浏览器
  无障碍扫描，不以自制规则替代。

## Requirements

### U1.1 通用弹窗

- dialog role 移到 modal box，使用 `useId()` 关联标题，保留 overlay 的 `click.self`。
- 复用现有 `useDialogA11y` 统一初始焦点、正反向 Tab 环、ESC、焦点恢复和引用计数 body
  scroll lock；删除组件内重复的 document/body 管理。
- `hideCloseButton` 默认改为 `false`；只有已有等价可见关闭命令的调用方才可显式隐藏。
- 关闭按钮有明确 accessible name；现有 `close` emit、slot、宽度和视觉结构保持兼容。

### U1.2 写作台交互

- `ChapterPipeline` 保留 `ol > li`，可选择节点内部使用原生 `button type=button`；waiting
  节点 disabled 且不能发出 `select`，当前节点继续暴露 `aria-current="step"`。
- 保持 Tooltip、节点状态、重试入口和 `select(key, index)` 事件参数不变。
- `WDAssistantPanel` 的实际滚动容器可通过键盘聚焦，并保留
  `marked -> DOMPurify.sanitize -> v-html` 安全链。
- 任务日志、AI 助手和登录/注册口令显示按钮的可交互尺寸不小于 44x44 CSS px，不改变
  图标大小和布局轨道。

### U1.3 自动化验收

- 增加 `useDialogA11y` 和 `GlobalModalContainer` focused tests，覆盖初始焦点、Tab 环、ESC、
  焦点恢复、多实例 body lock、role/name、默认关闭按钮和 close emit。
- 增加 `ChapterPipeline` focused tests，覆盖可选节点键盘选择、waiting 节点不可选择和
  `aria-current`。
- 使用 `@axe-core/playwright` 覆盖任务日志 dialog 的焦点生命周期，以及 desktop/mobile
  登录页、写作台和任务日志的 axe 扫描；断言三个目标按钮尺寸不小于 44x44。
- 浏览器验收覆盖浅色/深色主题无横向溢出；pipeline 普通文本对比度至少 4.5:1。

## Out Of Scope

- 不新增全局 modal manager，不支持产品当前不存在的嵌套 modal 工作流。
- 不重做视觉风格、文案、业务状态或写作台布局。
- 不修改 Markdown 渲染、安全清洗、API 或后端。
- 不修复 U1 清单之外的全站无障碍问题。

## Acceptance Criteria

- [ ] Global modal 具有可访问名称，打开后焦点进入弹窗，Tab/Shift+Tab 不逃逸，ESC 或关闭
  按钮关闭后焦点回到触发元素，多实例关闭不会提前解除 body scroll lock。
- [ ] 所有 `GlobalModalContainer` 消费方保留关闭路径；默认关闭按钮可见且 accessible name
  明确。
- [ ] ChapterPipeline 非 waiting 节点可用原生键盘行为选择，waiting 节点不会发出 select，
  当前节点保留 `aria-current="step"`。
- [ ] AI 助手滚动区域可聚焦，HTML 仍只渲染 DOMPurify 清洗后的 marked 输出。
- [ ] 三个目标按钮在 desktop/mobile 均不小于 44x44 CSS px。
- [ ] 指定页面和弹窗在 desktop/mobile、浅色/深色主题通过 axe，未出现横向溢出，pipeline
  普通文本对比度不低于 4.5:1。
- [ ] U1 focused unit/E2E、前端 lint、type-check、unit、build 与完整 Playwright 全部通过。

