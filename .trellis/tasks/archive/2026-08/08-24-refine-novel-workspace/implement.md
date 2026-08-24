# 实施计划：收敛优化小说项目库

## 1. 固化回归合同

- [x] 扩展 `uiAuditRegression.spec.ts`，断言标题均衡换行、创作快照移除、项目按钮降级、零章节状态文案与删除按钮中性色合同。
- [x] 保留已有加载状态、进度 ARIA、标题 44px 触控和账户菜单未提交改动。

验证：针对性 Vitest 在实现前失败、实现后通过。

## 2. 收敛左侧行动面

- [x] 在 `NovelWorkspace.vue` 删除 `workspace-hero__snapshot` 及仅被其消费的状态。
- [x] 保留今日目标内容，移除同权卡片视觉，收紧标题、目标与进度间距。
- [x] 在 `world-class.css` 使用原生均衡换行并略降标题字号上限。

验证：真实长标题无单字末行/横向溢出，主动作仍是唯一高饱和行动。

## 3. 降低档案列表噪声

- [x] 将 `ProjectCard` 创作按钮改为现有 outlined 变体。
- [x] 删除按钮默认中性，hover/focus 恢复错误色。
- [x] 零章节状态改为“蓝图已完成 · 正文未开始”。
- [x] 收紧档案头部和项目行留白，不改变连续列表拓扑。

验证：详情、继续、删除确认、进度语义与键盘焦点保持可用。

## 4. 响应式与质量门

- [x] 960px 以下取消固定 hero 最小高度。
- [x] 运行针对性 Vitest、`npm run type-check`、`npm run lint`。
- [x] 运行 `ui-p1-regression.spec.ts` 的桌面 Chromium 与 Pixel 7。
- [x] 一次性检查桌面/移动截图、无横向溢出、焦点、长标题和删除操作；必要修复后最多再确认一次。
- [x] 运行 `npm run build`，确认 CSS/JS 预算。
- [x] 独立复核最终 diff，确认无后端/API/路由变化，无范围外视觉清理。

## 验证结果（2026-08-24）

- 针对性 Vitest：`uiAuditRegression.spec.ts` 48/48 通过；全量 Vitest 50 个文件、380/380 通过。
- `npm run lint`、`npm run type-check`、`npm run build` 通过；JS/CSS hard budget 通过，入口 CSS gzip 25.33 KB 仍触发 24 KB 预警但低于 26 KB 上限。
- Playwright `ui-p1-regression.spec.ts` 在 desktop Chromium 与 Pixel 7 共 10/10 通过，覆盖 1440px、833px 与移动视口。
- 真实浏览器确认：833px hero 高约 526px，Pixel 7 高约 624px；长标题无单字末行且无横向溢出。
- 工作区 axe 定向扫描 0 violations；4 项 `color-mix()` 相关对比度需人工判定，运行色均已核对为高对比组合。
- Impeccable 定向检测 0 阻断；独立默认子代理复核未发现阻断项。
- Spec 判断：不更新 `.trellis/spec/`；本次未形成新接口或通用约定，最终覆盖层与选择器作用域规则已由现有前端组件规范覆盖，局部级联风险由新增回归测试固化。

## 风险与回滚

- `world-class.css` 是最终视觉覆盖层，选择器需保持工作台作用域，避免影响其他页面。
- 长标题依赖原生 `text-wrap: balance`，不支持时应安全退化且不横向溢出。
- 当前工作树已有账户菜单改动；提交时必须与本任务文件分组，不能误纳入或回退。
