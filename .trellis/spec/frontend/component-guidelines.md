# Frontend Component Guidelines

> Single-File Components with `<script setup lang="ts">`, typed `defineProps` / `defineEmits`, Naive UI imported from deep paths.

---

## File shape

- SFC + `<script setup lang="ts">` is the universal pattern (63 of 64 `.vue` files). Template-only SFCs (no `<script>`) are acceptable only for trivial presentational wrappers like `src/components/shared/AuthLayout.vue`.
- Filenames are **PascalCase** for both `components/` and `views/`. Group components by feature under `components/<feature>/`.
- One default export (the SFC) per file.

---

## Props — use the TypeScript generic form

Declare an interface, then `defineProps<Props>()`. Use `withDefaults` for defaults.

Good example — `src/components/Tooltip.vue`:

```ts
interface Props {
  text?: string
  showDelay?: number
}
const props = defineProps<Props>()
```

Good example with defaults:

```ts
interface Props {
  modelValue: Faction[]
  disabled?: boolean
}
const props = withDefaults(defineProps<Props>(), {
  disabled: false,
})
```

Bad example — runtime-options form with `Array as () => T` casts:

```ts
// AVOID in new code
const props = defineProps({
  modelValue: { type: Array as () => Faction[], default: () => [] },
})
```

Do not copy this style into new components.

---

## Emits — use the call-signature generic

Good example — `src/components/ProjectCard.vue`:

```ts
const emit = defineEmits<{
  (e: 'detail', id: string): void
  (e: 'continue', project: NovelProjectSummary): void
  (e: 'delete', id: string): void
}>()
```

Bad example — untyped string-array form (`defineEmits(['update:modelValue'])`) paired with the runtime-options props above. New code uses the call-signature generic.

For two-way binding on a custom v-model, name the emit `update:modelValue` (or `update:<modelName>` for named models).

> **Warning**: Vue reactive proxies cannot always be passed directly to `structuredClone`; browsers may throw `DataCloneError`. When an editor deep-clones watched reactive values, catch that failure and use its existing JSON clone fallback before emitting the copied model.

---

## Naive UI — import from deep paths

Import components from `naive-ui/es/<group>` so Vite can tree-shake. Avoid the top-level barrel `from 'naive-ui'` (only `src/views/AdminView.vue` uses it today, for breadth).

Good example — `src/components/admin/PasswordManagement.vue`:

```ts
import { NForm, NFormItem } from 'naive-ui/es/form'
import { NInput } from 'naive-ui/es/input'
```

Most-used primitives (by frequency): `n-button`, `n-form-item`, `n-tag`, `n-input`, `n-space`, `n-alert`, `n-spin`, `n-form`. Reach for these before adding a new library component.

---

## Styling

- Tailwind v4 (`@import 'tailwindcss';` in `src/assets/main.css`; typography via `@plugin "@tailwindcss/typography"`). No `tailwind.config.js`.
- Theme tokens are CSS custom properties in `src/assets/styles/tokens.css` under `:root` / `:root[data-theme='light']`, namespaced `--md-*` (design system) and `--ink-*` (compatibility aliases). The product uses one cue-book light theme: `--md-stage` owns structural blue surfaces, `--md-surface*` owns cold-white work surfaces, `--md-cue` owns the single critical action, and `--md-note` is reserved for temporary prompts/focus. Do not add a dark branch, warm-paper tokens, or large near-black surfaces.
- Per-component `<style scoped>` is the norm (55 of 64 files). Use `:deep(...)` to override Naive UI internals — reference: `src/components/shared/MofengTable.vue` (`:deep(.n-data-table-th)`, `:deep(.n-data-table-td)`).
- Shared cue-book overrides live in the final `main.css` partial `world-class.css`. Auth-only overrides are loaded by the async `AuthLayout.vue` through `world-class-auth.css`; keep route-exclusive CSS in that chunk so the entry stylesheet stays within its hard budget, and do not duplicate those selectors in `world-class.css`.

---

## Composition with Naive UI providers

Naive's `NMessageProvider` / `NDialogProvider` are **not** mounted globally. The app-level feedback channel is the custom `useAlert` composable (`globalAlert` singleton rendered by `App.vue`). `NMessageProvider` is mounted only locally where `useMessage()` is genuinely needed (e.g. `src/views/AdminView.vue`).

Rule: for transient user feedback, use `useAlert()` (the project convention); reach for Naive `useMessage()`/`useDialog()` only inside a component that already mounts the corresponding provider.

## Accessibility contracts

- Shared modal containers put `role="dialog"`, `aria-modal="true"`, and the accessible name on the modal box rather than its overlay. Reuse `useDialogA11y` for initial focus, Tab trapping, Escape, focus restoration, reference-counted body scroll lock, and background `inert`. Nested dialogs increment the same background element's retain count; closing or unmounting restores its original `inert` value only after the final dialog releases it.
- Responsive drawers expose their state from the trigger with `aria-expanded` and `aria-controls`. Escape closes the active drawer and restores focus to that trigger; a click-to-dismiss overlay must be a named native button. Keep these contracts when changing drawer layout or breakpoints.
- Keep list semantics (`ol`/`ul` with `li`) separate from interaction semantics. Put a native `button type="button"` inside each interactive item; use `disabled` for unavailable items and `aria-current="step"` for the active pipeline step.
- Browser accessibility tests must wait for page and drawer opacity transitions to reach their stable state before running axe. Scope axe to the component or surface owned by the task so unrelated historical debt does not hide regressions in the changed area.

> **Naive DynamicTags gotcha**: `NDynamicTags.inputProps` is passed to the inner `NInput`, not directly to its native `<input>`. Native attributes therefore stay nested: `:input-props="{ inputProps: { 'aria-label': '标签名称' } }"`. Verify the rendered input DOM before flattening this object; the direct form does not label the actual text field.

## Durable workflow status rendering

- A parent Job `running` state must not make every semantic child node look active. Only the currently running remote activity gets motion; a system persistence node stays in a static waiting state while its preceding activity is running, and wait/interrupt nodes always use a static waiting state.
- Missing trace data is always waiting, never skipped. Render a skipped state only from an explicit backend fact, with a Chinese business reason on the node and in its accessible tooltip; translate backend reason codes at the workflow presentation boundary.
- Parallel projection branches cannot advance one another. Summary, memory, RAG, and foreshadowing derive progress only from traces in the same branch; the projection wait gate is not evidence that any branch has started or completed.
- Regression fixtures for projection status must combine the parent projection Job, its running child activity, the current wait gate, and untouched sibling branches. Assert that only the remote activity has running motion and untouched branches remain waiting.

---

## Anti-patterns to avoid

- Runtime-options `defineProps({...})` and string-array `defineEmits([...])` in new components.
- `any` in emit or prop types (see [type-safety](./type-safety.md)).
- Top-level `from 'naive-ui'` barrel imports in feature components.
- Hard-coded color literals; use the `--md-*` / `--ink-*` tokens.
- Adding global styles outside the `main.css` entry chain (or `App.vue`'s scoped toast block). Global styles live in `src/assets/styles/` partials (`tokens.css` / `elements/*` / `components/*`), aggregated by `main.css` via `@import`; new global styles go into the matching partial, never into a standalone file bypassing the entry.
