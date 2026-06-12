## ADDED Requirements

### Requirement: History dashboard lists generated articles from mock data

The frontend SHALL provide a history/articles page that lists previously generated articles using local mock data until backend history APIs are available.

#### Scenario: User opens the history page
- **WHEN** an authenticated user navigates to the history/articles route
- **THEN** the page SHALL show a list of mock generated article records with title, generation time, status, template or knowledge context, token usage, cost, and available download actions

#### Scenario: User selects a history record
- **WHEN** the user selects one article from the history list
- **THEN** the page SHALL display that article's detail panel with metadata, token totals, cost, model usage summary, and document/report actions when present

### Requirement: History dashboard shows aggregate generation totals

The history/articles page SHALL show aggregate totals derived from the displayed history records.

#### Scenario: Aggregate totals are visible
- **WHEN** the history page loads mock article records
- **THEN** the page SHALL display total generated article count, total input tokens, total output tokens, total combined tokens, and total cost

#### Scenario: Totals update from filtered records
- **WHEN** the user filters the visible article list
- **THEN** aggregate totals SHALL reflect the currently displayed record set or clearly indicate whether they represent all records

### Requirement: History dashboard provides search and status filtering

The history/articles page SHALL let users narrow historical records by text and status.

#### Scenario: Search by article text
- **WHEN** the user enters text into the history search field
- **THEN** the list SHALL show records whose title, template, knowledge base, or status text matches the query case-insensitively

#### Scenario: Filter by status
- **WHEN** the user chooses a status filter such as completed, needs review, or failed
- **THEN** the list SHALL show only records matching that status

### Requirement: History dashboard shows model usage chart

The history/articles page SHALL provide a pie or donut-style model usage chart for aggregate records and for the selected article.

#### Scenario: View aggregate model usage
- **WHEN** the user activates the aggregate model usage view
- **THEN** the page SHALL display a chart and legend showing each model's share of total tokens across the relevant record set

#### Scenario: View selected article model usage
- **WHEN** the user selects a history article
- **THEN** the detail panel SHALL display that article's model usage breakdown with token totals per model

#### Scenario: Chart remains understandable without color alone
- **WHEN** the model usage chart is displayed
- **THEN** the chart SHALL include a textual legend with model names, token counts, and percentages

### Requirement: History dashboard is frontend-only in this phase

The history/articles page SHALL not require backend history APIs for this change and SHALL clearly keep its data source isolated so future backend integration can replace mock data.

#### Scenario: Backend history API is unavailable
- **WHEN** the app runs without any history backend endpoint
- **THEN** the history page SHALL still render using local mock data

#### Scenario: Future data source replacement
- **WHEN** implementation later replaces mock data with backend data
- **THEN** the page data model SHALL allow records with article metadata, download URLs, input/output tokens, cost, status, and per-model usage
