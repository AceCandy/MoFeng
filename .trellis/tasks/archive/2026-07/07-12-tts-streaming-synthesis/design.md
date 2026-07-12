# Design — TTS 流式合成

## 涉及文件

| 文件 | 改动 |
|---|---|
| `backend/app/services/tts_service.py` | 新 `_synthesize_mimo_stream` async generator（`stream:true` + `pcm16`，解析上游 SSE yield PCM16 chunk）；`synthesize_stream` 入口 |
| `backend/app/api/routers/tts.py` | 新 `POST /api/tts/speech/stream`，`StreamingResponse` 透传 PCM16 |
| `frontend/src/api/tts.ts` | 新 `synthesizeSpeechStream` → `ReadableStream<Uint8Array>` |
| `frontend/src/composables/useChapterReader.ts` | `playAudioStream`（queue scheduling）；mimo 走流式，失败回退非流式；pause/resume 改 `ctx.suspend/resume` |
| `backend/tests/`、`frontend/src/composables/__tests__/` | 流式路径测试 |

## D1 后端：流式透传

### D1.1 service
新 `_synthesize_mimo_stream(model, text, voice, speed)` → `AsyncIterator[bytes]`：
- payload 加 `stream: True`，`audio.format = "pcm16"`。
- `httpx.AsyncClient.stream("POST", url, json=payload)` 上游 SSE。
- `async for line in response.aiter_lines():` 解析以 `data: ` 开头的行 → JSON → `choices[0].delta.audio.data` → `base64.b64decode` → `yield` PCM16 bytes。
- 流结束校验累计字节数（≥ MIN）；上游 HTTP 错误或无 chunk → `raise TTSUpstreamError`。
- 不做 wav 标准化（流式是 raw PCM16，前端按已知格式 24kHz/mono/int16 解析）。

新 `synthesize_stream(user_id, text, voice, speed)` → `AsyncIterator[bytes]`：配置校验复用 `synthesize` 的前半段，分流到 `_synthesize_mimo_stream`；非 mimo 协议不支持流式 → `raise TTSConfigurationError`（或回退非流式，见 D1.3）。

### D1.2 router
新 `POST /api/tts/speech/stream`，`response_class=StreamingResponse`，`media_type="audio/pcm"`，`yield service.synthesize_stream(...)`。错误映射同 `/speech`（409/504/502）。

### D1.3 保留非流式
`/speech` + `synthesize` + `_synthesize_mimo`（wav 标准化）保留：作流式失败的回退路径 + `openai_speech` 入口。

## D2 前端 api
`synthesizeSpeechStream(text, options, signal)` → `fetch('/api/tts/speech/stream')` → `response.body`（`ReadableStream<Uint8Array>`）。认证头同 `synthesizeSpeech`。

## D3 前端播放：流式 queue

新 `playAudioStream(stream: ReadableStream<Uint8Array>, currentRun)`：
1. `ctx = getAudioContext()`；`reader = stream.getReader()`；pcm 累积 `Uint8Array`；`scheduledTime = ctx.currentTime`；`sources: AudioBufferSourceNode[]`。
2. 循环 `await reader.read()`：
   - 收到 chunk → 追加到 pcm 累积。
   - 当累积 ≥ 一块（`STREAM_CHUNK_SAMPLES = 12000` 即 0.5s @ 24kHz，24000 字节）：按 2 字节边界切出一块 → `Float32Array`（int16 LE → ÷32768）→ `ctx.createBuffer(1, n, 24000)` → `copyToChannel` → `source = ctx.createBufferSource()` → `source.buffer = buf` → `source.start(scheduledTime)` → `scheduledTime = max(scheduledTime, ctx.currentTime) + buf.duration`；`sources.push(source)`。
   - 首块 `scheduledTime = ctx.currentTime`（即播，秒播）。
   - `done` → 尾部剩余 PCM 同样切块 schedule；最后一个 source 的 `onended` → resolve。
3. 跨 chunk sample 对齐：切块按 2 字节边界，余 1 字节留下一轮。

### D3.1 暂停 / 续播 / 停止（关键简化）
- `pause` = `ctx.suspend()` + **暂停 reader 读取**（不发新 chunk 入 queue）。
- `resume` = `ctx.resume()` + 恢复 reader 读取。
- `stop` = `sources.forEach(stop)` + `reader.cancel()` + `ctx.resume()`。
- **关键**：暂停时必须停 reader，否则 suspend 期间 chunk 继续累积、`scheduledTime` 超前 `currentTime`，resume 后播放"追赶"快进。suspend + 停 reader 保证 `scheduledTime` 与 `currentTime` 同步冻结。
- 取代现状手动 `startOffset` offset 记忆（流式 queue 多 source，suspend/resume 整 ctx 最自然，offset 由时钟自动保持）。

### D3.2 非流式兼容
- `openai_speech` / 回退路径仍用 `playAudio(blob)`（完整 buffer + 手动 offset 暂停，现状不变）。
- 流式失败（stream 错误 / 上游 502）→ `playModelSegments` catch → 该段重试 `synthesizeSpeech`（非流式 Blob）+ `playAudio`；仍失败 → browser fallback。

### D3.3 playModelSegments 分流
- mimo：`synthesizeSpeechStream` + `playAudioStream`。
- 失败回退：非流式 `synthesizeSpeech` + `playAudio`。

## D4 决策点

**前端流式播放方案**：
- 方案 A（推荐）：分块 queue scheduling + `ctx.suspend/resume` 暂停 + 暂停 reader。标准 Web Audio，可控，暂停靠 ctx 时钟。
- 方案 B：AudioWorklet（processor 消费 PCM stream，ring buffer）。无缝但 worklet 模块复杂、调试难。

→ 采用 A。

## 风险与缓解

| 风险 | 缓解 |
|---|---|
| chunk 跨 2 字节边界切坏样本 | 切块前按 2 字节对齐，余数留下一轮 |
| queue 块间 click/gap | `source.start(scheduledTime)` 绝对时间精确调度，无 gap |
| suspend 期间 reader 超前导致 resume 快进 | pause 同步停 reader（D3.1 关键） |
| ctx.suspend 影响全局音频 | 朗读期间无其他音频并发（preview 已互斥） |
| 上游 SSE 解析脆（非 `data:` 行、空 delta） | 仅解析 `data: ` 前缀 + 校验 delta.audio 存在；robust 测试 |
| 流式中途取消（用户 stop / 切段） | `reader.cancel()` + 停所有 source |
| 流式失败回退路径复杂 | 失败先回退该段非流式，再 browser fallback（分层兜底） |
