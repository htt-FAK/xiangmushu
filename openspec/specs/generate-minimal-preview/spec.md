# generate-minimal-preview Specification

## Purpose
TBD - created by archiving change kb-formats-and-generate-redesign. Update Purpose after archive.
## Requirements
### Requirement: Main Generate page shows a minimal streaming banner instead of the full output list

The Generate page's main content column SHALL NOT render the per-section `OutputBlock` list inline. Instead, while a run is in progress, it SHALL render a single-line streaming banner summarising progress; after completion, it SHALL render a single-line completion summary with an action to open the full trace drawer.

#### Scenario: Page layout during a running session
- **WHEN** a user is on `/generate` and an active session is running with at least one streamed event
- **THEN** the main column SHALL display the text “AI 正在生成第 X/Y 节 ▮” where X and Y are the current `progress.done` and `progress.total`, followed by a button that opens the trace full-screen drawer

#### Scenario: Page layout after a completed session
- **WHEN** a user is on `/generate` after a session has completed with outputs
- **THEN** the main column SHALL display the text “已完成 N 个章节 · 查看完整生成过程 →” where N is `outputs.length`, and clicking the action SHALL open the trace full-screen drawer

#### Scenario: No outputs yet
- **WHEN** a user is on `/generate` with no outputs
- **THEN** the main column SHALL render the existing empty-state placeholder

### Requirement: Full OutputBlock list and regenerate live exclusively in the trace drawer

The full per-section `OutputBlock` list, including per-block regeneration actions, SHALL only be rendered inside the trace full-screen drawer. The main Generate page SHALL not expose per-block regenerate actions.

#### Scenario: Regenerate action on the main page
- **WHEN** a user inspects the main `/generate` page
- **THEN** no per-block regenerate button SHALL be visible

#### Scenario: Regenerate action in the trace drawer
- **WHEN** a user opens the trace drawer for a session that has at least one output block
- **THEN** each `OutputBlock` inside the drawer SHALL expose a regenerate button, and regenerating a block SHALL update the same session-level state shared with the banner

#### Scenario: Banner reflects post-regenerate state
- **WHEN** a user regenerating a section from the drawer
- **THEN** the main page banner's completion text (“已完成 N 个章节”) SHALL continue to reflect the current length of `outputs`

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

