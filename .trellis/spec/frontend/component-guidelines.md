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

Bad example — runtime-options form with `Array as () => T` casts, found in six legacy editor components (`FactionsEditor.vue`, `RelationshipsEditor.vue`, `KeyLocationsEditor.vue`, `ChapterOutlineEditor.vue`, `CharactersEditorEnhanced.vue`, `BlueprintEditModal.vue`):

```ts
// AVOID in new code
const props = defineProps({
  modelValue: { type: Array as () => Faction[], default: () => [] },
})
```

Do not copy this style into new components. If you edit one of those files for another reason, converting to the generic form is welcome but not required.

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
- Theme tokens are CSS custom properties in `src/assets/main.css` under `:root` / `:root[data-theme='light']` and `[data-theme='dark']`, namespaced `--md-*` (design system) and `--ink-*` (ink style). Prefer these tokens over hard-coded colors.
- Per-component `<style scoped>` is the norm (55 of 64 files). Use `:deep(...)` to override Naive UI internals — reference: `src/components/shared/MofengTable.vue` (`:deep(.n-data-table-th)`, `:deep(.n-data-table-td)`).

Bad example — writing into `src/assets/base.css`. It is a stub compat shim ("全局设计变量统一由 main.css 管理"); real tokens live in `main.css`.

---

## Composition with Naive UI providers

Naive's `NMessageProvider` / `NDialogProvider` are **not** mounted globally. The app-level feedback channel is the custom `useAlert` composable (`globalAlert` singleton rendered by `App.vue`). `NMessageProvider` is mounted only locally where `useMessage()` is genuinely needed (e.g. `src/views/AdminView.vue`).

Rule: for transient user feedback, use `useAlert()` (the project convention); reach for Naive `useMessage()`/`useDialog()` only inside a component that already mounts the corresponding provider.

---

## Anti-patterns to avoid

- Runtime-options `defineProps({...})` and string-array `defineEmits([...])` in new components.
- `any` in emit or prop types (see [type-safety](./type-safety.md)).
- Top-level `from 'naive-ui'` barrel imports in feature components.
- Hard-coded color literals; use the `--md-*` / `--ink-*` tokens.
- Adding global styles outside the `main.css` entry chain (or `App.vue`'s scoped toast block). Global styles live in `src/assets/styles/` partials (`tokens.css` / `elements/*` / `components/*`), aggregated by `main.css` via `@import`; new global styles go into the matching partial, never into a standalone file bypassing the entry.
