# Implement — TTS 流式合成

## 执行顺序（每步带验证）

1. **后端 service 流式 generator** → `synthesize_stream` + `_synthesize_mimo_stream`（stream+pcm16，SSE 解析 yield PCM16）。
   - verify: `pytest backend/tests/test_tts_service.py`（新增流式 generator 测试：mock 上游 SSE 行，断言 yield 的 PCM16 字节正确、空响应抛 TTSUpstreamError）。

2. **后端 router 流式端点** → `POST /api/tts/speech/stream` StreamingResponse + 错误映射。
   - verify: `pytest backend/tests/test_tts_router.py`（新增：端点返回 audio/pcm 流、409/502 映射）。

3. **前端 api** → `synthesizeSpeechStream` 返回 ReadableStream。
   - verify: 类型 + 简单 mock。

4. **前端播放** → `playAudioStream`（queue scheduling + 2 字节对齐 + 首块即播）；`pause/resume` 改 `ctx.suspend/resume` + reader 暂停；`stop` cancel reader + 停 source。常量 `STREAM_CHUNK_SAMPLES=12000`。
   - verify: `vitest useChapterReader.spec.ts`（新增：流式 chunk queue 播放、暂停 suspend+停 reader、resume 继续、流式失败回退非流式）。

5. **playModelSegments 分流** → mimo 走 stream；失败回退非流式 `synthesizeSpeech`+`playAudio`；仍失败 browser fallback。
   - verify: vitest 失败回退用例。

6. **全量验证**：`pytest backend/tests/test_tts_service.py test_tts_router.py` + `cd frontend && npx vitest run src/composables/__tests__/useChapterReader.spec.ts && npx vue-tsc --noEmit`。

## Review 门
- 实现完跑 trellis-check（独立复核：sample 对齐、suspend/reader 同步、回退路径、测试覆盖）。
- 浏览器实测首段秒播（用户验，无法自动测）。

## 回滚点
- 后端流式端点独立（/speech/stream 新增），删除即回退。
- 前端 playAudioStream 与 playAudio 并存；playModelSegments 分流开关可切回非流式。
