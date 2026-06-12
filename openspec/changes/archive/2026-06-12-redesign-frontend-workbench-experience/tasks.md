## 1. Navigation and Shared Frontend Structure

- [x] 1.1 Add a new history/articles route and navigation item in `frontend/src/App.tsx` using an appropriate lucide icon and existing protected-shell patterns.
- [x] 1.2 Add i18n labels in `frontend/src/i18n.ts` for the history page, aggregate cards, filters, chart labels, statuses, and revised Generate workbench text.
- [x] 1.3 Add or extend shared frontend types in `frontend/src/types.ts` for mock history article records and per-model usage rows.
- [x] 1.4 Add small shared UI helpers/components in `frontend/src/components` only where they reduce duplication for compact stats, filters, model legends, or workbench actions.

## 2. Generate Page Workbench Redesign

- [x] 2.1 Refactor `frontend/src/pages/GeneratePage.tsx` page header into a compact workbench header/command surface that keeps selected knowledge base, selected template, quality mode, and start/stop controls reachable near the top.
- [x] 2.2 Replace always-expanded long knowledge/template option rails with compact selectors or constrained selection panels while preserving search, selected values, disabled states, and empty links.
- [x] 2.3 Keep live streaming output visible in the main Generate page content area during active runs, including the active/current section and recently streamed output.
- [x] 2.4 Preserve the trace full-screen drawer as the detailed view for full `OutputBlock` metadata, evidence, audit issues, generated text, and per-section regenerate actions.
- [x] 2.5 Keep final document and quality report download actions easy to reach from the main Generate workbench after completion.
- [x] 2.6 Add restrained state transitions for run start, active streaming, section arrival, progress updates, and artifact readiness using existing CSS/Tailwind patterns.
- [x] 2.7 Verify the existing `enableWeb`, `enableAudit`, `enableVisualAudit`, `qualityMode`, template, knowledge base, and session subscription behavior remains unchanged.

## 3. History Articles Page

- [x] 3.1 Create a new history page component under `frontend/src/pages` backed by local mock history article data.
- [x] 3.2 Render aggregate totals for generated article count, input tokens, output tokens, combined tokens, and total cost from the displayed records.
- [x] 3.3 Render a searchable/filterable history record list with status, title, template, knowledge context, created time, token usage, cost, and artifact actions.
- [x] 3.4 Render a selected-article detail panel with metadata, document/report actions, token totals, cost, and per-model usage details.
- [x] 3.5 Implement a pie or donut-style model usage chart with textual legend for aggregate usage and selected-article usage without requiring backend data.
- [x] 3.6 Isolate mock history data and derived aggregations behind a small helper/module so a future backend data source can replace it cleanly.

## 4. Responsive and Visual Polish

- [x] 4.1 Ensure `/generate` fits the primary setup, live output, status, and delivery controls into a compact desktop workbench without large hero-style vertical waste.
- [x] 4.2 Ensure `/generate` on mobile uses stacked or tabbed/constrained sections so users can reach setup, live output, and delivery controls without incoherent overlap.
- [x] 4.3 Ensure the history page has usable desktop and mobile layouts with readable charts, legends, filters, and selected-record details.
- [x] 4.4 Preserve the existing dark/cyan/lime theme while reducing equal-weight panel noise and avoiding text overflow in controls, cards, charts, and navigation.

## 5. Verification

- [x] 5.1 Run `npm run build` in `frontend` and fix TypeScript or Vite build issues.
- [x] 5.2 Use Playwright to capture desktop and mobile screenshots for `/generate` and the new history route.
- [x] 5.3 Verify Generate page streaming/detail behavior with an existing or mockable session state: main page shows live output and trace drawer still shows full details.
- [x] 5.4 Verify history page filtering, selected record updates, aggregate totals, and model chart legends using the mock dataset.
