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

## Scenario: cross-device semantic creation state

### 1. Scope / Trigger

Apply this contract when a creation surface persists semantic working position across
sessions or devices, or when a child component edits one of those persisted values.
Transient presentation state such as scroll position, drawers, dialogs, and request
buttons stays local.

### 2. Signatures

```text
GET /api/creation-contexts
PATCH /api/creation-contexts/{project_id}

surface: inspiration | archive | writing
chapter_number: positive integer | null
desk_section: content | versions | evaluation | null
inspiration_draft: string | null
inspiration_turn: non-negative integer | null
```

```vue
<WDWorkspace
  :active-section="activeDeskSection"
  @update:active-section="handleDeskSectionChange"
/>
```

### 3. Contracts

- The server record is the cross-device source of truth and stays in Vue Query. Do not
  mirror it into Pinia or give a child component a second writable copy.
- Explicit route state wins over the remote context; the remote context wins over the
  existing local default. Validate a restored chapter/section against current project
  data before applying it.
- The nearest parent that loads and persists a semantic value owns the writable `ref`.
  Children receive a prop and emit `update:<name>`; they must not reset that value as a
  side effect of another prop changing.
- `localStorage` protects only an unsynchronized inspiration draft. Scope it by user,
  project, and conversation turn, expire it after 24 hours, and delete it after a
  successful PATCH, account change, logout, or authoritative turn advance.
- Draft writes are serialized. Last successful write wins only within the same
  authoritative turn; an older turn is discarded and a future turn is rejected by the
  server without adding a conflict UI.

### 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Route contains a valid chapter | Use it and update the remote context after selection |
| Remote chapter/section is unavailable | Fall back to the first usable chapter and `content` |
| Child requests a section change | Parent validates, updates its ref, then PATCHes it |
| Local draft turn equals the restored turn | Restore locally and retry synchronization |
| Local or remote draft turn is older | Delete/ignore it; never place it in the new prompt |
| PATCH fails or browser is offline | Keep the scoped local backup and show non-blocking status |
| Account identity changes | Remove the prior account's local draft backups |

### 5. Good / Base / Bad Cases

- Good: a parent restores `versions`, passes it to the workspace, accepts the emitted
  change to `evaluation`, and persists the same value once.
- Base: no server context exists; the existing route/default behavior remains intact.
- Bad: the child writes a local `activeTab` during chapter changes while the parent
  separately owns `activeDeskSection`, or server data is copied into Pinia.

### 6. Tests Required

- Unit-test controlled ownership: parent prop changes update the child view, child
  interaction emits one update, and unrelated chapter changes do not mutate the prop.
- Cover explicit-route priority, remote restore, invalid chapter/section fallback, and
  a refresh/new-page read after a successful PATCH.
- Cover serialized draft writes, offline retention, successful cleanup, 24-hour expiry,
  account cleanup, same-turn last-write wins, and stale/future turn behavior.
- Run desktop and mobile E2E checks for the restored semantic state; do not assert
  pixel scroll or drawer state as cross-device behavior.

### 7. Wrong vs Correct

```ts
// Wrong: the child creates a competing source of truth.
watch(selectedChapter, () => {
  activeTab.value = 'content'
})

// Correct: the parent owns persistence; the child only requests a change.
const activeTab = computed({
  get: () => props.activeSection,
  set: (section) => emit('update:activeSection', section),
})
```

---

## When to promote state to Pinia

Promote to a Pinia store only when **multiple unrelated components** must read or write the same client-side value (auth session, global panel toggle, alert queue). Otherwise keep it in the component (or lift to the nearest common parent). Do not promote server-fetched data into Pinia.

---

## Anti-patterns to avoid

- **Mirroring server data into Pinia.** Duplicates the Vue Query cache and drifts. Use `useXxxQuery`.
- **Two sources of truth for the same value** (e.g. Pinia + a sibling component's local `ref`).
- **`localStorage` writes scattered across actions.** Concentrate persistence.
- **Creating a store with a non-`useXxxStore` name** or storing server response interfaces in the store file (keep types in `src/api/`).
