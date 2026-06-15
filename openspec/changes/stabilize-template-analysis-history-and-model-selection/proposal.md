## Why

The workbench surfaces have drifted into inconsistent states: document generation uses a bounded live view plus detail trace, while template analysis still blocks and expands the page indefinitely, history silently falls back to mock data, and model selection depends on registry data without surfacing degraded states. We need to stabilize these flows now so users can trust what is live, what is historical, and which models are actually available before adding more workflow complexity.

## What Changes

- Add a template-analysis workbench flow with resumable progress state, bounded inline summary, and a dedicated detail surface for the full streamed trace and task list.
- Modify the Generate page preview contract so the main workbench remains bounded while the complete streamed trace and section-level actions stay in the detail drawer.
- Add a backend-truth history dashboard capability that distinguishes real empty states from backend-unavailable states and removes silent mock fallback from production behavior.
- Harden model-option and model-choice behavior so settings and template-analysis surfaces expose all available models for a role, warn when registry-backed data is degraded, and avoid collapsing to a single implicit default.
- Introduce explicit degraded-state handling for history and model-option APIs when registry or persistence dependencies are unavailable.

## Capabilities

### New Capabilities
- `template-analysis-workbench`: Template analysis progress, bounded summary cards, and full trace/detail behavior for streamed analysis output.
- `generation-history-dashboard`: History records sourced from backend article/session data with explicit empty, error, and filtered-summary states.

### Modified Capabilities
- `generate-minimal-preview`: Update the Generate page requirements to keep the main output surface bounded while preserving the full trace drawer as the complete streamed detail view.
- `model-provider-registry`: Update model-option and user-choice requirements to preserve role-level choice sets, surface degraded registry states, and define fallback persistence behavior when registry-backed reads fail.

## Impact

- Affected frontend code: `frontend/src/pages/TemplateAnalysisPage.tsx`, `frontend/src/pages/GeneratePage.tsx`, `frontend/src/pages/HistoryPage.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`, and shared output/detail UI components.
- Affected backend code: `server.py`, `core/history.py`, `core/provider_registry.py`, `core/auth.py`, and any new template-analysis session/event support module required to mirror generation-session behavior.
- API surface: add or revise template-analysis progress/detail endpoints, revise history responses to distinguish empty vs unavailable states, and extend model-option responses with degradation metadata or fallback-source metadata.
- Dependencies and systems: MySQL-backed history/model registry access, generation-session-style SSE/event streaming patterns, and existing legacy `USER_MODEL_OPTIONS` fallback configuration.
