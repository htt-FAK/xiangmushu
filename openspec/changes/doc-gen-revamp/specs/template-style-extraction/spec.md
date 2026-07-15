## ADDED Requirements

### Requirement: Extract template style profile from .docx

The system SHALL parse a .docx template file and produce a `TemplateStyleProfile` object containing the complete typographic and layout specifications used in the template.

#### Scenario: Extract body text style from sample template
- **WHEN** a .docx template is provided with body paragraphs using 仿宋_GB2312 font at 12pt
- **THEN** the `TemplateStyleProfile.body_font_east_asia` SHALL be `"仿宋_GB2312"` AND `body_size_pt` SHALL be `12.0`

#### Scenario: Extract heading styles from inline formatting
- **WHEN** template paragraphs use inline bold + 14pt for section headings (Normal style)
- **THEN** `TemplateStyleProfile.heading_styles[1]` SHALL contain `size_pt=14.0, bold=True`

#### Scenario: Extract column width ratios from tables
- **WHEN** a template table has columns with widths `[1602 dxa, 7189 dxa]` (total 8791 dxa)
- **THEN** `TemplateStyleProfile.column_widths[table_index]` SHALL contain `[1602, 7189]` preserving original dxa values

#### Scenario: Extract style from styles.xml inheritance chain
- **WHEN** a paragraph references style `Heading2` which is based on `Normal` with size 14pt
- **THEN** the extracted size for that heading level SHALL be the explicitly set value, not the inherited one

### Requirement: Dual-track extraction (API + XML fallback)

The system SHALL first attempt extraction via python-docx high-level API (`run.font.*`), then fall back to direct XML element inspection for attributes not exposed by the API.

#### Scenario: East Asian font extracted via XML
- **WHEN** python-docx `run.font.name` returns `"SimSun"` (ASCII font only)
- **THEN** the system SHALL inspect `w:rFonts/@w:eastAsia` in the run's XML to extract the East Asian font name

#### Scenario: Style inheritance resolved via XML
- **WHEN** a style has `basedOn="Normal"` and overrides only `bold` but not `size`
- **THEN** the resolved style SHALL include the inherited `size` from Normal plus the explicit `bold=True`

### Requirement: Cache template style profiles

The system SHALL cache extracted `TemplateStyleProfile` objects keyed by template file path and modification time, avoiding redundant re-extraction.

#### Scenario: Cache hit on unchanged template
- **WHEN** the same .docx template is used for generation twice without modification
- **THEN** the second call SHALL return the cached `TemplateStyleProfile` without re-parsing XML

#### Scenario: Cache invalidation on template update
- **WHEN** the template file's modification time changes (file replaced)
- **THEN** the cache SHALL invalidate and re-extract on next access

### Requirement: TemplateStyleProfile data structure

The system SHALL define `TemplateStyleProfile` as an immutable dataclass containing body font specs, heading style map, table cell default style, column widths per table, line spacing, first-line indent, and a cover-protected flag.

#### Scenario: Profile serializable for caching
- **WHEN** a `TemplateStyleProfile` is serialized to JSON for disk caching
- **THEN** deserializing it SHALL produce an identical object (including nested `RunStyle` instances)

#### Scenario: Profile mergeable with user preferences
- **WHEN** a `TemplateStyleProfile` is merged with user `format_overrides`
- **THEN** the result SHALL be a new profile where only overridden fields are replaced, original fields preserved
