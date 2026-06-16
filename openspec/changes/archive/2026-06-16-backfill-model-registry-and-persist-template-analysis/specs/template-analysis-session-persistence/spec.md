## ADDED Requirements

### Requirement: Template-analysis session snapshots are durably persisted
The system SHALL persist template-analysis session snapshots to MySQL so recent analysis state can be reloaded after process-local state is unavailable.

#### Scenario: Session creation persists an initial snapshot
- **WHEN** a user starts a template-analysis session in MySQL mode
- **THEN** the backend SHALL create a MySQL `template_analysis_sessions` row containing the session key, owner, params, current status fields, and timestamps

#### Scenario: Session progress updates are persisted
- **WHEN** template-analysis events update status, billing, tasks, or terminal state
- **THEN** the backend SHALL update the persisted template-analysis snapshot for that session

### Requirement: Template-analysis recovery prefers memory and falls back to MySQL
The system SHALL recover template-analysis sessions from MySQL when in-memory session state is no longer available.

#### Scenario: Active or latest session is loaded after refresh
- **WHEN** the frontend requests the active or latest template-analysis session for a user and the in-memory manager no longer has that session
- **THEN** the backend SHALL hydrate the session snapshot from MySQL and return the same persisted template-analysis state

#### Scenario: Hydrated session snapshot supports detail rendering
- **WHEN** a template-analysis session is hydrated from MySQL
- **THEN** the returned snapshot SHALL include persisted logs, tasks, billing, and last-error data needed for the detail view without replaying historical SSE events
