# PRD — TTS 流式合成：端到端首段秒播

## 背景
现状朗读合成非流式：后端 `_synthesize_mimo` 一次性请求上游、收完整 wav 返回前端，前端 `decodeAudioData` 完整 blob 后才开始播放。首段出声 = 上游完整合成时间。短段合并已减少请求数（解决"短段慢"主因），流式进一步降低首段 TTFB。

小米 MiMo 官方文档确认 `mimo-v2.5-tts` 已上线低延迟流式（`stream:true` + `audio.format:"pcm16"`，响应 `choices[0].delta.audio.data` 分块 PCM16LE mono 24kHz）。

## 目标
朗读启动后，首段在上游首个 PCM chunk 到达即开始播放（首段秒播），不等整段合成完。

## 验收标准（AC）
- [ ] 点朗读后，首段出声延迟显著低于非流式（首个 chunk 到达即播）。
- [ ] 暂停 / 续播 / 停止在流式播放下正常工作。
- [ ] 流式失败（上游错误 / 网络）→ 该段回退非流式合成；非流式仍失败 → browser fallback。
- [ ] 仅 `mimo_chat_audio` 协议走流式；`openai_speech` 仍非流式。
- [ ] vitest + pytest + vue-tsc 全绿；新增流式路径测试。

## 非目标
- `openai_speech` 流式（协议不支持流式 mp3）。
- 跨段流式（每段独立流式，段间仍 `SEGMENT_GAP_MS` 停顿）。

## 结论：评估后放弃（2026-07-12）
实现已完成（7 文件 + 自测绿）但浏览器实测卡顿（半成品经 HMR 加载 + 部署/queue 问题）；叠加短段合并也已被回退为逐段合成——逐段 + 预热并发（`PREFETCH_AHEAD=2`）下首字延迟可接受，流式的 TTFB 边际收益不值得「前后端协议 + 播放层重写」的复杂度与稳定性风险。`design.md` 保留供未来重做参考；流式代码已 `git stash drop` 弃，未提交。
