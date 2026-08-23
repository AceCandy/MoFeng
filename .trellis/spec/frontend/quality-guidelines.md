# Frontend Quality Guidelines

> Cross-cutting rules: HTTP, routing, styling, forms, feedback, testing, and the AIMETA header.

---

## HTTP — go through `src/api/http.ts`

All outbound requests use `requestJson<T>` / `requestRaw` from `src/api/http.ts`. The wrapper applies a 15s timeout, abort handling, and error normalization into `HttpRequestError` (codes: `http` / `timeout` / `network` / `abort`), and reads FastAPI's `detail`/`message`/`error`/`msg`/`title`/`errors[]` for the message.

- Per-domain modules (`src/api/<domain>.ts`) build URLs on `API_BASE_URL` + `API_PREFIX` and call `requestJson`.
- Components consume data via `queries/` hooks, not direct API calls (read path).
- Set the `Authorization` header from `useAuthStore().token`; on 401, call `authStore.logout()` and `router.push('/login')`.

Bad example — reimplementing a domain-local fetch wrapper with timeout/abort logic. Domain modules reuse `http.ts`.

There is **no axios** in the project. Do not introduce it.

### Scenario: authentication API requests

#### 1. Scope / Trigger

Use this contract for login, registration, auth options, verification code, and current-user requests under `src/api/auth.ts`.

#### 2. Signatures

- `getAuthOptions(): Promise<AuthOptions>`
- `loginWithPassword(credentials): Promise<LoginResult>`
- `getCurrentUser(token): Promise<{ data: AuthUser; refreshedToken: string | null }>`
- `sendVerificationCode(email): Promise<void>`
- `registerUser(payload): Promise<void>`

#### 3. Contracts

- Use `requestJson` for `/options`, `/token`, `/send-code`, and `/users`.
- Use `requestRaw` only for `/users/me`, because it must read both JSON and `X-Token-Refresh`.
- `/users/me` receives its explicit token argument; do not substitute the Pinia-backed `authJson` / `authRaw` wrappers.
- Keep endpoint timeouts explicit: 10s for `/options` and `/users/me`; 15s for the other three calls.

#### 4. Validation & Error Matrix

| Condition | Result |
|-----------|--------|
| HTTP error with string `detail` | `HttpRequestError(code='http')`, preserving message/status/payload |
| HTTP error without detail | domain fallback plus status code |
| Network failure | `HttpRequestError(code='network')` |
| Timeout / external cancel | distinct `timeout` / `abort` codes |
| `/options` failure | the existing permissive auth-options fallback |
| `/token` without `access_token` | `Missing access token in login response` |

#### 5. Good / Base / Bad Cases

- Good: `/users/me` returns user JSON plus `X-Token-Refresh`; the query layer stores the refreshed token.
- Base: 204 from verification/registration resolves to `undefined` through `requestJson<void>`.
- Bad: a domain helper calls `fetch`, owns an AbortController, or parses HTTP error bodies again.

#### 6. Tests Required

`src/api/__tests__/auth.spec.ts` asserts URLs, methods, bodies, headers, timeouts, refresh headers, 204, fallback, server errors, network errors, and timeout abort. `http.spec.ts` owns the external-cancel assertion.

#### 7. Wrong vs Correct

```ts
// Wrong: forks the shared transport boundary.
await fetch(url, { signal: localController.signal })

// Correct: use JSON by default; use raw only when response metadata is required.
await requestJson<AuthOptions>(url, { timeoutMs: 10_000 })
const response = await requestRaw(meUrl, {
  headers: { Authorization: `Bearer ${token}` },
  timeoutMs: 10_000,
})
```

---

## Routing

All routes live in `src/router/index.ts` (single file). Conventions:

- `createWebHistory`.
- Lazy-load every route component via dynamic `import('../views/X.vue')`.
- Route `name`s are lowercase-kebab constants (`'workspace-entry'`, `'novel-workspace'`, `'project-detail'`, `'project-write'`, `'admin'`, `'settings'`, `'login'`, …).
- `meta`: `requiresAuth`, `requiresAdmin`, `layout: 'app' | 'auth'`, plus `label`/`description` for nav.
- Legacy redirect routes (`/detail/:id`, `/novel/:id`, `/admin/novel/:id`) exist for back-compat — keep them when you rename a path.
- `router.beforeEach` does auth gating **and** session recovery (`queryClient.fetchQuery(currentUserQueryOptions)` when a token exists but the user is missing), plus the admin password-reset redirect.
- Vue Router 5 guards use return-value semantics: return a route location to redirect and `undefined` to continue. Do not add the deprecated `next()` callback; this keeps guards compatible with its planned removal.

