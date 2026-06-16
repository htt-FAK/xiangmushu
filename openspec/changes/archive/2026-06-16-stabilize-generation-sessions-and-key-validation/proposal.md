## Why

The current product breaks user trust in the main workflow: Generate and Knowledge Base page state disappears after navigation, API Keys can be saved without proving they work, and model failures do not clearly distinguish invalid keys, exhausted quota, or temporary network/provider issues. At the same time, first-time users still need a clearer path through setup, knowledge upload, template selection, and generation.

## What Changes

- Add workflow state continuity across route changes so important page state is preserved instead of resetting when users navigate away.
- Introduce resumable generation sessions with a server-owned session identifier, recoverable progress snapshots, and reconnectable live updates so users can return to `/generate` and continue watching active progress.
- Preserve Knowledge Base page context such as the selected library, recent upload results, and the latest source statistics during in-app navigation.
- Add strong API Key validation before save: the system must test the user-provided key directly, try more than one low-cost candidate model when appropriate, and refuse to save the key unless validation succeeds.
- Return structured API Key validation and generation failure diagnostics that distinguish invalid credentials, exhausted quota, permission/model access problems, network failures, and transient provider errors.
- Add guided first-run onboarding across Home, Settings, Knowledge Base, Template, and Generate so users can see what is required before generation and what step to do next.
- Add app-shell polish for workflow awareness and branding, including an active generation indicator outside the Generate page and a branded browser tab icon based on the provided SVG asset.

## Capabilities

### New Capabilities
- `workflow-state-continuity`: Preserves workflow-critical page state across navigation and provides recoverable live generation sessions that can be resumed from `/generate`.
- `user-api-key-validation`: Validates user-owned API Keys before save with direct provider checks, fallback model probing, and structured failure classification.
- `guided-first-run`: Guides first-time users through API Key setup, knowledge preparation, template selection, and generation readiness with clear next actions.
- `app-shell-branding`: Exposes shell-level workflow awareness and browser-tab branding, including a branded favicon and active-generation status outside the Generate page.

### Modified Capabilities
- `hello-page`: Update the homepage requirements so the landing experience reflects the guided setup path and current workflow readiness.

## Impact

- Backend: `server.py`, generation SSE flow, session storage/state management, user API Key routes, and model error normalization.
- Frontend: `frontend/src/App.tsx`, `frontend/src/pages/GeneratePage.tsx`, `frontend/src/pages/KnowledgeBasePage.tsx`, `frontend/src/pages/SettingsPage.tsx`, `frontend/src/pages/HomePage.tsx`, `frontend/src/api.ts`, `frontend/src/types.ts`, `frontend/src/i18n.ts`, and shell-level state handling.
- Static assets: add and reference the provided SVG-based browser icon in `frontend/index.html` and related public assets as needed.
- APIs: new or extended authenticated endpoints for generation session start/status/stream recovery and API Key validation diagnostics.
- Persistence/systems: session state storage for active generations, plus preservation of frontend workflow context during navigation.
