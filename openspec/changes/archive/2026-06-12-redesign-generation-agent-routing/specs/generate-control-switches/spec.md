## ADDED Requirements

### Requirement: Web enrichment switch controls web evidence branch
The web enrichment switch SHALL control whether the web search branch agent is allowed to collect structured web evidence. It SHALL NOT cause a web-capable model to directly write final document content.

#### Scenario: Web enrichment enabled
- **WHEN** a user enables web enrichment before starting generation
- **THEN** the generation request SHALL allow the web search branch to collect evidence and the main writer SHALL still produce final content

#### Scenario: Web enrichment disabled
- **WHEN** a user disables web enrichment before starting generation
- **THEN** the generation request SHALL not invoke the web search branch for that run

### Requirement: Quality mode maps to evidence and model budgets
The quality-mode selector SHALL map to retrieval/evidence budgets and model routing preferences instead of only raw `top_k`, `max_distance`, and `word_limit` values.

#### Scenario: Speed mode selected
- **WHEN** a user selects speed mode
- **THEN** the generation run SHALL use smaller evidence budgets and prefer fast writer routing where evidence is strong enough

#### Scenario: Quality mode selected
- **WHEN** a user selects quality mode
- **THEN** the generation run SHALL allow larger evidence budgets and quality-oriented main writer routing

### Requirement: Audit switch controls audit branch
The content audit switch SHALL control whether the audit branch is allowed to perform model-based review after main writer output, while rule-based checks may still run.

#### Scenario: Content audit enabled
- **WHEN** a user enables content audit
- **THEN** the generation run SHALL allow the audit branch to review main writer output using the compact evidence pack

#### Scenario: Content audit disabled
- **WHEN** a user disables content audit
- **THEN** the generation run SHALL not call the model-based audit branch for that run

### Requirement: Trace UI uses role names
Generation trace and quota guidance shown to users SHALL use role names such as main writing, web search, fast fill, template vision, template planning, and audit instead of internal tier names.

#### Scenario: Quota exhausted in main writing role
- **WHEN** provider quota is exhausted while calling the main writer
- **THEN** the frontend SHALL identify the affected role as main writing and offer model choices for that role

#### Scenario: Trace row rendered
- **WHEN** a trace row is rendered for a generated section
- **THEN** the UI SHALL show the role/model used for final writing and indicate whether branch web evidence contributed
