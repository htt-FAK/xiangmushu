## MODIFIED Requirements

### Requirement: Main Generate page shows a bounded live output overview with access to the full trace

The Generate page's main content column SHALL remain bounded even when many sections have streamed output. Instead of rendering an unbounded trace, it SHALL render a bounded live output overview that summarizes progress and shows read-only preview blocks, together with an action that opens the full trace drawer.

#### Scenario: Page layout during a running session
- **WHEN** a user is on `/generate` and an active session is running with at least one streamed event
- **THEN** the main column SHALL display current progress information together with a bounded-height live overview of output blocks and a button that opens the full trace drawer

#### Scenario: Page layout after a completed session
- **WHEN** a user is on `/generate` after a session has completed with outputs
- **THEN** the main column SHALL display a bounded-height completed overview of those outputs together with an action that opens the full trace drawer

#### Scenario: No outputs yet
- **WHEN** a user is on `/generate` with no outputs
- **THEN** the main column SHALL render the existing empty-state placeholder

### Requirement: Full OutputBlock list and regenerate live exclusively in the trace drawer

The complete streamed trace, including the full per-section `OutputBlock` detail view and per-block regeneration actions, SHALL only be rendered inside the trace full-screen drawer. The main Generate page MAY show read-only preview blocks, but it SHALL NOT expose per-block regenerate actions or act as the full trace surface.

#### Scenario: Regenerate action on the main page
- **WHEN** a user inspects the main `/generate` page
- **THEN** no per-block regenerate button SHALL be visible in the bounded overview

#### Scenario: Regenerate action in the trace drawer
- **WHEN** a user opens the trace drawer for a session that has at least one output block
- **THEN** each `OutputBlock` inside the drawer SHALL expose a regenerate button, and regenerating a block SHALL update the same session-level state shared with the main-page overview

#### Scenario: Bounded overview and drawer stay consistent
- **WHEN** a session continues streaming or a section is regenerated from the drawer
- **THEN** the main-page bounded overview SHALL continue reflecting the current session state without expanding into an unbounded trace
