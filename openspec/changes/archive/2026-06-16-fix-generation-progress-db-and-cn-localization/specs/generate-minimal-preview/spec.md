# Modified specs for generate-minimal-preview

## MODIFIED Requirements

### Requirement: Main Generate page shows a minimal streaming banner instead of the full output list

The Generate page's main content column SHALL NOT render the per-section `OutputBlock` list inline. Instead, while a run is in progress, it SHALL render a single-line streaming banner summarising progress; after completion, it SHALL render a single-line completion summary with an action to open the full trace drawer.

#### Scenario: Page layout during a running session
- **WHEN** a user is on `/generate` and an active session is running with at least one streamed event
- **THEN** the main column SHALL display the text “AI 正在生成第 X/Y 节 ▮” where X and Y are the current `progress.done` and `progress.total`, followed by a button that opens the trace full-screen drawer
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
- **THEN** the main column SHALL display the text “已完成 N 个章节 · 查看完整生成过程 →” where N is `outputs.length`, and clicking the action SHALL open the trace full-screen drawer

#### Scenario: No outputs yet
- **WHEN** a user is on `/generate` with no outputs
- **THEN** the main column SHALL render the existing empty-state placeholder
