## ADDED Requirements

### Requirement: MiMo API configuration

The system SHALL support MiMo-V2.5-Pro model via OpenAI-compatible API.

#### Scenario: MiMo client initialization
- **WHEN** MiMo API key is configured
- **THEN** the system SHALL create an OpenAI client pointing to MiMo endpoint
- **AND** use base URL `https://api.xiaomimimo.com/v1`

#### Scenario: MiMo API key from environment
- **WHEN** environment variable `MIMO_API_KEY` is set
- **THEN** the system SHALL use it for MiMo authentication
- **AND** fallback to hardcoded key if environment variable is empty

### Requirement: Model routing for MiMo

The system SHALL route requests to MiMo when configured.

#### Scenario: Visual audit with MiMo
- **WHEN** visual audit is performed
- **AND** MiMo is configured as audit model
- **THEN** the system SHALL use MiMo for visual quality assessment

#### Scenario: Content generation with MiMo
- **WHEN** content generation requires large model
- **AND** MiMo is configured as generation model
- **THEN** the system SHALL use MiMo for content generation

### Requirement: MiMo fallback mechanism

The system SHALL automatically fallback to alternative models when MiMo fails.

#### Scenario: MiMo service error
- **WHEN** MiMo API returns error or times out
- **THEN** the system SHALL automatically fallback to:
  1. DeepSeek (if configured)
  2. DashScope/Qwen (if configured)
  3. Return error if no fallback available

#### Scenario: MiMo API key expired
- **WHEN** MiMo API key expires (2026-05-30)
- **THEN** the system SHALL detect authentication failure
- **AND** automatically disable MiMo routing
- **AND** use fallback models exclusively

### Requirement: MiMo web search capability

The system SHALL leverage MiMo's built-in web search capability when available.

#### Scenario: Web search enabled with MiMo
- **WHEN** web search is enabled
- **AND** MiMo is used for generation
- **THEN** the system SHALL use MiMo's native web search
- **AND** include search results in generation context
