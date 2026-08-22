# 实施计划

1. 记录干净基线
   - `npm run build-only && npm run build:budget`
   - 保存 JS 总量、最大 CSS 与 Top 8 gzip 数据。
2. 最小化 TipTap 扩展
   - 更新 `MofengEditor.vue` 的扩展导入和注册。
   - 用 npm 更新直接依赖与 lock，保持所有 TipTap 包为 3.29.2，不升级其他依赖。
   - 运行编辑器聚焦测试、type-check，并重建确认 JS 总 gzip ≤560 KB。
3. 删除不可达自有 CSS
   - 只删除研究中确认零运行时引用的规则与专属 keyframes。
   - 删除 bottom-tab 的同义反复 CSS 文本断言；不动 Naive UI 内部选择器。
   - 重建确认最大 CSS gzip ≤24 KB。
4. 全量质量门禁
   - `npm run type-check`
   - `npm run test:unit`
   - `npm run lint`
   - `npm run build`
   - 核对 manifest 统计范围和预算阈值 diff 未变化。
5. 浏览器与独立复核
   - 验证写作台编辑、单换行、撤销/重做、描红/落墨、只读。
   - 验证 AppShell 桌面/移动、亮/暗主题；结束前关闭服务。
   - 运行 Impeccable detector、Trellis validate、`git diff --check` 和独立只读复核。

## 风险与回滚点

- TipTap 扩展缺失会表现为 schema、键盘或历史行为回归；JS 批次独立回滚。
- CSS 字面量扫描不能判断第三方运行时类，因此第三方选择器明确排除；自有 CSS 批次独立回滚。
- 软线余量有限，最终构建是唯一验收值；不通过时停止并回到规划，不改阈值。

## 验证结果

- 相同 Vite/manifest/gzip 链路：JS 总 gzip `580.36 KB → 556.55 KB`，最大 CSS gzip
  `25.14 KB → 23.63 KB`；预算脚本无软预警。
- `npm run type-check`、348 个完整单测、`npm run lint`、`npm run build` 均通过。
- 浏览器验证覆盖 AppShell 的桌面亮色与移动暗色，以及编辑器段落、单换行、描红/落墨、
  撤销/重做和只读；隔离网络桩、浏览器与开发服务均已关闭。
- 独立复核确认 lockfile 无版本漂移，删除的自有 CSS 选择器无运行时引用。
