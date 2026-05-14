---
name: MoFeng
description: Quiet professional writing workspace for long-form AI-assisted fiction.
colors:
  clear-blue: "#4285F4"
  clear-blue-light: "#669DF6"
  clear-blue-dark: "#1A73E8"
  clear-blue-container: "#D2E3FC"
  paper-white: "#FFFFFF"
  soft-paper: "#F8F9FA"
  quiet-gray: "#F1F3F4"
  quiet-gray-high: "#E8EAED"
  quiet-gray-highest: "#DADCE0"
  ink: "#202124"
  ink-muted: "#5F6368"
  success: "#34A853"
  success-container: "#E6F4EA"
  warning: "#FBBC04"
  warning-container: "#FEF7E0"
  error: "#EA4335"
  error-container: "#FCE8E6"
typography:
  display:
    fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "57px"
    fontWeight: 400
    lineHeight: 1.12
    letterSpacing: "-0.25px"
  headline:
    fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "32px"
    fontWeight: 400
    lineHeight: 1.25
  title:
    fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.3
  body:
    fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Noto Sans SC, PingFang SC, Microsoft YaHei, Segoe UI, sans-serif"
    fontSize: "12px"
    fontWeight: 600
    lineHeight: 1.4
rounded:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "32px"
  xxl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.clear-blue}"
    textColor: "{colors.paper-white}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "10px 24px"
    height: "40px"
  button-tonal:
    backgroundColor: "{colors.clear-blue-container}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "10px 24px"
    height: "40px"
  card:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "24px"
  input:
    backgroundColor: "{colors.paper-white}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "12px 16px"
    height: "48px"
  chip:
    backgroundColor: "{colors.quiet-gray}"
    textColor: "{colors.ink-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.full}"
    padding: "4px 12px"
---

# Design System: MoFeng

## 1. Overview

**Creative North Star: "安静写作台"**

MoFeng is a product interface for sustained long-form writing. The system should feel calm, professional, and dependable: a working desk where drafts, models, project state, and review results are always close at hand without competing for attention.

The visual language is Material 3 inspired, but tuned for creative productivity rather than brand performance. It uses clear blue as a rare action color, paper-white surfaces for long reading and editing sessions, and ink-gray text that supports scanning. The interface rejects SaaS landing-page drama, purple-blue AI spectacle, glassmorphism, novelty demo styling, and decorative card grids that slow operational work.

**Key Characteristics:**
- Quiet product surface for repeated daily use.
- Clear model and project configuration without hidden state.
- Light, breathable density for long Chinese text.
- Restrained color and motion, with hierarchy coming from layout, labels, and state.

## 2. Colors

The palette is a clear blue, paper white, and ink gray system with semantic success, warning, and error roles reserved for state.

### Primary
- **清晰蓝** (`#4285F4`): Primary actions, active navigation, selected controls, and the most important next step.
- **深清晰蓝** (`#1A73E8`): Hover or pressed emphasis when a primary action needs stronger contrast.
- **浅清晰蓝** (`#669DF6`): Secondary accent and subtle interactive affordances.
- **蓝色容器** (`#D2E3FC`): Selected tabs, active chips, and quiet emphasis behind action-related content.

### Neutral
- **纸白** (`#FFFFFF`): Main reading and writing surface.
- **软纸白** (`#F8F9FA`): App background and low-emphasis panels.
- **安静灰** (`#F1F3F4`): Neutral container fills, hover backgrounds, and grouped controls.
- **边界灰** (`#E8EAED` / `#DADCE0`): Borders, dividers, disabled surfaces, and subtle separation.
- **墨灰** (`#202124`): Primary text and labels.
- **浅墨灰** (`#5F6368`): Secondary text, helper copy, placeholders, and metadata.

### State
- **确认绿** (`#34A853`, container `#E6F4EA`): Saved, enabled, and successful states.
- **提醒黄** (`#FBBC04`, container `#FEF7E0`): Caution and partial-progress states.
- **错误红** (`#EA4335`, container `#FCE8E6`): Validation errors, destructive actions, and blocked states.

### Named Rules

**The Rare Blue Rule.** 清晰蓝 should mark action and selection, not decorate the page. If more than one thing screams primary, the screen loses trust.

**The Paper First Rule.** Long-form reading, editing, and generated content should sit on paper-white or soft-paper surfaces, never on saturated backgrounds.

## 3. Typography

**Display Font:** Noto Sans SC with PingFang SC, Microsoft YaHei, Segoe UI fallback.  
**Body Font:** Noto Sans SC with the same system fallback.  
**Label/Mono Font:** Noto Sans SC for labels; Consolas, JetBrains Mono, Courier New for technical snippets when needed.

**Character:** The typography is functional and calm. It favors readable Chinese UI text, stable form labels, and compact operational headings over expressive editorial display type.

### Hierarchy
- **Display** (400, 57px, 1.12): Rarely used; reserve for true empty-state or onboarding moments, not dashboard panels.
- **Headline** (400, 24-32px, about 1.25): Page titles and major workflow transitions.
- **Title** (600, 16-22px, about 1.3): Cards, panels, dialogs, and section headings.
- **Body** (400, 14-16px, 1.5): Normal UI copy, generated summaries, explanations, and settings text. Keep long prose near 65-75ch when possible.
- **Label** (600, 11-14px, about 1.4): Buttons, form labels, chips, metadata, and compact controls.

