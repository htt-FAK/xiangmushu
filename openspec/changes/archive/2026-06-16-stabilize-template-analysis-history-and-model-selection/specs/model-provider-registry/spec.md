## ADDED Requirements

### Requirement: Model-option responses surface degraded registry state
The system SHALL expose whether model options are coming from the registry, a legacy fallback configuration, or a degraded/unavailable source. When registry-backed reads fail, the system SHALL return a fallback option set that preserves role-level choice breadth and SHALL include warning metadata rather than silently collapsing to a single implicit default.

#### Scenario: Registry-backed options are healthy
- **WHEN** the settings or template-analysis UI requests model options and the registry is readable
- **THEN** the backend SHALL return all enabled role-appropriate model options together with metadata indicating that the registry is the active source

#### Scenario: Registry-backed options are degraded
- **WHEN** the registry-backed model catalog cannot be read successfully
- **THEN** the backend SHALL return legacy configured role options together with warning or source metadata indicating degraded fallback mode

## MODIFIED Requirements

### Requirement: User model choices reference registry records
The system SHALL persist user model choices by module or role using registry references when registry-backed persistence is healthy, and SHALL preserve stable role-to-model identifiers through compatibility storage when registry-backed persistence is degraded. The settings experience SHALL preserve the available choice set for each role and SHALL surface fallback warnings when a saved model becomes unavailable.

#### Scenario: User changes model selection with healthy registry persistence
- **WHEN** a user selects a model in Settings for a generation module while registry-backed persistence is available
- **THEN** the system SHALL validate the model is enabled for that module and persist the choice using registry-backed identifiers

#### Scenario: Selected model becomes disabled
- **WHEN** a previously selected model is disabled or removed
- **THEN** the system SHALL fall back to a configured default or compatible available model for that module and report the change or unavailable choice in the settings or API response

#### Scenario: User changes model selection during degraded registry mode
- **WHEN** the model-option source is degraded and the user selects another allowed fallback model
- **THEN** the system SHALL preserve that role-to-model choice through compatibility storage and SHALL report that the save occurred in degraded fallback mode
