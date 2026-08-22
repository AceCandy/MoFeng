# 前端 bundle 软预警收敛设计

## 边界

只处理两个已量化来源：TipTap 未使用扩展进入生产包，以及自有全局 CSS 的不可达旧规则。预算脚本、阈值、manifest 统计、路由结构、界面行为和视觉设计保持不变。

## JS 方案

`MofengEditor` 只需要 TipTap 的 Document、Paragraph、Text、HardBreak、UndoRedo 与项目自定义 MiaohongMark。移除 `@tiptap/starter-kit`，改为直接依赖并导入同版本的五个扩展包。

这不是拆包：未使用扩展不再进入模块图。相同 Vite 配置下的内存替换实验结果：

- JS 总 gzip：580.36 KB → 556.53 KB
- `tiptap-editor`：41.16 KB → 27.70 KB
- 最大 `vendor`：109.31 KB → 99.04 KB

## CSS 方案

对 `src/assets/styles/` 的自有选择器做源码引用核验，只删除零运行时引用的规则。保留 Naive UI 的运行时内部选择器，即使它们不以字面量出现在 Vue 源码中。

删除范围包括旧 Material list/badge/switch/checkbox、未使用 FAB/card/navigation/elevation/chip 变体、已不渲染的 AppShell bottom tabs，以及仅供已删除 progress 变体使用的 keyframes。同步删除 `responsive.spec.ts` 中只断言 bottom-tab CSS 文本存在的失效测试。

临时副本实验结果：最大 CSS gzip 25.14 KB → 23.89 KB，CSS 总 gzip 83.66 KB → 82.41 KB。

## 兼容与回滚

- 编辑器 schema 仍为 doc → paragraph → text/hardBreak，并保留 UndoRedo 与 MiaohongMark。
- 不改变任何 Vue template、主题 token、断点或可访问性属性。
- 若编辑器测试、浏览器验证或最终预算任一失败，分别回滚 TipTap 或 CSS 批次；不调整预算兜底。

## 验证边界

构建前后均以 `dist/.vite/manifest.json` 和预算脚本的 gzip level 9 结果为准。浏览器只验证受影响表面：写作台编辑弹窗、AppShell 桌面/移动宽度、亮/暗主题。
