## ADDED Requirements

### Requirement: Supported model catalog can be backfilled into MySQL
The system SHALL provide an explicit backfill path that seeds supported role/model catalog rows into MySQL without requiring application startup side effects.

#### Scenario: Dry run previews model-catalog changes
- **WHEN** an operator runs the model-catalog seed script without `--apply`
- **THEN** the script SHALL report which provider/role/model rows would be inserted or updated without mutating MySQL state

#### Scenario: Apply mode upserts supported role/model rows
- **WHEN** an operator runs the model-catalog seed script with `--apply`
- **THEN** the script SHALL upsert catalog rows for the UI-backed roles `main_writer`, `fast_writer`, `web_search`, `vision_layout`, `template_planner`, `audit_text`, and `embedding`

### Requirement: Backfill only exposes routable model families
The system SHALL seed only model ids that have a supported provider path in the current runtime.

#### Scenario: Unsupported legacy model families are skipped
- **WHEN** the legacy configuration includes models such as `glm-*`, `kimi-*`, or `MiniMax-*`
- **THEN** the seed process SHALL omit those models from the MySQL catalog

#### Scenario: Supported families are retained
- **WHEN** the legacy configuration includes `qwen*`, `text-embedding*`, or `deepseek-*` models for a UI role
- **THEN** the seed process SHALL include those models in the desired catalog set for that role

### Requirement: Existing catalog state is preserved where operator intent matters
The system SHALL update deterministic metadata for existing rows while preserving operator-managed availability state.

#### Scenario: Existing row stays disabled
- **WHEN** a matching `(provider_id, model_id, role_key)` catalog row already exists with `enabled = 0`
- **THEN** the seed process SHALL update metadata fields without changing that row back to enabled

#### Scenario: New row follows provider availability
- **WHEN** the seed process inserts a new catalog row for a provider
- **THEN** the new row SHALL default its `enabled` state to the provider's current enabled status
