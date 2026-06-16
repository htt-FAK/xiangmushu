## 1. Backend Data And Configuration

- [x] 1.1 Add AI model pricing and API Key encryption configuration in `config.py` and environment examples.
- [x] 1.2 Add SQLite initialization and helpers for `billing_records` and `user_api_keys` in the backend data/auth layer.
- [x] 1.3 Implement API Key encryption/decryption helpers using Fernet-compatible key material.

## 2. Backend APIs And Generation Integration

- [x] 2.1 Add authenticated user API Key status, save, and delete endpoints under `/api/user/apikey`.
- [x] 2.2 Add authenticated `GET /api/billing/summary` endpoint scoped to the current user.
- [x] 2.3 Extract usage metadata from LLM responses and record per-generation billing cost.
- [x] 2.4 Prefer the authenticated user's saved API Key for generation while preserving platform default fallback.
- [x] 2.5 Return latest generation billing metadata to the frontend when generation completes.

## 3. Frontend Settings And Billing UI

- [x] 3.1 Add `/settings` route and sidebar settings entry in `frontend/`.
- [x] 3.2 Add localized settings/API Key acknowledgement/save/delete UI with full-screen confirmation dialog.
- [x] 3.3 Add frontend API client/types for API Key management and billing summary.
- [x] 3.4 Display latest generation cost and refreshed cumulative cost after successful generation.
- [x] 3.5 Add all new Chinese and English copy to `frontend/src/i18n.ts`.

## 4. Verification

- [x] 4.1 Add or update backend tests for billing calculation, summary scoping, encrypted storage, and API Key deletion.
- [x] 4.2 Run `pytest` and fix regressions.
- [x] 4.3 Run `npx tsc --noEmit` in `frontend/` and fix type errors.
- [x] 4.4 Run `openspec validate user-apikey-billing --json` and fix validation errors.
