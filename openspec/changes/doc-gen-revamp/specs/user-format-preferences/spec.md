## ADDED Requirements

### Requirement: Format overrides accepted via API

The system SHALL accept an optional `format_overrides` parameter in the `/api/generate` request body, allowing users to customize typographic settings per generation session.

#### Scenario: User overrides body font and size
- **WHEN** a generate request includes:
  ```json
  {"format_overrides": {"body_font_east_asia": "楷体", "body_size_pt": 14}}
  ```
- **THEN** the generated document SHALL use 楷体 14pt for all body paragraphs
  AND heading sizes SHALL scale proportionally (heading = body + configured delta)

#### Scenario: Partial override leaves other styles from template
- **WHEN** `format_overrides` contains only `{"body_font_east_asia": "黑体"}`
- **THEN** body font SHALL be 黑体
  AND all other style properties (size, bold, line spacing, heading styles) SHALL come from `TemplateStyleProfile`

#### Scenario: No overrides provided
- **WHEN** the generate request does not include `format_overrides`
- **THEN** the system SHALL use `TemplateStyleProfile` values entirely (no behavior change from template-style-extraction capability)

#### Scenario: Invalid format override rejected
- **WHEN** `format_overrides` contains `{"body_size_pt": 0}` (invalid value)
- **THEN** the API SHALL return a 400 error with a descriptive message
  AND the generation SHALL NOT proceed with invalid overrides

### Requirement: Format overrides schema

The system SHALL define a strict schema for `format_overrides` with the following optional fields, all validated on input.

#### Scenario: Supported override fields
- **WHEN** the API receives format overrides
- **THEN** the system SHALL accept exactly these fields (all optional):
  - `body_font_ascii`: str (西文字体名, ASCII alphanumeric characters only)
  - `body_font_east_asia`: str (东亚字体名)
  - `body_size_pt`: float (8.0 – 24.0, step 0.5)
  - `body_bold`: bool
  - `heading_size_delta_pt`: float (-4.0 – +4.0) (adjusts all heading sizes relative to body)
  - `line_spacing`: float (1.0 – 2.5, step 0.25)
  - `first_line_indent_pt`: float (0.0 – 48.0)

#### Scenario: Unknown fields rejected
- **WHEN** `format_overrides` contains `{"unknown_field": "value"}`
- **THEN** the API SHALL return a 400 error indicating the unknown field

### Requirement: Frontend format preference UI

The system SHALL provide UI controls on the generation page allowing users to set format preferences before triggering document generation.

#### Scenario: Format settings panel accessible
- **WHEN** a user opens the format settings panel on the generate page
- **THEN** the panel SHALL display:
  - Font family dropdown (with common Chinese fonts: 宋体, 黑体, 楷体, 仿宋, 微软雅黑)
  - Font size selector (slider or dropdown, 10pt–18pt)
  - Line spacing selector (1.0, 1.25, 1.5, 2.0)
  - "Reset to template defaults" button

#### Scenario: Format settings sent with generate request
- **WHEN** a user sets body font to 楷体 and body size to 14pt, then clicks "生成"
- **THEN** the POST /api/generate request body SHALL include `format_overrides` reflecting those selections

#### Scenario: Format settings persisted per user session
- **WHEN** a user sets format preferences and refreshes the page
- **THEN** the format settings SHALL persist (stored in browser localStorage, keyed by user+template)
