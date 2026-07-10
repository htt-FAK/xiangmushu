---
name: xiangmushu-design-taste
description: Adapted Taste Skill for the 智能文档生成系统 (xiangmushu) cyberpunk SPA. Anti-slop frontend rules tailored for dashboards, admin panels, form-heavy tools, and data-rich interfaces. Preserves brand identity (signal-cyan #36f2e6, dark theme) while enforcing design quality.
---

# xiangmushu Design Taste — Anti-Slop for Cyberpunk SPAs

> This is an **adapted** Taste Skill for a cyberpunk-themed React SPA (document generation tool).
> Based on [Taste Skill](https://github.com/Leonxlnx/taste-skill) by Leonxlnx.
> Original covers landing pages/portfolios. This version targets: **dashboards, admin panels, form flows, data displays, and tool UIs**.

> Every rule below is **contextual**. None fires automatically. Read the brief, then pull only what fits.

---

## 0. BRIEF INFERENCE (Read the Room)

Before touching code, **infer what the task actually needs**.

### 0.A Signals to read first
1. **Component kind** — form panel, data table, generation workflow, settings card, status indicator, navigation element, modal/drawer, empty/loading/error state.
2. **Interaction intensity** — read-only display, single-action button, multi-step form, multi-select list, drag-and-drop, streaming output.
3. **Data density** — sparse (hero-like summary), medium (card grid), dense (table/list with many rows).
4. **Audience** — technical users managing document generation, not casual browsers.
5. **Brand assets** — this project uses a **locked cyberpunk design system**: signal-cyan (#36f2e6), signal-lime (#b8ff5e), signal-amber (#ffb84d), signal-rose (#ff4d8d), on night-950 (#05060a) background. **These are NOT negotiable.**

### 0.B Design Read
Before generating code, state: **"Reading this as: <component type> in a cyberpunk SPA, with <density> data, prioritizing <interaction quality>."**

### 0.C Anti-Default Discipline
Do NOT default to:
- Generic Material/Bootstrap card patterns
- Three-column-equal feature grids
- Generic toast notifications for everything
- Default browser form styling
- Placeholder-only empty states
- Skeleton loaders that don't match actual layout shape

---

## 1. THE THREE DIALS (Core Configuration)

Set three dials. Every layout, motion, and density decision is gated by these.

* **`DESIGN_VARIANCE: 6`** — 1 = Perfect Symmetry, 10 = Artsy Chaos
* **`MOTION_INTENSITY: 4`** — 1 = Static, 10 = Cinematic
* **`VISUAL_DENSITY: 7`** — 1 = Art Gallery, 10 = Cockpit / Packed Data

**Baseline for this project:** `6 / 4 / 7`. Admin/dashboard/tool UIs need higher density, restrained motion, moderate visual variety.

### 1.A Dial Inference
| Signal | VARIANCE | MOTION | DENSITY |
|---|---|---|---|
| Settings / config panel | 4-5 | 3-4 | 6-7 |
| Data table / history list | 3-4 | 2-3 | 8-9 |
| Form / multi-step wizard | 4-5 | 4-5 | 5-6 |
| Generation workflow / streaming | 5-6 | 5-6 | 6-7 |
| Knowledge base management | 4-5 | 3-4 | 6-7 |
| Dashboard summary / home | 5-7 | 4-5 | 5-6 |
| Admin panel | 3-4 | 2-3 | 7-8 |
| Modal / drawer / overlay | 5-6 | 5-6 | 5-6 |

---

## 2. STACK & CONVENTIONS (Locked for this Project)

### 2.A Stack (non-negotiable)
* **Framework:** React 18 + TypeScript + Vite 6
* **Styling:** Tailwind CSS v3.4 (NOT v4 — project is on v3)
* **Icons:** `lucide-react` (already installed, already standardized at strokeWidth 2)
* **Router:** `react-router-dom` v6
* **Animation:** CSS transitions + Tailwind utility classes (no Motion/GSAP — keep bundle small)
* **Fonts:** Inter (body) + Rajdhani (display). Already configured in tailwind.config.ts. **Do not change fonts.**

### 2.B Design Tokens (non-negotiable — defined in tailwind.config.ts)
```
night-950: #05060a  (deepest background)
night-900: #090d14  (panel backgrounds)
night-850: #0d131d  (card backgrounds)
night-800: #111a25  (elevated surfaces)
night-700: #172332  (hover states)

signal-cyan:  #36f2e6  (primary accent — CTAs, active states, links)
signal-lime:  #b8ff5e  (success, positive indicators)
signal-amber: #ffb84d  (warnings, billing metrics)
signal-rose:  #ff4d8d  (errors, destructive actions)
```

**LILA RULE OVERRIDE:** The "no purple/cyan glow" rule does NOT apply here. Signal-cyan glow IS the brand identity. Use it intentionally and consistently. The rule becomes: **no AI-purple gradients, no random neon effects.** Stick to the 4 signal colors.

### 2.C Component Patterns (this project's conventions)
* **Panel:** `<section className="border border-white/10 bg-white/[0.045] p-4 shadow-panel backdrop-blur md:p-5">` — used everywhere. Solid background (`bg-night-900` or `bg-night-950`) for performance. Opaque panel backgrounds are preferred over backdrop-blur.
* **Button:** `min-h-11 items-center justify-center gap-2 border px-4 text-sm font-semibold transition active:scale-[0.97]`
* **Input:** `min-h-12 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white focus:border-signal-cyan/70`
* **PageHeader:** eyebrow + title + description + optional action slot
* **ErrorBanner:** `border-signal-rose/40 bg-signal-rose/10 px-4 py-3 text-sm text-rose-100`

### 2.D Border Radius Convention
**All elements use sharp corners (radius 0).** Buttons, panels, inputs, cards, modals — all `border` with no `rounded-*`. This is a deliberate cyberpunk aesthetic choice. Do NOT add rounded corners unless explicitly asked.

---

## 3. DESIGN ENGINEERING DIRECTIVES

### 3.1 Typography
* **Display:** `font-display` (Rajdhani), `text-xl md:text-2xl` for section headers, `text-2xl md:text-5xl` for page titles
* **Body:** `text-sm text-slate-300 leading-6` for standard content, `text-xs text-slate-500` for secondary
* **Labels:** `text-xs font-semibold uppercase tracking-[0.16em] text-slate-500` for field labels
* **Monospace:** `font-mono text-sm` for code/key previews, API keys, technical values

### 3.2 Color Application
* **One accent per context.** A settings card might use signal-lime for success states. A generation card uses signal-cyan. Don't mix all 4 signal colors in one component.
* **COLOR CONSISTENCY LOCK:** Once a component picks its accent, stick to it throughout.
* **Contrast requirements:** All text must pass WCAG AA (4.5:1 for body, 3:1 for large text). Dark backgrounds: use slate-300+ for body, white for emphasis. Light text on signal-cyan backgrounds (buttons): use `text-night-950`.

### 3.3 Interactive UI States (MANDATORY — implement all of these)
LLMs default to "static successful state only." Always implement the full cycle:

* **Loading:** Skeleton loaders that match the actual layout shape. Not generic spinners. For lists: pulse rectangles following the row structure. For panels: skeleton matching the panel header + content area.
  ```tsx
  // GOOD: Layout-matched skeleton
  <div className="space-y-3">
    {[1,2,3].map(i => (
      <div key={i} className="flex items-center justify-between">
        <div className="h-4 w-20 animate-pulse rounded bg-white/10" />
        <div className="h-9 w-[200px] animate-pulse rounded border border-white/10 bg-white/[0.03]" />
      </div>
    ))}
  </div>
  ```

* **Empty States:** Beautifully composed empty states with icon, title, description, and action hint.
  ```tsx
  <div className="border border-dashed border-white/15 bg-night-900/60 p-6 text-center md:p-8">
    <p className="font-display text-xl font-semibold text-white">{title}</p>
    <p className="mt-2 text-sm text-slate-400">{body}</p>
  </div>
  ```

* **Error States:** Inline for forms, contextual for data loads. Use signal-rose border and rose-100 text. Never generic red — always border + bg + text with proper contrast.

* **Disabled State:** `opacity-45 pointer-events-none cursor-not-allowed` (already in Button component).

* **Active/Tactile Feedback:** `active:scale-[0.97] active:brightness-90` on buttons. `active:scale-[0.98]` on nav items.

* **Focus States:** All interactive elements must have visible focus rings. Use `focus:border-signal-cyan/70` or `focus:outline-none focus-visible:ring-2 focus-visible:ring-signal-cyan/50`.

### 3.4 Data Display Patterns
* **Lists/Tables:** Use `divide-y divide-white/10` for row separation. Hover rows: `hover:bg-white/[0.03]`. Selected rows: `bg-signal-cyan/10 border-signal-cyan/60`.
* **Cards in grids:** Use `grid gap-3 md:gap-4` (not `gap-2` — too tight). Cards get border + hover state.
* **Stats/Metrics:** Use the `<Stat>` component. Number in `font-display text-xl font-semibold`, label in `text-[11px] uppercase tracking-[0.12em] text-slate-500`.
* **Status badges:** `border px-2 py-1 text-xs font-semibold` with appropriate signal color.
  - Success: `border-signal-lime/40 bg-signal-lime/10 text-signal-lime`
  - Warning: `border-signal-amber/40 bg-signal-amber/10 text-signal-amber`  
  - Error: `border-signal-rose/40 bg-signal-rose/10 text-signal-rose`
  - Info: `border-signal-cyan/30 bg-signal-cyan/10 text-signal-cyan`

### 3.5 Form & Input Patterns
* **Label ABOVE input.** Never placeholder-as-label.
* **Helper text optional.** Error text BELOW input in `text-xs text-signal-rose`.
* **Standard gap:** `space-y-3` or `gap-4` for form fields.
* **Input groups:** When an input has a button next to it (e.g., "Test" button), use `flex items-end gap-3`.
* **Select/combobox:** Must have visible selected state, searchable dropdown list with proper keyboard navigation.

### 3.6 Navigation Patterns
* **Desktop sidebar:** Fixed left, 288px wide (`w-72`), with logo + nav items + account section at bottom.
* **Mobile bottom bar:** Fixed bottom, 3 primary items + "More" button that opens a bottom sheet.
* **Active state:** `border-signal-cyan/60 bg-signal-cyan/12 text-signal-cyan` with a top indicator bar.
* **Breadcrumb/Context:** Use the top status bar for generation/analysis progress, not breadcrumbs.

### 3.7 Loading & Streaming Patterns
* **SSE streaming:** Show content chunks as they arrive. Use `whitespace-pre-wrap` for generated text.
* **Progress indicators:** `type: "progress"` events show `(done/total)` with current task name.
* **Background sessions:** Show a sticky top banner when a session is running, linking back to the page.
- Banner style: `border-b border-signal-cyan/20 bg-signal-cyan/10 px-4 py-2.5 text-sm text-cyan-100`

### 3.8 Modal & Overlay Patterns
* **Full-screen overlay:** `fixed inset-0 z-50 bg-night-950/90 backdrop-blur` (or `bg-night-950` for performance).
* **Content area:** `mx-auto w-full max-w-3xl border border-white/10 bg-night-900 p-4 shadow-panel`.
- **Close button:** Always visible top-right, `h-10 w-10` with X icon.
* **Scroll:** Overlay content scrolls independently with `overflow-y-auto`.

---

## 4. CONTENT & COPY QUALITY

### 4.1 Copy Self-Audit (mandatory)
Before shipping any UI change, re-read every visible string. Flag:
- **Grammatically broken** strings
- **Unclear referents** without prior context
- **AI hallucination copy** — cute-but-wrong wordplay, forced metaphors
- **Placeholder text** left in production code

### 4.2 i18n Consistency
This project supports zh/en via `useI18n()`. All user-visible strings must go through `t("key")`. Check both language dictionaries in `src/i18n.ts` when adding new strings.

### 4.3 Error Messages
- **User-facing:** Chinese default, clear actionable language. "请先在设置页保存 API Key" not "API Key required".
- **Developer-facing (console.error):** English, technical, include context.
- **Never expose raw HTTP statuses or stack traces to users.**

---

## 5. PERFORMANCE GUARDRAILS

### 5.1 Render Performance
* **`memo()` for expensive list items.** Use `React.memo()` for components rendered in long lists (>10 items) with stable props.
* **`useMemo` for derived data.** Expensive computations (filtering, sorting, formatting) must be memoized.
* **Virtualization for long lists.** Lists with 50+ items should use virtualization (react-window or similar).
* **Avoid inline object/array literals in JSX props.** They create new references every render.

### 5.2 CSS Performance
* **No `backdrop-blur` on scrollable containers.** Causes continuous GPU repaints. Use solid backgrounds instead.
* **`will-change: transform` only on elements that actually animate.** Don't spray it everywhere.
* **CSS containment:** Use `contain: layout style paint` on decorative fixed elements (like grid-mask backgrounds).
* **Animate only `transform` and `opacity`.** Never animate `top`, `left`, `width`, `height`.

### 5.3 Network Performance
* **Debounce API calls** on focus/visibility events. Minimum 2-second gap between repeat calls.
* **Abort controllers** on all streaming/fetch operations. Clean up on unmount.
* **Lazy loading:** Page components use `React.lazy()` + `<Suspense>`. Only the currently viewed page loads.
* **Bundle size awareness:** No unnecessary dependencies. lucide-react tree-shakes well.

### 5.4 Touch/Scroll Performance (mobile)
* **Passive event listeners** for scroll-related touch events. `passive: true` for touchstart/touchend.
* **No `e.preventDefault()` in passive listeners.** This is a browser violation and causes jank.
* **`overscroll-behavior: contain`** on scroll containers to prevent pull-to-refresh interference.

---

## 6. EYEBROW & REPETITION RESTRAINT

### 6.A Eyebrow Restraint
An "eyebrow" is `text-xs font-semibold uppercase tracking-[0.16em] text-slate-500` above a section heading. In this project, eyebrows are used on **page headers only** (via `<PageHeader>`). Individual panels/cards within a page do NOT get eyebrows. If a card needs a label, it gets a `<SectionTitle>` or just a bold heading.

### 6.B Section Layout Diversity
On any given page, panels should not all look identical. Vary:
- Panel width (full-width vs grid columns)
- Header style (icon + title vs plain title)
- Content density (compact list vs spacious cards)
- Accent color usage (one panel uses lime, another uses cyan)

### 6.C Status Indicators
Max 3 status states visible simultaneously per view. If a page has 5 different status indicators, group them or use a summary badge.

---

## 7. ACCESSIBILITY (non-negotiable)

### 7.A Keyboard Navigation
- All interactive elements must be reachable via Tab
- All buttons must respond to Enter and Space
- Modal overlays must trap focus
- Escape key closes modals, drawers, and dropdowns

### 7.B Screen Readers
- Icon-only buttons need `aria-label` or `title`
- Status changes should announce via `aria-live` regions (e.g., generation progress)
- Form errors must be associated with their input via `aria-describedby`

### 7.C Color Independence
- Never communicate state through color alone. Always pair with icon, text, or shape.
  - GOOD: ✓ icon + signal-lime text + green border = success
  - BAD: just green background = inaccessible

### 7.D Reduced Motion
- All CSS transitions and animations must respect `prefers-reduced-motion: reduce`
- In this project, all Tailwind transitions inherently respect this setting (Tailwind's `transition` utility includes the media query)

---

## 8. PRE-FLIGHT CHECKLIST (before declaring any task complete)

- [ ] All interactive states implemented (loading, empty, error, disabled, active, focus)
- [ ] No `as any` or `@ts-ignore` in changed files
- [ ] `lsp_diagnostics` clean on all changed files
- [ ] Copy self-audit passed (no AI-sounding or grammatically broken strings)
- [ ] i18n: new strings added to both zh and en dictionaries
- [ ] Keyboard navigation tested (Tab through all interactive elements)
- [ ] Mobile layout verified (no horizontal scroll, no overflow, touch targets ≥ 44px)
- [ ] No inline `style={{}}` where a Tailwind class would work
- [ ] No hardcoded z-index values outside the established scale
- [ ] Performance: no backdrop-blur on scrollable elements, no unnecessary will-change
