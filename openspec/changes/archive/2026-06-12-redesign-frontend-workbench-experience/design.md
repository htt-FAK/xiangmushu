## Context

The React/Vite frontend already includes authenticated navigation, a Generate page with live stream state, a trace drawer, output blocks, billing summaries, acceptance checks, template analysis, knowledge management, and settings. The current Generate page implementation exposes many useful controls, but large headers, expanded option lists, and stacked panels push the live output and delivery actions away from the first viewport. An archived spec also moved the main page toward a minimal streaming banner, but the desired product direction is now to preserve visible streaming output on the main page and use the drawer for detailed inspection rather than as the primary output surface.

This change is frontend-first. The new history/articles page should prove the information architecture and presentation using mock data, without waiting for backend session-history APIs.

## Goals / Non-Goals

**Goals:**

- Keep live streaming output visible and emotionally central on `/generate`.
- Reduce Generate page scroll pressure by replacing large page headers and always-expanded setup lists with compact workbench controls.
- Preserve the existing trace/detail drawer pattern for full generation process review, model routing, evidence, audit issues, and per-section actions.
- Add a new history/articles page that shows generated article records, downloads, aggregate token/cost totals, and model-usage chart details using mock frontend data.
- Keep the current dark/cyan/lime visual theme while improving hierarchy, density, and state transitions.
- Verify desktop and mobile layouts with browser screenshots.

**Non-Goals:**

- No backend API, database, or session persistence changes in this phase.
- No replacement of existing generation streaming APIs or session state logic.
- No change to document generation, billing calculation, model routing, template analysis, or knowledge ingestion behavior.
- No requirement to add a chart dependency; a lightweight custom SVG/CSS chart is acceptable.

## Decisions

### Decision 1: Keep Generate as the live creation surface

The main Generate page will continue rendering streamed output blocks inline, with the currently active block visually emphasized. The trace drawer remains available for full-screen review, but it is not the only place users can see section output.

Alternative considered: keep the minimal banner and move all output to the drawer. This reduces page height but hides the most satisfying part of the product and conflicts with the desired interaction model.

### Decision 2: Move setup density into compact controls

The Generate page should use a compact command/workbench layout: selected knowledge base, selected template, quality mode, start/stop, and key status remain immediately reachable, while long template/knowledge lists and advanced controls move into constrained selectors, popovers, drawers, or compact panels. This keeps the page useful without making the user scroll past every option.

Alternative considered: leave the two-column layout and only shrink spacing. That would help a little, but the long option rails would still dominate the viewport when many templates exist.

### Decision 3: Add history as a separate asset-management page

Historical documents, aggregate totals, downloads, and model-consumption analysis belong in a dedicated page rather than the Generate page. Generate stays focused on the current run; history becomes the place for reviewing previous runs and costs.

Alternative considered: add a history panel below Generate. That would worsen the existing scroll problem and mix current-run work with asset management.

### Decision 4: Use mock data behind a clear frontend boundary

The history page should define a local `HistoryArticle` shape and mock dataset that mirrors likely future backend data: article metadata, artifact URLs, input/output tokens, cost, status, and per-model usage. The UI should consume this data through a small local helper so later backend integration can replace the data source without redesigning the page.

Alternative considered: wait for backend APIs. That would delay UX validation and make it harder to iterate on the desired dashboard behavior.

### Decision 5: Implement model usage chart with local rendering first

The model usage chart can be implemented as a small React/SVG donut or pie visualization with an adjacent legend. This avoids adding a dependency for one chart while still making the interaction feel complete.

Alternative considered: install a chart library immediately. That may be useful later, but it is unnecessary for the first frontend-only dashboard.

## Risks / Trade-offs

- Main-page streaming output can still become tall for large documents -> Mitigate by constraining the main output viewport, showing active/recent blocks prominently, and keeping full trace available in the drawer.
- Compact selectors may hide discoverability for new users -> Mitigate with clear selected values, search affordances, and empty states that link to template/knowledge setup.
- Mock history data can drift from future backend response shape -> Mitigate by documenting the local data type and isolating it behind a helper.
- Custom chart rendering may be less feature-rich than a library -> Mitigate with simple accessible legend text and deterministic color mapping.
- More animation can reduce clarity or performance -> Mitigate by limiting motion to state transitions, progress, active streaming, and new item insertion.

## Migration Plan

1. Introduce the history page route, navigation item, local mock data, and chart components without touching backend APIs.
2. Refactor Generate page layout around the existing generation state and output rendering logic, keeping API calls and session behavior intact.
3. Add compact selectors/advanced settings while preserving current `enableWeb`, `enableAudit`, `enableVisualAudit`, `qualityMode`, template, and knowledge state semantics.
4. Update i18n labels for the new page, compact controls, chart labels, history statuses, and revised Generate text.
5. Verify with `npm run build` and Playwright screenshots for desktop/mobile Generate and history pages.

Rollback is frontend-only: revert route/navigation/history additions and restore the previous Generate page layout if needed. No data migration is required.
