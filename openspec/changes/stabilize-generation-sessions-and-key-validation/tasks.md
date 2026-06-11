## 1. Generation Session Infrastructure

- [x] 1.1 Add a server-side generation session manager module and data structures that track user ownership, params snapshot, status, progress, outputs, billing, downloads, and terminal errors for one active session per user.
- [x] 1.2 Refactor `server.py` generation entrypoints to create and update sessions through the session manager instead of keeping live generation state only inside a single request-scoped SSE handler.
- [x] 1.3 Add authenticated backend endpoints in `server.py` for generation session start, session snapshot/status recovery, and session stream subscription by `session_id`, including user-ownership enforcement.
- [x] 1.4 Normalize generation-time provider failures into structured application error codes and attach them to generation session events and snapshots.

## 2. API Key Validation and Diagnostics

- [x] 2.1 Add a dedicated API Key validation routine that uses only the submitted user key, probes an ordered set of low-cost candidate models, and never falls back to platform-managed credentials.
- [x] 2.2 Extend the API Key backend routes in `server.py` and supporting modules such as `core/billing.py` and provider helpers to require successful validation before saving an encrypted key.
- [x] 2.3 Implement structured validation result payloads and error classification for invalid key, quota exhaustion, permission/model access issues, network failures, provider failures, and unknown failures.
- [x] 2.4 Add backend tests covering successful validation, rejected save on failed validation, multi-model probe behavior, and error classification for key and generation failures.

## 3. Frontend Workflow Recovery

- [x] 3.1 Introduce a shared workflow state layer in `frontend/src` that preserves Generate and Knowledge Base page context across route changes.
- [x] 3.2 Refactor `frontend/src/pages/GeneratePage.tsx`, `frontend/src/api.ts`, and `frontend/src/types.ts` to start generation sessions, recover active session snapshots on mount, reconnect to session streams, and restore outputs/progress after navigation.
- [x] 3.3 Update `frontend/src/pages/KnowledgeBasePage.tsx` to preserve selected knowledge base context, recent upload results, and latest source statistics during in-app navigation while still refreshing canonical server data.
- [x] 3.4 Update `frontend/src/App.tsx` and shared shell UI to surface active generation status outside `/generate` and provide a direct return path to the active session.

## 4. Settings, Onboarding, and Branding

- [x] 4.1 Update `frontend/src/pages/SettingsPage.tsx`, `frontend/src/api.ts`, and `frontend/src/types.ts` so API Key save flows run validation first, block save on failure, and present actionable validation diagnostics.
- [x] 4.2 Update `frontend/src/pages/HomePage.tsx`, `frontend/src/pages/GeneratePage.tsx`, and `frontend/src/i18n.ts` to show guided first-run readiness for API setup, knowledge preparation, template availability, and generation readiness.
- [x] 4.3 Add the provided SVG brand asset to the frontend static assets and configure `frontend/index.html` to use it as the browser tab favicon.

## 5. Verification

- [x] 5.1 Add or update frontend typing and localization coverage for generation session recovery, validation diagnostics, shell indicators, and onboarding messaging.
- [x] 5.2 Run backend-focused tests for the new session and validation flows, run `npm run build` in `frontend`, and fix any regressions found before marking the change complete.
