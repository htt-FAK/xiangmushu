## MODIFIED Requirements

### Requirement: Table cell format preservation

The system SHALL preserve existing formatting (font, color, borders, alignment) when replacing text content in table cells, AND SHALL additionally preserve original column widths (dxa values) so table layout proportions remain unchanged after fill-back.

#### Scenario: Font style preserved
- **WHEN** a table cell with formatted text (font family, size, bold, italic) is filled with new content
- **THEN** the new content SHALL retain the original font style

#### Scenario: Text color preserved
- **WHEN** a table cell with colored text is filled with new content
- **THEN** the new content SHALL retain the original text color

#### Scenario: Cell borders preserved
- **WHEN** a table cell with custom borders is filled with new content
- **THEN** the cell borders SHALL remain unchanged

#### Scenario: Cell alignment preserved
- **WHEN** a table cell with specific alignment (horizontal/vertical) is filled with new content
- **THEN** the alignment settings SHALL remain unchanged

#### Scenario: Original column widths preserved (NEW)
- **WHEN** a table has non-uniform column widths (e.g., label column = 1602 dxa, content column = 7189 dxa)
  AND `PRESERVE_ORIGINAL_COLUMN_WIDTHS` is set to `true` (default)
- **THEN** after fill-back, the column widths SHALL remain exactly `[1602, 7189]` dxa
  AND NOT be normalized to equal widths

#### Scenario: Column widths fallback to equal distribution (NEW)
- **WHEN** `PRESERVE_ORIGINAL_COLUMN_WIDTHS` is set to `false`
- **THEN** the `_ensure_table_readability()` legacy equal-width logic SHALL still apply
  AND column widths SHALL be `usable_width / num_columns`

#### Scenario: gridSpan merged cells not broken (NEW)
- **WHEN** a table has a cell with `gridSpan=3` (horizontally merged across 3 columns)
- **THEN** fill-back SHALL NOT split the merged cell
  AND the cell's content SHALL be written into the first physical cell only

#### Scenario: vMerge start cell not overwritten with wrong content (NEW)
- **WHEN** a table cell has `vMerge` start (i.e., `<w:vMerge w:val="restart"/>`) AND is a LABEL cell (column 0 of a label-value table)
- **THEN** fill-back SHALL NOT write new AI-generated content into that cell
  AND the cell's original label text SHALL be preserved

### Requirement: Minimum column width safety net (NEW)

The system SHALL enforce a minimum column width of 500 dxa (~8mm) per column to prevent text overflow in very narrow columns, even when preserving original widths.

#### Scenario: Very narrow column expanded to minimum
- **WHEN** a table column has original width < 500 dxa
- **THEN** that column width SHALL be expanded to exactly 500 dxa
  AND adjacent columns SHALL shrink proportionally to compensate, keeping total table width constant

#### Scenario: Normal-width columns unaffected
- **WHEN** all columns in a table have width ≥ 500 dxa
- **THEN** column widths SHALL be preserved exactly as extracted from the template

### Requirement: Table format preservation can be disabled

The system SHALL provide a configuration option to disable format preservation when not needed.

#### Scenario: Disable format preservation
- **WHEN** environment variable `PRESERVE_TABLE_FORMAT` is set to `false` or `0`
- **THEN** the system SHALL use the original text replacement method without format preservation

### Requirement: Fallback to simple replacement on format preservation failure

The system SHALL gracefully fall back to simple text replacement if format preservation fails.

#### Scenario: Format preservation fails
- **WHEN** format preservation encounters an error during cell content replacement
- **THEN** the system SHALL fall back to simple text replacement
  AND the system SHALL log a warning about the fallback
