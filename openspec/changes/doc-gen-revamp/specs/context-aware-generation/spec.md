## ADDED Requirements

### Requirement: Document type inference and injection into prompts

The system SHALL automatically infer the document type from the template filename and/or content, and inject a document type hint into the LLM system prompt to guide content generation.

#### Scenario: Document type inferred from template filename
- **WHEN** the template file is named `"创新计划书参考模板.docx"`
- **THEN** the system SHALL infer document type `"创新创业计划书"` 
  AND inject into the system prompt: `"⚠️ 文档类型：创新创业计划书"`

#### Scenario: Document type provided explicitly by user
- **WHEN** the generate request includes `{"document_type": "国家级项目申报书"}`
- **THEN** the system SHALL use the explicit value over any filename inference
  AND inject it verbatim into the system prompt

#### Scenario: Unknown document type falls back to generic
- **WHEN** the template filename does not match any known document type pattern
  AND no explicit `document_type` is provided
- **THEN** the system prompt SHALL contain: `"⚠️ 文档类型：项目申报文档（通用）"`

### Requirement: Chapter hierarchy path injected into prompts

The system SHALL pass the full chapter hierarchy path (parent chapters → current chapter) into the LLM user prompt, so the model understands context within the document structure.

#### Scenario: Nested chapter path provided to LLM
- **WHEN** the current FillTask targets `"项目实施方案"` which is a subsection of `"五、项目实施方案、技术路线及可行性分析"`
- **THEN** the user prompt SHALL include:
  `"📍 当前章节路径：五、项目实施方案、技术路线及可行性分析 > 项目实施方案"`

#### Scenario: Top-level chapter has no parent path
- **WHEN** the current FillTask targets `"一、项目基本信息"` (top-level)
- **THEN** the user prompt SHALL include only:
  `"📍 当前章节：一、项目基本信息"`

### Requirement: Table semantic role injected into table cell prompts

The system SHALL include the table's semantic role and the current cell's position context in the LLM user prompt for table cell generation tasks.

#### Scenario: Label-value pair cell gets label context
- **WHEN** generating content for a FILL cell in a LABEL_VALUE_PAIR table, where the label column text is `"项目痛点"`
- **THEN** the user prompt SHALL include:
  `"📋 表格类型：标签-内容对；本格的标签为「项目痛点」，请根据参考资料填写该项目的具体痛点。"`

#### Scenario: Multi-column data grid cell gets column+row context
- **WHEN** generating content for a FILL cell in a DATA_GRID table with column header `"专业年级"` and row label `"团队成员1"`
- **THEN** the user prompt SHALL include:
  `"📋 表格列：专业年级；当前行：团队成员1"`

#### Scenario: Skip instruction for READ_ONLY cells
- **WHEN** the table semantic analyzer marks a cell as `fill_intent=READ_ONLY`
- **THEN** NO FillTask SHALL be generated for that cell (content generation skipped entirely)

### Requirement: Prompt template versioning

The system SHALL maintain versioned prompt templates so that prompt improvements can be rolled back if quality degrades.

#### Scenario: Prompt version tracked in generation trace
- **WHEN** a generation uses prompt template version `v2.1`
- **THEN** `GenerationTrace` SHALL record `prompt_version="v2.1"`
  AND the route metadata SHALL include this version for audit

#### Scenario: Prompt version configurable via environment variable
- **WHEN** `PROMPT_TEMPLATE_VERSION` is set to `"v2.0"`
- **THEN** all generations in that session SHALL use the v2.0 prompt templates
  AND NOT the latest v2.1 templates
