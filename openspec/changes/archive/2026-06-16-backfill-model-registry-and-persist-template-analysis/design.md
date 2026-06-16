## Context

The current MySQL schema already stores provider rows, model catalog rows, generation sessions, generated article history, and artifact metadata. In practice, however, two important surfaces are still only partially aligned with that design:

- `model_catalog` is seeded with only a minimal default set, so healthy MySQL reads often return one enabled model per role even though the runtime still carries a broader legacy-supported inventory in `config.USER_MODEL_OPTIONS`.
- Template-analysis session recovery was added at the API/UI level, but `core/template_analysis_sessions.py` still stores state only in process memory. Refresh works only while the process-local manager still holds the session.

This change needs to add operational data backfill and new persistence without destabilizing the already-working generation-history path. The safest route is to reuse existing MySQL access patterns (`mysql_transaction`, JSON snapshot columns, session-key lookups) while keeping the public API shapes stable.

## Goals / Non-Goals

**Goals:**
- Add an idempotent model-catalog backfill script that restores supported multi-option role inventories in MySQL.
- Keep healthy `/api/user/model-options` reads fully driven by MySQL registry rows, with legacy options used only as degraded-read fallback.
- Persist template-analysis sessions to a dedicated MySQL table and hydrate snapshots when in-memory state is missing.
- Reuse existing generation-session conventions where they fit, without mixing template-analysis rows into generation-history queries.

**Non-Goals:**
- Re-enable legacy gateway-era models (`glm-*`, `kimi-*`, `MiniMax-*`) that do not have a working provider/adapter path in the current runtime.
- Add a new frontend surface for catalog administration or template-analysis history browsing.
- Make template-analysis jobs resume execution after a process restart; only snapshot recovery is in scope.
- Rewrite generation history or settings UI behavior beyond what is necessary to reflect the corrected MySQL truth.

## Decisions

### Decision 1: Backfill only currently routable model families

The seed path will build catalog candidates only for model ids that the current runtime can actually route:
- `dashscope`: `qwen*`, `text-embedding*`
- `deepseek`: `deepseek-*`

The source list for each UI role will be resolved in this order:
1. direct role config from `config.USER_MODEL_OPTIONS[role]`
2. legacy module mapping via `core.model_router.ROLE_TO_LEGACY_MODULE`
3. forced inclusion of `ROLE_DEFAULTS[role].default_model`

This preserves the user-visible model breadth that still maps to real providers, while excluding unsupported historical model names that would otherwise render as broken choices.

Alternative considered: backfill every model name present in legacy config. Rejected because the runtime no longer has enabled providers or request shapers for several of those families, and exposing them in Settings would create false-positive availability.

### Decision 2: Seeding is a dedicated script, not startup behavior

The change will add `scripts/seed_model_catalog.py` with `--dry-run`, `--apply`, and `--json`. The script will:
- inspect current provider rows,
- compute the desired role/model rows,
- upsert by `(provider_id, model_id, role_key)`,
- update metadata/pricing/config fields for existing rows,
- preserve the current row's `enabled` flag when it already exists,
- default new rows to the provider's enabled state.

This keeps deployment explicit and auditable. We will not modify the already-applied initial migration or add automatic startup seeding, which could unexpectedly overwrite operator-managed catalog state.

Alternative considered: extend `001_initial_schema.sql`. Rejected because that migration has already been applied in live environments and cannot safely serve as the new canonical seed path.

### Decision 3: Template-analysis sessions get a dedicated table and repository

Template analysis will use a new `template_analysis_sessions` table instead of reusing `generation_sessions`. The new table stores:
- ownership and lookup: `session_key`, `owner_user_id`
- current status fields: `status`, `current_phase`, `status_message`, `template_name`, `vision_model`, `planner_model`, `mode`, `vision_status`
- snapshot payloads: `params_json`, `result_json`, `billing_json`, `last_error_json`
- lifecycle timestamps: `created_at`, `updated_at`, `completed_at`

A new repository module will encapsulate create/update/load-latest behavior so the persistence logic stays separate from `core/history.py`.

Alternative considered: reuse `generation_sessions` with a broader JSON schema. Rejected because generation queries already rely on that table for “latest generation session” behavior, and mixing template-analysis rows into the same table would complicate every existing query and test.

### Decision 4: Keep the in-memory manager for streaming, add MySQL hydration for recovery

`core/template_analysis_sessions.py` will keep its current condition-variable/event-stream model for active SSE delivery. Persistence is additive:
- `create_session()` writes the initial snapshot to MySQL.
- `append_event()` updates the in-memory snapshot and then persists the new snapshot.
- `get_session_for_user()` first checks memory, then loads and hydrates a session object from MySQL if needed.
- `get_latest_session()` consults MySQL when there is no in-memory latest id.

Hydrated sessions will not reconstruct past event batches. The detail view will continue rendering from the persisted snapshot (`logs`, `tasks`, `billing`, `last_error`), and SSE remains responsible only for new events emitted while the process is alive.

Alternative considered: persist the full event log and replay it into a fresh manager. Rejected because the UI requirements only need current snapshot truth after refresh, and replayable event logs would add unnecessary storage and complexity.

## Risks / Trade-offs

- [Catalog backfill may overwrite operator-tuned labels or pricing] -> Only update deterministic metadata sourced from code, and preserve explicit `enabled` state on existing rows.
- [Provider filtering may omit a model an operator still wants visible] -> Keep the filter rules centralized and test-covered so future provider support can expand the seed set intentionally.
- [Hydrated template-analysis sessions have no historical SSE backlog] -> Persist the snapshot fields the UI actually needs so refresh recovery remains complete even without event replay.
- [A new session table adds one more migration and repository path] -> Mirror the existing generation-session persistence pattern so the code stays familiar and isolated.

## Migration Plan

1. Add a new MySQL migration creating `template_analysis_sessions`.
2. Add the repository module and wire `core/template_analysis_sessions.py` to persist and hydrate snapshots.
3. Add `scripts/seed_model_catalog.py` and document it in MySQL setup docs.
4. Add regression tests for seed resolution, template-analysis persistence, and healthy-registry multi-option behavior.
5. Run the seed script in dry-run mode first, then apply it in target environments after migration.

Rollback:
- Template-analysis persistence can be disabled operationally by not applying the new migration and reverting the code path, with in-memory behavior still available in development.
- Catalog changes can be rolled back by disabling or deleting seeded rows explicitly, since the script itself is idempotent and does not hard-delete existing data.

## Open Questions

- None for implementation. Future provider expansion can extend the seed filter once a real provider adapter and credential path exist for additional model families.
