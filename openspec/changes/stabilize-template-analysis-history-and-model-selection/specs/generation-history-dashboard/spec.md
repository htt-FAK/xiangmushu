## ADDED Requirements

### Requirement: History dashboard uses backend article data as the source of truth
The history dashboard SHALL use backend article/session history APIs as its primary runtime data source. In normal runtime behavior, the page SHALL NOT silently replace backend results with mock article data.

#### Scenario: Backend returns historical articles
- **WHEN** an authenticated user opens the history page and the backend returns one or more articles
- **THEN** the page SHALL render those backend articles and their backend-provided summary values as the displayed record set

#### Scenario: Backend returns no historical articles
- **WHEN** the backend returns an empty article list for the current user and filter set
- **THEN** the page SHALL show an explicit empty-state message instead of substituting mock records

### Requirement: History dashboard distinguishes empty, filtered, and unavailable states
The history dashboard SHALL explicitly distinguish between "no records," "no records match the current filter," and "backend history is unavailable."

#### Scenario: Filter produces no matches
- **WHEN** the user applies a query or status filter and the active filter set matches no backend records
- **THEN** the page SHALL show a filter-specific no-results state while preserving the active filter controls

#### Scenario: Backend history is unavailable
- **WHEN** the history API request fails or the backend reports an unavailable/degraded history source
- **THEN** the page SHALL show an explicit unavailable or error state with a retry path and SHALL NOT show mock records as if they were real history

### Requirement: Aggregate history totals follow the displayed backend filter set
The history dashboard SHALL display aggregate usage totals that correspond to the currently displayed backend record set or backend-filtered query result.

#### Scenario: User changes query or status filter
- **WHEN** the user updates the history search text or status filter
- **THEN** the page SHALL update the visible records and aggregate totals so they describe the same filtered backend result set

#### Scenario: User selects a history record
- **WHEN** the page shows backend-backed history results and the user selects one article
- **THEN** the detail panel SHALL display that backend record's metadata, usage breakdown, and download actions without mixing data from mock records
