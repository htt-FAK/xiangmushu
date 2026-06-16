## ADDED Requirements

### Requirement: Unique Email User Identity
The system SHALL store user accounts in SQLite with email as a unique identity. Email comparison MUST be case-insensitive after normalizing leading and trailing whitespace.

#### Scenario: First verified email creates a user
- **WHEN** a verification code is successfully verified for an email that has no user record
- **THEN** the system creates exactly one user record for the normalized email

#### Scenario: Existing email logs in without duplicate registration
- **WHEN** a verification code is successfully verified for an email that already has a user record
- **THEN** the system reuses the existing user record and MUST NOT create another record for that email

### Requirement: Verification Code Request
The system SHALL expose an API endpoint that accepts an email address and creates a six-digit numeric verification code for that email. The code MUST expire, and newer codes for the same email MUST supersede older unused codes.

#### Scenario: Request code for valid email
- **WHEN** a client submits a syntactically valid email address to the code request endpoint
- **THEN** the system stores a six-digit numeric code with an expiration timestamp and reports that the code was sent

#### Scenario: Request code for invalid email
- **WHEN** a client submits an invalid email address to the code request endpoint
- **THEN** the system rejects the request with a validation error and MUST NOT store a verification code

### Requirement: Verification Code Login
The system SHALL expose an API endpoint that accepts an email address and six-digit numeric code, validates the latest unexpired unused code, consumes it, and returns a JWT access token.

#### Scenario: Verify valid code
- **WHEN** a client submits the latest unexpired unused code for an email
- **THEN** the system marks the code as consumed and returns a JWT access token for that email's user

#### Scenario: Reject invalid code
- **WHEN** a client submits a missing, malformed, expired, consumed, or superseded code
- **THEN** the system rejects the login request and MUST NOT issue a JWT token

### Requirement: JWT Authenticated API Access
The system SHALL require a valid bearer JWT token for protected backend routes used by authenticated application pages. Invalid, missing, expired, or malformed tokens MUST be rejected with an unauthorized response.

#### Scenario: Access protected API with token
- **WHEN** a client calls a protected API route with a valid bearer JWT token
- **THEN** the system allows the request to continue

#### Scenario: Access protected API without token
- **WHEN** a client calls a protected API route without a valid bearer JWT token
- **THEN** the system rejects the request with HTTP 401

### Requirement: Frontend Login Flow
The frontend SHALL provide a dark-theme login page where users enter an email, request a verification code, submit the six-digit code, and persist the returned JWT token for subsequent API requests.

#### Scenario: Complete login flow
- **WHEN** a user requests a code for a valid email and then submits the matching code
- **THEN** the frontend stores the returned JWT token and navigates the user to the originally requested protected page or the home page

#### Scenario: Login error feedback
- **WHEN** the code request or code verification request fails
- **THEN** the frontend displays an error message without leaving the login page

### Requirement: Protected Frontend Routes
The frontend SHALL redirect unauthenticated users from `/`, `/template`, `/generate`, and `/knowledge` to the login page. Authenticated users MUST be allowed to access those routes.

#### Scenario: Unauthenticated protected route visit
- **WHEN** a user without a stored JWT token opens `/template`, `/generate`, `/knowledge`, or `/`
- **THEN** the frontend redirects the user to the login page and preserves the original destination

#### Scenario: Authenticated protected route visit
- **WHEN** a user with a stored JWT token opens `/template`, `/generate`, `/knowledge`, or `/`
- **THEN** the frontend renders the requested page
