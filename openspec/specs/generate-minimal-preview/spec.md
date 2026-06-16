# generate-minimal-preview Specification

## Purpose
TBD - created by archiving change kb-formats-and-generate-redesign. Update Purpose after archive.
## Requirements
### Requirement: Main Generate page shows a bounded live output overview with access to the full trace

The Generate page's main content column SHALL remain bounded even when many sections have streamed output. Instead of rendering an unbounded trace, it SHALL render a bounded live output overview that summarizes progress and shows read-only preview blocks, together with an action that opens the full trace drawer.

#### Scenario: Page layout during a running session
- **WHEN** a user is on `/generate` and an active session is running with at least one streamed event
- **THEN** the main column SHALL display current progress information together with a bounded-height live overview of output blocks and a button that opens the full trace drawer
- **AND** the current active task and progress SHALL update incrementally as the generation thread actually executes each section, rather than showing the final task at the start

#### Scenario: Locked settings panel after run completes
- **WHEN** a generation session completes with a "done", "error" or "terminated" status
- **THEN** the setup/configuration panel on `/generate` (including Quality Mode and custom instructions inputs) SHALL remain locked/disabled to prevent post-generation modifications from altering the rendered run metrics dynamically
- **AND** the run-overview panel SHALL display the Quality Mode that was actually used for that generation session

#### Scenario: Local rule audit is distinct from model audit steps
- **WHEN** a generation session is executed with `enable_audit` set to `False`
- **THEN** the local regular expression and length verification rules (`rule_audit`) SHALL run, but the session status/step SHALL NOT transition to "audit" (Audit Step)
- **AND** the output block SHALL render any rule audit issues as warnings, but without showing "Auditor Agent" active indicators or running a model audit

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

### Requirement: Bottom billing panel is removed; compact token summary moved to run-overview

The Generate page SHALL NOT render the previous bottom “费用与 Token” panel. Instead, the run-overview section SHALL display a compact one-line summary of the current session's input and output token counts, and retain the existing live `runCost` stat.

#### Scenario: No bottom billing panel
- **WHEN** a user inspects the Generate page during or after a run
- **THEN** there SHALL be no section titled “费用与 Token” / “Cost and tokens” at the bottom of the main column

#### Scenario: Compact token summary visible from run-overview
- **WHEN** a run has produced at least one billing event
- **THEN** the run-overview SHALL display a one-line text of the form “本会话：输入 {input} tokens · 输出 {output} tokens” using the aggregated `runBilling.input_tokens` and `runBilling.output_tokens`

#### Scenario: Run-cost stat continues to update live
- **WHEN** billing events are streamed during a run
- **THEN** the existing `runCost` stat in the run-overview SHALL update live with `runBilling.cost_cny`

### Requirement: Cumulative billing summary is not shown in the Generate panel

The Generate page SHALL NOT display account-level cumulative billing (`billingSummary.cost_cny` / `billingSummary.generation_count`) inside the main page. These values remain available in the admin dashboard and settings area.

#### Scenario: No cumulative totals in main column
- **WHEN** a user is on `/generate` after a session has completed
- **THEN** the main column SHALL NOT render the account-level cumulative cost or total generation count

