# Frontend Directory Structure

> Vue 3 + TypeScript SFC app under `frontend/src/`. Server cache via TanStack Vue Query, client state via Pinia, UI via Naive UI + Tailwind v4.

---

## Stack

Vue 3.5, TypeScript ~5.8 (`strict`), Vite 7, Pinia 3, Vue Router 4.5, `@tanstack/vue-query` 5.100, Naive UI 2.39, Tailwind 4.1 (+ `@tailwindcss/typography`), Chart.js, `marked` + `dompurify`. **No axios** — a custom fetch wrapper is the HTTP client. See `frontend/package.json`.

---

## `src/` layout

```
src/
├── api/         fetch wrapper + per-domain API modules (typed functions / static classes)
├── assets/      CSS (main.css, base.css shim, blueprint.css) + fonts/images
├── components/  PascalCase .vue, grouped by feature (admin/, novel-detail/, writing-desk/, shared/, llm-settings/)
├── composables/ UI-only helpers, useXxx.ts (alert, dialog a11y, responsive)
├── constants/   plain TS constants (promptUsage, responsive tiers)
├── lib/         cross-cutting singletons (queryClient.ts, chartLine.ts)
├── queries/     TanStack Vue Query hooks + query-key factories, one file per domain
├── router/      index.ts only (all routes)
├── stores/      Pinia stores (auth.ts, novel.ts)
├── utils/       pure helpers (chapter, date, text)
└── views/       route-level pages (PascalCase .vue)
```

Directories that **do not exist** — do not invent them or route new code into them: `pages/`, `hooks/`, `services/`, `types/`, `context/`. There is intentionally **no central `types/` dir**; types live next to their API module (see [type-safety](./type-safety.md)).

The data-fetching split is deliberate:

| Dir | Purpose |
|-----|---------|
| `composables/` | UI-only stateful helpers (`useAlert`, `useDialogA11y`, `useResponsiveViewport`) |
| `queries/` | Server-cache hooks (`useXxxQuery` / `useXxxMutation`) + `xxxQueryKeys` factories |

Do not put `useQuery` hooks in `composables/`, and do not put UI helpers in `queries/`.

---

## HTTP client

Single fetch wrapper at `src/api/http.ts`. Symbols: `requestJson<T>`, `requestRaw`, `HttpRequestError`, `HttpRequestOptions`. Base path constants in `src/api/base.ts` (`API_BASE_URL`, `API_PREFIX='/api'`).

```ts
export const requestJson = async <T>(url: string, options: HttpRequestOptions = {}): Promise<T> => {
  const response = await requestRaw(url, options)
  const payload = await readResponsePayload(response)
  return (payload ?? undefined) as T
}
```

`requestRaw` normalizes transport failures into `HttpRequestError` with `code: 'http' | 'timeout' | 'network' | 'abort'`, applies a default 15s timeout, and reads the FastAPI `detail`/`message`/`error`/`msg`/`title`/`errors[]` fields for the error message. Per-domain modules (`src/api/novel.ts`, `llm.ts`, `tasks.ts`, …) build URLs on top of `requestJson`; they do not call `fetch` directly.

---

## AIMETA file header (project convention)

Every TS/Vue module starts with an `AIMETA` comment line on line 1 describing purpose, responsibility, entity, layer, archetype, deps, and state. Keep it accurate when a file's role changes.

```ts
// AIMETA P=HTTP请求工具_超时与错误归一化|R=统一fetch错误处理及JSON解析|NR=不含业务API路径|E=api:http|X=internal|A=requestJson_requestRaw|D=fetch|S=net|RD=./README.ai
```

New files should include this header.

---

## Adding a new API domain

1. `src/api/<domain>.ts` — typed interface for response shapes + an API object (or namespace) of methods calling `requestJson<T>`. Reference: `src/api/tasks.ts`.
2. `src/queries/<domain>.ts` — `xxxQueryKeys` factory + `useXxxQuery` / `useXxxMutation` hooks. Reference: `src/queries/tasks.ts`.
3. Components consume the hooks; they do not call `src/api/*` directly except in mutations' `mutationFn`.

---

## Anti-patterns to avoid

- **Calling `fetch` directly** in an API module or component. Go through `requestJson` / `requestRaw` so error normalization, timeout, and abort are consistent.
- **Reimplementing an HTTP wrapper.** `src/api/auth.ts` defines its own `authRequest` fetch/abort/timeout path instead of reusing `http.ts` — legacy; new code reuses `http.ts`.
- **Misleading `AIMETA` headers.** `src/api/novel.ts` and `src/api/llm.ts` declare `D=axios`; the code is fetch. Keep headers truthful.
- **Creating `types/`, `services/`, `pages/`, or `hooks/` dirs.** They break the established split.
- **Importing Naive UI from the top-level barrel** (`from 'naive-ui'`) in feature components — use deep paths (`naive-ui/es/...`) for tree-shaking (see [component-guidelines](./component-guidelines.md)).
