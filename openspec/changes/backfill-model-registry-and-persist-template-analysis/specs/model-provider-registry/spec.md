## MODIFIED Requirements

### Requirement: Providers and models are represented in a registry
The system SHALL represent model providers and model catalog entries as structured records rather than scattering provider-specific constants across generation modules.

#### Scenario: Provider registry is loaded
- **WHEN** the backend starts or settings data is requested
- **THEN** the system SHALL load enabled providers and models including provider code, model id, display name, capabilities, pricing, supported roles, and enabled status

#### Scenario: DeepSeek provider is configured
- **WHEN** a DeepSeek-compatible provider is added to the registry
- **THEN** the system SHALL be able to represent its base URL, credential requirements, OpenAI-compatible behavior, supported models, pricing, and provider-specific request options

### Requirement: User model choices reference registry records
The system SHALL persist user model choices by module/role using provider and model registry references or stable provider/model identifiers.

#### Scenario: User changes model selection
- **WHEN** a user selects a model in Settings for a generation module
- **THEN** the system SHALL validate the model is enabled for that module and persist the choice in MySQL

#### Scenario: Selected model becomes disabled
- **WHEN** a previously selected model is disabled or removed
- **THEN** the system SHALL fall back to a configured default for that module and report the change or unavailable choice in the settings/API response

#### Scenario: Healthy MySQL exposes all enabled role options
- **WHEN** MySQL registry reads succeed for a role that has multiple enabled catalog rows
- **THEN** the settings/model-options response SHALL expose all enabled options from `model_catalog` for that role instead of collapsing to a single default entry

#### Scenario: Legacy fallback is used only for degraded registry reads
- **WHEN** MySQL registry reads fail or the registry is otherwise unavailable
- **THEN** the settings/model-options response SHALL fall back to the compatible legacy option set with warning metadata rather than treating fallback data as healthy registry truth
