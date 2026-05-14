# Admin Domain Polish Design

## Goal

Polish the full admin domain to flagship quality while keeping it visually and
behaviorally consistent with the rest of MoFeng.

Scope includes:

- `/admin` control console.
- Admin tabs: statistics, users, prompts, novels, update logs, system settings,
  and password management.
- `/admin/novels/:id` admin project detail.

The admin domain should feel like a trusted operating surface inside the same
quiet writing workspace, not a separate enterprise dashboard.

## Product Context

MoFeng is a quiet, professional writing workspace for long-form fiction.
Admin users maintain users, prompts, projects, logs, and system configuration so
writers can keep creative momentum.

The admin surface is task-first. It should be denser than author-facing pages,
but still use the same paper surfaces, clear blue action color, restrained
motion, and direct Chinese copy used by the workspace and settings pages.

Physical scene: an administrator checks system state on a desktop monitor during
normal work hours, then makes focused fixes to prompts, users, or configuration.
The interface should be calm, explicit, and easy to verify.

## Current Drift

The current admin domain works, but it drifts from the product surface in three
ways.

1. Conceptual misalignment

   `AdminView.vue` uses a nested Naive UI layout with its own sider and header.
   Because the whole app already uses `AppShell.vue`, the admin page feels like
   an app inside another app.

2. One-off implementation

   Admin navigation uses emoji icons. Some child panels use custom gradients,
   hard-coded gray/blue colors, and local spacing values instead of the existing
   `--md-*` design tokens.

3. Flow mismatch

   The settings page already uses a compact segmented console pattern. The admin
   page should use a similar shape: one task-labeled navigation surface, one
   active content panel, and predictable toolbar behavior.

This is not a missing-token problem. `main.css` already has enough Material
tokens for this polish pass.

## Design Direction

Use a restrained product UI strategy.

- Theme: light paper surface, aligned with workspace and settings.
- Color: blue only for active selection, primary actions, focus, and important
  state.
- Density: operational and scan-friendly, with clear row height and stable
  toolbar placement.
- Motion: 150 to 250 ms state transitions only. No decorative page-load
  choreography.
- Icons: inline SVG icons matching `AppShell.vue` and `NovelDetailShell.vue`.
  Do not use emoji in navigation or statistic tiles.

## Admin Console Shape

`AdminView.vue` should become an admin console inside the existing app shell.

Structure:

1. Intro strip
   - Compact title: `管理控制台`.
   - Short direct description: `维护用户、提示词、项目、更新日志和系统配置。`
   - Context chips for active section and admin-only access.
   - A `返回工作台` action using the existing button vocabulary.

2. Section navigation
   - Use a segmented or rail-like admin nav, visually related to
     `SettingsView.vue`.
   - Include section label and short supporting text on desktop.
   - Collapse to horizontally scrollable segmented controls or a compact grid on
     mobile.
   - Store selected tab in `?tab=` as it does today.

3. Content panel
   - One visible active panel.
   - Use `--md-surface`, `--md-outline-variant`, `--md-radius-lg/xl`, and
     `--md-spacing-*`.
   - Avoid nested page-level cards. Use cards only for repeated rows, mobile
     cards, modals, or truly framed tools.

## Shared Admin Panel Pattern

Each admin tab should follow a common shell:

- Header row: title, optional subtitle, count chip, and actions.
- Toolbar row: search, filters, refresh, or create actions where needed.
- State row: error, warning, empty, or loading state.
- Data area: table, split editor, list, or form.

Copy should name the task directly:

- `数据总览`
- `用户管理`
- `提示词管理`
- `小说项目`
- `更新日志`
- `系统配置`
- `安全中心`

Avoid redundant marketing copy. Use helper text only when it prevents mistakes.

## Tab-Specific Design

### Statistics

Replace emoji statistic tiles with compact metric tiles using SVG icons and
semantic labels.

Use three equal tiles on desktop and stacked tiles on mobile:

- `小说总数`
- `用户总数`
- `API 请求总数`

The tile treatment should use borders and quiet fills, not purple gradients.
Loading should keep the metric area stable.

### Users

Keep the data table, but align header and toolbar with the shared pattern.

Required refinements:

- Search field and actions should wrap cleanly on mobile.
- `新建用户` remains the primary action.
- `刷新` is secondary or text-level.
- Permission and status tags should keep semantic color only for real state.
- Destructive delete remains protected by confirmation.

### Prompts

Keep the split list/editor model because it fits the task.

Required refinements:

- Left list should use tokenized border, surface, hover, focus, and selected
  states.
