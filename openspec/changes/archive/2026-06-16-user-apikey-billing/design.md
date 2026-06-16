## Context

The project already has a FastAPI backend, SQLite-backed authentication in `core/auth.py`, and a React/TypeScript frontend. AI generation currently uses platform-level model credentials. This change adds per-user billing records and optional user-owned Aliyun Bailian API Keys while keeping existing generation behavior as the fallback.

## Goals / Non-Goals

**Goals:**
- Persist token usage and RMB cost for authenticated generation calls when usage metadata is available.
- Provide an authenticated billing summary endpoint scoped to the current user.
- Store user API Keys encrypted at rest and never return plaintext keys.
- Prefer a saved user API Key for that user's generation requests.
- Add a localized settings page and post-generation cost display.

**Non-Goals:**
- Payment collection, invoices, quotas, or hard spending limits.
- Retroactive cost calculation for historical generations that did not record usage.
- Showing full API Key values after save.
- Supporting non-Aliyun provider key management in this change.

## Decisions

### Data model

Add SQLite tables through the existing backend initialization path:

- `billing_records`: `id`, `user_id`, `model`, `input_tokens`, `output_tokens`, `cost_cny`, `created_at`.
- `user_api_keys`: `user_id` primary key, `encrypted_api_key`, `created_at`, `updated_at`.

Using separate tables avoids changing existing auth records and keeps billing append-only.

### Pricing

Define `AI_MODEL_PRICING` in `config.py` as `{model: {"input": yuan_per_1k, "output": yuan_per_1k}}`. Cost calculation is deterministic and tolerant of missing model prices: usage is retained, but cost is `0`.

### Usage extraction

Generation code will normalize common usage shapes from OpenAI-compatible responses, such as `prompt_tokens`/`completion_tokens`/`total_tokens` and `input_tokens`/`output_tokens`. If no usage is available, generation completes without billing failure.

### API Key encryption

Use `cryptography.fernet.Fernet` when available. The encryption key is read from an environment variable. If the configured value is not already a Fernet key, derive one with SHA-256 and URL-safe base64 encoding. This keeps setup flexible while still avoiding plaintext storage. If `cryptography` is unavailable, use the documented fallback only if required by the current dependency set.

### Generation credential selection

For authenticated generation requests:

```text
request -> current user -> lookup saved key
  -> if found, decrypt and pass as API key for this generation
  -> otherwise use configured platform API key
  -> call LLM -> extract usage -> write billing record -> return cost metadata
```

The selected key is scoped to the current request and is not written to logs or frontend responses.

### Frontend

Add `/settings` route and sidebar entry. The settings page contains a custom API Key card, a full-screen acknowledgement dialog, save/delete actions, and status display. All visible strings go through `frontend/src/i18n.ts` in Chinese and English.

Generation completion displays latest cost from the generation response when available, then refreshes `GET /api/billing/summary` for cumulative totals.

## Risks / Trade-offs

- [Risk] Some LLM paths may not expose token usage consistently -> Normalize known shapes and treat missing usage as non-fatal.
- [Risk] Environment encryption key rotation can make stored keys undecryptable -> Document that the key must remain stable; deletion and re-save can recover.
- [Risk] Floating point currency accumulation can drift -> Store and return rounded decimal values appropriate for display; keep calculations small and deterministic.
- [Risk] User-owned keys may fail because of quota or permissions -> Surface generation errors through the existing error path without falling back silently to platform credentials.

## Migration Plan

1. Add pricing configuration and environment variable documentation.
2. Create tables idempotently during backend startup.
3. Add backend API routes and wire generation credential/cost recording.
4. Add frontend settings and billing display.
5. Add tests for encryption storage, billing calculation, summary scoping, and frontend type checks.

Rollback removes the new frontend routes/API usage. Existing billing and API key tables can remain unused without affecting legacy generation.

## Open Questions

None.
