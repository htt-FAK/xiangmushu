# xiangmushu Design System — 智能文档生成系统

> 本文件是项目视觉决策的**唯一真相来源**。所有 UI 代码必须引用本文件中的 token，禁止 raw hex / 任意 px / 未经批准的组件模式。
> 配套阅读：`.claude/skills/taste-skill/SKILL.md`（cyberpunk SPA 反 AI-slop 守卫）

---

## 1. Atmosphere & Identity

**A command-center darkroom.** Dense, technical, and calm — the user is orchestrating a document-generation workflow that feels like programming, not marketing. Surfaces are separated by thin tonal shifts and hairline borders, not shadows. Cyan glow is the signature: it appears only when something is live, active, or ready. Never ambient.

Signature idea: **signal glow on deep night**. The single neon color (#36f2e6) activates elements on interaction, then recedes when idle. Think a server rack with only the relevant LEDs lit — never a nightclub.

What it is NOT:
- Not a SaaS dashboard with pastel gradients
- Not a crypto/web3 site with rainbow neon
- Not a generic AI-purple aesthetic
- Not a bright, playful consumer app

---

## 2. Color

### Palette

The palette is a **locked cyberpunk system** defined in `frontend/tailwind.config.ts`. No new hex may be introduced without updating this table first.

**Night scale (surfaces)** — cool-tinted dark blues

| Token | Hex | Usage |
|-------|------|----------|
| `night-950` | `#05060a` | Page background, `<html>`, overlays, deepest surface |
| `night-900` | `#090d14` | Panel backgrounds, sidebar, scroll track |
| `night-850` | `#0d131d` | Card backgrounds, nested surfaces |
| `night-800` | `#111a25` | Elevated cards, hover states for rows |
| `night-700` | `#172332` | Hover highlight (rare), deeper emphasis |

**Signal colors (accents)** — four semantic channels, each with ONE primary role

| Token | Hex | Role | Use for |
|-------|------|------|---------|
| `signal-cyan` | `#36f2e6` | Primary action | CTAs, active states, focused inputs, links, info badges |
| `signal-lime` | `#b8ff5e` | Positive signal | Success states, "done" status, verified status, recommendations |
| `signal-amber` | `#ffb84d` | Warning | Caution banners, pending states, billing warnings |
| `signal-rose` | `#ff4d8d` | Negative signal | Errors, destructive actions, delete buttons, failed states |

**Slates (text/neutral)** — use Tailwind built-ins, no custom tokens

| Tailwind Token | Typical usage |
|----------------|---------------|
| `slate-100` | Primary text (body in dark mode) |
| `slate-300` | Secondary body text |
| `slate-400` | Tertiary hints, icons |
| `slate-500` | Disabled text, section subtitles |
| `slate-600` | Placeholders, muted icons |
| `white` | Headlines, emphasis |

**White-with-opacity (surface differentiation)** — only TWO levels, no others

| Token | Opacity | Usage |
|-------|---------|-------|
| `bg-white/[0.045]` | 4.5% | Elevated surface (panels, card rows) |
| `bg-white/[0.025]` | 2.5% | Subtle inset (secondary cards, inactive nav items) |

❌ **Deprecated**: `bg-white/[0.035]`, `bg-white/[0.03]`, `bg-night-950/45`, `bg-night-950/60`, `bg-night-950/70` — consolidate to the two levels above.

### Rules

- **One accent per context.** A settings card uses `signal-lime`. A generation card uses `signal-cyan`. A home page uses ONE signal color as the page accent — the others appear only in context-specific badges.
- **Accent is interactive, never decorative.** Do not use signal colors on purely ornamental icons, dividers, or backgrounds. They mean "this is live/active/a thing you can act on."
- **Signal-cyan may glow** — only via the `shadow-glow` token on primary CTAs and active nav items. Never spray glow elsewhere.
- **No AI-purple gradients, no random neon effects.** If a new color feels needed, propose adding it to the palette with a justification before applying.
- **Shadows are tinted** — use `rgba(5,6,10,N)` (night-950) instead of pure black. ❌ `rgba(0,0,0,0.34)` is deprecated.

---

## 3. Typography

### Scale

| Level | Tailwind | Font | Weight | Line Height | Tracking | Usage |
|-------|----------|------|--------|-------------|----------|-------|
| Display/lg | `text-3xl md:text-5xl` | `font-display` (Rajdhani) | 600 | 1.1 (`leading-tight`) | 0 | Login hero, landing hero only |
| Display | `text-2xl md:text-3xl` | `font-display` | 600 | 1.2 | 0 | Page titles |
| H2 | `text-xl md:text-2xl` | `font-display` | 600 | 1.3 | 0 | Section headers inside panels |
| H3 | `text-lg md:text-xl` | `font-display` | 600 | 1.4 | 0 | Card titles, panel headers |
| Body | `text-sm` | `font-sans` (Inter) | 400 | 1.6 (`leading-6`) | 0 | Default text, form labels |
| Body/sm | `text-xs` | `font-sans` | 400 | 1.5 | 0 | Hints, secondary info |
| Overline | `text-xs` | `font-sans` | 600 | 1.3 | `tracking-[0.16em]` | Field labels, small caps |
| Mono | `text-sm font-mono` | monospace fallback | 400 | 1.6 | 0 | Code keys, location_hints preview |

### Font Stack

Defined per-family in `tailwind.config.ts` and mirrored in `src/styles.css`:

```
font-sans: Inter, ui-sans-serif, system-ui, -apple-system,
  BlinkMacSystemFont, Segoe UI, Microsoft YaHei, PingFang SC,
  sans-serif

font-display: Rajdhani, Inter, ui-sans-serif, system-ui,
  Microsoft YaHei, sans-serif
```

- CJK fallbacks (`Microsoft YaHei`, `PingFang SC`) are **essential** — Chinese is the primary language.
- **Rajdhani is display only** — never use below `text-xl`. Body text stays Inter.
- Use `font-display: swap` at Google Fonts level for fast load.
- **Numeric columns** should add `font-variant-numeric: tabular-nums` (or `tabular-nums` utility) to stat displays, billing tables, cost columns — prevents number jitter.

### Rules

- **Max 2 font families.** Rajdhani + Inter. Mono only for code previews.
- **Body text never below `text-xs` (12px).** `text-[10px]` and similar are forbidden.
- **Headlines that wrap to 4+ lines are too large** — reduce scale before truncating content.
- **Max reading width for body paragraphs**: `max-w-[65ch]` for long-form description text (hero descriptions, error explanations).
- **`text-wrap: balance`** on page titles (`<h1>`) to prevent orphaned words on narrow screens.
- **Chinese punctuation**: prefer full-width in Chinese copy (`，` `。` `：` not `, :`).

---

## 4. Spacing & Layout

### Base Unit

All spacing derives from a **4px base**. Tokens below are in multiples of 4.

| Tailwind | px | Usage |
|----------|----|-------|
| `p-1 / gap-1 / space-y-1` | 4 | Icon-to-label, tight inline groups |
| `p-2 / gap-2 / space-y-2` | 8 | List item separation, compact groups |
| `p-3 / gap-3 / space-y-3` | 12 | Default form field inner spacing |
| `p-4 / gap-4 / space-y-4` | 16 | Card padding (mobile), form grouping |
| `p-5 / gap-5 / space-y-5` | 20 | Card padding (desktop `md:p-5`) |
| `p-6 / gap-6 / space-y-6` | 24 | Section separation, page-level gap |
| `p-8 / gap-8` | 32 | Login page internal spacing |
| `p-12` | 48 | Major section vertical rhythm |

### Layout

- **Max content width**: `max-w-7xl` = 1280px (applied in `Shell`'s `<main>`)
- **Sidebar**: `w-72` = 288px, visible at `lg:` (1024px) and above
- **Mobile breakpoint**: `< md` (768px) — bottom nav bar replaces sidebar
- **Breakpoints**: Tailwind defaults
  - `sm`: 640px (narrow phones / small tablets in landscape)
  - `md`: 768px (tablets, sidebar collapses)
  - `lg`: 1024px (laptops, sidebar visible)
  - `xl`: 1280px (desktop, max content width reached)
  - `2xl`: 1536px (large desktop, no new layout change — use whitespace)
- **Touch target minimum**: `min-h-11` (44px) per WCAG 2.5.8, used on all interactive elements
- **Touch target preferred**: `min-h-12` (48px) for primary CTAs

### Rules

- **No magic numbers.** Every margin/padding/gap maps to a token in the table above.
- **Never use `h-screen`** — always `min-h-[100dvh]` to prevent iOS Safari viewport jumps.
- **Asymmetric grids are permitted**: e.g. `xl:grid-cols-[0.85fr_1.15fr]` on TemplateAnalysisPage, `xl:grid-cols-[390px_minmax(0,1fr)]` on KnowledgeBasePage — only when the left/right content genuinely needs different weights.
- **Section-level gap consistency**: a page uses ONE `space-y-*` value for its top-level sections, not multiple.

---

## 5. Components

Reusable patterns used 2+ times. Documented as they exist in `src/components/ui.tsx` and pages.

### Panel (basic card)

```tsx
<section className="border border-white/10 bg-white/[0.045] p-4 shadow-panel md:p-5">
```

- **Variants**: default only; accent via child elements (icons, colored headings)
- **Spacing**: `p-4` mobile, `p-5` desktop (`md:p-5`)
- **States**: default only. `hover:` variants are for child elements, not the Panel itself.
- **Use for**: any grouped content. Do NOT wrap trivial `div`s in Panel — use `divide-y` or `space-y` for those.
- **Accessibility**: semantic `<section>` tag; no aria needed.

### Button (3 variants)

```tsx
<button className="inline-flex min-h-11 items-center justify-center gap-2 border px-4 text-sm font-semibold transition active:scale-[0.97] active:brightness-90 disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-45">
```

| Variant | Purpose | Classes |
|---------|---------|---------|
| `primary` (default) | Main CTA, submit, confirm | `border-signal-cyan/70 bg-signal-cyan text-night-950 shadow-glow hover:bg-white` |
| `ghost` | Secondary action, cancel, navigation | `border-white/10 bg-white/[0.055] text-slate-100 hover:border-signal-cyan/50 hover:text-signal-cyan` |
| `danger` | Delete, destructive actions | `border-signal-rose/50 bg-signal-rose/10 text-signal-rose hover:bg-signal-rose hover:text-white` |

- **Missing variants (proposed for future)**: `secondary` (muted primary), `link` (text-only with underline on hover).
- **Height**: `min-h-11` (44px) default; `min-h-12` for primary CTAs on form pages.
- **States**: default, hover, active (scale-down), focus-visible ring, disabled (45% opacity).
- **Accessibility**: `<button>` tag, type explicitly set (`submit`/`button`/`reset`), disabled state removes pointer events.

### Input

```tsx
<input className="min-h-12 w-full border border-white/10 bg-night-950/70 px-3 text-sm text-white outline-none transition placeholder:text-slate-600 focus:border-signal-cyan/70" />
```

- **Label**: always uses `Field` wrapper above with uppercase overline
- **Focus**: `focus:border-signal-cyan/70`, no ring for now (proposed: add `focus:ring-2 focus:ring-signal-cyan/30`)
- **Error**: inline text below in `text-xs text-signal-rose`, associated via `aria-describedby`
- **Accessibility**: `<label htmlFor>` wired to input `id` (currently via Field wrapper)

### Field (labeled wrapper)

```tsx
<label className="block">
  <span className="mb-2 block text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
    {label}
  </span>
  {children}
</label>
```

- Uses native `<label>` semantics, no `htmlFor` wiring currently — children must be focusable.
- **Overline style** is the canonical "field label" pattern.

### Stat (metric display)

```tsx
<div className="border border-white/10 bg-night-850/80 p-3.5 md:p-4">
  <p className="text-[11px] uppercase tracking-[0.12em] text-slate-500">{label}</p>
  <p className="text-xl font-display font-semibold">{value}</p>
</div>
```

- **Tones**: `cyan`, `lime`, `amber`, `rose` — colors only the VALUE, label stays slate-500.
- **Add**: `font-variant-numeric: tabular-nums` on value (pending consolidation).
- Accessibility: wrap value with `role="status"` when representing live data.

### PageHeader (page top)

```tsx
<header className="mb-5 flex flex-col gap-4 border-b border-white/10 pb-5 md:mb-8 lg:flex-row lg:items-end lg:justify-between">
  <div>
    <p className="text-xs font-semibold uppercase tracking-[0.22em] text-signal-cyan">{eyebrow}</p>
    <h1 className="font-display text-2xl md:text-5xl font-semibold">{title}</h1>
    <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300">{description}</p>
  </div>
  {action && <div className="w-full lg:w-auto">{action}</div>}
</header>
```

- **Eyebrow restraint**: Only used on page headers, never inside page sections. Max 1 per page.
- **Title sizing**: `text-2xl` mobile, `text-5xl` desktop (`md:text-5xl`). Add `text-wrap: balance`.
- **Description**: `max-w-2xl` (672px) constrains reading width.

### EmptyState (no-data)

```tsx
<div className="border border-dashed border-white/15 bg-night-900/60 p-6 text-center md:p-8">
  <p className="text-xl font-display font-semibold">{title}</p>
  <p className="mt-2 text-sm text-slate-400">{body}</p>
</div>
```

- Used in every list/card-grid when data is empty.
- **Add proposed**: action button slot (e.g., "Upload template" CTA)

### ErrorBanner (validation error block)

```tsx
<div className="mb-5 border border-signal-rose/40 bg-signal-rose/10 px-4 py-3 text-sm text-rose-100">
  {message}
</div>
```

- Used at page level and inside form cards.
- **Accessibility**: `role="alert"` should be added (pending).

### DetailOverlay (full-screen modal)

```tsx
<div className="fixed inset-0 z-50 flex flex-col overflow-hidden bg-night-950/95">
  <div className="flex shrink-0 items-start justify-between gap-4 border-b border-white/10 px-4 py-3">
    ...header with close button
  </div>
  <div className="flex-1 overflow-y-auto px-4 py-4">
    {children}
  </div>
</div>
```

- **z-index**: `z-50` (topmost modal layer)
- **Close**: X button top-right, h-9 w-9, keyboard: Esc key (pending implementation).
- **Focus trap**: NOT yet implemented — pending accessibility enhancement.
- **Scroll**: body scroll disabled while modal open (pending).

---

## 6. Motion & Interaction

### Timing

| Type | Tailwind class | Duration | Usage |
|------|----------------|----------|-------|
| Micro | `transition` (default) | 150ms | Button press, hover state change |
| Standard | `transition duration-200` | 200ms | Panel open/close, tab switch |
| Tactile | `active:scale-[0.97]` | Instant + transition back | Button press feedback |
| Loader | `animate-spin` | 1000ms loop | Loading spinners |
| Skeleton | `animate-pulse` | 2000ms loop | Skeleton loaders |
| Transform | `transform duration-100` | 100ms | PullToRefresh drag |

### Rules

- **Only `transform` and `opacity` are animated.** Never `top`, `left`, `width`, `height`, `margin`, `padding`.
- **`active:scale` is the tactile language** — buttons use `[0.97]`, nav items use `[0.98]`.
- **No automatic animations on data-only sections.** Lists/tables/grids don't animate unless user triggers them.
- **`prefers-reduced-motion`**: Tailwind's `transition` utility automatically respects this. For `animate-spin` and `animate-pulse`, add `motion-safe:` or `motion-reduce:` prefixes where they appear (pending consolidation).
- **`will-change: transform`** only on elements that actually animate (fixed gradient backgrounds in Shell, PullToRefresh container). Spraying it causes layer explosion.
- **Scroll animations**: never use `window.addEventListener("scroll", ...)` — use IntersectionObserver or CSS `scroll-driven animations`.

---

## 7. Depth & Surface

### Strategy: Borders-primary with subtle panel shadows

The system uses **borders as the primary depth separator**, not shadows. Shadows are applied only to Panel and overlays. Most visual separation comes from:

1. **Hairline borders**: `border border-white/10` (primary), `border-white/5` (subtle)
2. **Tonal shifts**: `bg-night-950` (page) → `bg-night-900` (panel) → `bg-night-850` (nested card)
3. **White-opacity surfaces**: `bg-white/[0.045]` for elevated (rare)

### Depth Hierarchy (from back to front)

| Layer | Token | Usage |
|-------|-------|-------|
| Page background | `bg-night-950` | Root canvas |
| Decorative gradients | `bg-[linear-gradient(...)]` + `will-change: transform` | Visual atmosphere (fixed behind content) |
| Sidebar / Shell | `bg-night-900` | Persistent navigation frame |
| Content panels | `bg-night-900` + `border-white/10` | Primary grouping |
| Nested cards inside panels | `bg-night-850/70` + `border-white/10` | Secondary grouping |
| Active/selected rows | `bg-signal-cyan/10 + border-signal-cyan/60` | Highlighted state |
| Modal overlays | `bg-night-950/95` (full opacity) | Full-screen detail |

### Shadow Tokens

| Token | Value | Usage |
|-------|-------|-------|
| `shadow-panel` | `0 18px 60px rgba(5,6,10,0.5)` | Panels on non-950 backgrounds (proposed: tint to night-950) |
| `shadow-glow` | `0 0 0 1px rgba(54,242,230,0.18), 0 0 20px rgba(54,242,230,0.12)` | Primary CTAs, active nav items ONLY |
| `shadow-[0_18px_54px_rgba(54,242,230,0.18)]` | inline | Primary CTA emphasis on login/auth pages |

❌ **Deprecated**: `backdrop-blur-*` on all containers except decorative overlays. Causes GPU jank. Use solid opaque backgrounds instead.

### Rules

- **Never use `backdrop-blur` on scrollable containers.** Mobile GPU performance collapse.
- **Solid backgrounds preferred over opacity.** `bg-night-900` over `bg-night-900/88`.
- **Glow is precious** — appears only on the primary CTA of the current view and on active nav items.
- **Border-first depth** — before reaching for a shadow, ask: would a `border-white/10` or tonal shift suffice?
- **No `drop-shadow` filters** — these aren't GPU-accelerated and cause repaints on scroll.

---

## 8. Icon Scale

All icons from `lucide-react`. Stroke width standardized to **2** (Tailwind `strokeWidth` default).

| Size | px | Usage |
|------|----|-------|
| `sm` | 16 | Inline with `text-xs`, form error icons, small actions |
| `md` | 20 | Default for list item actions, nav icons, section icons |
| `lg` | 24 | Card header accents, brand logos in auth |
| `xl` | 32 | Landing hero accents (rare) |

❌ **Deprecated**: `size={15, 17, 18, 21, 22, 25, 28, 34}` — consolidate to the 4 sizes above.

### Rules

- **Decorative icons**: `aria-hidden="true"` (so screen readers don't read them).
- **Action icons**: either `<button>` with `aria-label` or `<a>` with visible text.
- **Icon colors**: inherit from text color. Use `text-signal-cyan`, `text-signal-lime`, etc. on the wrapper.
- **Do not mix icon families** — only `lucide-react`.

---

## 9. Accessibility (Non-Negotiable)

### Keyboard

- All interactive elements reachable via **Tab**
- Buttons respond to **Enter** and **Space**
- Modals trap focus (**pending implementation**)
- **Esc** closes modals, drawers, dropdowns
- Add **skip-to-content** link (`<a href="#main" className="sr-only focus:not-sr-only">`) (**pending**)

### Screen Readers

- Icon-only buttons: `aria-label` or `title`
- Live regions: `aria-live="polite"` for generation progress, status updates
- Form errors: `aria-describedby` linking to error text (**pending on all forms**)
- `<html lang>`: must switch with i18n (`zh-CN` ↔ `en-US`) (**pending**)

### Color Independence

- Never communicate state via color alone. Always pair with icon, text, or shape change.
- Good: ✓ + lime text + lime border (success)
- Bad: just lime background (unlabeled)

### Contrast

- Body text against night-950: `slate-300` or lighter (≥ 4.5:1)
- Large text (18px+): `slate-400` or lighter (≥ 3:1)
- Interactive text on signal backgrounds: verify 4.5:1 for `text-night-950` on `bg-signal-cyan`

### Motion

- Respect `prefers-reduced-motion`: all Tailwind `transition` already does.
- Animations > 300ms should degrade to instant under reduced motion.

---

## 10. Tokens Reference

### Complete Tailwind Token Map

The complete, definitive source is `frontend/tailwind.config.ts` and `frontend/src/styles.css`. This section maps the most-used ones for quick lookup.

```
Surfaces:
  night-950  #05060a
  night-900  #090d14
  night-850  #0d131d
  night-800  #111a25
  night-700  #172332

Signal:
  cyan       #36f2e6  (primary)
  lime       #b8ff5e  (success)
  amber      #ffb84d  (warning)
  rose       #ff4d8d  (error)

Shadows:
  panel = 0 18px 60px rgba(5,6,10,0.5)
  glow  = 0 0 0 1px rgba(54,242,230,0.18), 0 0 20px rgba(54,242,230,0.12)

Selection:
  background: rgba(54,242,230,0.3)

Scrollbar:
  track:      #090d14
  thumb:      #263546
  thumb-hover: #36f2e6
```

### Tailwind Arbitrary Values in Use

These are the **currently-used** `[x]` values — any new arbitrary value should be consolidated here or promoted to tailwind.config.ts.

| Value | Where used | Proposal |
|-------|-----------|---------|
| `tracking-[0.16em]` | Field labels, overlines | Standardize to this value |
| `tracking-[0.22em]` | PageHeader eyebrow | Standardize to this value |
| `tracking-[0.24em]` | Verification code inputs | OK (numeric display) |
| `tracking-[0.12em]` | Stat labels | Standardize to this value |
| `tracking-[0.18em]` | Sidebar account label | Keep (brand signature) |
| `bg-night-950/70` | Scattered inputs | Migrate to solid `bg-night-950` |
| `bg-white/[0.035]` | Header buttons | Migrate to `bg-white/[0.025]` |
| `scale-[0.97]` | Button active | Keep (tactile standard) |
| `scale-[0.98]` | Nav items active | Keep |
| `scale-[0.99]` | History article | Migrate to `[0.98]` for consistency |

---

## 11. Evolution Rules

### When to UPDATE DESIGN.md

- A new component is reused 2+ times → add to §5
- A new color serves a genuine new semantic role → add to §2
- A spacing token insufficient for a real need → add to §4
- User explicitly changes direction ("make it warmer", "go brutalist")
- A new icon size is needed for a real new use case → add to §8 (rare)

### When NOT to Update

- One-off styling for a unique section → use inline override
- "I might need this later" → you won't
- Temporary experiments → experiments don't get tokens
- A "vibe" without a concrete need → reject

### Discipline

> The design system that grows every week is dying. The one that holds its size or shrinks is getting sharper. Every addition must justify itself by removing ambiguity, not adding options.

---

## Appendix A: Pending Consolidations

These deviations from the current system were flagged during the Phase 0 audit. Each has a priority and a proposed consolidation path.

**Status: 18 / 19 items fixed. 1 deferred (custom `<select>` dropdown — native browser select is acceptable for now).**

| # | Deviation | Impact | Fix | Priority | Status |
|---|-----------|--------|-----|----------|--------|
| 1 | 5 different night-950 opacities | Visual noise | Consolidate to 1 solid value | 🔴 High | ✅ Fixed |
| 2 | 4 different white opacities | Visual noise | Consolidate to 2 levels | 🔴 High | ✅ Fixed |
| 3 | 11 icon sizes | Visual noise | Consolidate to 4 (16/20/24/32) | 🔴 High | ✅ Fixed |
| 4 | Login `backdrop-blur-2xl` | Perf + consistency | Remove | 🔴 High | ✅ Fixed |
| 5 | `rounded-lg` in LoginForm | Consistency | Remove (all sharp) | 🔴 High | ✅ Fixed |
| 6 | No DESIGN.md until now | Foundation | Resolved | — | ✅ Done |
| 7 | Stats use proportional numbers | Readability | Add `tabular-nums` | 🟡 Medium | ✅ Fixed |
| 8 | No `max-w-[65ch]` on body text | Readability | Add on description paragraphs | 🟡 Medium | ✅ Fixed |
| 9 | Native `<select>` | Consistency | Build custom dropdown | 🟡 Medium | ⏸️ Deferred |
| 10 | `shadow-panel` in pure black | Aesthetic | Tint to night-950 | 🟢 Low | ✅ Fixed |
| 11 | Login `rounded-lg` badge | Consistency | Remove | 🟢 Low | ✅ Fixed |
| 12 | 生成舱 naming | Clarity | Changed to 生成工作台 | 🟢 Low | ✅ Fixed |
| 13 | Hardcoded Chinese in code | i18n | Moved 52 strings to i18n.ts | 🟡 Medium | ✅ Fixed |
| 14 | Skip-to-content link missing | A11y | Added to Shell | 🟡 Medium | ✅ Fixed |
| 15 | Modal focus trap missing | A11y | Added useFocusTrap hook | 🟡 Medium | ✅ Fixed |
| 16 | `<html lang>` not dynamic | A11y | Sync in I18nProvider | 🟢 Low | ✅ Fixed |
| 17 | Button variants lacking | UX | Added secondary + link | 🟢 Low | ✅ Fixed |
| 18 | Signal colors overused in views | Visual hierarchy | One accent per page unified | 🟡 Medium | ✅ Fixed |
| 19 | Decorative icons lack aria-hidden | A11y | Added to 128 icons (17 files) | 🟢 Low | ✅ Fixed |

---

## Appendix B: Brand Guidelines Summary

**Do:**
- Deep night backgrounds, cyan accents, sharp corners
- Technical language, clear hierarchy, minimal motion
- Tonal shifts and hairlines for surface separation

**Don't:**
- Pastel gradients, rounded corners everywhere, AI-purple aesthetic
- Drop shadows on every card, generic stock imagery
- Emoji as icons, rounded pill buttons as default
- 3-column equal feature grids, all-caps everywhere
- "Elevate / Seamless / Unleash" type marketing copy

**The vibe in one phrase:**
> "Programmer's desk at 2am, the one good terminal lit up in cyan."
