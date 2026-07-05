# Frontend State Management

> Pinia for client/UI state. TanStack Vue Query for server cache. Keep the boundary explicit.

---

## The boundary

| Store | Tool | What lives here |
|-------|------|-----------------|
| Client / UI state | **Pinia** (`src/stores/`) | auth token + user, conversation scratch state, panel visibility, alert queue |
| Server cache | **TanStack Vue Query** (`src/queries/`) | all domain data: novels, chapters, llm config, admin, tasks, updates |

Rule of thumb: if the value comes from the API and could be refetched, it belongs in Vue Query. If it is produced by the UI or survives only for the session, it belongs in Pinia (or local `ref`/`reactive` in the component).

Pinia is intentionally thin: `useAuthStore` is used in ~11 files; `useNovelStore` in only 3. Do not push server data into Pinia to "avoid a query".

---

## Pinia store shape

Both styles exist; pick per store.

**Options-store** — `src/stores/auth.ts` (config-shaped, with getters and actions):

```ts
export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('token') || (null as string | null),
    user: null as AuthUser | null,
  }),
  getters: {
    isAuthenticated: (state) => !!state.token,
    mustChangePassword: (state) => state.user?.must_change_password ?? false,
  },
  actions: { /* setToken, setUser, setSession, logout */ },
})
```

**Setup-store** — `src/stores/novel.ts` (composition style with `ref`/`function`):

```ts
export const useNovelStore = defineStore('novel', () => {
  const currentConversationState = ref<Record<string, unknown>>({})
  const isAssistantPanelVisible = ref(true)
  function resetConversationState() { currentConversationState.value = {} }
  return { currentConversationState, isAssistantPanelVisible, resetConversationState }
})
```

Conventions:

- Name: `useXxxStore`. Define in `src/stores/`.
- One store per file.
- Types: declare state field types explicitly (no implicit `any`).

---

## Auth token plumbing

`useAuthStore` is the single owner of the token + user. API modules in `src/api/` read `authStore.token` to set the `Authorization` header, and on a 401 they call `authStore.logout()` + `router.push('/login')`. New API modules should follow the same read-from-auth-store pattern instead of receiving the token as a parameter.

> Known smell: `auth.ts` writes `localStorage` *inside* store actions (`setToken` persists), mixing persistence with state mutation. The `novel.ts` store is pure in-memory. For new fields, prefer keeping the action a pure state update and persisting at a single, explicit boundary; do not spread `localStorage.setItem` across multiple actions.

---

## Server cache (Vue Query) — see [hook-guidelines](./hook-guidelines.md)

All server data goes through `useXxxQuery` / `useXxxMutation` hooks in `src/queries/`. Components read `data` / `isLoading` / `error`; they do not mirror server entities into Pinia.

---

## When to promote state to Pinia

Promote to a Pinia store only when **multiple unrelated components** must read or write the same client-side value (auth session, global panel toggle, alert queue). Otherwise keep it in the component (or lift to the nearest common parent). Do not promote server-fetched data into Pinia.

---

## Anti-patterns to avoid

- **Mirroring server data into Pinia.** Duplicates the Vue Query cache and drifts. Use `useXxxQuery`.
- **Two sources of truth for the same value** (e.g. Pinia + a sibling component's local `ref`).
- **`localStorage` writes scattered across actions.** Concentrate persistence.
- **Creating a store with a non-`useXxxStore` name** or storing server response interfaces in the store file (keep types in `src/api/`).
