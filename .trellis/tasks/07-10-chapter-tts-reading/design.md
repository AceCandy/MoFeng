# 章节朗读与 TTS 模型接入技术设计

## 1. Scope And Assumptions

- Only finalized chapters with resolved content expose reading controls.
- Reading content is `chapter title + selectedChapterResolvedContent`.
- One user can have at most one enabled default TTS model.
- A provider base URL already includes its API version prefix. The service only appends
  `/chat/completions` or `/audio/speech`.
- MiMo uses the confirmed Chat Completions audio contract; OpenAI-compatible speech uses
  `/v1/audio/speech` semantics relative to the saved provider URL.
- Audio generation cannot guarantee that an already accepted upstream request is not billed after a
  local abort. Cancellation prevents local playback and later requests.

## 2. Architecture

```text
SettingsView / PersonalModelRouting
  -> llm API + Vue Query bundle
  -> llm-config router/service/repository
  -> user_model_providers + user_ai_models

WDWorkspace
  -> useChapterReader
     -> split title and body into <= 2500-character segments
     -> default TTS exists: POST /api/tts/speech for one segment
        -> TTSService
           -> MiMo Chat Audio branch OR OpenAI Speech branch
           -> audio bytes + MIME type
     -> no default TTS / synthesis failure: speechSynthesis queue
```

No generic provider adapter hierarchy is introduced. `TTSService` owns two private protocol methods,
which is the minimum abstraction required for the two approved contracts.

## 3. Persistence And Configuration Contract

`user_ai_models` gains:

| Field | Type | Rule |
|---|---|---|
| `is_default_tts` | boolean | Unique per user through service normalization |
| `tts_protocol` | nullable string(32) | `mimo_chat_audio` or `openai_speech` |
| `tts_voice` | nullable string(120) | Required when TTS capability is enabled |
| `tts_speed` | float | `0.5 <= value <= 2.0`, default `1.0` |

`capabilities_json` and provider capability normalization add the `tts` key. Existing chat and
embedding records remain valid because all new fields have backward-compatible defaults.

The ORM, Pydantic schemas, TypeScript interfaces, startup schema upgrade, `schema.sql`, and a
human-readable SQL migration must change together. Deleting a default TTS model is blocked until a
replacement is selected, matching existing chat and embedding behavior.

## 4. Backend Speech Contract

```http
POST /api/tts/speech
Authorization: Bearer <token>
Content-Type: application/json

{"text":"one segment, 1..2500 characters"}
```

Success returns raw audio bytes with the upstream-compatible MIME type. The endpoint never accepts a
model ID: `TTSService` resolves only the current user's enabled default TTS model, enabled provider,
capability, protocol, voice, and speed.

MiMo request:

```json
{
  "model": "mimo-v2.5-tts",
  "messages": [
    {"role": "user", "content": "请以正常语速的 1.2 倍朗读。"},
    {"role": "assistant", "content": "..."}
  ],
  "audio": {"format": "wav", "voice": "白桦"}
}
```

At speed `1.0`, the MiMo control message is omitted. OpenAI Speech sends `model`, `input`, `voice`,
`speed`, and `response_format: "mp3"`.

Error mapping:

| Condition | HTTP | Frontend behavior |
|---|---:|---|
| No valid default TTS | 409 | Browser fallback |
| Invalid/oversized text | 422 | Stop and show validation error |
| Upstream timeout | 504 | Browser fallback with notice |
| Auth, rate limit, empty/invalid audio | 502 | Browser fallback with notice |

Upstream response bodies, chapter text, and credentials are never logged or returned.

## 5. Frontend Playback State

`useChapterReader` owns `idle -> generating -> playing <-> paused -> stopped/completed` and exposes:

```ts
type ReaderStatus = 'idle' | 'generating' | 'playing' | 'paused'

interface ChapterReader {
  status: Readonly<Ref<ReaderStatus>>
  isBrowserFallback: Readonly<Ref<boolean>>
  start(title: string, content: string): Promise<void>
  pause(): void
  resume(): void
  stop(): void
}
```

The composable splits by paragraphs, then sentence punctuation, then a hard 2500-character boundary.
It requests the first model segment before playback, prefetches at most the next segment while the
current segment plays, and does not start further requests while paused. Object URLs are revoked when
consumed or stopped.

If any model segment fails, the composable cancels model prefetch and continues from that failed
segment through browser speech. It does not restart completed segments. Browser speech uses the same
segment list and `speechSynthesis.cancel/pause/resume`.

The toolbar initially adds one reading button. While active it expands into a play/pause control and a
separate stop icon. Chapter selection changes and component unmount call `stop()`.

## 6. Settings UX

`SettingsView` adds a keyboard-navigable `语音朗读` tab. `PersonalModelRouting` extends its existing
section/capability mapping with `tts`; it continues using the existing provider cards, model CRUD, and
bundle query invalidation.

TTS model editing adds protocol, voice, and speed controls. MiMo shows the eight confirmed voices plus
a custom voice input. OpenAI-compatible speech accepts a custom voice ID. The speed control is a
bounded slider/input with default `1.0`. Audio format is not user-configurable in this release.

## 7. Compatibility, Rollback, And Security

- Startup migration adds only nullable/defaulted columns, so existing data remains readable.
- Rollback can stop exposing the TTS tab and route while leaving additive columns in place; destructive
  schema rollback is not required.
- Existing API key storage is reused without broad encryption refactoring. Full keys remain server-only.
- This task does not add arbitrary request templates, voice cloning, voice design, audio persistence,
  downloads, or playlists.

## 8. Verification Strategy

- Backend unit tests cover schema validation, capability normalization, unique default handling,
  ownership, protocol request bodies, Base64 decode, binary response, timeout, and invalid audio.
- Frontend unit tests cover deterministic splitting, model/browser selection, state transitions,
  one-segment prefetch, fallback continuation, cancellation, and cleanup.
- Component tests cover visibility and toolbar controls; settings regression tests cover the fourth tab,
  keyboard navigation, and TTS fields.
- Final gates: focused tests, full backend tests with timeout, frontend unit tests, `vue-tsc`, and build.
