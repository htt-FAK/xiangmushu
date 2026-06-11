## ADDED Requirements

### Requirement: App shell shows active generation status outside Generate page
The protected application shell SHALL surface the current user's active generation status outside the Generate page.

#### Scenario: User navigates away during generation
- **WHEN** a user starts generation and then navigates to another protected page while the session is still active
- **THEN** the shell shows that generation is in progress
- **AND** the shell provides a navigation action back to `/generate`

### Requirement: Browser tab uses branded SVG icon
The frontend entrypoint SHALL configure a browser-tab icon using the provided SVG brand asset.

#### Scenario: User opens the app in a browser tab
- **WHEN** the frontend HTML entrypoint is loaded
- **THEN** the browser can resolve a favicon reference that points to the branded SVG asset

### Requirement: Branding changes do not replace functional workflow guidance
Shell-level branding enhancements SHALL coexist with workflow guidance and SHALL NOT remove access to actionable generation status or onboarding cues.

#### Scenario: User relies on shell status while multiple pages are available
- **WHEN** branding assets and shell status indicators are both present
- **THEN** the shell still presents readable workflow state and navigation back to generation
