# Personal Model Routing Design

## Summary

Users need model settings that can support multiple AI providers, multiple API
keys, multiple available models, and per-stage model selection. The current
system has a single user-level chat model plus a single embedding model. This
design keeps the setting personal to each user, but replaces the single-model
shape with a provider/model/stage routing model.

The recommended first release is:

- Personal provider profiles: API base URL, API key, provider type, and status.
- Personal model pool: model names owned by a provider profile, with capability
  flags for chat and embedding.
- Personal stage routing: each AI stage has one default model. High-frequency
  actions can optionally override the stage model for that single request.

## Goals

- Allow one user to configure multiple providers and API keys.
- Allow one user to register multiple usable models under those providers.
- Route each AI task stage to a specific model.
- Keep backward compatibility with the current `/api/llm-config` behavior during
  migration.
- Keep stage names product-facing and understandable, rather than exposing every
  internal service method.
- Support embedding models through the same model pool, while preserving the
  stricter requirements around vector dimensions and provider protocol.

## Non-Goals

- No admin-level global model pool in the first release.
- No shared organization-wide API keys in the first release.
- No automatic cost tracking by provider in the first release.
- No complex policy engine or prompt-dependent dynamic routing in the first
  release.
- No per-project routing in the first release, though the data model should not
  block adding it later.

## Current State

The current front-end model page is `SettingsView.vue`, which renders
`LLMSettings.vue`. The current backend config API is `/api/llm-config`.

The current persistence shape is `llm_configs`, keyed by `user_id`, with these
fields:

- `llm_provider_url`
- `llm_provider_api_key`
- `llm_provider_model`
- `embedding_provider_url`
- `embedding_provider_api_key`
- `embedding_provider_model`
- `embedding_provider_format`

Text generation currently resolves a single model through `LLMService` before
calling the provider. Embedding generation uses `get_embedding` and reads the
embedding fields from the same user config record.

## AI Stages

The UI should expose a curated set of stages. Internally, multiple service calls
can map to the same stage.

### Import and Ideation

- `import_analysis`: imported novel character filtering and imported novel
  structure analysis.
- `concept_conversation`: inspiration-mode concept conversation, including
  streaming conversation.
- `world_blueprint`: full novel blueprint generation from concept history.

### Planning

- `chapter_outline`: chapter outline generation.
- `chapter_blueprint`: chapter blueprint generation, including single-chapter
  and batch blueprint generation.
- `chapter_mission`: chapter director script generation.

### Writing

- `chapter_preview`: chapter preview, preview evaluation, and preview expansion.
- `chapter_writing`: main chapter body generation.
- `chapter_rewrite`: guardrail rewrite and consistency auto-fix.
- `chapter_compression`: word-count compression after generation.
- `chapter_enrichment`: dialogue, scene, and chapter enrichment.

### Review and Optimization

- `version_review`: multi-version review and single-version evaluation.
- `chapter_optimization`: rhythm, psychology, environment, dialogue, and
  recommended-version optimization.
- `deep_review`: six-dimension review, periodic chapter review, reader
  simulation, and self-critique.
- `emotion_analysis`: AI emotion curve analysis.
- `consistency_check`: consistency checks that only diagnose issues.

### Memory, RAG, and Continuity

- `summary_memory`: chapter summaries, global summary update, character state
  update, and plot arc update.
- `rag_embedding`: embedding generation for chapter chunks, chapter summaries,
  retrieval queries, and review-context retrieval.
- `rag_query`: LLM-generated search query planning and LLM-based retrieved
  context filtering.
- `foreshadowing`: foreshadowing candidate filtering, status judgement, and
  reminder generation.

## Recommended Defaults

If a user only configures one chat model and one embedding model, all stages
should work without extra setup.

Default routing rules:

- All chat stages default to the first enabled chat model marked as default.
- `rag_embedding` defaults to the first enabled embedding model marked as
  default.
- If a specific stage has no mapping, fall back to the default chat or embedding
  model by capability.
- If fallback is unavailable, return the existing style of actionable error:
  ask the user to complete model settings.

## Data Model

Add provider profiles:

```text
user_model_providers
- id
- user_id
- name
- provider_type
- base_url
- api_key_encrypted
- api_key_preview
- is_enabled
- created_at
- updated_at
```

Add model records:

```text
user_ai_models
- id
- user_id
- provider_id
- display_name
- model_name
- capabilities_json
- context_window
- is_default_chat
- is_default_embedding
- is_enabled
- sort_order
- created_at
- updated_at
```

Add stage routing:

```text
user_ai_stage_routes
- user_id
- stage
- model_id
- created_at
- updated_at
```

Notes:

- `provider_type` should support `openai_compatible`, `ollama`, and `custom` in
  the first release. Existing provider detection logic can still help fetch
  model lists.
- `capabilities_json` should minimally support `chat` and `embedding`.
- `api_key_preview` stores only a masked suffix for UI display.
- The actual key should not be returned by GET APIs after it is saved.

## API Design

Keep `/api/llm-config` as the user model settings namespace.

Suggested endpoints:

```text
GET    /api/llm-config
PUT    /api/llm-config

GET    /api/llm-config/providers
POST   /api/llm-config/providers
PATCH  /api/llm-config/providers/{provider_id}
DELETE /api/llm-config/providers/{provider_id}

GET    /api/llm-config/models
POST   /api/llm-config/models
PATCH  /api/llm-config/models/{model_id}
DELETE /api/llm-config/models/{model_id}

POST   /api/llm-config/providers/{provider_id}/models/discover
POST   /api/llm-config/models/{model_id}/test

GET    /api/llm-config/stage-routes
PUT    /api/llm-config/stage-routes
POST   /api/llm-config/stage-routes/{stage}/test
```

