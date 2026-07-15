## ADDED Requirements

### Requirement: Classify table structural types

The system SHALL classify each table in a document into one of the following semantic types based on its structural properties:

- `LABEL_VALUE_PAIR`: 2-column tables where column 0 is a narrow label
- `DATA_GRID`: multi-column tables with a header row and empty data rows
- `INNOVATION_TRIPLE`: 3-column tables with headers containing "创新/实现/应用"
- `RUBRIC_SCORING`: tables with scoring/grading keywords in column 0
- `COVER_INFO`: tables containing cover page identity fields
- `UNKNOWN`: tables not matching any known pattern

#### Scenario: Label-value pair table detected
- **WHEN** a table has exactly 2 columns where column 0 width is less than 40% of total table width
  AND column 0 contains short text labels (e.g., "项目痛点", "项目实施方案")
- **THEN** the classifier SHALL return type `LABEL_VALUE_PAIR`
  AND column 0 cells SHALL be marked `fill_intent=LABEL`
  AND column 1 cells SHALL be marked `fill_intent=FILL`

#### Scenario: Cover info table excluded from filling
- **WHEN** a table contains multiple cover keywords ("学号", "姓名", "学院", "专业班级") in its cells
- **THEN** the classifier SHALL return type `COVER_INFO`
  AND ALL cells in the table SHALL be marked `fill_intent=READ_ONLY`

#### Scenario: Scoring rubric table excluded
- **WHEN** column 0 header cell contains "评分", "评价", or "打分"
  AND total row count ≤ 5
- **THEN** the classifier SHALL return type `RUBRIC_SCORING`
  AND ALL cells SHALL be marked `fill_intent=READ_ONLY`

#### Scenario: Innovation triple column table
- **WHEN** a table has exactly 3 columns where the header row (row 0) contains terms like "创新点" in col 0, "实现" in col 1, "应用" or "价值" in col 2
- **THEN** the classifier SHALL return type `INNOVATION_TRIPLE`
  AND row 0 cells SHALL be marked `fill_intent=LABEL` (headers preserved)
  AND data row cells in cols 1-2 SHALL be marked `fill_intent=FILL`

#### Scenario: Unknown table type falls back safely
- **WHEN** a table does not match any known structural pattern
- **THEN** the classifier SHALL return type `UNKNOWN`
  AND `fill_intent` assignment SHALL fall back to the existing `cell_needs_fill()` logic

### Requirement: Per-cell fill intent annotation

The system SHALL annotate each cell in a table with a `fill_intent` value indicating how it should be treated during content generation and fill-back.

#### Scenario: FillIntent enum values
- **WHEN** a cell annotation is produced
- **THEN** `fill_intent` SHALL be one of: `"FILL"`, `"LABEL"`, `"READ_ONLY"`, `"USER_INPUT"`

#### Scenario: Empty cell in data grid marked FILL
- **WHEN** a DATA_GRID table has an empty cell in a data row (not the header row)
- **THEN** that cell SHALL have `fill_intent=FILL`

#### Scenario: Non-empty label cell in label-value pair not filled
- **WHEN** a LABEL_VALUE_PAIR table has a cell in column 0 containing text "项目实施方案（含时间安排）"
- **THEN** that cell SHALL have `fill_intent=LABEL` AND shall NOT be modified during fill-back

### Requirement: Table semantic annotation exposed to generator

The system SHALL provide the table semantic annotations (type + fill_intent per cell) to the `ContentGenerator` so that LLM prompts can be contextually enriched with table semantic roles.

#### Scenario: Generator receives table context for FILL cells
- **WHEN** a FillTask targets a cell with `fill_intent=FILL` in a `LABEL_VALUE_PAIR` table
- **THEN** the generator's prompt SHALL include the label column's text as context (e.g., "本格的标签为：项目痛点")

#### Scenario: Generator skips LABEL cells entirely
- **WHEN** a table scan encounters a cell with `fill_intent=LABEL`
- **THEN** no FillTask SHALL be created for that cell
