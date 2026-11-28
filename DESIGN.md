---
name: BisaRx
description: A precise, familiar conversational workspace for patient and pharmacist care.
colors:
  bg: "#ffffff"
  rail: "#f7f7f8"
  soft: "#f1f1f3"
  hover: "#e8e8eb"
  ink: "#202123"
  muted: "#62656b"
  line: "#e3e3e7"
  input-line: "#c7c7ce"
  primary: "#252527"
  accent: "#345dc7"
  accent-soft: "#eef2ff"
  success: "#167347"
  warning: "#895600"
  danger: "#b42336"
  dark-bg: "#202123"
  dark-rail: "#171719"
  dark-soft: "#2c2d30"
  dark-hover: "#37383c"
  dark-ink: "#ececef"
  dark-muted: "#b1b1b9"
  dark-line: "#3b3b40"
  dark-primary: "#f1f1f3"
  dark-accent: "#9eb7ff"
  dark-accent-soft: "#29334a"
  dark-success: "#77d4a4"
  dark-warning: "#f3cb76"
  dark-danger: "#ff9ca9"
typography:
  headline:
    fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif'
    fontSize: "26px"
    fontWeight: 550
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  title:
    fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif'
    fontSize: "20px"
    fontWeight: 550
    lineHeight: 1.2
    letterSpacing: "-0.035em"
  body:
    fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  label:
    fontFamily: '"Helvetica Neue", Helvetica, Arial, sans-serif'
    fontSize: "13px"
    fontWeight: 500
rounded:
  xs: "6px"
  sm: "8px"
  md: "12px"
  lg: "16px"
spacing:
  compact: "8px"
  control: "12px"
  group: "16px"
  section: "24px"
  page: "40px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.bg}"
    rounded: "{rounded.sm}"
    padding: "10px 16px"
    typography: "{typography.label}"
  button-secondary:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 16px"
  input:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "11px 12px"
  nav-item:
    textColor: "{colors.ink}"
    rounded: "{rounded.sm}"
    padding: "10px 12px"
  status-chip:
    backgroundColor: "{colors.soft}"
    textColor: "{colors.muted}"
    rounded: "5px"
    padding: "4px 8px"
  case-card:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "24px"
  composer:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "14px 14px 10px"
---

# Design System: BisaRx

## Overview

**Creative North Star: "The Conversational Workspace"**

BisaRx follows the user's pinned ChatGPT-style direction: familiar, premium, professional, and restrained. White working surfaces and a quiet neutral rail support conversation and human review. Precision comes from clear text, consistent outline icons, thin divisions, and compact controls.

The same visual vocabulary spans patient, pharmacist, administrator, public utility pages, and the embedded widget. Light is the default; the persisted dark preference reverses neutral layers while preserving hierarchy. The widget follows an explicit host light/dark theme, falling back to the system dark preference only when the host has no theme attribute. The former layered blue-green card identity is the confirmed anti-reference.

**Key Characteristics:**
- Neutral surfaces with graphite actions.
- Familiar sans-serif typography and outline SVG icons.
- Flat working areas with selective floating depth.
- Responsive navigation and restrained, reducible motion.

## Colors

The palette is neutral first, with functional blue and semantic status colors.

### Primary
- **Graphite Action** (`primary`): filled actions; the circular composer send control uses `ink` with the same light-on-dark relationship.
- **Focus Blue** (`accent`): keyboard outlines, selected body regions, and informational states; `accent-soft` supplies their quiet background.

### Neutral
- **Working White** (`bg`): main canvas, fields, cards, and dialogs.
- **Quiet Rail** (`rail`): navigation and supporting regions.
- **Soft Gray** (`soft`): user message bubbles and low-emphasis grouping.
- **Hover Gray** (`hover`): navigation and icon-control feedback.
- **Graphite Text** (`ink`) and **Secondary Gray** (`muted`): reading hierarchy.
- **Divider Gray** (`line`) and **Field Gray** (`input-line`): section boundaries and editable fields.
- Dark-prefixed tokens record the corresponding theme values. CSS variables, rather than literal light values, govern theme-aware surfaces.

Success, warning, and danger colors communicate actual status. Status chips mix these colors into the current background at low opacity; their text retains the semantic color.

**The Functional Color Rule.** Reserve blue and semantic hues for focus, selection, information, and actual status.

## Typography

**Display Font:** Helvetica Neue, Helvetica, Arial, sans-serif.
**Body Font:** the same family stack.

**Character:** one familiar family creates a cohesive working interface. Moderate weight changes and tighter heading tracking establish hierarchy without decorative type.

### Hierarchy
- **Headlines:** shared heading sizes step through 36, 26, 20, and 17px, with weight 550 and line-height 1.2. Staff panel headings use 27px; mobile panel headings reduce to 24 or 23px.
- **Conversation greeting:** responsive 27–36px, weight 500, line-height 1.2, tracking -0.04em; smaller viewports use 30 or 28px.
- **Body:** the normative body role above; paragraphs use line-height 1.6 and conversation responses 1.8. Conversation text reduces to 15px on small screens.
- **Labels:** 13px, weight 500. Navigation uses 14px; metadata uses 11–12px. Labels retain sentence case.
- **Statistics:** 32px, weight 500, tight tracking, tabular numerals; compact variants use 27–28px.

**The Single Family Rule.** Use the shared family across headings, controls, and content; establish hierarchy through size, spacing, and weight.

## Layout

The workspace fills the visible viewport, tracking visualViewport resize when available and falling back to the window height. This keeps the composer above the mobile keyboard. A desktop rail (248px) sits beside a flexible scrolling content region; its collapsed state is 72px. Staff panels use 34px vertical and 40px horizontal padding, reducing through 28px, 24px/20px, and 24px/16px at smaller widths.

