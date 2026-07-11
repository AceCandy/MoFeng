# Chapter Reader (useChapterReader) Guidelines

> Conventions for `src/composables/useChapterReader.ts` and `src/components/writing-desk/ChapterReaderBar.vue` — the floating chapter-readout control on the writing desk. Playback routes by TTS model availability, falling back to the browser.

---

## Playback routes by the configured default TTS model; voice/speed are runtime prefs chosen on the bar

`refreshTTSConfig()` (runs on mount, inside `getCurrentInstance()`, and before every `start()`) finds the first model with `is_enabled && is_default_tts && capabilities.tts`, exposes `hasModelTTS` + the model's `tts_protocol` (`modelProtocol`), and primes the global model-voice pref (`modelVoice`, localStorage `mofeng:reader-model-voice`): if the stored voice isn't in the new protocol's preset candidates, it resets to the first candidate. `start()` plays model segments when `hasModelTTS` is true; otherwise it falls back to browser `speechSynthesis`.

Voice and speed are **runtime preferences owned by the reader, not the model**: `modelVoiceOptions` is the preset voice list for `modelProtocol` (MiMo presets vs OpenAI `alloy`/`echo`/…), where each option's `label` tags **gender + language** (e.g. `白桦 · 男 · 中文`) so users can pick by voice characteristics; `modelVoice` stores the chosen voice id (persisted), and `rate` is the speed. Both are sent to the backend on every `synthesize`/`previewModelVoice` call and override the model's stored `tts_voice`/`tts_speed`. The model only carries `tts_protocol` (how to call the upstream API); it no longer stores voice/speed.

The reader bar mirrors this so users pick the real voice on the bar:

```ts
const useModelVoice = computed(() => props.hasModelTTS && !props.isBrowserFallback)
```

- `useModelVoice` true → a `<select>` of `modelVoiceOptions` bound to `modelVoice` (`model-voice-change` → `setModelVoice`), plus the existing speed `<select>` (`rate`).
- otherwise (`showVoiceControl = isBrowserFallback || status === 'idle'`) → the browser system-voice `<select>`, used only for the fallback path.

`previewVoice()` splits the same way: model mode synthesizes `PREVIEW_SAMPLE` via the backend with the current `modelVoice`/`rate` (`previewModelVoice`, borrowing `status='generating'` to disable the button while the request is in flight); browser mode speaks via `speechSynthesis`. `stop()` calls `stopPreview()` so a preview audio never outlives its run.

Never configure voice/speed on the model in the settings page, and never show a browser voice dropdown while a default TTS model is configured — voice/speed belong to the reader as global prefs. If the bar shows browser voices despite a configured default TTS model, the bug is in `hasModelTTS` propagation (`refreshTTSConfig` / `WDWorkspace` props wiring), **not** in the playback path.
