# Frontend Deep Restructure Design

## 1. Feature Summary

This design restructures the MoFeng frontend from a set of mostly independent route pages into a coherent writing workspace. The target user is a long-form fiction writer returning to the product repeatedly to continue projects, inspect story material, configure AI routes, and draft chapters without losing context.

The work should make the product feel like a calm writing desk: visible project state, predictable navigation, restrained visual hierarchy, and explicit model/configuration surfaces.

## 2. Primary User Action

The primary user action is to resume meaningful writing work quickly. From the first authenticated screen, the user should understand which project can be continued, where project material lives, where the writing desk is, and whether model configuration needs attention.

## 3. Design Direction

- Color strategy: Restrained.
- Theme scene sentence: A writer uses the app during a long daytime or evening desktop writing session, focused on continuity and trust, with enough ambient light for a paper-white workspace to feel natural.
- Anchor references: Notion for calm workspace structure, Linear for compact operational density, Google Docs for writing-surface trust.

The design follows `PRODUCT.md` and `DESIGN.md`: quiet, professional, dependable, and explicit about writing state and AI configuration. Blue is reserved for current navigation, focus, and the primary next action. Gradients, glassmorphism, decorative Google-color strips, hover zoom effects, and purple-blue AI spectacle are removed from operational screens.

## 4. Scope

- Fidelity: Production-ready UI direction.
- Breadth: Whole authenticated frontend surface, including workspace, project detail, writing desk, settings, and admin entry.
- Interactivity: Shipped-quality route and shell behavior, not a static mockup.
- Time intent: Deep restructure with compatibility redirects, implemented in stages to avoid breaking existing flows.

Authentication pages are included for visual normalization, but they do not need the authenticated app shell.

## 5. Layout Strategy

### App Shell

Authenticated routes should share a single `AppShell`:

- Top bar: current area, active project context when available, compact primary action.
- Side navigation: Workspace, Inspiration, Settings, Admin when allowed.
- Content region: stable soft-paper background with paper-white work surfaces.
- Mobile behavior: side navigation collapses behind a clear menu button; content remains first-class and avoids horizontal overflow.

The root `App.vue` should stop being only a `RouterView` wrapper for authenticated pages. It should route through either the authenticated shell or an auth-only layout.

### Route Model

New canonical route shape:

- `/workspace`: project dashboard, continuation entry, project list, create/import entry.
- `/projects/:id`: project archive, blueprint, world, characters, outline, chapters, emotion, foreshadowing.
- `/projects/:id/write`: focused writing desk for drafting and version work.
- `/inspiration`: inspiration creation flow.
- `/settings`: personal model settings and stage routing.
- `/admin`: admin console landing.
- `/admin/novels/:id`: admin project detail.

Compatibility redirects:

- `/detail/:id` redirects to `/projects/:id`.
- `/novel/:id` redirects to `/projects/:id/write`.
- `/admin/novel/:id` redirects to `/admin/novels/:id`.

### Workspace

`/workspace` becomes the product home, not a landing or entry-card page. It should prioritize:

1. Continue writing: the most recent or active project.
2. Project list: searchable, scannable, with status and last update.
3. New project actions: inspiration mode and import, presented as compact actions rather than oversized cards.
4. Configuration health: subtle notice only when model settings block generation.

### Project Detail

Project detail keeps the existing section model but makes it feel like the archive attached to a project:

- Left or top section navigation depending on viewport.
- Header shows title, project status, and direct "去写作台" action.
- Each section owns one clear content purpose.
- Loading, empty, and error states are section-local.

### Writing Desk

The writing desk is the most focused surface:

- Remove its local token override and gradient background.
- Keep a stable three-part structure: chapter sidebar, writing/content surface, contextual actions.
- Use paper-white content areas for long text.
- Preserve version selection and generation states, but normalize buttons, empty states, and dialogs.

### Settings

Settings remains a console-style product page:

- Keep the existing section navigation for LLM, embedding, and stage routing.
- Align the page shell with the authenticated app shell.
- Use explicit health/status panels only where they help the user verify model readiness.

### Admin

Admin can keep Naive UI for dense management tables, but the surrounding shell should match MoFeng:

- No blurred/glass header treatment.
- No unrelated teal/indigo gradients.
- Admin navigation stays compact and task-labeled.
- Admin uses the same surface, text, and border token vocabulary as user-facing pages.

## 6. Key States

- Default: user lands in `/workspace` and sees current writing context first.
- Empty workspace: user sees a concise first project action with no decorative card grid.
- Loading: page and section skeletons occupy the final layout, avoiding centered spinners where content will appear.
- Error: errors explain what failed and provide a retry or navigation recovery path.
- Model misconfiguration: generation-related surfaces show a restrained warning with a link to `/settings`.
- Project missing: project routes show a clear not-found state and a return to `/workspace`.
- Mobile: navigation collapses, touch targets remain at least 44px, and long project titles wrap without overlapping controls.
- Admin-only: admin nav appears only for authorized admin users.

## 7. Interaction Model

- Navigation is stable across authenticated pages. Users should not re-learn controls per route.
- Project cards/rows open project detail; the primary continue action opens the writing desk.
- Old route links continue to work through redirects during the transition.
- Destructive actions remain confirmation-gated.
- Hover states are subtle color or border shifts, not scale transforms.
- Focus states are visible for keyboard users.
- Motion stays between 150ms and 250ms and communicates state changes only.

## 8. Content Requirements

Use direct, task-oriented labels:

- "工作台" for the project dashboard.
- "小说档案" for project detail material.
- "写作台" for drafting.
- "模型设置" for personal model configuration.
- "管理" for admin.

Avoid marketing-style copy. Page headings should name the task or object, not sell the product. Empty states should tell the user the next recoverable action, for example "创建一个项目后，这里会显示最近写作进度。"

Dynamic content must handle:

- Project title lengths from short titles to long Chinese web-novel titles.
- Zero projects, one project, and many projects.
- Missing chapter content, failed generation, and multiple chapter versions.
- Admin lists with enough rows to require table density.

## 9. Implementation Boundaries

Recommended first implementation slice:

1. Normalize global CSS token ownership in `main.css`; stop importing or relying on Vue template `base.css` tokens.
2. Introduce shared authenticated layout components.
3. Update router canonical paths and compatibility redirects.
4. Refactor workspace, project detail shell, and writing desk to use the shared shell.
5. Normalize settings and admin shell treatment.
6. Do a final pass on auth pages and shared modal/alert surfaces.

Avoid backend changes unless route URLs are persisted server-side. No database migration is expected.

## 10. Verification Plan

Run these before claiming completion:

- `npm run type-check` in `frontend`.
- `npm run build` in `frontend`.
- Browser smoke test for `/workspace`, `/projects/:id`, `/projects/:id/write`, `/settings`, `/admin`, and compatibility redirects.
- Mobile viewport smoke test for workspace, writing desk, settings, and admin.
- Keyboard navigation check for primary nav, project actions, settings tabs, and dialogs.

## 11. Product Decisions

- "Continue writing" uses the most recently updated project for the first implementation slice. A later "recently opened" signal can replace it only after that data exists.
- `/inspiration` stays a top-level route for this restructure. It can later become a create-project mode under `/workspace` if the creation flow is redesigned.
- Admin project detail should reuse the same project detail shell in an admin mode where practical. If admin-only controls make reuse awkward, keep a thin admin wrapper while preserving the same route shape and visual vocabulary.

No blocking open questions remain for the implementation plan.
