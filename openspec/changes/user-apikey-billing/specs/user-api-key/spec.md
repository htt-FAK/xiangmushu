## ADDED Requirements

### Requirement: Settings entry for custom API Key
The frontend SHALL provide a `/settings` page reachable from the sidebar where authenticated users can manage a custom Aliyun Bailian API Key.

#### Scenario: User opens settings page
- **WHEN** a user navigates to `/settings`
- **THEN** the page shows a localized custom API Key management card

### Requirement: Acknowledgement before saving API Key
The frontend SHALL require users to acknowledge the self-owned API Key notice before saving a custom API Key.

#### Scenario: User starts custom API Key setup
- **WHEN** the user clicks the custom API Key action
- **THEN** the UI opens a full-screen acknowledgement dialog with the required title, liability points, Bailian key link, checkbox, consent input, confirm button, and cancel button

#### Scenario: User has not completed acknowledgement controls
- **WHEN** the acknowledgement checkbox is unchecked or the consent input is not exactly `我同意`
- **THEN** the confirm button remains disabled

#### Scenario: User completes acknowledgement controls
- **WHEN** the acknowledgement checkbox is checked and the consent input is exactly `我同意`
- **THEN** the confirm button is enabled

### Requirement: Save encrypted user API Key
The backend SHALL save the authenticated user's custom API Key encrypted at rest.

#### Scenario: User saves API Key
- **WHEN** an authenticated user submits a valid API Key to `POST /api/user/apikey`
- **THEN** the backend encrypts the key using environment-derived key material and stores only the encrypted value

#### Scenario: Unauthenticated user saves API Key
- **WHEN** an unauthenticated request submits to `POST /api/user/apikey`
- **THEN** the system rejects the request using the existing authentication behavior

### Requirement: Prefer user API Key for generation
The backend SHALL use a saved custom API Key before the platform default API Key for that user's future generation requests.

#### Scenario: User has saved API Key
- **WHEN** an authenticated user with a saved API Key starts generation
- **THEN** the LLM request uses the user's decrypted API Key

#### Scenario: User has no saved API Key
- **WHEN** an authenticated user without a saved API Key starts generation
- **THEN** the LLM request uses the existing platform default API Key behavior

### Requirement: Delete saved user API Key
The system SHALL allow authenticated users to delete their saved custom API Key.

#### Scenario: User deletes saved API Key
- **WHEN** an authenticated user calls the delete API for their custom API Key
- **THEN** the backend removes the saved key and later generation uses the platform default API Key

#### Scenario: User views saved key status
- **WHEN** an authenticated user opens settings
- **THEN** the frontend can determine whether a custom API Key exists without exposing the secret value
