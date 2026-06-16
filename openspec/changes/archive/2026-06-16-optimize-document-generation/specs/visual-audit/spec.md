## ADDED Requirements

### Requirement: Document visual quality assessment

The system SHALL convert generated Word documents to images and use a Vision Language Model (VLM) to assess visual quality across five dimensions.

#### Scenario: Visual audit execution
- **WHEN** a Word document is generated
- **AND** visual audit is enabled
- **THEN** the system SHALL convert the document to PNG images
- **AND** send the images to VLM for quality assessment

#### Scenario: Multi-dimensional scoring
- **WHEN** visual audit is performed
- **THEN** the system SHALL evaluate and score:
  - Watermark integrity (0-20 points)
  - Format correctness (0-20 points)
  - Content richness (0-20 points)
  - Table normativity (0-20 points)
  - Layout aesthetics (0-20 points)
- **AND** calculate a total score (0-100 points)

### Requirement: Visual audit can be disabled

The system SHALL provide a configuration option to disable visual audit.

#### Scenario: Disable visual audit
- **WHEN** environment variable `VISUAL_AUDIT_ENABLED` is set to `false` or `0`
- **THEN** the system SHALL skip visual audit and return a perfect score

### Requirement: Graceful degradation on visual audit failure

The system SHALL NOT fail document generation if visual audit encounters an error.

#### Scenario: VLM service unavailable
- **WHEN** visual audit API call fails
- **THEN** the system SHALL log the error
- **AND** continue with document output
- **AND** return a warning status

### Requirement: Visual audit result parsing

The system SHALL parse VLM response into structured data.

#### Scenario: Valid JSON response
- **WHEN** VLM returns valid JSON with scores
- **THEN** the system SHALL extract all score dimensions
- **AND** extract issues and suggestions lists

#### Scenario: Invalid response
- **WHEN** VLM returns non-JSON or malformed response
- **THEN** the system SHALL log the parsing failure
- **AND** return a fallback result with parse_ok=false
