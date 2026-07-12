# Implement — TTS模型配置修复

执行顺序：先后端（R1，独立可验），再前端（R2/R3）。每步带验证。

## Step 1 — 后端去 claude 回退（R1）

改 `backend/app/services/llm_config_service.py::_get_anthropic_models`（`:686-723`）：

- 删除 `fallback_models` 列表与函数末尾的回退 `return [*fallback_models]`。
- 无 `api_key` 时 `return []`。
- 有 `api_key`：请求成功且 `model_ids` 非空 → 返回；任何异常或空 → `return []`。

验证：
- `rg -n "claude-3" backend/app/services/llm_config_service.py` → 应无结果。
- 轻量人工核对：该方法签名/调用方（`:550-551`）不变，仅内部返回值收敛。

## Step 2 — 前端音色候选随协议（R3）

改 `frontend/src/components/llm-settings/PersonalModelRouting.vue`：

- `:852` 上方新增 `const openAIPresetVoices = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']`。
- 新增 computed `ttsPresetVoices`：按 `ttsForm.protocol` 在两套预设间切换。
- `<datalist id="mimo-tts-voices">`（`:411-413`）`v-for` 源由 `mimoPresetVoices` 改为 `ttsPresetVoices`。

验证：
- `cd frontend && npx vue-tsc --noEmit` 无新增类型错误。

## Step 3 — 前端 picker 顺序重排 + 选中后显示表单（R2）

改 `PersonalModelRouting.vue`：

- 将「搜索框（`:428-438`）」与「模型列表（`:440-498`）」移到「协议/音色/语速表单（`:394-426`）」之前；或让表单块 `v-if="pendingTTSModelName"` 并移到列表之后（任选其一，优先移动表单块以减少搜索框/列表相对顺序变动）。
- 表单容器加 `v-if="pendingTTSModelName"`。
- `selectPendingTTSModel`（`:1643-1645`）扩展：选中模型后，若 `ttsModelForName(provider.id, modelName)` 存在已存的 `tts_protocol/tts_voice/tts_speed`，回填 `ttsForm`。
- `openProviderModelPicker`（`:1376-1384`）保持。

验证：
- `cd frontend && npx vue-tsc --noEmit`。
- `cd frontend && npx vitest run src/components/__tests__` 相关 spec（若有 PersonalModelRouting 的）。

## Step 4 — 文案（R2 配套）

- `:370` hint 改为「先选择默认朗读模型，再设置它的协议、音色与语速。」
- `:932` section 描述若与旧文案呼应，同步调整。

验证：人工读一遍两处文案一致。

## Step 5 — 朗读控件体现已配置的模型音色（R4）

配了默认 TTS 模型后，章节朗读悬浮控件仍显示浏览器系统音色下拉，应改为体现模型音色（模型音色由后端按 `tts_voice` 播放，前端不可切换，故只读展示）。

改 `frontend/src/composables/useChapterReader.ts`：
- 新增 `hasModelTTS` / `modelVoiceLabel` 状态与 `refreshTTSConfig()`：按 `is_enabled && is_default_tts && capabilities.tts` 找默认 TTS 模型，取其 `tts_voice`；挂载时（`getCurrentInstance()` 内）与每次 `start()` 前刷新。
- `start()` 改为复用 `refreshTTSConfig()` + `hasModelTTS.value`，删除原内联 `configured` 判定。
- `previewVoice()` 改 async 并分流：`hasModelTTS` 为真走新增 `previewModelVoice()`（合成 `PREVIEW_SAMPLE` 样例句播放，借用 `status=generating` 防重入），否则维持浏览器 `speechSynthesis`。
- 新增 `stopPreview()`，在 `stop()` 中调用，避免试听音频残留。

改 `frontend/src/components/writing-desk/ChapterReaderBar.vue`：
- 新增 props `hasModelTTS` / `modelVoiceLabel`，computed `useModelVoice = hasModelTTS && !isBrowserFallback`。
- 音色区分流：`useModelVoice` 显示只读标签「模型音色 · {modelVoiceLabel}」，否则保留浏览器音色下拉；试听按钮 `v-if="useModelVoice || showVoiceControl"` 两种模式都显示。

