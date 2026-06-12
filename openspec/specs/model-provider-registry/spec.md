# model-provider-registry Specification

## Purpose
TBD - created by archiving change design-mysql-storage-provider-foundation. Update Purpose after archive.
## Requirements
### Requirement: Providers and models are represented in a registry
The system SHALL represent model providers and model catalog entries as structured records rather than scattering provider-specific constants across generation modules.

#### Scenario: Provider registry is loaded
- **WHEN** the backend starts or settings data is requested
- **THEN** the system SHALL load enabled providers and models including provider code, model id, display name, capabilities, pricing, supported roles, and enabled status

#### Scenario: DeepSeek provider is configured
- **WHEN** a DeepSeek-compatible provider is added to the registry
- **THEN** the system SHALL be able to represent its base URL, credential requirements, OpenAI-compatible behavior, supported models, pricing, and provider-specific request options

### Requirement: Provider adapters isolate request differences
The system SHALL route model calls through provider adapters that encapsulate provider-specific request options such as DashScope compatible-mode parameters, DeepSeek thinking controls, search support, streaming support, and vision support.

#### Scenario: Generation requests a model by role
- **WHEN** the generation workflow needs a model for a role such as main writer, fast writer, vision layout, template planner, web search, or audit text
- **THEN** the system SHALL resolve a model/provider choice and invoke it through the appropriate provider adapter

#### Scenario: Provider-specific options are needed
- **WHEN** a selected provider requires special request body fields
- **THEN** the provider adapter SHALL add those fields without requiring each caller module to duplicate provider-specific conditionals

### Requirement: User model choices reference registry records
The system SHALL persist user model choices by module/role using provider and model registry references or stable provider/model identifiers.

#### Scenario: User changes model selection
- **WHEN** a user selects a model in Settings for a generation module
- **THEN** the system SHALL validate the model is enabled for that module and persist the choice in MySQL

#### Scenario: Selected model becomes disabled
- **WHEN** a previously selected model is disabled or removed
- **THEN** the system SHALL fall back to a configured default for that module and report the change or unavailable choice in the settings/API response

### Requirement: Provider credentials support platform and user scopes
The system SHALL support provider credentials that are platform-wide, user-owned, or both, with explicit validation status.

#### Scenario: Platform credential is available
- **WHEN** a user has no personal key for a provider and a platform credential is enabled for that provider
- **THEN** the backend MAY use the platform credential according to configured policy

#### Scenario: User credential is available
- **WHEN** a user has a validated personal key for a provider
- **THEN** the backend SHALL use the user credential where policy prefers user-owned credentials

### Requirement: Quota and provider errors are normalized
The system SHALL normalize provider errors and quota states across DashScope, OpenAI-compatible gateways, DeepSeek, and future providers.

#### Scenario: Provider quota is exceeded
- **WHEN** a provider returns a quota or balance error
- **THEN** the system SHALL classify it into a normalized quota error that can drive retry, fallback, or user-facing model switch behavior

#### Scenario: Provider is unavailable
- **WHEN** a provider request fails due to network, authentication, model availability, or validation error
- **THEN** the system SHALL return a normalized provider error without leaking credentials or raw provider secrets

