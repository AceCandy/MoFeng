# Implement — 章节朗读喇叭按钮交互改造与浏览器朗读首字修复

## 执行清单

### A. 浏览器朗读首字修复（先做，独立可验证）

1. `useChapterReader.ts` `playBrowserSegments`：循环体每段 `speak` 前加 `speech.cancel()` + `await setTimeout(0)` + `currentRun` 复检。 → 验证：`useChapterReader.spec.ts` 现有 4 用例通过。
2. `useChapterReader.spec.ts` 新增用例：未配置 TTS 时连续多段，断言 `browserSpeech.cancel` 在每段 `speak` 前都被调用（验证修复存在，回归防护）。 → 验证：新用例通过。
3. `cd frontend && npx vitest run src/composables/__tests__/useChapterReader.spec.ts` 全绿。

### B. 朗读按钮交互改造（WDWorkspace.vue）

4. 脚本：新增 `hoverResetReady` ref、`hoverTimer`、`clearHoverTimer`、`onReaderEnter`、`onReaderLeave`、`RESET_DELAY=3000`、`readerIcon` computed、`readerAriaLabel` computed。 → 验证：无 TS 报错。
5. 脚本：`watch(readerStatus)` 在离开 playing/paused 时 `clearHoverTimer()`；`onBeforeUnmount` 追加 `clearHoverTimer()`（合并到已有清理处，避免重复挂卸载钩子）。
6. 脚本：`handleReaderToggle` 首部加分流：`hoverResetReady` 为 true 时 `clearHoverTimer()` + `stop()` + `start()`，提前 return。
7. 模板：移除独立「停止」按钮（L53-61）；主按钮内容由 `{{ readerPrimaryLabel }}` 改为按 `readerIcon` 分支渲染的内联 SVG（speaker/loading/pause/play/reset），`@mouseenter`/`@mouseleave` 接入，`:aria-label="readerAriaLabel"`。
8. 样式：新增 `.writing-workspace__tool-btn--icon`（方形、flex 居中、SVG 18px）与 `@keyframes spin`；重置态 `color` 强调。保留 ghost 容器基样。

### C. 验证

9. `cd frontend && npx vue-tsc --noEmit`（用绝对路径 `-p` 或先 cd）→ 0 错误。
10. `cd frontend && npx vitest run`（含 wdWorkspaceLockedChapter.spec.ts）→ 全绿；若 locked chapter spec 断言了「停止」文字按钮，改为断言 aria-label。
11. 人工听感验证（交付用户）：未配置 TTS 时朗读多段章节，确认每段首字不再被吞；播放中悬停 3s 出现重置图标，点击从头朗读。

## 验证命令

```bash
cd /vol1/1000/ssd/workai/MoFeng/frontend
npx vitest run src/composables/__tests__/useChapterReader.spec.ts
npx vitest run src/components/__tests__/wdWorkspaceLockedChapter.spec.ts
npx vue-tsc --noEmit
```

## 回滚点

- A 与 B 互相独立：A 是 composable 单点修复，B 是组件 UI。可分别提交。
- 若听感修复无效，仅回滚 A，B 的按钮改造不受影响。
