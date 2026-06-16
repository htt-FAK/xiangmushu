# generate-page-interactions Specification

## Purpose
TBD - created by syncing change optimize-generate-mobile-regen. Update Purpose after implementation is stable.

## Requirements
### Requirement: Users can regenerate a single generated section
The Generate page SHALL expose a regenerate action on every rendered output block after a section appears, and activating that action SHALL refresh only the targeted block's displayed content and status without clearing or overwriting other blocks already shown on the page.

#### Scenario: Regenerate one completed section
- **WHEN** the user clicks the regenerate action for one output block after a run has produced multiple sections
- **THEN** the page keeps all non-target blocks visible and unchanged while only the selected block enters a loading state and is replaced with the refreshed result

#### Scenario: Prevent conflicting section actions
- **WHEN** one output block is already regenerating
- **THEN** the page disables regenerate actions for other blocks until the in-flight block completes or fails

### Requirement: Section regeneration preserves page-level artifacts
The Generate page SHALL preserve current selections, existing output ordering, download actions, and accumulated acceptance information when a user regenerates a single section.

#### Scenario: Keep output order stable
- **WHEN** a section regeneration finishes successfully
- **THEN** the refreshed block remains in its original position and the surrounding block order is unchanged

#### Scenario: Keep existing artifacts visible during section refresh
- **WHEN** a user regenerates one section after a completed run
- **THEN** the page does not clear previously available downloads, report summaries, or other completed sections while the refresh is in progress

### Requirement: Mobile option rails support name filtering
The Generate page SHALL provide a mobile-visible search input for knowledge-base and template option rails, and filtering SHALL match against each item's visible title or metadata.

#### Scenario: Filter templates by typed text
- **WHEN** the user types into the template search field on mobile
- **THEN** the rail only shows template cards whose title or metadata contains the query, using case-insensitive matching

#### Scenario: Filter knowledge bases by typed text
- **WHEN** the user types into the knowledge-base search field on mobile
- **THEN** the rail only shows knowledge-base cards whose title or metadata contains the query, using case-insensitive matching

### Requirement: Mobile option rails use a card grid layout
The Generate page SHALL render knowledge-base and template options in a two-column touch-friendly card grid on mobile breakpoints while preserving the current single-column rail layout on desktop breakpoints.

#### Scenario: Mobile card grid
- **WHEN** the Generate page is viewed on a mobile-width viewport
- **THEN** template and knowledge-base options are shown as a two-column card grid with touch-friendly tap targets

#### Scenario: Desktop rail unchanged
- **WHEN** the Generate page is viewed on a desktop-width viewport
- **THEN** template and knowledge-base options continue to render in the existing single-column vertical rail style
