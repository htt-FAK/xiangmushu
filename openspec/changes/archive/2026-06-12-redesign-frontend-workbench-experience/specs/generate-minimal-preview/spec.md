## MODIFIED Requirements

### Requirement: Main Generate page shows live streaming output in a compact workbench

The Generate page's main content area SHALL render live per-section streaming output on the page while using compact setup and status controls to reduce page-level scrolling. While a run is in progress, the page SHALL keep the active or recently updated output blocks visible in the main workbench; after completion, it SHALL keep generated output accessible on the main page and provide an action to open the full trace drawer.

#### Scenario: Page layout during a running session
- **WHEN** a user is on `/generate` and an active session is running with at least one streamed output
- **THEN** the main page SHALL display live generated section content inline, including the currently active section, progress context, and an action that opens the trace full-screen drawer

#### Scenario: Page layout after a completed session
- **WHEN** a user is on `/generate` after a session has completed with outputs
- **THEN** the main page SHALL continue to show generated output or a compact output list/viewport, and clicking the trace action SHALL open the full generation process drawer

#### Scenario: No outputs yet
- **WHEN** a user is on `/generate` with no outputs
- **THEN** the main page SHALL render an empty-state placeholder that indicates live output will appear in the workbench after generation starts

### Requirement: Full OutputBlock details and regenerate remain available in the trace drawer

The trace full-screen drawer SHALL provide the detailed per-section `OutputBlock` view, including model routing, evidence references, audit issues, and per-block regeneration actions. The main Generate page MAY render compact or full streamed section previews, but detailed inspection and regenerate actions SHALL remain available in the trace drawer.

#### Scenario: Trace drawer shows full details
- **WHEN** a user opens the trace drawer for a session that has at least one output block
- **THEN** each `OutputBlock` inside the drawer SHALL expose full available metadata, generated text, evidence references, audit information, and the regenerate action

#### Scenario: Main page preserves streaming context
- **WHEN** a user inspects the main `/generate` page during a run
- **THEN** the user SHALL be able to see live streaming output context without opening the trace drawer

#### Scenario: Regenerate action in the trace drawer
- **WHEN** a user opens the trace drawer and activates regenerate for one output block
- **THEN** regenerating the block SHALL update the same session-level output state reflected by the main Generate page

## ADDED Requirements

### Requirement: Generate page uses a compact workbench command surface

The Generate page SHALL keep primary setup and run actions visible in a compact workbench surface, including selected knowledge base, selected template, quality mode, start/stop controls, and access to advanced settings.

#### Scenario: Primary controls visible without deep scrolling
- **WHEN** a desktop user opens `/generate`
- **THEN** the selected knowledge base, selected template, quality mode, and start/stop controls SHALL be visible near the top of the workbench without requiring the user to scroll below large page header content

#### Scenario: Advanced settings do not dominate the default view
- **WHEN** a user opens `/generate`
- **THEN** web enrichment, content audit, and visual audit controls SHALL remain accessible but SHALL NOT force all setup content and live output out of the first workbench view

### Requirement: Generate page keeps delivery actions easy to reach

After a generation run produces downloadable artifacts, the Generate page SHALL keep final document and quality report download actions visible from the workbench or a persistent delivery area without requiring users to search through the full trace drawer.

#### Scenario: Completed run shows downloads
- **WHEN** a generation session completes with a final document download path
- **THEN** the Generate page SHALL show a final document download action in the main workbench

#### Scenario: Completed run shows quality report when available
- **WHEN** a generation session completes with a quality report path
- **THEN** the Generate page SHALL show a quality report download action in the main workbench

### Requirement: Generate page provides purposeful motion for streaming states

The Generate page SHALL use motion only to clarify state changes such as starting a run, active streaming, section completion, progress changes, and artifact readiness.

#### Scenario: Active section is visually distinguished
- **WHEN** a section is currently receiving streamed content
- **THEN** the main page SHALL visually distinguish that section from completed or pending sections

#### Scenario: New section appears
- **WHEN** a new output section appears during streaming
- **THEN** the page SHALL introduce it with a restrained transition that does not shift unrelated controls unpredictably