### Named Rules

**The Working Heading Rule.** Use headings to orient workflow, not to market the product. Page and panel titles should name the task or object directly.

**The Long Text Rule.** Generated story material and review text need comfortable line height and restrained width before visual density.

## 4. Elevation

The system uses 克制分层: soft tonal surfaces at rest, with light shadows only where a layer is genuinely above another layer. Cards, dialogs, floating model pickers, dropdowns, and snackbars may use elevation; standard page sections should rely on spacing, borders, and surface color.

### Shadow Vocabulary
- **Elevation 1** (`0 1px 2px 0 rgba(60, 64, 67, 0.3), 0 1px 3px 1px rgba(60, 64, 67, 0.15)`): Small cards, snackbars, low-priority floating feedback.
- **Elevation 2** (`0 1px 2px 0 rgba(60, 64, 67, 0.3), 0 2px 6px 2px rgba(60, 64, 67, 0.15)`): Raised cards and important panels.
- **Elevation 3** (`0 1px 3px 0 rgba(60, 64, 67, 0.3), 0 4px 8px 3px rgba(60, 64, 67, 0.15)`): Dropdowns, floating selectors, dialogs, and temporary surfaces.

### Named Rules

**The Layer Has a Job Rule.** A shadow must explain stacking, focus, or interaction. Do not use shadows just to make a screen feel richer.

## 5. Components

### Buttons
- **Shape:** Fully rounded pills (`9999px`) for primary, tonal, outlined, and text buttons.
- **Primary:** 清晰蓝 background with white text, usually 40px high with 10px vertical and 24px horizontal padding.
- **Tonal:** 蓝色容器 background with ink text for secondary actions such as fetch, save, and low-risk workflow commands.
- **Hover / Focus:** Use restrained color shifts and clear focus indicators. Do not animate layout size or move neighboring content.
- **Text Buttons:** Use for non-primary commands such as edit, cancel, back, and contextual navigation.

### Chips
- **Style:** Rounded pill chips, quiet-gray or blue-container backgrounds, label typography, compact padding.
- **State:** Selected chips should be visually clear but calm. Action chips may include small inline controls only when the action is local and recoverable.
- **Use:** Model selections, admin badges, filter states, project metadata, and compact status labels.

### Cards / Containers
- **Corner Style:** Medium to large radii (`12px` to `24px`) depending on surface scale.
- **Background:** Paper-white for primary cards, soft-paper or quiet-gray for nested operational groups.
- **Shadow Strategy:** Use elevation only for meaningful stacked surfaces. Prefer borders for ordinary cards.
- **Border:** `#E8EAED` or `#DADCE0` for quiet separation.
- **Internal Padding:** Use the 8dp scale, usually 16px, 24px, or 32px.

### Inputs / Fields
- **Style:** White or soft-paper background, quiet border, 12px radius, explicit label, and clear helper text.
- **Focus:** Shift border or emphasis to 清晰蓝; keep focus visible for keyboard users.
- **Error / Disabled:** Use semantic containers. Disabled controls should remain legible but clearly unavailable.

### Navigation
- **Style:** Product navigation should be compact and task-labeled. Active state uses blue-container or clear-blue accent, not large decorative treatment.
- **Mobile:** Horizontal tabs or stacked controls are acceptable when labels remain readable and no text overlaps.

### Dialogs and Floating Surfaces
- **Style:** Use paper-white surface, elevation 3, clear title, and explicit close or cancel action.
- **Use:** Confirm destructive actions, show focused pickers, and isolate short forms. Avoid modals for flows that can live inline.

### Writing and Review Surfaces
- **Style:** Favor readable columns, stable toolbars, and visible version state. Generated text and critique content should feel inspectable, not decorative.
- **Use:** Distinguish draft content, AI review, metadata, and actions through layout and labels before color.

## 6. Do's and Don'ts

### Do:
- **Do** use 清晰蓝 (`#4285F4`) for primary actions, selected state, and active navigation.
- **Do** keep long writing and review text on paper-white or soft-paper surfaces with comfortable line height.
- **Do** use the 8dp spacing scale consistently, especially 8px, 16px, 24px, and 32px.
- **Do** make model, provider, and route settings explicit, recoverable, and easy to verify.
- **Do** preserve keyboard operation, visible focus states, and sufficient contrast for WCAG 2.1 AA.
- **Do** use state colors only for real state: success, warning, error, enabled, disabled, blocked.

### Don't:
- **Don't** make the product feel like a SaaS landing page, game UI, novelty AI demo, or over-branded content site.
- **Don't** use oversized hero sections, decorative illustration-first layouts, or marketing-style composition on operational screens.
- **Don't** use purple-blue AI gradients, glassmorphism, neon accents, or theatrical AI spectacle.
- **Don't** build identical decorative card grids that make settings, writing state, or project lists harder to scan.
- **Don't** hide critical configuration behind vague labels or unclear default states.
- **Don't** convey critical information by color alone, and don't animate layout properties in ways that disturb reading or editing.