```ts
router.beforeEach(async (to) => {
  if (to.meta.requiresAuth && !authStore.isAuthenticated) return '/login'
  return undefined
})
```

---

## Styling

Tailwind v4, CSS-first. `src/assets/main.css` is the entry: it pulls in Tailwind, then aggregates domain-split partials via `@import` (`./styles/tokens.css`, `./styles/elements/*`, `./styles/components/*`). `main.ts` imports only `main.css`.

```css
@import 'tailwindcss';
@import './styles/tokens.css';
@plugin "@tailwindcss/typography";
```

- Theme tokens are CSS custom properties under `--md-*` (design system) and `--ink-*` (ink style), defined in `src/assets/styles/tokens.css`. `index.html` fixes `data-theme="light"` before the app boots; do not add runtime theme preference, system-color listeners, or dark-theme branches.
- Use `<style scoped>` per component; `:deep(...)` for Naive UI overrides (reference: `src/components/shared/MofengTable.vue`).
- Do not add a `tailwind.config.js`; v4 is config-less.

### Bundle-size changes

- Use `npm run build-only` followed by `npm run build:budget`; compare totals from the same
  `dist/.vite/manifest.json` chain. `manualChunks` changes chunk boundaries, not total gzip, so it
  is not a fix for a total-size warning.
- Import only the TipTap extensions a surface uses. Disabling StarterKit extensions at runtime does
  not remove StarterKit's top-level imports from Rollup's module graph.
- Delete global CSS only after confirming the project-owned selector has no runtime source reference
  and checking the affected surface in a browser. Do not classify third-party runtime selectors
  (for example Naive UI `.n-*` classes) as dead from a source-literal scan.

```ts
// Wrong: unused StarterKit extensions still enter the module graph.
StarterKit.configure({ heading: false, bulletList: false })

// Correct: register the schema and behavior this editor actually uses.
extensions: [Document, Paragraph, Text, HardBreak, UndoRedo, MiaohongMark]
```

---

## Forms and validation

Two strategies coexist. For new code, follow the **manual validation** pattern (the dominant style):

- `reactive` form state + a `ref<string | null>` error holder.
- Validate in the submit handler before calling the mutation; render `formError.value` near the field.
- Reference: `src/components/admin/PasswordManagement.vue`.

```ts
const handleSubmit = async () => {
  formError.value = null
  changePasswordMutation.reset()
  if (!form.oldPassword.trim() || !form.newPassword.trim()) {
    formError.value = '请填写完整的密码信息'; return
  }
  if (form.newPassword.length < 8) { formError.value = '新密码长度需至少 8 位'; return }
  ...
}
```

Naive UI `:rules` + `formRef.value.validate()` is used in exactly one place (`src/components/admin/UserManagement.vue`). Do not mix the two within the same form.

---

## User feedback

Use the project's custom alert channel — `useAlert()` / `globalAlert` — for transient notifications (rendered by `App.vue`). Naive `useMessage()` / `useDialog()` only inside a component that already mounts the corresponding provider (e.g. `src/views/AdminView.vue`).

---

## Testing

- Runner: `vitest` (`npm run test:unit`). Config excluded from the build tsconfig.
- Colocate tests as `src/**/__tests__/*` or alongside the module.
- Prefer testing composables and pure utils (`src/utils/`) and query/mutation behavior over snapshot tests.

### Scenario: Node and build-toolchain upgrades

#### 1. Scope / Trigger

Use this contract whenever the frontend Node baseline or Vite/Vitest/jsdom/TypeScript toolchain changes.

#### 2. Signatures

- Runtime baseline: `frontend/package.json#engines.node`.
- Node consumers: frontend CI workflows, transport-contract CI, Docker frontend builder, `@types/node`, and `@tsconfig/node*`.
- Required commands run from `frontend/`: `npm ci`, `npm ls --depth=0`, audit, API check, type-check, unit tests, lint, and build.

#### 3. Contracts

- Keep the Node major aligned across runtime declarations, CI, Docker, Node types, and the Node tsconfig package.
- Use npm's normal peer resolution; do not bypass incompatibilities with `--force` or `--legacy-peer-deps`.
- Keep TypeScript at the newest version accepted by every installed peer dependency, not merely the registry latest.
- Preserve strict checking and the existing bundle warning/hard limits.

