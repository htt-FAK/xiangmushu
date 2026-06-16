## ADDED Requirements

### Requirement: Record generation token usage
The system SHALL record LLM token usage for each authenticated generation when the LLM response includes usage metadata.

#### Scenario: Usage metadata exists
- **WHEN** an authenticated generation completes and the LLM response includes input and output token usage
- **THEN** the system persists a billing record containing user id, model name, input tokens, output tokens, calculated cost, and creation time

#### Scenario: Usage metadata is missing
- **WHEN** an authenticated generation completes and the LLM response does not include usage metadata
- **THEN** the system completes the generation without failing and records zero cost or omits the billing record

### Requirement: Calculate RMB cost from configured model prices
The system SHALL calculate generation cost in RMB from a model price table configured in `config.py` using yuan per thousand input and output tokens.

#### Scenario: Model has configured price
- **WHEN** a billing record is created for a priced model
- **THEN** the cost equals `(input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price)`

#### Scenario: Model price is not configured
- **WHEN** a billing record is created for a model missing from the price table
- **THEN** the system records token usage with zero calculated cost and does not fail generation

### Requirement: Expose authenticated billing summary
The system SHALL provide an authenticated billing summary API returning the user's accumulated AI generation cost.

#### Scenario: User requests billing summary
- **WHEN** an authenticated user calls `GET /api/billing/summary`
- **THEN** the response includes cumulative RMB cost and aggregate token usage for only that user

#### Scenario: Unauthenticated user requests billing summary
- **WHEN** an unauthenticated request calls `GET /api/billing/summary`
- **THEN** the system rejects the request using the existing authentication behavior

### Requirement: Display generation cost in frontend
The frontend SHALL display the latest generation cost and updated cumulative cost after generation completes.

#### Scenario: Generation completes with cost data
- **WHEN** a generation request finishes successfully and cost data is available
- **THEN** the UI shows the current run cost and cumulative cost using localized text

#### Scenario: Billing summary cannot be loaded
- **WHEN** generation succeeds but cumulative billing summary loading fails
- **THEN** the UI still shows the generated content and does not block the user workflow