- Prompt list items should not lift or use custom shadow on hover.
- Active prompt state should use `--md-primary-container`.
- Editor actions stay at the bottom of the active form.
- Mobile stacks list above editor with bounded height.

### Novels

Keep table on desktop and cards on mobile.

Required refinements:

- Title cell, owner, progress, and date colors use `--md-on-surface` tokens.
- Count chip aligns with shared header pattern.
- Detail action uses the same secondary action vocabulary as other panels.
- Empty state tells the admin there are no projects to inspect.

### Update Logs

Keep inline publishing because it is a short, local task.

Required refinements:

- Publishing form should sit in a framed tool section, not a decorative card.
- Log entries use bordered paper rows, not green gradients.
- Pinned state can use warning container only when the log is pinned.
- Delete and pin controls stay local to each entry.

### System Settings

Preserve the managed quick cards because they reduce configuration risk.

Required refinements:

- Replace teal/white gradient overview with a quiet information strip.
- Health items use tokenized surface and border.
- `code` chips use neutral or primary container tokens.
- Warning about deleting config remains prominent and recoverable.
- Table managed rows use a subtle selected-state tint from `--md-primary`.

### Security Center

Keep the single-column password form.

Required refinements:

- Align card width, title, warning, and actions with the shared admin shell.
- Keep warning state explicit when default password reset is required.
- The submit button remains the only primary action.

## Admin Project Detail

`AdminNovelDetail.vue` already reuses `NovelDetailShell.vue`, which is the right
content strategy.

The polish target is the wrapper behavior:

- Admin detail should not feel like a second full-screen app nested inside
  `AppShell.vue`.
- The detail surface should share the same paper background and spacing as the
  user project detail.
- Admin mode should keep read-only content behavior.
- `返回列表` in admin mode should return to `/admin?tab=novels`.
- The top area should clearly identify admin read-only context without adding
  another large banner.

Implementation can update `NovelDetailShell.vue` with an admin-friendly layout
mode if needed, but it should preserve the user detail route behavior.

## Responsiveness

Desktop:

- Admin console width aligns with `.app-page`.
- Navigation and content fit inside the existing app shell.
- Dense tables remain readable.

Tablet:

- Admin navigation wraps or scrolls without text overlap.
- Toolbars wrap into two rows if needed.

Mobile:

- Touch targets are at least 44px.
- No horizontal page scroll.
- Tables either remain scroll-contained or switch to existing mobile card
  treatment where already implemented.
- Prompt editor stacks list and editor vertically.

## Accessibility

Required:

- All custom buttons have visible `:focus-visible`.
- SVG icons are decorative with `aria-hidden="true"` unless they provide the
  only label.
- Navigation exposes active section through `aria-current`.
- Loading, empty, error, and destructive confirmation states remain explicit.
- Critical state is not conveyed by color alone.

## Implementation Boundaries

Likely frontend files:

- `frontend/src/views/AdminView.vue`
- `frontend/src/views/AdminNovelDetail.vue`
- `frontend/src/components/shared/NovelDetailShell.vue`
- `frontend/src/components/admin/Statistics.vue`
- `frontend/src/components/admin/UserManagement.vue`
- `frontend/src/components/admin/PromptManagement.vue`
- `frontend/src/components/admin/NovelManagement.vue`
- `frontend/src/components/admin/UpdateLogManagement.vue`
- `frontend/src/components/admin/SettingsManagement.vue`
- `frontend/src/components/admin/PasswordManagement.vue`
- `frontend/src/assets/main.css` only if shared admin utilities are clearly
  useful across multiple admin panels.

Avoid backend changes unless a UI bug proves an API contract problem.

## Verification Plan

Run static and build checks:

- `cd frontend && npm run build`

Run browser smoke checks after implementation:

- `/admin?tab=statistics`
- `/admin?tab=users`
- `/admin?tab=prompts`
- `/admin?tab=novels`
- `/admin?tab=logs`
- `/admin?tab=settings`
- `/admin?tab=password`
- `/admin/novels/:id` when a project id is available.

Viewport checks:

- Desktop around 1440px width.
- Tablet around 900px width.
- Mobile around 390px width.

Manual behavior checks:

- Tab query stays in sync.
- Back from admin project detail returns to the admin novel list.
- Keyboard focus is visible on admin navigation and main actions.
- Error, loading, and empty states remain reachable in code.

## Out of Scope

- Backend API changes.
- New global dependency.
- Full replacement of Naive UI tables, forms, modals, or tags.
- Rewriting user-facing workspace, settings, or project detail outside what is
  needed for admin detail layout consistency.
