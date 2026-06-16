## ADDED Requirements

### Requirement: Template analysis main page remains bounded during long-running analysis
The template analysis workbench SHALL keep its main surface height bounded while an analysis is running or after it completes. The main page SHALL show analysis summary information such as template name, selected models, current phase or status, and a bounded preview of results without expanding into the full trace.

#### Scenario: Analysis is running
- **WHEN** a user starts template analysis from upload or reanalysis and the backend has emitted at least one progress event
- **THEN** the main template-analysis page SHALL display the active template, current status or phase, and a bounded summary area with a control to open detailed analysis output

#### Scenario: Analysis completes with many tasks
- **WHEN** a template analysis completes and produces a long task list
- **THEN** the main template-analysis page SHALL continue to render a bounded summary or preview container instead of expanding the page to the full task-list height

### Requirement: Full streamed analysis output is shown in a dedicated detail surface
The system SHALL provide a dedicated detail surface for template analysis that contains the full streamed analysis output, including phase logs, detailed status text, and the complete task list. The main page SHALL NOT display the entire streamed trace by default.

#### Scenario: User opens details during a running analysis
- **WHEN** a template-analysis session is still running and the user selects "view details"
- **THEN** the detail surface SHALL show the complete streamed analysis trace accumulated so far and continue updating as new events arrive

#### Scenario: User opens details after analysis completion
- **WHEN** a completed template-analysis session has stored tasks and trace output
- **THEN** the detail surface SHALL show the complete task list and final trace without requiring the main page to render that full content inline

### Requirement: Template analysis supports resumable session-style progress
Template analysis SHALL expose session-style state so the frontend can reconnect to the active run, restore progress after refresh, and render the same detail output stream consistently.

#### Scenario: User refreshes during analysis
- **WHEN** a template-analysis session is active and the user refreshes or revisits the page
- **THEN** the frontend SHALL be able to reload the active session state and continue rendering progress and detail events for that session

#### Scenario: Analysis ends with an error
- **WHEN** a template-analysis session fails before producing a final task set
- **THEN** the session state SHALL preserve the error outcome and the detail surface SHALL show the terminal error instead of pretending the analysis completed successfully
