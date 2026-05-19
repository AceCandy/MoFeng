---
name: MoFeng
description: Quiet professional writing workspace for long-form AI-assisted fiction. Warm-paper tonal palette.
colors:
  primary: "#4d6b97"
  primary-light: "#6e8ab3"
  primary-dark: "#355274"
  on-primary: "#f7f4ef"
  primary-container: "#dfe8f4"
  on-primary-container: "#273b58"
  secondary: "#5f6676"
  secondary-container: "#e6eaf0"
  surface: "#fbfaf7"
  surface-dim: "#f3efe8"
  surface-container-lowest: "#fefcf8"
  surface-container-low: "#f7f3ec"
  surface-container: "#f0ece4"
  surface-container-high: "#e8e2d8"
  surface-container-highest: "#dcd5c8"
  background: "#f4f0e9"
  on-surface: "#1f2530"
  on-surface-variant: "#5e6674"
  outline: "#d8d0c4"
  outline-variant: "#e6dfd2"
  error: "#b85c58"
  error-container: "#f8e5e2"
  success: "#4f7b66"
  success-container: "#e3eee7"
  warning: "#b5904c"
  warning-container: "#f8eed8"
typography:
  display:
    fontFamily: "STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif"
    fontSize: "54px"
    fontWeight: 400
    lineHeight: 1.12
  headline:
    fontFamily: "STSong, Songti SC, Noto Serif CJK SC, Source Han Serif SC, serif"
    fontSize: "32px"
    fontWeight: 400
    lineHeight: 1.25
  title:
    fontFamily: "Noto Sans SC, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif"
    fontSize: "22px"
    fontWeight: 500
    lineHeight: 1.27
  body:
    fontFamily: "Noto Sans SC, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "Noto Sans SC, PingFang SC, Hiragino Sans GB, Microsoft YaHei, sans-serif"
    fontSize: "12px"
    fontWeight: 500
    lineHeight: 1.33
rounded:
  xs: "6px"
  sm: "10px"
  md: "14px"
  lg: "18px"
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
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 20px"
    height: "42px"
  button-tonal:
    backgroundColor: "{colors.primary-container}"
    textColor: "{colors.on-primary-container}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 20px"
    height: "42px"
  card:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.lg}"
    padding: "16px"
    border: "1px solid {colors.outline-variant}"
  input:
    backgroundColor: "transparent"
    textColor: "{colors.on-surface}"
    rounded: "{rounded.xs}"
    padding: "16px"
    height: "56px"
    border: "1px solid {colors.outline}"
  chip:
    backgroundColor: "{colors.surface-container}"
    textColor: "{colors.on-surface-variant}"
    typography: "{typography.label}"
    rounded: "{rounded.sm}"
    padding: "0 16px"
    height: "32px"
---

# Design System: MoFeng

## 1. Overview

**Creative North Star: "安静写作台"**

MoFeng is a product interface for sustained long-form writing. The system should feel calm, professional, and dependable: a working desk where drafts, models, project state, and review results are always close at hand without competing for attention.

The visual language is Material 3 inspired, tuned toward a warm-paper tonal palette for creative productivity. It uses a desaturated blue-gray as a rare action color, warm off-white surfaces for long reading and editing sessions, and ink-gray text that supports scanning. The interface rejects SaaS landing-page drama, purple-blue AI spectacle, glassmorphism, novelty demo styling, and decorative card grids that slow operational work.

**Key Characteristics:**
- Warm paper surfaces for sustained daily use without eye fatigue.
- Clear model and project configuration without hidden state.
- Light, breathable density for long Chinese text.
- Restrained color and motion, with hierarchy coming from layout, labels, and state.

## 2. Colors

The palette is a warm-paper tonal system: desaturated blue-gray primary, warm off-white surfaces, and ink-gray text. Semantic success, warning, and error roles are reserved for state.

### Primary
- **墨蓝** (`#4d6b97`): Primary actions, active navigation, selected controls, and the most important next step.
- **深墨蓝** (`#355274`): Hover or pressed emphasis when a primary action needs stronger contrast.
- **浅墨蓝** (`#6e8ab3`): Secondary accent and subtle interactive affordances.
- **蓝色容器** (`#dfe8f4`): Selected tabs, active chips, and quiet emphasis behind action-related content.

