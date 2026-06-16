## 1. Model catalog backfill

- [x] 1.1 Add a dedicated `scripts/seed_model_catalog.py` workflow with dry-run/apply/json modes and deterministic supported-model filtering.
- [x] 1.2 Add any supporting registry helpers needed to resolve per-role seed candidates and preserve existing enabled state on upsert.

## 2. Template-analysis MySQL persistence

- [x] 2.1 Add a MySQL migration for `template_analysis_sessions`.
- [x] 2.2 Add a dedicated template-analysis session repository for create/update/load-latest snapshot persistence.
- [x] 2.3 Refactor `core/template_analysis_sessions.py` to persist on create/update and hydrate from MySQL when in-memory state is missing.
- [x] 2.4 Keep existing template-analysis session APIs in `server.py` stable while switching recovery to memory-first with MySQL fallback.

## 3. Verification

- [x] 3.1 Add or update tests for supported-model filtering, seed idempotency, and healthy registry multi-option responses.
- [x] 3.2 Add or update tests for template-analysis session persistence and hydration behavior.
- [x] 3.3 Update MySQL setup docs with the explicit seed-script workflow and run targeted verification.
