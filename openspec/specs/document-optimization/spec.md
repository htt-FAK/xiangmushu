# document-optimization

基于视觉审核结果的自动二轮优化：问题诊断、段落级定向修复与多轮循环。

## Requirements

### Requirement: Two-round optimization based on audit results

The system SHALL automatically optimize document content based on visual audit results.

#### Scenario: Score below threshold triggers optimization
- **WHEN** visual audit total score is below 85
- **THEN** the system SHALL enter optimization mode
- **AND** diagnose specific issues from audit results

#### Scenario: Issue diagnosis
- **WHEN** optimization is triggered
- **THEN** the system SHALL categorize issues as:
  - Visual issues (watermark, format, layout)
  - Content issues (insufficient length, poor quality)
  - Structure issues (table disorder, alignment problems)

### Requirement: Paragraph-level targeted optimization

The system SHALL optimize only problematic paragraphs rather than regenerating the entire document.

#### Scenario: Content issue optimization
- **WHEN** content score is below threshold
- **THEN** the system SHALL identify low-scoring paragraphs
- **AND** regenerate those paragraphs with stronger prompts
- **AND** use a more capable model (LARGE_TIER or MiMo)

#### Scenario: Format issue optimization
- **WHEN** format score is below threshold
- **THEN** the system SHALL adjust typography parameters
- **AND** re-apply document formatting

### Requirement: Optimization loop with round limit

The system SHALL perform multiple optimization rounds with a maximum limit.

#### Scenario: Multi-round optimization
- **WHEN** first optimization round completes
- **THEN** the system SHALL re-run visual audit
- **AND** compare scores with previous round
- **AND** continue if score improved but still below threshold

#### Scenario: Maximum rounds reached
- **WHEN** optimization reaches 3 rounds
- **THEN** the system SHALL stop optimization
- **AND** output the best version achieved
- **AND** log all round results

### Requirement: Optimization progress tracking

The system SHALL track and report optimization progress.

#### Scenario: Progress reporting
- **WHEN** optimization is running
- **THEN** the system SHALL report:
  - Current round number
  - Current scores per dimension
  - Improvements from previous round
  - Remaining issues
