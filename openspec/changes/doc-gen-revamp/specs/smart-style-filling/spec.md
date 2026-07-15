## ADDED Requirements

### Requirement: Apply template style when filling paragraphs

The system SHALL apply the `RunStyle` from the `TemplateStyleProfile` matching the paragraph's style or heading level when writing content, instead of using hardcoded font specifications.

#### Scenario: Body paragraph preserves template's 仿宋_GB2312 font
- **WHEN** a template body paragraph uses `仿宋_GB2312` at 12pt
  AND a new paragraph is written with generated content
- **THEN** the new paragraph SHALL use `font_ascii="FangSong"` AND `font_east_asia="仿宋_GB2312"` at 12pt
  AND NOT use the hardcoded "SimSun"/"宋体" default

#### Scenario: Heading paragraph preserves template bold size
- **WHEN** a template heading uses 华文中宋 at 15pt bold
  AND that heading paragraph is encountered during fill-back
- **THEN** the heading's `RunStyle` SHALL be applied from `TemplateStyleProfile.heading_styles[level]`
  AND NOT overwritten with hardcoded `_make_rPr(SZ_H1, bold=True)`

#### Scenario: Inline run style preserved from template
- **WHEN** a template paragraph's first run has `color_rgb="000000"` and no bold
- **THEN** when that paragraph is cleared and rewritten, the run SHALL retain `color_rgb="000000"` AND `bold=False`

### Requirement: Three-tier style priority

The system SHALL apply styles using the following priority order (highest wins):
1. User format overrides (from `format_overrides` API parameter)
2. Template original style (from `TemplateStyleProfile`)
3. System defaults (hardcoded fallback)

#### Scenario: User override beats template style
- **WHEN** `TemplateStyleProfile.body_font_east_asia` is "仿宋_GB2312"
  AND user provides `format_overrides={"body_font_east_asia": "楷体"}`
- **THEN** filled paragraphs SHALL use "楷体" (user override wins)

#### Scenario: Template style used when no user override provided
- **WHEN** `TemplateStyleProfile.body_font_east_asia` is "仿宋_GB2312"
  AND no `format_overrides` are provided
- **THEN** filled paragraphs SHALL use "仿宋_GB2312"

#### Scenario: System default used when template has no style info
- **WHEN** a paragraph in the template has no explicit font or size set (and its style also has no explicit settings)
- **THEN** the system SHALL fall back to hardcoded defaults: `宋体 12pt`

### Requirement: Style application function replaces global override

The system SHALL expose `apply_smart_style(para, style_profile, user_overrides)` that replaces the existing `apply_document_typography()` as the primary style application entry point.

#### Scenario: Smart style applied per-paragraph
- **WHEN** `apply_smart_style()` is called on a paragraph
- **THEN** it SHALL detect the paragraph's effective style (from style name, inline rPr, or surrounding context)
  AND apply the best-matching `RunStyle` from the merged profile

#### Scenario: Existing apply_document_typography kept as fallback
- **WHEN** `APPLY_TEMPLATE_STYLE` config is set to `false`
- **THEN** the system SHALL use the existing `apply_document_typography()` (hardcoded 宋体) behavior unchanged
  AND `apply_smart_style()` SHALL not be called

### Requirement: Table cell style preservation during fill-back

The system SHALL preserve each table cell's original typographic style when injecting new content, using the cell's first formatted run as the style reference.

#### Scenario: Cell with Times New Roman preserves font on fill
- **WHEN** a table cell originally contains `"项目痛点"` in Times New Roman 12pt bold
  AND the content cell (right column) uses 仿宋_GB2312 12pt
- **THEN** after fill-back, the content cell SHALL still use 仿宋_GB2312 12pt (preserved from original)

#### Scenario: Cell with no prior content uses template table default
- **WHEN** a table cell is completely empty (no runs, no text)
- **THEN** the system SHALL use `TemplateStyleProfile.table_cell_style` for the new content