### Neutral (warm-paper tonal)
- **暖纸白** (`#fbfaf7`): Main reading and writing surface.
- **暖纸灰** (`#f3efe8`): Dimmed surface for app background.
- **容器面** (`#f0ece4`): Neutral container fills, hover backgrounds, and grouped controls.
- **高容器面** (`#e8e2d8` / `#dcd5c8`): Borders, dividers, disabled surfaces, and subtle separation.
- **墨色** (`#1f2530`): Primary text and labels.
- **浅墨色** (`#5e6674`): Secondary text, helper copy, placeholders, and metadata.
- **边界** (`#d8d0c4`): Standard borders and outlines.
- **浅边界** (`#e6dfd2`): Subtle separation and variant borders.

### State
- **确认绿** (`#4f7b66`, container `#e3eee7`): Saved, enabled, and successful states.
- **提醒黄** (`#b5904c`, container `#f8eed8`): Caution and partial-progress states.
- **错误红** (`#b85c58`, container `#f8e5e2`): Validation errors, destructive actions, and blocked states.

### Named Rules

**The Rare Blue Rule.** 墨蓝 should mark action and selection, not decorate the page. If more than one thing screams primary, the screen loses trust.

**The Paper First Rule.** Long-form reading, editing, and generated content should sit on warm-paper surfaces, never on saturated backgrounds.

## 3. Typography

**Display Font:** STSong / Songti SC / Noto Serif CJK SC (serif) for headings h1–h3.  
**Body Font:** Noto Sans SC with PingFang SC, Hiragino Sans GB, Microsoft YaHei fallback.  
**Mono Font:** JetBrains Mono, Consolas, Courier New for technical snippets.

**Character:** The typography pairs a literary serif for display headings with a functional sans for body and UI. It favors readable Chinese text, stable form labels, and compact operational headings over expressive editorial display type.

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
- **Elevation 1** (`0 1px 2px rgba(42, 46, 56, 0.05), 0 4px 12px rgba(42, 46, 56, 0.05)`): Small cards, snackbars, low-priority floating feedback.
- **Elevation 2** (`0 2px 6px rgba(42, 46, 56, 0.08), 0 12px 26px rgba(42, 46, 56, 0.06)`): Raised cards and important panels.
- **Elevation 3** (`0 8px 30px rgba(42, 46, 56, 0.09)`): Dropdowns, floating selectors, dialogs, and temporary surfaces.

### Named Rules

**The Layer Has a Job Rule.** A shadow must explain stacking, focus, or interaction. Do not use shadows just to make a screen feel richer.

## 5. Components

### Buttons
- **Shape:** Rounded rectangles (`10px` / `--md-radius-sm`) for primary, tonal, outlined, and text buttons. Not pills.
- **Primary:** 墨蓝 background with warm off-white text, usually 42px high with 0 20px padding.
- **Tonal:** 蓝色容器 background with on-primary-container text for secondary actions such as fetch, save, and low-risk workflow commands.
- **Hover / Focus:** Use restrained color shifts and clear focus indicators. Do not animate layout size or move neighboring content.
- **Text Buttons:** Use for non-primary commands such as edit, cancel, back, and contextual navigation.

### Chips
- **Style:** Rounded chips (`10px`), surface-container or primary-container backgrounds, label typography, compact padding.
- **State:** Selected chips should be visually clear but calm. Action chips may include small inline controls only when the action is local and recoverable.
- **Use:** Model selections, admin badges, filter states, project metadata, and compact status labels.

### Cards / Containers
- **Corner Style:** Medium to large radii (`14px` to `24px`) depending on surface scale.
- **Background:** Warm-paper white for primary cards, surface-container or surface-dim for nested operational groups.
- **Shadow Strategy:** Use elevation only for meaningful stacked surfaces. Prefer borders for ordinary cards.
- **Border:** `#e6dfd2` (outline-variant) for quiet separation.
- **Internal Padding:** Use the 8dp scale, usually 16px, 24px, or 32px.

### Inputs / Fields
- **Style:** Transparent background, outline border, 6px radius, explicit label, and clear helper text.
- **Focus:** Shift border to 墨蓝 with 2px width; keep focus visible for keyboard users.
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
- **Do** use 墨蓝 (`#4d6b97`) for primary actions, selected state, and active navigation.
- **Do** keep long writing and review text on warm-paper surfaces with comfortable line height.
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
