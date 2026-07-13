# 朗读变速保调：audio 元素替换 Web Audio 主路径

## 背景

当前模型 TTS 段用 Web Audio（`AudioBufferSourceNode`）播放，倍速通过 `source.playbackRate.value = rate` 实现（`useChapterReader.ts:315/399/550` 三处）。该属性是线性重采样，**变速同时变调**（倍速越高音调越高）。Web Audio 规范层面不支持保调（`WebAudio/web-audio-api#2487`、Chromium `#41263293` 均未实现）。

`<audio>` 元素的 `playbackRate` 默认 `preservesPitch=true`，浏览器内置时间拉伸，**变速不变调**。当初未用 `<audio>` 是因 MiMo 偶发返回非标准 wav（高位深 / 异常 chunk），`<audio>` 的 FFmpeg demuxer 解码失败而静音；后端 `8f6e79c` 已将所有 MiMo wav 标准化为 16-bit PCM，**根因已消除**。用户已实测：标准化后的 wav 用 `<audio>` 可正常播放。

## 目标

模型段朗读倍速调节时保持音调不变（变速不变调），同时保留 Web Audio 作为 `<audio>` 失败时的兜底，避免回退到"某些段落静音"的旧问题。

## 需求

1. 模型段主播放路径改为 `<audio>` 元素 + `preservesPitch`，倍速通过 `audio.playbackRate` 控制，变速不变调
2. 保留现有 Web Audio（`decodeAudioData` + `AudioBufferSourceNode`）作为兜底：当 `<audio>` 触发 `error` 事件（demux 失败）时，自动用 Web Audio 重播当前段
3. Web Audio 兜底仍失败（空音频 / 解码失败）时，维持现有行为：切浏览器 `speechSynthesis` 朗读（`playModelSegments` 的 catch → `playBrowserSegments`，不改）
4. 暂停 / 续播 / 停止在两条播放路径上都正常工作
5. 试听 `previewModelVoice` 一并切 `<audio>`（保调）
6. 浏览器朗读路径（`speechSynthesis`）完全不动

## 约束

- 仅改 `frontend/src/composables/useChapterReader.ts` 及其测试 `__tests__/useChapterReader.spec.ts`
- 不动后端；不动 `ChapterReaderBar.vue` 的音色 / 倍速控件交互（spec `chapter-reader.md:24`：播放路径与音色路由解耦）
- 不引入第三方依赖（SoundTouch.js / RubberBand 等）——A 方案零依赖
- 不动 `synthesize()` 调用契约（仍只传 `voice`，不传 `speed`）
- 遵守 `CLAUDE.md`：commit / 注释不含 AI 工具或模型名；面向用户输出中文

## 验收标准

1. 倍速 1.5x / 2x 朗读，音调无明显升高（**人工验**——唯一能验保调的方式）
2. 正常段落用 `<audio>` 播放；`<audio>` `error` 的段落自动切 Web Audio 且能出声；Web Audio 也失败切浏览器（单测覆盖三级兜底）
3. 暂停 → 续播 → 停止 全程正常，续播从暂停位置继续（单测覆盖 audio 与 webaudio 两条路径）
4. 试听在倍速下不变调
5. `cd frontend && npx vue-tsc --noEmit` 无新增类型错误
6. `cd frontend && npx vitest run useChapterReader` 全绿
7. 组件卸载后无 `<audio>` 元素泄漏 / 继续播放

## 范围外

- MiMo 流式 `pcm16` 改造（独立大改，从协议层彻底标准化格式）
- `<audio>` 静音但无 `error` 事件的检测（信任后端 `_wav_has_signal` + 重试防线）
- 倍速音质极致优化
- SoundTouch.js / RubberBand WASM 集成（B/C 方案）
