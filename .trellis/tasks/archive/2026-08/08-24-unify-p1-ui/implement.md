# 实施计划

## Success Criteria

- 九个主页面在桌面与 Pixel 7 保持统一剧场提示本视觉，无用户可见 P1。
- 详情长内容、灵感长对话和写作长章节可滚动到末尾，无横向溢出或软键盘相关裁切。
- 删除已被最终层完整接管的遗留暖纸、宋楷、印章和纸影声明，最终 computed style 与清理前等价。
- 唯一主动作、设置健康摘要、跨设备恢复和任务回跳不退化。

## Execution

1. **建立当前运行时合同**
   - 复用 fixture server 和 Playwright 双视口，为九页增加聚焦 P1 E2E。
   - 断言最终色面/字体、横向溢出、关键动作与长内容滚动可达。
   - verify：新用例在产品代码未改前通过；真实失败项形成可复现测试。

2. **清理认证遗留视觉**
   - 删除 AuthIntro 已隐藏的纯装饰样式/无语义 DOM。
   - 删除 Login/Register 被认证最终层完整覆盖的背景、纹理、旧字体、印章和 panel 视觉属性。
   - verify：登录/注册 computed style、桌面/移动截图、axe、表单键盘和触控合同不变。

3. **清理应用页遗留视觉**
   - 按 `world-class.css` 的 workspace/inspiration/detail/writing/settings/admin 区段逐属性核对并删除完全失效规则。
   - 保留长文、描红、落墨、AI provenance、弹层和未被完整接管的布局/交互规则。
   - verify：每个页面批次运行聚焦 E2E；不以新增覆盖修补删除回归。

4. **修复真实复现的 P1**
   - 仅处理基线或长内容场景实际复现的主动作、滚动、裁切或配置阻断问题。
   - 优先修改共享滚动所有者或最终样式层，一处修复所有调用路径。
   - verify：对应失败测试转绿，并抽查相邻路由无回归。

5. **集中视觉复验**
   - 同批运行九页桌面与 Pixel 7，检查视觉、滚动、焦点、200% 缩放/低高度场景。
   - 集中修正一轮，最多再确认一轮；临时截图不入仓。
   - 完成后运行一次 Impeccable detector，不在清理过程中反复运行。

6. **独立质量门**
   - 独立复核 diff 是否只覆盖 PRD、是否误删长文例外、是否产生临时或隐私文件。
   - 运行聚焦 E2E、creation continuity、global modal accessibility、类型检查、单元测试、lint、生产构建和 bundle budget。
   - 检查调试服务、浏览器会话和临时输出均已关闭/清理。

## Validation Commands

```bash
cd frontend
npx playwright test e2e/ui-p1-regression.spec.ts --project=desktop-chromium --project=mobile-chromium
npx playwright test e2e/creation-continuity.spec.ts e2e/global-modal-accessibility.spec.ts --project=desktop-chromium --project=mobile-chromium
npm run type-check
npm run test:unit
npm run lint
npm run build
```

Impeccable detector 在产品改动完成后只运行一次：

```bash
node .agents/skills/impeccable/scripts/detect.mjs --json frontend/src
```

## Review Gates

- 删除前能指出最终层的等价覆盖选择器与属性。
- 不用关键词批量删除 serif/kai/shadow/gradient；每条都按运行时用途判断。
- 写作正文、描红、落墨和 AI provenance 例外不被通用无衬线规则吞掉。
- `world-class.css` 保持最后加载，认证样式保持路由级异步加载。
- 不改变稳定 class、ARIA 文案、1200 / 834 / 833 断点和业务路由。
- 若基线没有真实 P1，步骤 4 不产生产品行为改动。

## Rollback Points

- 新 E2E 合同可独立保留。
- 认证、应用页和真实 P1 修复分别作为独立回滚批次。
- 任一清理批次视觉不等价时恢复被删声明，不增加新的补丁覆盖层。
