# LLM Settings (PersonalModelRouting) Guidelines

> Conventions for `src/components/llm-settings/PersonalModelRouting.vue` — the shared component behind the 乾坤万象中枢 tabs (文本生成 / 记忆检索 / 语音朗读 / 阶段路由). One provider/model store, partitioned by capability.

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
