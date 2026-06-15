## 1. Template analysis workbench

- [x] 1.1 Design and add template-analysis session/progress endpoints in `server.py` and any supporting session module so analysis state can be resumed and streamed.
- [x] 1.2 Update `frontend/src/pages/TemplateAnalysisPage.tsx`, `frontend/src/api.ts`, and `frontend/src/types.ts` to consume session-style analysis progress and render a bounded overview.
- [x] 1.3 Add a template-analysis detail surface that renders the full streamed trace and complete task list without expanding the main page.

## 2. Generate and shared bounded-detail patterns

- [x] 2.1 Align `frontend/src/pages/GeneratePage.tsx` and related shared components with the updated `generate-minimal-preview` contract for bounded inline previews plus full trace drawer.
- [x] 2.2 Reuse or extract shared preview/detail UI behavior in `frontend/src/components/OutputBlock.tsx` or adjacent shared UI modules so generate and template-analysis surfaces stay consistent.

## 3. History dashboard data truth

- [x] 3.1 Update history APIs in `server.py` and `core/history.py` so empty, filtered, and unavailable states are explicit and summary data matches the returned record set.
- [x] 3.2 Update `frontend/src/pages/HistoryPage.tsx`, `frontend/src/api.ts`, and `frontend/src/types.ts` to remove silent mock fallback from runtime behavior and render backend-truth, empty, and unavailable states distinctly.
- [x] 3.3 Keep any mock history data in `frontend/src/historyData.ts` behind an explicit development-only path or remove it from the runtime page flow.

## 4. Model option degradation and persistence

- [x] 4.1 Update `core/provider_registry.py`, `core/auth.py`, and `server.py` so model-option responses expose source/warning metadata and fall back to legacy option sets when registry reads fail.
- [x] 4.2 Update settings and template-analysis model selectors in `frontend/src/pages/SettingsPage.tsx` and `frontend/src/pages/TemplateAnalysisPage.tsx` to render all returned options, show degraded-state warnings, and avoid collapsing to a single implicit default.
- [x] 4.3 Adjust model-choice save behavior in backend and frontend so degraded registry mode preserves compatible role-to-model selections instead of silently discarding them.

## 5. Verification

- [x] 5.1 Add or update tests for history API state handling, model-option fallback behavior, and any new template-analysis session logic in `tests/`.
- [x] 5.2 Run targeted frontend/manual verification for template analysis, generate, history, and settings flows to confirm bounded layouts and explicit degraded-state messaging.
