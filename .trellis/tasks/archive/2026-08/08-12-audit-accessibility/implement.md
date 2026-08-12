# 实施计划

1. 补 `useDialogA11y` 和 `GlobalModalContainer` focused tests，再将容器接入现有 composable；
   核对所有消费方关闭路径。
2. 将 ChapterPipeline 节点改为列表内原生 button，保证 retry 控件不嵌套，并补 focused tests。
3. 让实际助手滚动容器可聚焦，扩大三个目标按钮 hit area，保持安全渲染链和布局不变。
4. 加入固定 lockfile 的 `@axe-core/playwright` dev dependency，新增 U1 Playwright 场景。
5. 运行 focused unit tests、lint、type-check、unit、build 和完整 E2E；使用浏览器同时检查
   desktop/mobile 与浅色/深色主题。
6. 运行 Impeccable detector 一次，独立复核语义、焦点、多实例 lock、触控尺寸和回归范围。

验证命令：

```bash
cd frontend
npm run lint
npm run type-check
npm run test:unit
npm run build
npm run test:e2e
```

回滚点：U1 作为单独提交；若浏览器验收失败，停留在本任务内修复，不混入 D1/T1。

