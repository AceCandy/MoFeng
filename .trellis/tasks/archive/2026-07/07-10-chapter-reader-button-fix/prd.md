# 章节朗读喇叭按钮交互改造与浏览器朗读首字修复

## Goal

把已完成章节工具栏的朗读入口从「主文字按钮 + 独立停止按钮」改造为单个喇叭图标按钮：播放/暂停/继续/停止状态在同一图标上变化，悬停超过 3 秒切换为「重置」图标、点击即可从头朗读；并修复浏览器原生朗读每段第一个字被吞的问题。

## Background

- 朗读入口现状位于 `WDWorkspace.vue:45-61`：一个 `md-btn-text` 主按钮显示 `readerPrimaryLabel`（朗读/暂停/继续/停止），另在 `playing`/`paused` 时显示一个独立「停止」按钮。
- 状态判定与切换在 `WDWorkspace.vue:875-896`（`readerPrimaryLabel`、`handleReaderToggle`），底层状态机来自 `useChapterReader`（`status: 'idle' | 'generating' | 'playing' | 'paused'`）。
- 浏览器回退朗读在 `useChapterReader.ts:122-144` 的 `playBrowserSegments`：循环里上一段 `onend` 一触发就紧接着 `speech.speak(下一段)`，相邻 utterance 之间没有 `speechSynthesis.cancel()` 清队列、也不留收尾时间，Chrome 的 `speechSynthesis` 在这种连续入队下会裁掉每段开头首帧——表现为「每段第一个字听不清」。
- 可朗读正文已由 `selectedChapterResolvedContent` 统一处理（标题 + 正文顺序由 `splitSpeechText` 保证）。
- 用户当前实际走的是浏览器回退路径（未配置默认 TTS 模型）。

## Requirements

- 工具栏朗读入口合并为单个图标按钮，移除独立「停止」文字按钮。
- 图标随朗读状态变化：`idle` 喇叭、`generating` 加载、`playing` 暂停符、`paused` 继续符；点击行为与现有一致（开始/中止/暂停/继续）。
- 在 `playing` 或 `paused` 状态下，鼠标悬停在按钮上超过 3 秒，按钮切换为「重置」图标；点击重置 = 停止当前朗读并从头重新朗读（标题 + 正文）。
- 悬停计时：`mouseenter` 启动 3 秒计时；`mouseleave`、状态变化、或组件卸载时清除计时，恢复当前状态图标。
- `idle` 与 `generating` 状态不启用悬停重置（重置无意义；`generating` 点击仍为中止）。
- 重置后状态正确进入新一轮朗读，不与旧朗读并发。
- 修复浏览器回退朗读每段首字被吞：在每段 `speak` 前清空 `speechSynthesis` 队列残留并让入队推迟一帧，避免首帧被裁。
- 修复不得影响已配置默认 TTS 模型的服务端合成与播放路径，也不得影响暂停/继续/停止既有行为。
- 现有 `useChapterReader` 与朗读入口相关测试同步更新并通过。

## Acceptance Criteria

- [ ] 已完成章节工具栏的朗读入口为单个喇叭图标按钮，不再有独立「停止」按钮。
- [ ] 图标随 `idle`/`generating`/`playing`/`paused` 正确变化，点击分别触发 开始/中止/暂停/继续。
- [ ] `playing` 或 `paused` 时悬停 ≥3 秒，按钮变为重置图标且 `aria-label` 更新为「从头朗读」；点击后从章节标题开始重新朗读。
- [ ] 悬停不足 3 秒即移开，按钮恢复原状态图标且不触发重置。
- [ ] 重置后不产生并发朗读，状态机回到 `generating` → `playing`。
- [ ] 浏览器回退朗读每段首字不再被吞（人工听感验证，记录验证结果）。
- [ ] 已配置默认 TTS 模型时，服务端合成与播放路径行为不变。
- [ ] `useChapterReader`、`WDWorkspace` 相关单元测试通过；`vue-tsc` 0 类型错误。

## Out Of Scope

- 朗读进度条、段落高亮、语速即时调节 UI。
- 跨章节播放列表与音频持久化下载。
- 服务端 TTS 音频首字问题（本次仅修浏览器 `speechSynthesis` 回退路径）。
- 朗读按钮的可访问性大改（仅保持/更新 `aria-label`，不引入新 ARIA 模式）。
