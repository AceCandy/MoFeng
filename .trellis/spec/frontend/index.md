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
| State | Pinia = client/UI state; Vue Query = server cache | [state-management](./state-management.md) |
| Types | `strict`; hand-authored interfaces colocated with `src/api/*`; no `any` | [type-safety](./type-safety.md) |
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
| [Quality Guidelines](./quality-guidelines.md) | HTTP, routing, Tailwind tokens, forms, testing, review checklist |
| [LLM Settings](./llm-settings.md) | PersonalModelRouting supplier/model capability isolation, TTS provider separation |

---

## Known cross-cutting debt (context, not a TODO list)

1. Six legacy editor components use runtime-options `defineProps({...})` + untyped `defineEmits([...])`. New components use the generic forms.
2. `src/api/auth.ts` reimplements a fetch wrapper instead of reusing `src/api/http.ts`.
3. ~49 `any` occurrences concentrated in `src/api/novel.ts` and a few components.
4. Two form-validation strategies coexist (manual vs Naive `:rules`); new forms use manual validation.
5. `src/assets/base.css` is a dead compat shim; real tokens live in `main.css`.

---

**Language**: documentation in English; user-facing strings and form messages are Chinese.
