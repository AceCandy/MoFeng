# Design — 章节朗读喇叭按钮交互改造与浏览器朗读首字修复

## 1. 改动范围

| 文件 | 改动 |
|---|---|
| `frontend/src/components/writing-desk/WDWorkspace.vue` | 模板：朗读入口合并为单个图标按钮，移除独立「停止」按钮；脚本：hover-reset 计时器、点击分流、图标 computed；样式：图标按钮尺寸/状态视觉 |
| `frontend/src/composables/useChapterReader.ts` | `playBrowserSegments`：每段 `speak` 前清队列 + 推迟一帧，修复首字被吞 |
| `frontend/src/composables/__tests__/useChapterReader.spec.ts` | 适配 cancel/延时调用，必要时 `waitFor` |

不动：`api/tts.ts`、模型 TTS 合成路径、`splitSpeechText` 分段逻辑、`PersonalModelRouting.vue`。

## 2. 按钮交互设计

### 2.1 状态 → 图标 → 点击行为

| `readerStatus` | `hoverResetReady` | 图标 | aria-label | 点击 |
|---|---|---|---|---|
| idle | — | 喇叭 | 朗读 | `start` |
| generating | — | 加载(旋转) | 停止朗读 | `stop` |
| playing | false | 暂停 | 暂停 | `pause` |
| playing | true | 重置 | 从头朗读 | `stop` + `start` |
| paused | false | 继续 | 继续 | `resume` |
| paused | true | 重置 | 从头朗读 | `stop` + `start` |

`hoverResetReady` 仅在 `playing`/`paused` 下可能为 true；其余状态强制 false。

### 2.2 图标 computed

```ts
type ReaderIcon = 'speaker' | 'loading' | 'pause' | 'play' | 'reset'
const readerIcon = computed<ReaderIcon>(() => {
  if (hoverResetReady.value && (readerStatus.value === 'playing' || readerStatus.value === 'paused')) {
    return 'reset'
  }
  if (readerStatus.value === 'generating') return 'loading'
  if (readerStatus.value === 'playing') return 'pause'
  if (readerStatus.value === 'paused') return 'play'
  return 'speaker'
})
```

模板用 `v-if` 分支渲染对应内联 SVG（沿用项目约定：`viewBox="0 0 24 24"`、`fill="none"`、`stroke="currentColor"`、`aria-hidden="true"`）。`loading` 图标靠 CSS `animation: spin` 旋转。

### 2.3 hover 计时器

```ts
const RESET_DELAY = 3000
const hoverResetReady = ref(false)
let hoverTimer: ReturnType<typeof setTimeout> | null = null

const clearHoverTimer = () => {
  if (hoverTimer) { clearTimeout(hoverTimer); hoverTimer = null }
  hoverResetReady.value = false
}
const onReaderEnter = () => {
  if (readerStatus.value !== 'playing' && readerStatus.value !== 'paused') return
  hoverTimer = setTimeout(() => { hoverResetReady.value = true }, RESET_DELAY)
}
const onReaderLeave = clearHoverTimer
```

- `watch(readerStatus)`：状态离开 `playing`/`paused` 时 `clearHoverTimer()`（重置后回到 generating，计时必须清掉，避免误触）。
- `onBeforeUnmount`：`clearHoverTimer()`。
- 按钮模板：`@mouseenter="onReaderEnter" @mouseleave="onReaderLeave"`。

### 2.4 点击分流

```ts
const handleReaderToggle = () => {
  if (hoverResetReady.value) {
    clearHoverTimer()
    chapterReader.stop()
    void chapterReader.start(chapterTitle, selectedChapterResolvedContent.value)
    return
  }
  // 原有 idle/generating/playing/paused 分支不变
}
```

点击重置后立即 `clearHoverTimer()`（status 即将变 generating，重置态不应残留）。`stop()` 内部 `runId += 1` 保证旧播放队列被作废，`start()` 重新分段，不会并发。

