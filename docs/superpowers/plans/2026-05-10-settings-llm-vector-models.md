# Settings LLM And Vector Models Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the settings model console with three focused sections: LLM models, vector model, and AI stage routing.

**Architecture:** Keep providers as the source of all models. LLM models are chat-capable records with exactly one primary model. Vector model is embedding-capable and globally single-selected. Legacy basic LLM config is removed from the UI and no longer used as backend fallback.

**Tech Stack:** Vue 3 SFC, TypeScript, scoped CSS, existing FastAPI services, pytest static/service guards, Vite build.

---

### Task 1: Guard The New Console Shape

**Files:**
- Modify: `backend/tests/test_settings_console_static.py`
- Modify: `backend/tests/test_llm_service.py`
- Modify: `backend/tests/test_llm_config_routes_static.py`

- [ ] Update static tests so `SettingsView.vue` only declares `llm`, `embedding`, and `routes`.
- [ ] Update static tests so `LLMSettings` is no longer rendered by `/settings`.
- [ ] Update static tests so `PersonalModelRouting.vue` exposes LLM and embedding model UI labels.
- [ ] Update service tests so legacy LLM config fallback is rejected when no routed/default model exists.
- [ ] Run the changed tests and verify they fail before implementation.

### Task 2: Add Provider-Based Model Fetching

**Files:**
- Modify: `backend/app/schemas/llm_config.py`
- Modify: `backend/app/api/routers/llm_config.py`
- Modify: `backend/app/services/llm_config_service.py`
- Modify: `frontend/src/api/llm.ts`

- [ ] Add a provider-owned model-list endpoint that uses the saved provider URL and API key.
- [ ] Keep the old transient `/models` endpoint only for any remaining non-settings callers.
- [ ] Add frontend API helper `getProviderModels(providerId)`.

### Task 3: Rebuild Settings UI

**Files:**
- Modify: `frontend/src/views/SettingsView.vue`
- Modify: `frontend/src/components/llm-settings/PersonalModelRouting.vue`

- [ ] Replace settings sections with `LLM 模型`, `向量模型`, and `AI 阶段路由`.
- [ ] Remove `概览`, `可用模型`, and `基础 LLM 配置`.
- [ ] Remove the repeated `个人模型路由` header.
- [ ] Render providers as cards with clear add/edit provider states.
- [ ] Let each provider fetch models and enable LLM chat models.
- [ ] Enforce exactly one primary LLM model.
- [ ] Let vector model selection use providers but allow only one selected embedding model.
- [ ] Restrict stage routing choices to enabled LLM models.

### Task 4: Verify

**Files:**
- No production edits.

- [ ] Run `pytest backend/tests/test_settings_console_static.py backend/tests/test_llm_service.py backend/tests/test_llm_config_routes_static.py -q`.
- [ ] Run `npm run build` from `frontend/`.
- [ ] If browser verification is needed, start local services only for verification and close them immediately after.