改 `frontend/src/components/writing-desk/WDWorkspace.vue`：
- 暴露 `readerHasModelTTS` / `readerModelVoiceLabel` 并传给 `ChapterReaderBar`。

验证：
- `cd frontend && npx vitest run src/composables/__tests__/useChapterReader.spec.ts`（含新增 refreshTTSConfig / 模型试听用例）。
- `cd frontend && npx vue-tsc --noEmit` 无新增类型错误。

## Step 6 — 音色/倍速移到朗读控件，设置页只留模型（R5，方向修正）

用户反馈：不应在配置模型时选音色/倍速，应在朗读控件里选。据此回退/调整 R2/R3/R4。

后端（运行时覆盖模型值）：
- `schemas/tts.py` `SpeechRequest` 加可选 `voice/speed`。
- `tts_service.py` `synthesize(user_id, text, voice=None, speed=None)`；放宽 `tts_voice` 必填校验；mimo/openai 用传入音色倍速。
- `routers/tts.py` 透传 `payload.voice/speed`。
- `llm_config_service.py` `_validate_tts_model` 不再要求模型预置音色。

前端合成链路：
- `api/tts.ts` `synthesizeSpeech(text, {voice, speed}, signal)`。
- `useChapterReader.ts` 新增全局模型音色偏好 `modelVoice`（localStorage，按协议匹配候选，切换协议回退首个）；`refreshTTSConfig` 读默认模型协议并初始化；合成/试听传 `{voice, speed}`；暴露 `modelProtocol/modelVoice/modelVoiceOptions/setModelVoice`。

朗读控件：
- `ChapterReaderBar.vue` 模型模式下拉选购 `modelVoiceOptions`（替代 R4 的只读标签），绑定全局偏好；`WDWorkspace.vue` 接 `model-voice-change → setModelVoice`。

设置页简化：
- `PersonalModelRouting.vue` 移除 TTS 协议/音色/倍速表单、`ttsForm`、`TTSForm` 类型、预设音色、`__tts-form`/`__tts-speed` 样式、`TTSProtocol` import；`saveTTSSelection`/`createModelPayload` 协议兜底 `mimo_chat_audio`、不写 voice/speed；文案改"选择默认语音朗读模型；音色与倍速在朗读控件里调整"。

验证：
- `cd frontend && npx vue-tsc --noEmit` 无错误。
- `cd frontend && npx vitest run src/composables/__tests__/useChapterReader.spec.ts src/components/__tests__/ttsSettings.spec.ts`（17 passed；ttsSettings 重写为"设置页只选模型"断言）。

## Review Gates

- 每步完成后各自验证通过再进下一步。
- Step 3 是 UI 改动，需用户浏览器回归（见下）。

## 浏览器回归清单（交付前由用户执行）

1. 类型 = Anthropic 的供应商 → 拉取模型 → 显示「没有可选模型」，无 claude。
2. 类型 = OpenAI 兼容（小米）→ 拉取 → 正常返回小米模型。
3. TTS 弹窗默认进入 → 表单隐藏，模型列表可见；选中模型 → 表单出现。
4. 协议切 openai_speech → 音色建议变 alloy/echo/…；切回 mimo → 变回白桦/…。
5. 保存 → 重新打开弹窗 → 选中模型与协议/音色/语速正确回显。
6. chat / embedding 标签配置不受影响。
7. 设置页 TTS tab 只有模型单选（无协议/音色/倍速表单）；选中保存 = 设为默认。
8. 朗读控件配模型后：音色下拉列协议预设（白桦/alloy…），倍速下拉维持；切换即时影响下次合成/试听；未配模型维持浏览器音色下拉与浏览器试听。

## Rollback

`git revert` 本次 commit，或按 design.md D3 风险表分别回滚两个文件。