## 3. 首字被吞修复

`useChapterReader.ts:122-144` `playBrowserSegments`，循环体改为：

```ts
for (let index = startIndex; index < segments.length && currentRun === runId; index += 1) {
  status.value = 'playing'
  // 清掉上一段在 speechSynthesis 队列里的残留，并让出入队错开一帧，
  // 规避 Chrome 连续 speak 裁掉每段首字的问题。
  speech.cancel()
  await new Promise<void>((resolve) => setTimeout(resolve, 0))
  if (currentRun !== runId) return
  await new Promise<void>((resolve, reject) => {
    resolveCurrentPlayback = resolve
    const utterance = new SpeechSynthesisUtterance(segments[index])
    utterance.onend = () => resolve()
    utterance.onerror = () => reject(new Error('浏览器朗读失败'))
    speech.speak(utterance)
  })
  resolveCurrentPlayback = null
}
```

### 3.1 时序安全性

- `speech.cancel()` 在上一段 `onend` 已 resolve 之后调用，此时无 active utterance，不会触发任何 `onerror`（`onerror` 仅在 speak 中的 utterance 被 cancel 时触发，而上一段已 ended）。
- 第一段：`start()` 里 `stop()` 已 `speechSynthesis.cancel()` 一次，此处再 cancel 为幂等空操作。
- `setTimeout(0)` 让出当前宏任务，给 speechSynthesis 状态机完成上一轮收尾再入队。
- `currentRun !== runId` 在延时后复检，保证 stop 期间不再入队。

### 3.2 为何不动模型 TTS 路径

`playModelSegments` 用 `<audio>` 元素播 Blob，不经过 `speechSynthesis`，无此 bug；且 AC 要求该路径行为不变，故不触碰。

## 4. 按钮样式

朗读按钮保留 `writing-workspace__tool-btn--ghost` 容器（与复制/导出同高 32px、方角、古籍风），内容由文字改为 SVG。新增修饰类 `writing-workspace__tool-btn--icon`：

- `padding-inline` 收为方形（约 32×32），`display: inline-flex; align-items: center; justify-content: center`。
- SVG `width/height: 18px`，`color: var(--md-on-surface-variant)`，hover 时随 `tool-btn` 既有配色变化。
- `loading` 图标 `animation: spin 1s linear infinite`，`@keyframes spin` 新增。
- 重置态可加轻微强调色（`color: var(--md-primary-dark)`）提示状态切换，但不引入新交互。

## 5. 测试影响

- `useChapterReader.spec.ts`：
  - `browserSpeech.cancel` 已是 `vi.fn()`，新增调用不破坏断言。
  - `setTimeout(0)` 不改变 `await reader.start(...)` 后 `browserSpeech.spoken` 的最终内容（start 仍 await 全部段落完成），现有 `toEqual` 断言应仍通过；若时序敏感处失败，用 `vi.waitFor` 包裹。
  - 新增一个用例：断言每段 speak 前都调用了 `speechSynthesis.cancel()`（验证修复存在）。
- `WDWorkspace` 朗读入口测试（`wdWorkspaceLockedChapter.spec.ts` 已在 git status 中修改）：若该 spec 断言了「停止」按钮文字，需改为断言图标按钮的 aria-label。实现时按实际断言调整。

## 6. 风险与回滚

- **首字修复无效**：若 `cancel + setTimeout(0)` 仍不能消除听感问题，备选加大延时到 ~120ms 或改 `requestAnimationFrame`；属 composable 单点改动，回滚成本低。
- **hover-reset 误触**：3s 阈值可能偏短/偏长，`RESET_DELAY` 抽常量便于调整；若用户反馈暂停时常被误转重置，调大阈值。
- **图标视觉不协调**：保留 tool-btn 容器而非换 md-icon-btn，确保与相邻文字按钮高度一致；若仍突兀，回退为「图标 + 短文字」。
- 改动集中在 2 文件 + 测试，`git revert` 单提交即可回滚。