Conversation content centers on a composer measure of 760px and a message measure of 800px. The welcome greeting sits above the composer; once messages arrive, the message area expands and suggestions disappear. Content remains fluid rather than becoming a stack of decorative cards.

At 900px and below, a 58px mobile header replaces the persistent rail; navigation becomes a 260px drawer. At 600px and below, forms and supporting grids become one column, four-column statistics become two, and composer padding respects the bottom safe area. The composer stays within the flex viewport layout, whose height follows the visible viewport. Public layouts use a maximum width of 1120px and collapse their paired columns at 900px.

Spacing repeatedly uses 8, 12, 16, and 24px, with 40px outer desktop space. Case cards use 24px padding, reducing to 18px on small screens. Long case summaries cap at 78ch.

## Elevation & Depth

Working surfaces are primarily flat. Neutral fills and single-pixel borders separate regions; case cards do not lift on hover. Floating dialogs, toasts, and widget surfaces carry selective soft depth. The composer has a subtle ambient shadow (`0 3px 14px #00000006`). Shared shadow variables range from `0 2px 8px #00000005` to `0 20px 70px #00000020`; their presence does not justify applying them to every card.

**The Flat Workspace Rule.** Keep navigation, statistics, and case content flat; use depth to distinguish floating interaction surfaces.

## Shapes

Controls generally use the small radius; content containers use the medium radius and the composer uses the large radius. Status labels use compact 5px corners, send buttons are circular, and avatars may be circular or gently squared. Thin neutral borders define editable and contained regions. Icons use inline SVG, normally 20px with 1.7px rounded outline strokes, with smaller variants in suggestions and navigation. The installed-app SVG retains the same outlined medical cross on a graphite rounded square; manifest and browser theme surfaces use neutral white.

## Components

### Buttons
Compact and direct. Primary buttons use the primary/background pairing, a 40px minimum height, and the recorded padding. Secondary buttons use the working surface, ink, and a neutral border. Small and extra-small variants reduce minimum heights to 34 and 30px. Shared button hover reduces opacity; icon buttons use a neutral hover fill. Disabled buttons halve opacity. Interactive elements receive a blue 2px focus-visible outline with 3px offset.

### Chips
Small status labels use the recorded neutral chip style. Semantic variants use lightly tinted backgrounds and semantic text. Body-region choices instead carry a visible border and blue selection treatment; do not confuse status labels with interactive filters.

### Cards / Containers
Case, administrative, profile, and clinical containers use the medium radius, a single-pixel divider border, flat background, and section padding. Statistics use open columns with vertical rules. Empty states use quiet rail fill and a dashed border. Public utility containers use 14px corners.

### Inputs / Fields
Fields use a field-gray border, small corners, recorded padding, 44px minimum height, and 16px text. Labels sit above with an 8px gap. Textareas resize vertically. Focus uses the shared outline; the conversational textarea sits inside its enclosing composer and suppresses its own border.

### Navigation
Rows are at least 44px high with outline icons and 12px corners. The selected row has a raised translucent surface and accent icon. Profile tabs use a compact segmented control with a solid selected state. Patient navigation prioritizes Chat, History, Care Team, and Profile; secondary health tools live in a native expandable group. Staff access links are absent from the patient page. Mobile navigation closes into a drawer; hidden drawer contents are inert.

### Dialogs

Dialogs use a floating working surface, large corners, 36px padding, and the shared large shadow. The standard width caps at 440px, with a 680px wide variant. One shared accessibility controller supplies dialog semantics, focus trapping, opener restoration, and Escape handling; the background app is inert while a dialog is open. Small screens reduce padding and cap height within the viewport.

### Conversation Composer
The large-radius translucent container has a full-width text area above photo and voice tools, a circular send action at bottom right, and a short hint. One photo control replaces duplicate attachment/camera actions. Focus within highlights its border. Suggested tasks sit below the welcome composer. User messages have soft rounded bubbles; assistant messages remain open on the page.

### Glass material

`workspace-glass.css` supplies the user-requested glass refinement. The canvas is #f3f6f5 in light mode and #191f21 in dark mode, with quiet sage and slate light fields. Navigation uses 24px backdrop blur and a translucent surface; the composer and dialogs use stronger opacity for legibility. Desktop navigation floats 12px from the viewport edge. Unsupported backdrop filters fall back to solid surfaces. Welcome content arrives in one staggered sequence under 700ms, using slight movement and a 3px-to-zero blur. Hover lift is limited to suggested actions. Reduced motion removes every added transition and animation.

Motion is functional: state colors transition over 160ms, message arrival uses 280ms with a slight 5px rise, and the drawer uses 240ms with `cubic-bezier(.16,1,.3,1)`. When the welcome state changes, the composer settles from its previous vertical position into the active conversation over 320ms with the same easing. The settling animation is skipped when reduced motion is requested. Reduced-motion preference removes animation, transitions, and smooth scrolling.

## Do's and Don'ts

### Do:
- **Do** use theme variables for working surfaces and text.
- **Do** preserve visible focus and accessible names for icon controls.
- **Do** keep case content flat and use borders to define groups.
- **Do** respect reduced-motion preference and mobile safe areas.

### Don't:
- **Don't** reintroduce the replaced blue-green layered card identity.
- **Don't** use semantic colors as unrelated decoration.
- **Don't** replace the shared SVG vocabulary with glyph icons.
- **Don't** add decorative kickers or eyebrows to working screens.
