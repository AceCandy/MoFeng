# Design — TTS模型配置修复

## 涉及文件

| 文件 | 改动 | 角色 |
|---|---|---|
| `backend/app/services/llm_config_service.py` | `_get_anthropic_models` 去硬编码回退 | R1 |
| `frontend/src/components/llm-settings/PersonalModelRouting.vue` | TTS picker UI 重排 + 音色候选随协议切换 + 选中同步 | R2/R3 |

无 schema/DB 变更（`tts_protocol` / `tts_voice` / `tts_speed` 字段已存在于 `UserAIModel`）。

## D1 后端：消除 claude 回退（R1）

现状（`llm_config_service.py:686-723`）：`_get_anthropic_models` 拉取失败或返回空时，落到 `fallback_models`（5 个写死的 claude 模型）。

改法：删除 `fallback_models` 与末尾的回退返回，拉取失败/空统一 `return []`，与 `_get_google_models` / `_get_ollama_models` 等一致。

```python
async def _get_anthropic_models(self, api_key, base_url) -> List[str]:
    # 无 api_key 直接返回空（无兜底）
    # 有 api_key：请求 anthropic models 端点，成功返回列表，任何异常 return []
```

效果：Anthropic 类型供应商拉取失败时，`get_available_models` 返回 `[]` → 前端 `providerFetchState.modelsByCapability` 为空 → 显示「没有可选模型」。

**决策点 A（已定）**：直接 `return []`，不保留任何预设兜底。理由：其他 provider 一致、diff 最小、避免再次误导。代价：真正的 Anthropic 官方供应商偶发拉取失败时不再有兜底——可接受，Anthropic `/v1/models` 已稳定，且兜底本身就是误导来源。

## D2 前端：TTS picker 交互重排（R2 + R3）

### D2.1 顺序调整

当前（`PersonalModelRouting.vue:394-498`）picker 内顺序：协议/音色/语速表单 → 搜索框 → 模型 radio 列表。

改为：搜索框 → 模型 radio 列表 → （选中后）协议/音色/语速表单。

- 协议/音色/语速容器加 `v-if="pendingTTSModelName"`，未选中模型时不渲染。
- 模型列表区块保持不变（radio 绑定 `pendingTTSModelName`，`@change="selectPendingTTSModel"`）。

### D2.2 切换选中模型时同步表单

`selectPendingTTSModel(modelName)`（当前仅赋值 `pendingTTSModelName`）扩展：查找该模型在已保存模型集合中的 `tts_protocol` / `tts_voice` / `tts_speed`，有则回填 `ttsForm`，无则保持当前 `ttsForm`（用户未选模型前不强行清空，避免抖动）。

数据来源：`ttsModelForName(provider.id, modelName)`（已存在，用于 upsert 查 existing），取其 `tts_protocol` 等。

> 备选：切换时无条件重置为协议默认音色。否决——会丢用户已填值。

### D2.3 音色候选随协议切换

- 新增常量 `openAIPresetVoices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']`。
- 新增 computed `ttsPresetVoices`：`ttsForm.protocol === 'openai_speech' ? openAIPresetVoices : mimoPresetVoices`。
- 模板 `<datalist id="mimo-tts-voices">` 的 `v-for` 源由 `mimoPresetVoices` 改为 `ttsPresetVoices`；datalist 的 `id` 保留不变（`list="mimo-tts-voices"` 引用不变，避免误改牵连）。

### D2.4 初始化不变

`openProviderModelPicker`（`:1376-1384`）打开时仍从当前默认 TTS 模型同步 `ttsForm` 与 `pendingTTSModelName`。由于 D2.1 让表单在选中后才显示，初始化已选中默认模型时表单正常回显；未选中时表单隐藏，符合预期。

### D2.5 hint 文案

`PersonalModelRouting.vue:370` 的 TTS hint 由「先设置协议、音色和语速，再选择默认朗读模型。」改为「先选择默认朗读模型，再设置它的协议、音色与语速。」（`:932` 的 section 描述同步调整）。

## D3 保存逻辑（不变，仅确认）

- `saveTTSSelection`（`:1647-1682`）：校验 `pendingTTSModelName` 与 `ttsForm.voice`，upsert 模型 + 写入 `is_default_tts/tts_protocol/tts_voice/tts_speed`。不变。
- `createModelPayload` tts 分支（`:1412-1428`）：把 `ttsForm` 写入新模型。不变。

## 风险与回滚

| 风险 | 影响 | 缓解 |
|---|---|---|
| 去掉 anthropic 兜底，真正 anthropic 用户拉取失败变空 | 低 | 可接受；失败本就异常，空列表比假 claude 更诚实 |
| picker UI 重排影响已有 TTS 用户回显 | 低 | D2.4 保留初始化同步，选中默认模型即回显 |
| 音色 datalist id 名含 "mimo" 但实际通用 | 极低 | 仅语义残留，不影响功能；本次不改 id 避免牵连 |
| 改动集中在 2 个文件 | 回滚成本低 | 直接 revert 这 2 文件 |

回滚点：两文件独立，R1（后端）与 R2/R3（前端）可分别回滚互不影响。
