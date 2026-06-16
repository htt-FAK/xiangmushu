## ADDED Requirements

### Requirement: Generate sessions remain recoverable across route navigation
The system SHALL create a recoverable generation session for each active authenticated generation so that navigating away from `/generate` does not discard live progress or completed output already produced by that run.

#### Scenario: User returns to Generate during an active run
- **WHEN** an authenticated user starts generation, navigates to another in-app page, and later returns to `/generate` while the run is still active
- **THEN** the page restores the current session snapshot including progress, current task, and outputs generated so far
- **AND** the page reconnects to the active session stream so new progress continues to appear live

#### Scenario: User returns to Generate after completion
- **WHEN** an authenticated user leaves `/generate` during a run and returns after that run has completed
- **THEN** the page restores the terminal session state including generated outputs, download information, report information, and billing summary if available

### Requirement: Generation sessions are owned and queryable per user
The backend SHALL expose authenticated session recovery APIs that return only the requesting user's generation session state.

#### Scenario: User fetches own active session
- **WHEN** an authenticated user requests the current or specific generation session recovery endpoint for a session they own
- **THEN** the backend returns the session snapshot and status for that user

#### Scenario: User requests another user's session
- **WHEN** an authenticated user requests a generation session owned by a different user
- **THEN** the backend denies access and does not reveal the session snapshot

### Requirement: The system limits each user to one active generation session
The system SHALL enforce at most one active generation session per authenticated user at a time.

#### Scenario: User starts generation while another session is active
- **WHEN** an authenticated user attempts to start a new generation while one of their sessions is still running
- **THEN** the system does not create a second active session
- **AND** the response clearly indicates that an active generation already exists

### Requirement: Generate page setup state persists across route changes
The frontend SHALL preserve workflow-critical Generate page setup state across in-app route navigation, including selected knowledge base, selected template, and entered generation instructions.

#### Scenario: User returns to Generate before starting a run
- **WHEN** a user selects a knowledge base and template, enters generation instructions, navigates away, and returns to `/generate` before starting generation
- **THEN** the page restores those selections and instructions instead of resetting to empty defaults

### Requirement: Knowledge Base page context persists across route changes
The frontend SHALL preserve recent Knowledge Base page context across in-app route navigation, including the selected library, recent upload results, and latest source statistics.

#### Scenario: User returns to Knowledge Base after upload
- **WHEN** a user uploads files into a knowledge base, navigates to another in-app page, and returns to `/knowledge`
- **THEN** the page restores the previously selected knowledge base and the most recent upload result summary
- **AND** the latest known source statistics remain visible until refreshed canonical data arrives

### Requirement: Shell exposes active generation awareness
The protected app shell SHALL expose whether the current authenticated user has an active generation session outside the Generate page.

#### Scenario: Active generation exists while user is on another page
- **WHEN** a user has an active generation session and navigates to Home, Knowledge Base, Template, or Settings
- **THEN** the shell shows that generation is currently in progress
- **AND** the shell offers a direct path back to `/generate`
