## Why

MySQL is now the production source of truth for model registry data and session-backed workflow recovery, but two gaps remain visible to users. The model catalog in MySQL only contains a minimal seed set, so Settings often shows a single selectable model per role even when the product previously exposed a richer supported set. Template analysis also still keeps its resumable session state only in memory, which breaks refresh and reconnect expectations once the process-local state is lost.

This change closes those gaps now so the MySQL-backed runtime behaves like the real system of record instead of a partial compatibility layer. It restores trustworthy model selection options from supported provider-backed inventory and brings template-analysis recovery onto the same durable session pattern already used by generation history.

## What Changes

- Add an idempotent MySQL model-catalog backfill script that repopulates supported role/model rows from the current legacy configuration and role defaults without re-enabling intentionally disabled entries.
- Persist template-analysis sessions to MySQL through a dedicated repository and table so active or recent analysis snapshots survive refresh/navigation and can be reloaded after process-local state is gone.
- Keep existing `/api/user/model-options` and template-analysis session API shapes stable while making healthy-MySQL behavior rely on MySQL registry/session truth and reserving legacy fallback only for degraded reads.
- Add regression coverage for supported-model filtering, catalog seeding behavior, multi-option registry responses, and template-analysis snapshot recovery.

## Capabilities

### New Capabilities
- `template-analysis-session-persistence`: Durable MySQL-backed storage and recovery for template-analysis session snapshots.
- `model-catalog-backfill`: A repeatable operational path for seeding supported model catalog entries into MySQL from current role configuration.

### Modified Capabilities
- `model-provider-registry`: Healthy registry reads must expose the full enabled MySQL catalog for each role, with legacy fallback limited to degraded reads.

## Impact

- Affected backend modules: `core/provider_registry.py`, `core/template_analysis_sessions.py`, `server.py`, and new MySQL/session repository helpers.
- Affected operations/tooling: new `scripts/seed_model_catalog.py`, MySQL migration files, and setup documentation for post-migration seeding.
- Affected tests: provider-registry, history/model-option API assertions, and template-analysis session recovery coverage.