#### 4. Validation & Error Matrix

| Condition | Result |
|-----------|--------|
| `npm ci` or `npm ls` reports peer/engine conflicts | Stop; adjust the incompatible version instead of bypassing resolution |
| A toolchain latest requires a newer Node patch | Raise every Node consumer to that same minimum patch |
| TypeScript latest falls outside an installed peer range | Keep the newest compatible TypeScript and record the blocker |
| Build exceeds a bundle hard limit | Upgrade is blocked; a warning-only threshold is recorded as remaining risk |

#### 5. Good / Base / Bad Cases

- Good: Node runtime, types, CI, and Docker share one major; install and all quality gates pass.
- Base: an application framework major remains outdated because it belongs to a separate migration task.
- Bad: only `package.json` is updated, CI remains on an older Node, or peer conflicts are suppressed.

#### 6. Tests Required

- Assert reproducible install, zero audit findings, valid top-level dependency tree, Vite config loading, API generation consistency, type-check, complete unit suite, lint, and bundle budget.
- Start the Vite dev server and smoke-test login, the authenticated AppShell, and the writing-desk editor; close all started services.
- Confirm the selected Docker Node tag has a published manifest.

#### 7. Wrong vs Correct

```jsonc
// Wrong: declarations drift from CI/Docker and peer conflicts are ignored.
{ "engines": { "node": ">=24" }, "scripts": { "install": "npm ci --legacy-peer-deps" } }

// Correct: pin the shared minimum and let npm enforce the dependency graph.
{ "engines": { "node": "^24.15.0" } }
```

### Node-side config tests

Vitest runs in jsdom and the shared setup requires `window`, while Vite config loading requires
Node-native globals and a file-based `import.meta.url`. Do not inspect config source text, switch a
single spec to the Node environment, or import `vite.config.ts` through jsdom. Run Vite's config
loader in an isolated Node child process and assert the returned runtime behavior instead:

```ts
execFileSync(process.execPath, ['--input-type=module', '--eval', `
  const { loadConfigFromFile } = await import('vite')
  const loaded = await loadConfigFromFile(configEnv, 'vite.config.ts', process.cwd())
  if (!loaded) throw new Error('Vite config did not load')
`], { cwd: process.cwd() })
```

### Motion verification

Motion changes require real-browser evidence. An `animation` declaration or one static screenshot
does not prove that users can see the effect.

- Verify that the animation timeline advances on the intended element or pseudo-element.
- Compare at least two time-separated frames on desktop and mobile; confirm direction as well as movement.
- Emulate `prefers-reduced-motion: reduce`: continuous animations must stop while a static state marker remains.
- For progress timelines, animate the connector entering the current node, not the connector leaving it.

```ts
const activeAnimations = root.getAnimations({ subtree: true })
expect(activeAnimations.some((animation) => animation.currentTime !== null)).toBe(true)
```

---

## AIMETA header (project convention)

Every TS/Vue module starts with an `AIMETA` comment on line 1. Keep it accurate; do not leave stale claims (e.g. `D=axios` on a fetch-based file). See [directory-structure](./directory-structure.md).

---

## Forbidden patterns

- `fetch` / `XMLHttpRequest` called directly outside `src/api/http.ts`.
- Reimplementing an HTTP/timeout/abort wrapper.
- `axios` (not used in this project).
- `any` in new API signatures, props, emits, or `useQuery<T>` (see [type-safety](./type-safety.md)).
- Runtime-options `defineProps({...})` / string-array `defineEmits([...])` in new components.
- Top-level `from 'naive-ui'` barrel imports in feature components.
- Hard-coded colors instead of `--md-*` / `--ink-*` tokens.
- Mixing manual validation and Naive `:rules` in the same form.
- Creating `types/`, `services/`, `pages/`, or `hooks/` directories.

---

## Review checklist

- [ ] New file has an accurate `AIMETA` header.
- [ ] Reads go through `queries/` hooks; writes through `useMutation` + typed `src/api/*`.
- [ ] No direct `fetch`; no `axios`.
- [ ] Props/emits use generic forms; no `any`.
- [ ] `useQuery<T>` / `useMutation<T>` typed with real interfaces.
- [ ] Tailwind tokens used; `<style scoped>` with `:deep()` for Naive UI.
- [ ] Feedback via `useAlert()` (or Naive provider only where mounted).
- [ ] Route (if any) is lazy-loaded, named lowercase-kebab, with correct `meta`.
- [ ] `npm run type-check` and `npm run test:unit` pass.
