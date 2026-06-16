## ADDED Requirements

### Requirement: API Key save requires successful validation
The system SHALL validate a user-provided API Key before persisting it and SHALL refuse to save the key unless validation succeeds.

#### Scenario: Validation succeeds before save
- **WHEN** an authenticated user submits a candidate API Key that passes validation
- **THEN** the backend stores the encrypted API Key for that user
- **AND** the response indicates that validation succeeded

#### Scenario: Validation fails before save
- **WHEN** an authenticated user submits a candidate API Key that does not pass validation
- **THEN** the backend does not persist the API Key
- **AND** the response indicates the validation failure reason

### Requirement: Validation uses only the submitted user key
API Key validation SHALL test the submitted key directly and SHALL NOT silently fall back to any platform-managed API Key during validation.

#### Scenario: Submitted key is invalid but platform key is configured
- **WHEN** the user submits an invalid API Key while the platform still has its own working key configured
- **THEN** validation reports the submitted key as unusable
- **AND** the system does not treat platform-key success as validation success

### Requirement: Validation can probe multiple candidate models
The system SHALL support validation by probing more than one low-cost candidate model when needed so that one unavailable model does not automatically mark the key as invalid.

#### Scenario: First candidate model fails but later candidate succeeds
- **WHEN** the first validation probe fails due to model-specific availability or permission issues and a later candidate probe succeeds
- **THEN** the overall validation result is successful
- **AND** the response identifies at least one model that validated successfully

#### Scenario: All candidate probes fail
- **WHEN** all candidate model probes fail
- **THEN** the overall validation result is unsuccessful
- **AND** the response includes a summary error classification derived from the probe results

### Requirement: Validation distinguishes key failures from network or provider failures
The system SHALL classify API Key validation failures into structured categories so users are not told their key is invalid when the real problem is quota exhaustion, network failure, provider outage, or model access restrictions.

#### Scenario: Invalid key
- **WHEN** the provider rejects the submitted key as unauthorized
- **THEN** the validation result code is `invalid_api_key`

#### Scenario: Quota exhausted
- **WHEN** the provider reports exhausted quota or equivalent allocation exhaustion for the submitted key
- **THEN** the validation result code is `quota_exceeded`

#### Scenario: Network failure
- **WHEN** the provider cannot be reached due to timeout, connection failure, or similar transport problem during validation
- **THEN** the validation result code is `network_error`

#### Scenario: Provider-side transient failure
- **WHEN** validation fails because of a provider-side service problem not specific to the submitted key
- **THEN** the validation result code is `provider_error`

### Requirement: Generation surfaces structured user-key diagnostics
When generation uses a saved user API Key, generation failures SHALL expose structured diagnostics that the frontend can map to user-facing guidance.

#### Scenario: Generation fails due to exhausted user quota
- **WHEN** generation uses a saved user API Key and the provider reports exhausted quota
- **THEN** the generation error payload identifies the condition as `quota_exceeded`
- **AND** the frontend can present that the model cannot run because the key's quota is exhausted
