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
The system SHALL persist user model choices by module or role using registry references when registry-backed persistence is healthy, and SHALL preserve stable role-to-model identifiers through compatibility storage when registry-backed persistence is degraded. The settings experience SHALL preserve the available choice set for each role and SHALL surface fallback warnings when a saved model becomes unavailable.

#### Scenario: User changes model selection with healthy registry persistence
- **WHEN** a user selects a model in Settings for a generation module while registry-backed persistence is available
- **THEN** the system SHALL validate the model is enabled for that module and persist the choice using registry-backed identifiers

#### Scenario: Selected model becomes disabled
- **WHEN** a previously selected model is disabled or removed
- **THEN** the system SHALL fall back to a configured default or compatible available model for that module and report the change or unavailable choice in the settings or API response

#### Scenario: Healthy MySQL exposes all enabled role options
- **WHEN** MySQL registry reads succeed for a role that has multiple enabled catalog rows
- **THEN** the settings/model-options response SHALL expose all enabled options from `model_catalog` for that role instead of collapsing to a single default entry

#### Scenario: Legacy fallback is used only for degraded registry reads
- **WHEN** MySQL registry reads fail or the registry is otherwise unavailable
- **THEN** the settings/model-options response SHALL fall back to the compatible legacy option set with warning metadata rather than treating fallback data as healthy registry truth

#### Scenario: User changes model selection during degraded registry mode
- **WHEN** the model-option source is degraded and the user selects another allowed fallback model
- **THEN** the system SHALL preserve that role-to-model choice through compatibility storage and SHALL report that the save occurred in degraded fallback mode

#### Scenario: Database connectivity error handling in model choices
- **WHEN** user model choices or registry details are fetched or saved, and the MySQL database connection is unavailable or degraded
- **THEN** the system SHALL log the error, and the API response SHALL return an explicit, localized validation warning (e.g., in `warnings`) indicating that database-backed model selections could not be validated or saved
- **AND** the system SHALL fall back to in-memory configuration values without silently masking database connection failures

### Requirement: Provider credentials support platform and user scopes
The system SHALL support provider credentials that are platform-wide, user-owned, or both, with explicit validation status.

#### Scenario: Platform credential is available
- **WHEN** a user has no personal key for a provider and a platform credential is enabled for that provider
- **THEN** the backend MAY use the platform credential according to configured policy

#### Scenario: User credential is available
- **WHEN** a user has a validated personal key for a provider
- **THEN** the backend SHALL use the user credential where policy prefers user-owned credentials

### Requirement: Model-option responses surface degraded registry state
The system SHALL expose whether model options are coming from the registry, a legacy fallback configuration, or a degraded/unavailable source. When registry-backed reads fail, the system SHALL return a fallback option set that preserves role-level choice breadth and SHALL include warning metadata rather than silently collapsing to a single implicit default.

#### Scenario: Registry-backed options are healthy
- **WHEN** the settings or template-analysis UI requests model options and the registry is readable
- **THEN** the backend SHALL return all enabled role-appropriate model options together with metadata indicating that the registry is the active source

#### Scenario: Registry-backed options are degraded
- **WHEN** the registry-backed model catalog cannot be read successfully
- **THEN** the backend SHALL return legacy configured role options together with warning or source metadata indicating degraded fallback mode

### Requirement: Quota and provider errors are normalized
The system SHALL normalize provider errors and quota states across DashScope, OpenAI-compatible gateways, DeepSeek, and future providers.

#### Scenario: Provider quota is exceeded
- **WHEN** a provider returns a quota or balance error
- **THEN** the system SHALL classify it into a normalized quota error that can drive retry, fallback, or user-facing model switch behavior

#### Scenario: Provider is unavailable
- **WHEN** a provider request fails due to network, authentication, model availability, or validation error
- **THEN** the system SHALL return a normalized provider error without leaking credentials or raw provider secrets

### Requirement: Chinese Localization and English Error Message Removal
All user-visible interface headers, statistics labels, load indicators, and error message fallbacks in History, Template Analysis, and Knowledge Base workflows SHALL be fully localized in Chinese.

#### Scenario: History page connection status and loading indicator
- **WHEN** the History page is rendered or loading
- **THEN** the load indicator SHALL show "正在加载历史记录..." rather than English, and the backend connection banner SHALL display "后端服务未连接" (or similar Chinese text) when offline
- **AND** any query or status filters that result in no records SHALL display "没有符合当前筛选条件的历史记录。"

#### Scenario: Template analysis statistics and status labels
- **WHEN** the Template Analysis panel is inspected
- **THEN** all statistical cards (Stat labels) SHALL show "输入 Tokens", "输出 Tokens", "费用 (元)" rather than English labels
- **AND** state variables such as "Phase", "Status", and "Model" roles SHALL display using localized Chinese terms

#### Scenario: Localized error message fallbacks
- **WHEN** api requests or document streaming actions on History, Template Analysis, or Settings pages fail
- **THEN** the default error fallbacks in `normalizeErrorMessage` or components SHALL use concise Chinese explanations (e.g., "加载模板失败", "分析模板失败") instead of hardcoded English error strings

