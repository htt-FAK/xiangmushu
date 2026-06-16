## Why

Users need visibility into AI generation costs and control over which Aliyun Bailian API Key is used for their requests. Adding token-based billing summaries and user-owned API Key support makes generation costs transparent and lets users shift model usage to their own account when desired.

## What Changes

- Record token usage from LLM responses for each generation.
- Convert input/output token usage into RMB using a configurable model price table in `config.py`.
- Add `GET /api/billing/summary` to return the authenticated user's accumulated cost.
- Return or expose the latest generation cost so the frontend can display both per-run and cumulative cost after generation.
- Add a `/settings` frontend page and sidebar entry.
- Add a custom API Key settings card with a required full-screen acknowledgement dialog before saving.
- Add `POST /api/user/apikey` to save the authenticated user's encrypted Aliyun Bailian API Key.
- Add API support for checking and deleting a saved user API Key.
- Prefer a saved user API Key over the platform default key during later generation.

## Capabilities

### New Capabilities
- `ai-billing`: Tracks LLM token usage, computes RMB cost by configured model pricing, exposes cumulative billing summary, and returns/display per-generation cost.
- `user-api-key`: Allows authenticated users to save, use, and delete an encrypted Aliyun Bailian API Key after acknowledging usage and liability terms.

### Modified Capabilities

None.

## Impact

- Backend: `config.py`, generation/LLM call paths, authenticated API routes, SQLite persistence, tests.
- Frontend: React routes/sidebar, settings page, i18n strings, generation result cost display, API client/types.
- Data: new SQLite storage for user API keys and billing records or equivalent schema additions.
- Security: API Keys must be encrypted at rest using Fernet when available, with key material loaded from environment configuration.
