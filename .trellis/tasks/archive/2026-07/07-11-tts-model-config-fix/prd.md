# TTS模型配置:消除拉取claude回退+表单改为先选模型再配协议音色

## 背景

语音朗读（TTS）模型配置存在两个相互独立但都影响可用性的问题：

1. **拉取到一堆 claude 模型**：当供应商「类型」被选成 Anthropic 时，后端用 Anthropic 协议去请求该供应商的 `base_url` 必然失败；失败后 `_get_anthropic_models` 静默回退到一份硬编码的 5 个 claude 模型列表，前端原样展示，用户误以为「这个供应商拉到了 claude」。小米（MiMo）这类 OpenAI 兼容服务被误选成 Anthropic 时就会触发。
2. **表单顺序反了**：TTS 拉取弹窗把「语音协议 / 默认音色 / 语速」放在模型列表之上，要求先填协议音色、再到下面选模型。但 `tts_protocol` / `tts_voice` / `tts_speed` 在数据模型上是 per-model 字段，且音色候选列表与协议强相关（MiMo 协议是「冰糖/茉莉/白桦…」，OpenAI Speech 协议是「alloy/echo/…」），「先选模型再配协议音色」才符合直觉。

## Goal

让 TTS 模型配置：拉取结果可信（失败就是空，不再伪装成 claude），配置顺序自然（先选默认朗读模型，再对该模型设置协议/音色/语速）。

## Requirements

### R1 拉取不再回退硬编码 claude
- 后端 `_get_anthropic_models` 在真实拉取失败或返回空时，返回空列表，不再回退到硬编码 claude 模型。
- 行为与其他 provider（google/azure/cohere/ollama/openai-like）保持一致：失败/空即空。

### R2 TTS 表单改为「先选模型再配置」
- 拉取弹窗内：模型单选列表在上，选中某个模型后才显示并允许编辑该模型的「语音协议 / 默认音色 / 语速」。
- 未选中模型时，协议/音色/语速区域不显示。
- 切换选中模型时，表单同步到该模型已保存的协议/音色/语速；若该模型无保存值，使用合理默认。

### R3 音色候选随协议切换
- `mimo_chat_audio` 协议：维持现有 MiMo 预设音色（冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean）。
- `openai_speech` 协议：提供 OpenAI 标准音色预设（alloy/echo/fable/onyx/nova/shimmer）。
- 音色输入仍允许自由填写（保持 datalist 建议而非强制枚举）。

### R4 不破坏其他流程
- chat / embedding 标签的拉取与配置行为不变。
- TTS 保存语义不变：仍把协议/音色/语速写入「被选为默认朗读」的那个模型。

## Acceptance Criteria

- [ ] 供应商类型 = Anthropic 且其 `base_url` 实际不可达/非 Anthropic 时，点「拉取模型」返回空，前端显示「没有可选模型」，不出现任何 claude 模型名。
- [ ] 供应商类型 = OpenAI 兼容（如小米 MiMo）时，拉取行为不受本次改动影响，能正常返回该服务模型列表。
- [ ] TTS 拉取弹窗：默认进入时模型列表可见，协议/音色/语速区域不可见；选中一个模型后该区域出现并可编辑。
- [ ] 在弹窗内切换选中模型，协议/音色/语速随之同步为该模型已存值（若有）。
- [ ] 协议选 `openai_speech` 时，音色输入的建议列表变为 OpenAI 标准音色；选 `mimo_chat_audio` 时变回 MiMo 音色。
- [ ] 保存后，被选中的默认朗读模型携带正确的 `tts_protocol` / `tts_voice` / `tts_speed`；再次打开弹窗能回显。
- [ ] chat / embedding 流程回归正常，无行为变化。

## Out of Scope

- 不改后端「拉取失败时把具体错误原因透传到前端」的可观测性增强（保持现状：空列表 + 前端「没有可选模型」）。
- 不改 TTS 合成协议本身（`mimo_chat_audio` / `openai_speech` 的请求逻辑不变）。
- 不改 provider 类型选项（仍为 OpenAI 兼容 / Anthropic / Ollama）。
