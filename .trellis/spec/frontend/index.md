# Frontend Development Guidelines

> Vue 3 + TypeScript SFCs under `frontend/src/`. Server cache via TanStack Vue Query, client state via Pinia, UI via Naive UI + Tailwind v4.

---

## At a glance

| Concern | Convention | Reference |
|---------|------------|-----------|
| Layout | `api / queries / composables / stores / components / views / router / utils` (no `types/`, `services/`, `pages/`) | [directory-structure](./directory-structure.md) |
| HTTP | Custom fetch wrapper `src/api/http.ts` (`requestJson`); no axios | [directory-structure](./directory-structure.md) · [quality-guidelines](./quality-guidelines.md) |
| Components | `<script setup lang="ts">`; generic `defineProps<Props>()` / call-signature `defineEmits`; Naive UI from deep paths | [component-guidelines](./component-guidelines.md) |
| Data fetching | UI hooks in `composables/`, server cache in `queries/` (Vue Query + key factories) | [hook-guidelines](./hook-guidelines.md) |
| State | Pinia = client/UI state; Vue Query = server cache; semantic state has one controlled owner | [state-management](./state-management.md) |
| Types | `strict`; migrated wire DTOs use generated aliases, legacy/domain types remain colocated; no `any` | [type-safety](./type-safety.md) |
| Quality | Manual form validation, `useAlert()` feedback, AIMETA header, `vue-tsc` + `vitest` | [quality-guidelines](./quality-guidelines.md) |

---

## Guidelines Index

| Guide | Description |
|-------|-------------|
| [Directory Structure](./directory-structure.md) | `src/` map, HTTP client, adding an API domain, AIMETA header |
| [Component Guidelines](./component-guidelines.md) | SFC shape, typed props/emits, Naive UI imports, scoped styling |
| [Hook Guidelines](./hook-guidelines.md) | `composables/` vs `queries/`, Vue Query key factories, QueryClient |
| [State Management](./state-management.md) | Pinia vs Vue Query boundary, store styles, auth token plumbing |
| [Type Safety](./type-safety.md) | strict tsconfig, colocated interfaces, `any` policy |
| [Generated Transport Contract](../backend/transport-contracts.md) | OpenAPI ownership, generated aliases, runtime decoder, and CI gates |
| [Quality Guidelines](./quality-guidelines.md) | HTTP, routing, Tailwind tokens, forms, testing, review checklist |
| [LLM Settings](./llm-settings.md) | PersonalModelRouting supplier/model capability isolation, TTS provider separation |
| [Chapter Reader](./chapter-reader.md) | useChapterReader TTS-model-vs-browser playback routing, model voice label, preview split |
| [Task Reminder Indicator](./task-reminders.md) | App-shell task status aggregation, terminal acknowledgement, and per-user browser persistence |

---

## Known cross-cutting debt (context, not a TODO list)

1. Remaining `any` debt is concentrated in a few legacy utilities/components outside the migrated blueprint editor chain; migrated blueprint and concept-conversation DTOs use generated aliases.
2. Two form-validation strategies coexist (manual vs Naive `:rules`); new forms use manual validation.

---

**Language**: documentation in English; user-facing strings and form messages are Chinese.
