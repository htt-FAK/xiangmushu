# content-richness

内容充实度控制：提高默认字数、强化生成提示词，并通过审核规则检测与触发再生成。

## Requirements

### Requirement: Default word limit increased

The system SHALL use increased default word limits for content generation to ensure more substantial output.

#### Scenario: Fast mode word limit
- **WHEN** generation mode is set to "快速" (Fast)
- **THEN** the default word limit SHALL be 500 characters (increased from 300)

#### Scenario: Normal mode word limit
- **WHEN** generation mode is set to "普通" (Normal)
- **THEN** the default word limit SHALL be 800 characters (increased from 500)

#### Scenario: Enhanced mode word limit
- **WHEN** generation mode is set to "增强" (Enhanced)
- **THEN** the default word limit SHALL be 1200 characters (increased from 800)

### Requirement: Content richness prompt enhancement

The system SHALL include prompts that encourage the AI model to generate more substantial and detailed content.

#### Scenario: Richness prompt included
- **WHEN** generating paragraph content
- **THEN** the prompt SHALL include instructions like "内容要充实，避免简短" and "请详细展开，不要只写要点"

### Requirement: Content richness audit check

The system SHALL verify that generated content meets the minimum word count threshold.

#### Scenario: Content meets threshold
- **WHEN** generated content has at least 80% of the target word limit
- **THEN** the content SHALL be accepted

#### Scenario: Content below threshold triggers warning
- **WHEN** generated content has less than 80% of the target word limit
- **THEN** the system SHALL log a warning about insufficient content length
- **AND** the audit result SHALL indicate "minor_fix" or "major_issue" based on severity

#### Scenario: Content below threshold triggers regeneration
- **WHEN** generated content has less than 50% of the target word limit
- **AND** audit regeneration is enabled
- **THEN** the system SHALL attempt to regenerate the content with emphasis on length
