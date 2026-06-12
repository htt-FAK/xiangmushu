# mysql-persistence-foundation Specification

## Purpose
TBD - created by archiving change design-mysql-storage-provider-foundation. Update Purpose after archive.
## Requirements
### Requirement: MySQL stores core account and business records
The system SHALL support MySQL as the durable store for account, preference, credential metadata, billing, generation session, generated article, audit, provider, model, knowledge metadata, and artifact metadata records.

#### Scenario: MySQL mode starts with schema present
- **WHEN** the backend starts with MySQL persistence enabled
- **THEN** the system SHALL verify or apply the required schema for users, roles, preferences, credentials, billing records, generation sessions, generated articles, artifact metadata, provider registry, and knowledge metadata before serving authenticated requests

#### Scenario: Structured records are not written only to SQLite
- **WHEN** MySQL persistence is enabled and a user signs in, updates preferences, generates a document, or accrues billing
- **THEN** the system SHALL persist the resulting structured records to MySQL rather than relying only on local SQLite tables

### Requirement: Account tables support users, roles, and preferences
The system SHALL model users, role assignments, preferred language, and model choices as queryable MySQL records.

#### Scenario: User signs in
- **WHEN** a user authenticates successfully
- **THEN** the system SHALL load the user, role assignments, preferred language, and model choices from MySQL-backed records

#### Scenario: User updates generation preferences
- **WHEN** a user changes language or model choices
- **THEN** the system SHALL persist the preference change in MySQL and return the updated preference state to the frontend

### Requirement: API keys and provider credentials are encrypted
The system SHALL store user and platform provider credentials encrypted at rest and SHALL NOT expose plaintext credentials through admin, history, settings, or generation responses.

#### Scenario: User saves an API key
- **WHEN** a user saves a provider API key
- **THEN** the system SHALL encrypt the key before writing it to MySQL and SHALL return only validation status and metadata to the frontend

#### Scenario: Provider key is used for generation
- **WHEN** a generation workflow needs a provider credential
- **THEN** the backend SHALL decrypt the credential only inside the provider/client layer and SHALL NOT serialize it into session, billing, or artifact records

### Requirement: Generation sessions and generated articles are durable
The system SHALL persist generation session lifecycle state and generated article summary records in MySQL so history and recovery survive process restarts.

#### Scenario: Running session is updated
- **WHEN** a generation session emits progress, output, billing, artifact, done, or error events
- **THEN** the system SHALL update the corresponding MySQL session record with status, progress, timestamps, current task, error summary, billing totals, and artifact links

#### Scenario: History page requests generated articles
- **WHEN** a user opens the generated article history page after previous successful runs
- **THEN** the backend SHALL be able to return MySQL-backed generated article records for that user without relying on frontend mock data

### Requirement: Billing records are linked to user, session, provider, and model
The system SHALL record token usage and cost in MySQL with enough references to aggregate by user, generation session, generated article, provider, and model.

#### Scenario: Model call records token usage
- **WHEN** a model call returns input/output token usage
- **THEN** the system SHALL write a billing record that includes user id, model id or model name, provider id when known, input tokens, output tokens, cost, timestamp, and related generation session when available

#### Scenario: Admin stats are requested
- **WHEN** an admin requests usage statistics
- **THEN** the system SHALL aggregate counts, costs, tokens, and model usage from MySQL billing records

### Requirement: SQLite migration is explicit and repeatable
The system SHALL provide an explicit migration path from current SQLite-backed data to MySQL-backed records.

#### Scenario: Existing SQLite data is migrated
- **WHEN** a migration script runs against an existing SQLite auth database
- **THEN** the script SHALL copy users, verification metadata where needed, preferences, API key records, billing records, and audit events into MySQL with deterministic mapping and without duplicating rows on repeated dry runs

#### Scenario: Migration cannot complete
- **WHEN** required SQLite data cannot be mapped into the MySQL schema
- **THEN** the migration SHALL report the failed table/row category and SHALL NOT silently drop account, credential, or billing data

