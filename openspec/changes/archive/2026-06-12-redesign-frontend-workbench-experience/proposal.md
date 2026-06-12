## Why

The current frontend has useful generation controls and live output, but the main workflows feel visually heavy and too scroll-dependent because setup, status, outputs, acceptance, and analytics compete in the same vertical stack. Users also need a dedicated place to review and download previously generated articles and understand token/model usage, even before backend history APIs are available.

## What Changes

- Redesign the Generate page into a compact workbench that preserves the existing main-page streaming output and detail drawer behavior while reducing header height, tightening controls, and keeping primary actions visible.
- Keep live streaming output as the central Generate page experience; use expanded detail views for full generation trace, model routing, evidence, audit issues, and per-section actions.
- Add a frontend-only history/articles page with mock data showing previously generated documents, download actions, run metadata, aggregate totals, and model token usage.
- Add a model-usage chart interaction on the history page so users can inspect total or per-article model consumption in a pie/donut-style breakdown.
- Add navigation and shared UI affordances needed for the new history page without changing backend APIs in this phase.

## Capabilities

### New Capabilities
- `generation-history-dashboard`: Frontend requirements for browsing historical generated articles, viewing aggregate usage, downloading historical artifacts, and inspecting model consumption with mock data.

### Modified Capabilities
- `generate-minimal-preview`: Replace the minimal-banner-only Generate page requirement with a compact workbench that keeps live streaming output visible on the main page while retaining the detail drawer for full trace inspection.

## Impact

- Affected code: `frontend/src/App.tsx`, `frontend/src/pages/GeneratePage.tsx`, a new frontend history page, shared UI components in `frontend/src/components`, `frontend/src/i18n.ts`, and related frontend types/helpers.
- APIs: no backend API contract changes; the history page SHALL use frontend mock data in this change.
- Dependencies: no required new dependency; charting can be implemented with CSS/SVG/React unless the implementation intentionally introduces a small chart library.
- Verification: TypeScript build plus browser screenshots for desktop and mobile Generate page, and desktop/mobile history page states.
