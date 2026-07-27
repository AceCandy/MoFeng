# WritingDesk Statechart Implementation Plan

## Steps

- [ ] 盘点 WritingDesk/composables 的 lifecycle refs、watchers、commands 和 query effects，建立 transition inventory。
- [ ] 锁定兼容的 XState/Vue binding 版本，先实现 pure machine、types、guards 和 model tests。
- [ ] 建立 generated contract adapter、SSE decoder actor、snapshot query actor 和 mutation actors。
- [ ] 迁移 start/generate/review/select/finalize/projection/retry/cancel/reconnect。
- [ ] 将 component controls 改为 machine selectors/allowed commands，保留展示类 composables。
- [ ] shadow compare 后 feature flag cutover，删除 lifecycle 双状态源和本任务产生的 orphan。
- [ ] 运行独立 UI/可访问性/响应式复核；本任务不做无关视觉重设计。

## Validation

```bash
cd frontend
npm run test:unit -- src/**/__tests__/*WritingDesk* src/**/__tests__/*statechart*
npm run type-check
npm run lint
```

增加浏览器集成：刷新 waiting selection、SSE disconnect/replay、double click、stale event、projection retry。调试服务若启动，验证完成后必须关闭。

## Rollback

- feature flag 切 legacy UI，statechart actor 停止订阅/提交 command。
- backend run 和 cursor 不回滚；legacy UI 使用兼容 snapshot/status。
- legacy composables 只在一个稳定发布窗口后删除。
