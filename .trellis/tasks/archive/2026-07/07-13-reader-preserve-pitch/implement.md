# 执行计划

## 改动文件

- `frontend/src/composables/useChapterReader.ts`（主改）
- `frontend/src/composables/__tests__/useChapterReader.spec.ts`（测试适配 + 新增兜底用例）

## 前置基线

改动前先确认现有测试绿，作为回归基线：
```bash
cd frontend && npx vitest run useChapterReader
```

## 步骤

### 1. 抽出 Web Audio 播放为内部函数 `playWithWebAudio(blob, currentRun)`

把现有 `playAudio` 里的 `decodeAudioData` + `createBufferSource` + 空音频检测（`elapsed < MIN_VALID_AUDIO_SECONDS`）逻辑整体搬入。`startOffset` / `startedAt` / `getElapsed` / `stopBufferSource` 保留，仅供该兜底路径使用。

> **验证**：搬迁后现有 Web Audio 相关测试（prefetch / pause-resume / 空音频兜底）在切到兜底路径时仍绿。

### 2. 新增 `<audio>` 主路径 `playWithAudioElement(blob, currentRun)`

- 懒创建单个模块级 `audioEl: HTMLAudioElement | null`；每段 `revokeObjectURL` 旧 url 后设 `audioEl.src = URL.createObjectURL(blob)`
- `audioEl.preservesPitch = true`（兼容 `mozPreservesPitch` / `webkitPreservesPitch` 前缀）
- `audioEl.playbackRate = rate.value`
- 用 `onerror` / `onended` / `oncanplay` 赋值（自动覆盖，避免累积 listener）；`error` → reject 一个标记错误（`AudioDecodeError`），`ended` → resolve
- `audio.play()` 返回 promise，catch autoplay-block（`resume()` AudioContext 思路不适用，`<audio>` 静音策略下可直接 play）
- 返回 `Promise<void>`，与 `playWithWebAudio` 同形

> **验证**：单测 mock `HTMLAudioElement`，断言 `src` / `playbackRate` / `preservesPitch` 正确设置。

### 3. 重写 `playAudio(blob, currentRun)`：主 + 兜底编排

```ts
try {
  activeBackend = 'audio'
  await playWithAudioElement(blob, currentRun)
} catch (error) {
  if (currentRun !== runId) return
  if (error instanceof AudioDecodeError) {
    activeBackend = 'webaudio'
    await playWithWebAudio(blob, currentRun)   // 兜底；再失败向上抛
  } else {
    throw error
  }
}
```

`activeBackend: 'audio' | 'webaudio' | null` 是新增的运行时标记。

> **验证**：单测覆盖「`<audio>` error → Web Audio 兜底成功」「Web Audio 也失败 → 向上抛由 `playModelSegments` catch 切浏览器」。

### 4. 暂停 / 续播按 `activeBackend` 分派（**最易出 bug，重点复核**）

- `audio`：`audioEl.pause()` / `audioEl.play()`，`currentTime` 自动记忆，无需手动 offset
- `webaudio`：沿用现有 `startOffset = getElapsed()` → `stopBufferSource()`；续播 `source.start(0, startOffset)`
- `pause()` / `resume()` 开头判断 `activeBackend` 分派；浏览器路径（`speechSynthesis`）分支保留不变

> **验证**：单测两条路径分别测 pause→resume→stop，续播位置正确。

### 5. 试听 `previewModelVoice` 切 `<audio>`

复用主路径的 `<audio>` 元素或单独一个 `previewEl`（倾向单独，避免与主播放状态互相干扰）。无兜底，`error` → `notify('模型试听失败。', 'error')`（现有文案不变）。`stopPreview()` 清理。

> **验证**：现有 `previewVoice` 相关测试适配（断言 `<audio>` 而非 bufferSource）。

### 6. 清理：`stop` / `releasePlayback` / `onBeforeUnmount`

- `releasePlayback()` 增加：`audioEl` 存在则 `pause()` + `revokeObjectURL(currentObjectUrl)` + `audioEl.src = ''` + `audioEl = null`
- `onBeforeUnmount(stop)` 链路不变，靠 `stop` 触发清理

> **验证**：单测验卸载后无残留 `<audio>` 在播放、objectURL 已 revoke。

### 7. 测试基础设施扩展

- 新增 `FakeAudioElement`（mock `HTMLAudioElement`：`play` / `pause` / `src` / `playbackRate` / `preservesPitch` / `onerror` / `onended` / `currentTime` / `duration`）
- 保留 `FakeBufferSource` / `FakeAudioContext`（兜底路径用）
- 适配现有测试主路径断言：`vi.waitFor` 等 `audioEl.play()` 调用而非 `FakeBufferSource.instances`
- 改造受影响用例：
  - `prefetches ... pause resume stop` → 主路径走 audio
  - `falls back ... empty audio` → 改为 `<audio>` `error` 触发兜底（或保留 webaudio 空音频检测用例作为兜底路径覆盖）
  - `continues from failed model segment` → 不变（synthesize reject 走浏览器）
- 新增用例：`<audio>` error → Web Audio 兜底成功

> **验证**：`cd frontend && npx vitest run useChapterReader` 全绿。

## 验证命令

```bash
cd frontend && npx vitest run useChapterReader   # 单测
cd frontend && npx vue-tsc --noEmit              # 类型
```

人工（用户）：
- 倍速 1.5x / 2x 朗读一章，确认音调不再升高
- 试听在倍速下不变调

## 回滚点

- 改动集中在 1 源文件 + 1 测试文件，单 commit。`git revert` 即可回退到 Web Audio 主路径。
- 每完成一个步骤跑一次单测，保证可随时回退到上一个绿点。

## Review gate（实现后独立复核）

- `activeBackend` 状态机分派是否覆盖所有 pause/resume/stop 入口
- `onerror` / `onended` 等 listener 是否用赋值方式（防累积）
- objectURL 是否在每次换段 + stop + 卸载时 revoke（防内存泄漏）
- 空音频检测（`MIN_VALID_AUDIO_SECONDS`）是否正确迁移到 webaudio 兜底路径
- `currentRun !== runId` 中断检查在两条路径的关键 await 点是否都在
