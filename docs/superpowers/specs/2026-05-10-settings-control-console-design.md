# Settings Control Console Design

## Goal

Improve the Settings page layout by turning it from one long stacked form into a control-console style page.

The approved direction is:

- Desktop: left navigation plus right detail panel.
- Mobile: compact top navigation plus single-column detail.
- Keep current API contracts, save behavior, and data structures unchanged.

## Current Problem

`SettingsView.vue` owns the Settings route shell.
`LLMSettings.vue` renders the legacy main model and embedding model form.
`PersonalModelRouting.vue` renders provider management, user model management, and AI stage routing.

These sections currently sit in one vertical content stream. That makes the page feel heavy and gives weak priority cues:

- Version/status information sits near primary configuration.
- Personal model routing and legacy LLM config feel like one form even though they serve different workflows.
- Provider/model/stage-routing controls are related, but visually compete with each other.
- Users cannot quickly jump to the part they want to maintain.

## Proposed Layout

The Settings page should become a settings console with one persistent navigation surface and one active content surface.

Navigation items:

1. Overview
2. Providers & API Key
3. Available Models
4. AI Stage Routing
5. Basic LLM Config

Desktop layout:

```text
+-------------------------------------------------------------+
| Back  Model Settings                         Version Status  |
+----------------------+--------------------------------------+
| Overview             | Active Panel                         |
| Providers & API Key  |                                      |
| Available Models     |                                      |
| AI Stage Routing     |                                      |
| Basic LLM Config     |                                      |
+----------------------+--------------------------------------+
```

Mobile layout:

```text
+--------------------------------------+
| Back  Model Settings                 |
| Version Status                       |
+--------------------------------------+
| Overview | Providers | Models | ...  |
+--------------------------------------+
| Active Panel                         |
+--------------------------------------+
```

## Component Shape

Keep the change focused on presentation and local component boundaries.

`SettingsView.vue`:

- Keeps the route-level page shell.
- Keeps version status loading and inspiration-mode redirect behavior.
- Owns active settings section state.
- Renders the left/top section navigation.
- Passes no new backend data contract.

`LLMSettings.vue`:

- Remains the owner of legacy LLM config form state and save/delete behavior.
- Should expose presentation hooks or props only if needed to hide its internal header when embedded in the new panel.
- Should not change payload shape for `createOrUpdateLLMConfig`.

`PersonalModelRouting.vue`:

- Remains the owner of provider, model, and stage-route state.
- Should allow rendering one logical section at a time:
  - providers
  - models
  - routes
- The first implementation can use a simple prop such as `activeSection`.
- No API behavior changes.

## Detailed Behavior

Overview:

- Shows compact version status.
- Shows quick explanation of which section controls what.
- Optionally shows config health indicators derived from already-loaded local state if cheap.
- No new backend endpoint.

Providers & API Key:

- Shows provider list and provider form.
- Keeps existing create/update behavior.
- Keeps API Key placeholder semantics.

Available Models:

- Shows model list and model form.
- Keeps capability checkboxes and default model flags.
- Keeps current validation copy.

AI Stage Routing:

- Shows grouped stage routing selectors.
- Keeps current save button and route selection behavior.

Basic LLM Config:

- Shows legacy main model and embedding model form.
- Keeps existing model-list fetching, save, and delete behavior.
- Treat this as compatibility/advanced configuration, visually lower priority than personal routing.

## UX Rules

- Do not nest cards inside cards where a simple panel section is enough.
- Keep the active panel width readable on desktop.
- Left navigation should be sticky on desktop.
- Mobile navigation should be horizontally scrollable and not wrap into multiple rows.
- Buttons should keep explicit action labels such as `保存供应商`, `保存模型`, `保存阶段路由`, and `保存配置`.
- Feedback messages should stay close to the section that generated them.
- Do not introduce a wizard flow in this iteration.

## Accessibility

- Navigation controls should be real `<button>` elements.
- Active navigation item should expose `aria-current="page"` or equivalent state.
- Form controls must keep labels.
- Newly introduced icon-only controls are out of scope; if added later, they need `aria-label`.
- Preserve visible focus states from the existing Material button/input classes.

## Testing And Verification

Recommended checks after implementation:

1. `npm run build` from `frontend/`.
2. Browser smoke test for `/settings` desktop width.
3. Browser smoke test for `/settings` mobile width.
4. Manual checks:
   - switching each nav item shows the correct panel,
   - existing save/delete buttons still call the same behavior,
   - inspiration-mode notice still appears and redirect after save still works,
   - version status still renders.

## Out Of Scope

- Backend API changes.
- New model routing data model.
- New global state management.
- Full onboarding wizard.
- Rewriting visual design tokens.
- Changing admin settings pages.
