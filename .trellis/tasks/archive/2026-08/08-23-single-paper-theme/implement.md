# 统一为单一暖纸浅色主题：实施计划

1. 固定单主题启动
   - 在 `frontend/index.html` 静态标记浅色主题。
   - 删除 `main.ts` 与 `AppShell.vue` 的主题解析、存储、监听、事件和切换入口。
   - 验证：定向静态测试 + 类型检查；确认顶栏其他按钮仍可用。

2. 收敛全局 token 与主题分支
   - 以现有浅色 token block 为唯一颜色来源，设置 `color-scheme: light`。
   - 先替换所有 `--md-night-*` 消费方，再删除夜色 token、暗色 token block 和暗色专用 CSS。
   - 验证：`rg` 确认没有项目自有夜色引用、暗色选择器或主题偏好逻辑。

3. 统一受影响界面
   - 首页 Hero：保留信息层级，改为暖纸表面和焦墨文字。
   - 登录/注册：保留表单和响应式双栏，移除夜色局部 token 重映射及仅为黑底服务的装饰。
   - 写作台：页底、顶栏、章节侧栏、工具带和助手面板改用纸色层级；保持现有布局、抽屉、滚动和工作流。
   - 验证：定向组件测试 + 桌面/移动端浏览器检查。

4. 同步合同
   - 更新 `DESIGN.md`、`.trellis/spec/frontend/component-guidelines.md` 和 `.trellis/spec/frontend/quality-guidelines.md` 中的主题规则。
   - 更新现有测试，不新建重复的主题测试套件。
   - 验证：相关 Vitest 与 E2E 合同与新规则一致。

5. 独立复核与质量门
   - 独立检查 diff，确认没有顺手重构、无孤儿导入/样式、无隐私或调试产物。
   - 执行前端 lint、类型检查、全量 Vitest 和 `git diff --check`。
   - 启动本地服务时，检查登录、首页、项目详情/章节和写作台，覆盖桌面与 390×844；运行可行的 axe 检查，最后关闭服务并清理临时凭据/会话。

## Risky Areas And Rollback Points

- `AppShell.vue` 同时拥有顶栏、抽屉和多个弹层；只删除主题相关符号与按钮，不改相邻交互。
- `WDSidebar.vue` 与 `WDAssistantPanel.vue` 夜色引用密集；采用可审查的小批量替换，每批后检查对比度和状态区分。
- 删除暗色 CSS 前先完成引用替换；如某表面回归，回退对应组件小批次，不恢复双主题架构。

## Validation Commands

```bash
cd frontend
npm run lint
npm run type-check
npm run test:unit
```

```bash
git diff --check
```
