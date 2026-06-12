## ADDED Requirements

### Requirement: Fill content is produced by the main writer
For paragraph and table-cell FillTasks, generated content inserted into the Word document SHALL come from the main writer flow using a compact evidence pack.

#### Scenario: Paragraph FillTask is generated
- **WHEN** the system generates content for a paragraph FillTask
- **THEN** the text passed to the filler SHALL be produced by the main writer using the task evidence pack

#### Scenario: Table-cell FillTask is generated
- **WHEN** the system generates content for a table-cell FillTask
- **THEN** the text passed to the filler SHALL be produced by the main writer using table context and task evidence

### Requirement: Branch-generated evidence is not inserted directly
The filler SHALL NOT receive direct final text from web search, visual layout, retrieval, or evidence compression branch agents.

#### Scenario: Web evidence exists for a fill task
- **WHEN** web search returns evidence for a FillTask
- **THEN** that evidence SHALL be provided to the main writer before filling and SHALL NOT be inserted directly into the template

#### Scenario: Visual notes exist for a fill task
- **WHEN** visual layout notes are associated with a FillTask
- **THEN** those notes SHALL guide the main writer and SHALL NOT be inserted directly unless the main writer includes them in final content

### Requirement: Filled output keeps existing slot behavior
The new main-writer routing SHALL preserve existing filler slot selection and replacement behavior for instruction lines, bracket fill slots, placeholder-only spans, abstract-like chapters, deterministic scanner reconciliation, and post-fill sweeps.

#### Scenario: Existing placeholder-only span
- **WHEN** a FillTask targets a placeholder-only span
- **THEN** the filler SHALL continue replacing only the placeholder span while using main-writer content

#### Scenario: Existing instruction-line target
- **WHEN** a FillTask targets a fill-instruction line
- **THEN** the filler SHALL continue replacing or clearing the instruction line according to existing slot rules while using main-writer content
