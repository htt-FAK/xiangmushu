# guided-first-run Specification

## Purpose
TBD - synced from change stabilize-generation-sessions-and-key-validation.

## Requirements

### Requirement: Home page shows guided setup readiness
The authenticated homepage SHALL show the user's current readiness for the main workflow, including API Key setup, knowledge preparation, template availability, and generation readiness.

#### Scenario: User opens home page without finishing setup
- **WHEN** an authenticated user opens the homepage before completing all prerequisites for generation
- **THEN** the page shows which setup steps are incomplete
- **AND** the page provides a clear next action for each incomplete step

#### Scenario: User opens home page after finishing setup
- **WHEN** an authenticated user opens the homepage after completing generation prerequisites
- **THEN** the page shows that generation is ready
- **AND** the page provides a direct path to `/generate`

### Requirement: Generate page blocks start with actionable prerequisite guidance
The Generate page SHALL prevent starting generation when required prerequisites are missing and SHALL explain what the user must do next.

#### Scenario: Missing validated API Key
- **WHEN** the user opens `/generate` without a saved validated API Key
- **THEN** the page blocks generation start
- **AND** the page instructs the user to go to Settings and save a validated key

#### Scenario: Missing usable knowledge content
- **WHEN** the user opens `/generate` without a knowledge base containing uploaded content
- **THEN** the page blocks generation start
- **AND** the page instructs the user to prepare knowledge content first

#### Scenario: Missing template
- **WHEN** the user opens `/generate` without any available template
- **THEN** the page blocks generation start
- **AND** the page instructs the user to upload or prepare a template first

### Requirement: Settings page communicates validation outcome clearly
The Settings page SHALL present API Key validation outcomes using actionable guidance rather than a generic save failure.

#### Scenario: API Key invalid
- **WHEN** API Key validation returns `invalid_api_key`
- **THEN** the page tells the user the key is invalid and asks them to check whether it was copied correctly

#### Scenario: API Key quota exhausted
- **WHEN** API Key validation returns `quota_exceeded`
- **THEN** the page tells the user that the key's model quota is exhausted and that generation cannot proceed with that key

#### Scenario: Validation blocked by network or provider state
- **WHEN** API Key validation returns `network_error` or `provider_error`
- **THEN** the page tells the user that validation could not complete because of external service conditions rather than confirming the key is wrong
