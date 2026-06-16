# Modified specs for model-provider-registry

## MODIFIED Requirements

### Requirement: User model choices reference registry records

The system SHALL persist user model choices by module/role using provider and model registry references or stable provider/model identifiers.

#### Scenario: User changes model selection
- **WHEN** a user selects a model in Settings for a generation module
- **THEN** the system SHALL validate the model is enabled for that module and persist the choice in MySQL

#### Scenario: Selected model becomes disabled
- **WHEN** a previously selected model is disabled or removed
- **THEN** the system SHALL fall back to a configured default for that module and report the change or unavailable choice in the settings/API response

#### Scenario: Database connectivity error handling in model choices
- **WHEN** user model choices or registry details are fetched or saved, and the MySQL database connection is unavailable or degraded
- **THEN** the system SHALL log the error, and the API response SHALL return an explicit, localized validation warning (e.g., in `warnings`) indicating that database-backed model selections could not be validated or saved
- **AND** the system SHALL fall back to in-memory configuration values without silently masking database connection failures

## ADDED Requirements

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
