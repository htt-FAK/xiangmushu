# watermark-preservation

Word 文档处理过程中保留页眉/页脚水印（文字与图片），支持可配置开关与失败降级。

## Requirements

### Requirement: Watermark preservation during document processing

The system SHALL preserve all watermark elements (text and image watermarks) in the document header and footer sections during the Word template filling process.

#### Scenario: Text watermark preserved after filling
- **WHEN** a document with text watermark in header is processed by WordFiller
- **THEN** the output document SHALL contain the same text watermark with identical formatting

#### Scenario: Image watermark preserved after filling
- **WHEN** a document with image watermark in header is processed by WordFiller
- **THEN** the output document SHALL contain the same image watermark with identical position and size

#### Scenario: Footer watermark preserved
- **WHEN** a document with watermark in footer section is processed by WordFiller
- **THEN** the output document SHALL contain the same footer watermark

#### Scenario: Multiple watermarks preserved
- **WHEN** a document has watermarks in both header and footer
- **THEN** the output document SHALL preserve all watermarks in their original locations

### Requirement: Watermark preservation can be disabled

The system SHALL provide a configuration option to disable watermark preservation when not needed.

#### Scenario: Disable watermark preservation
- **WHEN** environment variable `PRESERVE_WATERMARK` is set to `false` or `0`
- **THEN** the system SHALL skip watermark preservation logic

### Requirement: Graceful degradation on watermark preservation failure

The system SHALL NOT fail the document generation process if watermark preservation encounters an error.

#### Scenario: Watermark extraction fails
- **WHEN** watermark extraction encounters an unexpected XML structure
- **THEN** the system SHALL log the error and continue with document processing
- **AND** the output document SHALL still be generated without watermarks
