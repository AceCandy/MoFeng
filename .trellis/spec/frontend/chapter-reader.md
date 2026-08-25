# Chapter Reader (useChapterReader) Guidelines

> Conventions for `src/composables/useChapterReader.ts` and `src/components/writing-desk/ChapterReaderBar.vue` — the floating chapter-readout control on the writing desk. Playback routes by TTS model availability, falling back to the browser.

---

## Playback routes by the configured default TTS model; voice/speed are runtime prefs chosen on the bar

`refreshTTSConfig()` runs before every `start()` and is deliberately not prefetched when the reader mounts, so TTS configuration never blocks the chapter's initial content request. It finds the first model with `is_enabled && is_default_tts && capabilities.tts`, exposes `hasModelTTS` and the model's `tts_protocol` (`modelProtocol`), and primes the global model-voice preference (`modelVoice`, localStorage `mofeng:reader-model-voice`): if the stored voice is not in the new protocol's preset candidates, it resets to the first candidate. `start()` plays model segments when `hasModelTTS` is true; otherwise it falls back to browser `speechSynthesis`.

## Model-segment playback uses `<audio>` (pitch-preserving) first, with Web Audio as fallback

Inside a model segment, playback tries an `<audio>` element with `preservesPitch=true` so `rate` changes tempo without shifting pitch — `AudioBufferSourceNode.playbackRate` cannot do this (Web Audio has no pitch-preserving mode; see WebAudio/web-audio-api#2487). If `<audio>` emits `error` (a wav its FFmpeg media demuxer rejects), the segment falls back to Web Audio (`decodeAudioData` + `AudioBufferSourceNode`): it plays wavs `<audio>` can't, but speed changes shift pitch there. If Web Audio also fails (empty/corrupt audio), `playModelSegments`'s catch switches to browser `speechSynthesis` as before. An `activeBackend` flag (`'audio' | 'webaudio' | null`) routes `pause`/`resume`/`stop` to the right backend; the browser path sets it `null`. The `<audio>` wav-silence bug that once forced Web Audio-only playback is gone — `tts_service._normalize_to_pcm16_wav` rewrites every upstream wav to standard 16-bit PCM, so `<audio>` is the correct default now; Web Audio stays only as defense-in-depth.

Voice and speed are **runtime preferences owned by the reader, not the model**: `modelVoiceOptions` is the preset voice list for `modelProtocol` (MiMo presets vs OpenAI `alloy`/`echo`/…), where each option's `label` tags **gender + language** (e.g. `白桦 · 男 · 中文`) so users can pick by voice characteristics; `modelVoice` stores the chosen voice id (persisted), and `rate` is the speed. Both are sent to the backend on every `synthesize`/`previewModelVoice` call and override the model's stored `tts_voice`/`tts_speed`. The model only carries `tts_protocol` (how to call the upstream API); it no longer stores voice/speed.

The reader bar mirrors this so users pick the real voice on the bar:

```ts
const useModelVoice = computed(() => props.hasModelTTS && !props.isBrowserFallback)
```

- `useModelVoice` true → a `<select>` of `modelVoiceOptions` bound to `modelVoice` (`model-voice-change` → `setModelVoice`), plus the existing speed `<select>` (`rate`).
- otherwise (`showVoiceControl = isBrowserFallback || status === 'idle'`) → the browser system-voice `<select>`, used only for the fallback path.

`previewVoice()` splits the same way: model mode synthesizes `PREVIEW_SAMPLE` via the backend with the current `modelVoice`/`rate` (`previewModelVoice`, borrowing `status='generating'` to disable the button while the request is in flight); browser mode speaks via `speechSynthesis`. `stop()` calls `stopPreview()` so a preview audio never outlives its run.

Never configure voice/speed on the model in the settings page, and never show a browser voice dropdown while a default TTS model is configured — voice/speed belong to the reader as global prefs. If the bar shows browser voices despite a configured default TTS model, the bug is in `hasModelTTS` propagation (`refreshTTSConfig` / `WDWorkspace` props wiring), **not** in the playback path.