Compatibility:

- `GET /api/llm-config` should return both the legacy fields and the new
  provider/model/stage route payload for one release cycle.
- `PUT /api/llm-config` should accept the legacy single-model payload and create
  or update a default provider/model/stage setup.

## Backend Routing Design

`LLMService` should accept a stage parameter on generation and embedding calls:

```python
await llm_service.get_llm_response(..., user_id=user_id, stage="chapter_writing")
await llm_service.generate(..., user_id=user_id, stage="summary_memory")
await llm_service.get_embedding(text, user_id=user_id, stage="rag_embedding")
```

Resolution order:

1. Request override model ID, if provided and owned by the user.
2. User stage route.
3. User default chat or embedding model by capability.
4. Legacy `llm_configs` fields during migration.
5. Error with actionable model-settings instructions.

The resolver should return:

```text
- provider_type
- base_url
- api_key
- model_name
- model_id
- stage
```

Provider construction should stay centralized in `LLMService` or a small helper
owned by the model config module. Individual feature services should only pass a
stage key, not manually inspect provider settings.

## Frontend Design

The personal model settings page should become a four-section settings surface:

1. Provider Profiles
   - Add provider.
   - Edit provider name, provider type, base URL, and API key.
   - Test provider connectivity.
   - Discover models from provider when supported.

2. Available Models
   - Show model records grouped by provider.
   - Allow manual model entry.
   - Mark capabilities: chat and embedding.
   - Mark default chat model and default embedding model.

3. Stage Defaults
   - Show curated stage groups: import and ideation, planning, writing, review,
     memory and RAG.
   - Each stage uses a model selector filtered by capability.
   - Empty route means fallback to the default model.

4. Test and Diagnostics
   - Test a provider.
   - Test a model.
   - Test a stage route.
   - Surface incomplete config warnings before users enter AI workflows.

High-frequency AI buttons can later expose a request-level model override:

- Generate blueprint.
- Generate chapter outline.
- Generate chapter.
- Review versions.
- Optimize chapter.

The override should default to the stage route and should not rewrite the saved
default unless the user explicitly saves it.

## Migration

On startup or migration:

1. For each existing `llm_configs` row with chat fields, create a provider named
   `Default Chat Provider`.
2. Create a chat model using `llm_provider_model`.
3. Mark it as `is_default_chat`.
4. Route all chat stages to that model only if explicit stage routes are empty.
5. For embedding fields, create either a separate provider or reuse the chat
   provider when URL and key match.
6. Create an embedding model using `embedding_provider_model`.
7. Mark it as `is_default_embedding`.
8. Route `rag_embedding` to the embedding model.

Keep legacy columns for one release cycle so rollback is possible.

## Error Handling

- Missing provider URL: report the provider name and ask the user to fill API
  URL.
- Missing API key: report the provider name and ask the user to fill API Key,
  except for local providers that allow keyless calls.
- Missing stage route: fall back to default model by capability.
- Missing default model: show the stage name and required capability.
- Disabled provider or model: reject route resolution and show which record is
  disabled.
- Failed model discovery: return an empty list plus a readable warning, without
  blocking manual model entry.

## Security

- Never return saved API keys in full from GET endpoints.
- Store only masked key previews for display.
- Keep provider/model records scoped by `user_id`.
- Validate model IDs in stage routes and request overrides against the current
  user.
- Do not allow admin APIs to read personal keys unless a separate, explicit
  admin-support feature is designed later.

## Testing

Backend tests:

- Migration from legacy `llm_configs` creates default provider, models, and
  stage routes.
- Stage resolver chooses explicit request override before saved stage route.
- Stage resolver falls back to default model when route is empty.
- Embedding stages reject chat-only models.
- Chat stages reject embedding-only models.
- Provider/model ownership is enforced.
- Legacy single-model payload still saves a usable default configuration.

Frontend tests or smoke checks:

- User can add provider, add model, and assign stage route.
- Model selectors filter by capability.
- Stage route page warns when no default model exists.
- API key is not displayed after save.
- Existing single-model config is shown as a default provider/model after
  migration.

Manual verification:

- Save two providers and route `chapter_writing` and `version_review` to
  different models.
- Generate a chapter and confirm backend logs show the writing model.
- Run version review and confirm backend logs show the review model.
- Trigger RAG embedding and confirm the embedding model is used.

## Rollout Plan

1. Add data model and migration while keeping legacy fields.
2. Add backend provider/model/stage-route APIs.
3. Add resolver support in `LLMService`.
4. Add stage keys to the highest-impact AI calls first:
   - concept conversation
   - world blueprint
   - chapter outline
   - chapter mission
   - chapter writing
   - version review
   - chapter optimization
   - summary memory
   - rag embedding
5. Add remaining stage keys across supporting services.
6. Replace `LLMSettings.vue` with the new settings surface.
7. Add request-level override only for high-frequency actions.
8. Remove legacy fallback after one stable release cycle.

## Future Extension

Project-level overrides can be added with:

```text
project_ai_stage_routes
- project_id
- stage
- model_id
```

Resolution order would become:

1. Request override.
2. Project stage route.
3. User stage route.
4. User default model.
5. Legacy fallback during migration.

This is intentionally excluded from the first release to keep the change focused.
