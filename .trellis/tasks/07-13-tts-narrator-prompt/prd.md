# TTS 朗读语气优化：去模型侧变速 + 有声书主播提示词

## Goal

朗读倍速统一交给前端 `AudioBufferSourceNode.playbackRate` 控制，后端 MiMo 合成不再介入变速；同时在 MiMo 合成链路注入「有声书主播」system 提示词，让朗读更具感情与临场感。

## Background

- `_synthesize_mimo`（`backend/app/services/tts_service.py:224`）原在 `speed != 1.0` 时向 `messages` 插入一条自然语言 prompt「请以正常语速的 {speed:g} 倍朗读」实现模型侧变速。
- 实际上前端朗读控件（`useChapterReader.ts`）调用合成时从不传 `speed`，倍速由播放端 `playbackRate`（`:315/:399/:550`）实现。后端那段分支恒不触发，属闲置的「半死代码」，且与前端 playbackRate 存在潜在的双重变速叠加。
- MiMo 走 chat/completions 协议，是 LLM 驱动的音频模型，可通过 system 消息引导语气演绎。

## Requirements

1. 移除 `_synthesize_mimo` 中 `if speed != 1.0` 的 prompt 变速分支，模型侧不再产出变速音频。
2. 在 `_synthesize_mimo` 的 `messages` 头部插入 system 消息，定义「有声书演播艺术家」角色（采用方案 B 文案，见 Acceptance Criteria），强调忠实原文、不得改写/增删/解说。
3. 清理因改动产生的孤立 `speed` 形参：`_synthesize_mimo` 不再接收 `speed`，`synthesize` 调用处不再向其透传。
4. `openai_speech` 协议（`_synthesize_openai`）保持不动，其结构化 `speed` 字段在前端不传时默认 1.0，本就不变速。
5. 前端播放链路、`rate`/playbackRate 行为不变。

## Constraints

- 不改动 OpenAI 协议、前端、DB schema、`SpeechRequest`、`UserAIModel.tts_speed` 字段。
- `synthesize` 公开签名的 `speed` 形参保留（`openai_speech` 仍用），仅断开它与 mimo 的联系。
- 提示词必须显式约束「只演绎不创作」，避免模型改写原文或添加开场/收尾/解说。

## Acceptance Criteria

- [ ] `_synthesize_mimo` 不再出现「倍朗读」prompt；其 messages 结构为 `[system, assistant]`，system 文案为方案 B：

  ```
  你是一位顶级有声书演播艺术家。请朗读提供的文本：
  1. 感情饱满，语调随情节起伏——紧张处提速上扬，舒缓处放慢沉静；
  2. 区分旁白与对白：旁白叙述有温度，对白贴合角色情绪与性格；
  3. 善用停顿、气息与重音制造戏剧张力；
  4. 全程忠实原文，只演绎不创作，不得改写、增删或加入开场/收尾/解说。
  ```

- [ ] `_synthesize_mimo` 签名不再含 `speed`；`synthesize` 中 mimo 分支调用不再传 `speed`。
- [ ] `backend/tests/test_tts_service.py` 更新断言并全部通过：移除对「倍朗读」字样的断言；新增对 system 提示词存在与角色的断言。
- [ ] 后端 lint / 类型 / 测试全绿（`backend` 校验命令）。

## Out of Scope

- `AudioBufferSourceNode` 变调问题（独立话题，本任务不处理）。
- 前端变速 UI 或 playbackRate 保音高改造。
- MiMo 结构化 `audio.speed` / `emotion` / `speech_style` 接入（后续可选增强）。
