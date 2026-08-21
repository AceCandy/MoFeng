# Frontend Quality Guidelines

> Cross-cutting rules: HTTP, routing, styling, forms, feedback, testing, and the AIMETA header.

---

## HTTP — go through `src/api/http.ts`

All outbound requests use `requestJson<T>` / `requestRaw` from `src/api/http.ts`. The wrapper applies a 15s timeout, abort handling, and error normalization into `HttpRequestError` (codes: `http` / `timeout` / `network` / `abort`), and reads FastAPI's `detail`/`message`/`error`/`msg`/`title`/`errors[]` for the message.

- Per-domain modules (`src/api/<domain>.ts`) build URLs on `API_BASE_URL` + `API_PREFIX` and call `requestJson`.
- Components consume data via `queries/` hooks, not direct API calls (read path).
- Set the `Authorization` header from `useAuthStore().token`; on 401, call `authStore.logout()` and `router.push('/login')`.

Bad example — reimplementing a fetch wrapper. `src/api/auth.ts` defines its own `authRequest` with timeout/abort logic instead of reusing `http.ts`. New modules reuse `http.ts`.

There is **no axios** in the project. Do not introduce it.

---

## Routing

All routes live in `src/router/index.ts` (single file). Conventions:

- `createWebHistory`.
- Lazy-load every route component via dynamic `import('../views/X.vue')`.
- Route `name`s are lowercase-kebab constants (`'workspace-entry'`, `'novel-workspace'`, `'project-detail'`, `'project-write'`, `'admin'`, `'settings'`, `'login'`, …).
- `meta`: `requiresAuth`, `requiresAdmin`, `layout: 'app' | 'auth'`, plus `label`/`description` for nav.
- Legacy redirect routes (`/detail/:id`, `/novel/:id`, `/admin/novel/:id`) exist for back-compat — keep them when you rename a path.
- `router.beforeEach` does auth gating **and** session recovery (`queryClient.fetchQuery(currentUserQueryOptions)` when a token exists but the user is missing), plus the admin password-reset redirect.

---

## Styling

Tailwind v4, CSS-first. `src/assets/main.css` is the entry: it pulls in Tailwind, then aggregates domain-split partials via `@import` (`./styles/tokens.css`, `./styles/elements/*`, `./styles/components/*`). `main.ts` imports only `main.css`.

```css
@import 'tailwindcss';
@import './styles/tokens.css';
@plugin "@tailwindcss/typography";
```

- Theme tokens are CSS custom properties under `--md-*` (design system) and `--ink-*` (ink style), with light/dark keyed on `:root[data-theme]`, defined in `src/assets/styles/tokens.css`. `src/main.ts` resolves theme preference from `localStorage['mofeng-theme-preference']` and sets `document.documentElement.dataset.theme`.
- Use `<style scoped>` per component; `:deep(...)` for Naive UI overrides (reference: `src/components/shared/MofengTable.vue`).
- Do not add a `tailwind.config.js`; v4 is config-less.

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
