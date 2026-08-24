# LLM Settings (PersonalModelRouting) Guidelines

> Conventions for `src/components/llm-settings/PersonalModelRouting.vue` — the shared component behind the 乾坤万象中枢 tabs (文本生成 / 记忆检索 / 语音朗读 / 阶段路由). One provider/model store, partitioned by capability.

## Stage routing mirrors the shared chapter workflow definition

The chapter workflow shown in stage routing and `ChapterGenerating.vue` must both consume
`CHAPTER_WORKFLOW_STEPS` from `src/utils/generationTrace.ts`. A workflow node may declare an
existing `routeStage` and its `routeCapability`; nodes sharing a stage are multiple views of the
same `routeSelections[stage]` value, not separate backend routes. Nodes without `routeStage` must
be presented as having no model call.

Candidate generation is intentionally independent: `generate_candidate_1` routes through
`chapter_writing_1` and `generate_candidate_2` through `chapter_writing_2`. Calls that omit a
business stage use `general_chat`; show that route only under “其他功能”, never as a chapter node.
The obsolete `chapter_writing` key is not accepted or preserved.

Keep non-chapter stages in the separate “其他功能” group. Filter each route selector by
`routeCapability`: chat stages receive enabled chat models and `rag_embedding` receives enabled
embedding models. The save payload is generated from the deduplicated stage key list, so shared
workflow nodes never produce duplicate route entries.

---

## Supplier list is filtered by the active section's capability

`activeProviders` must filter `providers` by the capability of the current section (`chat` / `embedding` / `tts`). All three sections share one filter path — never branch per section.

Good — `src/components/llm-settings/PersonalModelRouting.vue`:

```ts
const activeProviders = computed(() =>
  providers.value.filter((provider) => providerCapabilities(provider)[activeModelCapability()]),
)
```

`activeModelCapability()` maps `llm → 'chat'`, `embedding → 'embedding'`, `tts → 'tts'`. `providerCapabilities(provider)` reads `provider.capabilities.<cap>`. Each tab therefore shows only providers explicitly marked with that capability, and the readiness count / empty-state / picker-close watch all derive from the same filtered set.

---

## Don't: per-section "show all providers" special-case

A capability tab must not bypass the filter to surface every provider. This was the original TTS behavior and it leaked chat/embedding-only providers into the 语音朗读 tab.

Bad:

```ts
// AVOID — leaks non-tts providers into the TTS tab
const activeProviders = computed(() =>
  activeSection.value === 'tts'
    ? providers.value
    : providers.value.filter((provider) => providerCapabilities(provider)[activeModelCapability()]),
)
```

Why it's bad: TTS is meant to use a dedicated provider configured with the `tts` capability (own base URL / API key / voice). Mixing in chat-only providers lets users attach TTS models to providers that were never declared TTS-capable, breaking the isolation users expect, and it also inflated the readiness "N 个供应商" count.

If the same upstream account should serve TTS, create a separate provider entry **from inside the TTS tab** — do not reuse the chat provider in place.

---

## Gotcha: provider capability is explicit, model aggregation is fallback-only

A provider appears in a capability tab only when its own `capabilities_json` has that flag set. Backend `_infer_provider_capabilities` (in `llm_config_service.py`) aggregates capabilities from a provider's models, but `_provider_to_read` + `_normalize_capabilities` prefer the provider's own `capabilities_json`; the aggregation is used only when that field is empty — and `create_provider` always writes a non-empty normalized dict, so in practice the fallback never fires.

Consequence: saving a TTS model under a chat-only provider does **not** make that provider appear in the TTS tab. The provider must be created or edited in the TTS tab so `createProviderCapabilities()` (new) or the edit merge (`{ ...existing, [activeModelCapability()]: true }`) sets `tts: true`.

```ts
// createProviderCapabilities() — new provider created in the TTS tab
const createProviderCapabilities = (): Record<Capability, boolean> => {
  const capability = activeModelCapability() // 'tts' in the TTS tab
  return {
    chat: capability === 'chat',
    embedding: capability === 'embedding',
    tts: capability === 'tts',
  }
}
```

So: to configure TTS, add/edit a provider from inside the TTS tab; that is what marks it `tts`-capable and makes it visible there.

---

## TTS settings page only selects the default model — voice/speed live on the reader

The 语音朗读 tab in `PersonalModelRouting.vue` lets the user pick **only** the default TTS model. Protocol/voice/speed are **not** configured here:

- `tts_protocol` is bound to the model, defaulted to `mimo_chat_audio` when a model is marked default (`createModelPayload` / `saveTTSSelection` use `'mimo_chat_audio'` as fallback, preserving any already-set protocol). It tells the backend which upstream API to call (`/chat/completions` vs `/audio/speech`).
- `tts_voice` / `tts_speed` are **not** stored on the model — they are runtime preferences chosen on the chapter reader bar (`useChapterReader`) and sent to the backend per request (see [Chapter Reader](./chapter-reader.md)).

Consequently backend `synthesize(user_id, text, voice=None, speed=None)` accepts optional runtime `voice`/`speed` overriding the model's stored values, and `_validate_tts_model` no longer requires `tts_voice`. Do **not** re-introduce a protocol/voice/speed form in the model picker — that splits the mental model (model = which engine; reader bar = how it sounds) and was the earlier R2/R3 approach, since reverted.

```ts
// saveTTSSelection — only sets default + protocol fallback, never voice/speed
data: {
  is_enabled: true,
  is_default_tts: true,
  tts_protocol: selected.tts_protocol || 'mimo_chat_audio',
}
```

---

## Model-list fetch returns empty on failure — never a hardcoded fallback

`get_available_models` and every per-provider helper (`_get_anthropic_models`, `_get_google_models`, …) return `[]` on any fetch failure or empty result. Do not add a hardcoded "preset models" fallback that masks the failure — an earlier `_get_anthropic_models` returned a baked-in claude list on failure, which made a misconfigured provider (e.g. an OpenAI-compatible service whose type was set to `anthropic`) look like it had "fetched claude models." Empty + the picker's "没有可选模型" state is honest; if fetch health needs to surface, propagate the error explicitly rather than substituting fake data.

---

## Pending picker state belongs to the page dirty contract

Text and TTS model pickers keep selections locally until the user saves them. Their dirty state must
therefore be part of the `PersonalModelRouting.isDirty` value exposed to `SettingsView`; checking it
only inside the panel-close handler still allows tab changes, browser history, and route leave to
discard a pending selection.

```ts
const isDirty = computed(
  () => isStageRoutesDirty.value || isChatPickerDirty.value || isTTSPickerDirty.value,
)

defineExpose({ isDirty })
```

Closing the panel and leaving the page are separate boundaries and both must use the same pending
state. Regression coverage must assert chat and TTS dirty values are included in the exposed page
contract; embedding selection is excluded because it saves immediately.
