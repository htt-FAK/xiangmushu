## ADDED Requirements

### Requirement: Phase-one product scope is limited to initial draft generation

The application SHALL present phase one as a knowledge-base-driven Word initial draft generator, not as an automatic visual review or auto-repair system.

#### Scenario: User reads product entry points
- **WHEN** the user opens the app or reads the primary product description
- **THEN** the system describes the core workflow as knowledge base ingestion, anchor template analysis, segmented generation, and Word export
- **AND** the system does not present automatic finalization as a phase-one promise

### Requirement: Primary flow keeps only core generation stages

The primary application flow SHALL be limited to knowledge base management, anchor template configuration, segmented generation, and Word export.

#### Scenario: User follows the recommended workflow
- **WHEN** the user works through the main tabs
- **THEN** the visible recommended path is `知识库管理 -> 模板配置 -> 生成预览`
- **AND** generation completes without requiring template vision analysis, content audit, visual audit, or optimization loops

### Requirement: Anchor templates are the default phase-one template path

The system SHALL treat anchor-based `.docx` templates as the default supported template format for phase one.

#### Scenario: Template contains anchors
- **WHEN** the user uploads a `.docx` template containing `{{ANCHOR_NAME}}` placeholders
- **THEN** template analysis produces FillTask entries from anchor scanning
- **AND** the user can continue directly to generation

#### Scenario: Template has no anchors
- **WHEN** the uploaded template does not contain recognized anchors
- **THEN** the system may classify it as outside the default phase-one path
- **AND** the UI or workflow guidance SHALL NOT depend on template vision as a required default stage

### Requirement: Advanced experimental features are not part of phase-one primary UI

The application SHALL NOT expose experimental features as required or default parts of the phase-one primary UI.

#### Scenario: User opens generation settings
- **WHEN** the user views normal phase-one controls
- **THEN** the visible controls are limited to generation intensity, stream display, web supplementation, default word limit, `top_k`, retrieval distance, and template re-analysis
- **AND** the primary UI does not require audit-agent toggles, visual-audit toggles, MiMo toggles, or template-vision toggles

### Requirement: Phase-one generation success is measured by editable Word output

The system SHALL define successful phase-one generation as producing an editable Word output whose anchor tasks have been filled and that is suitable for manual review.

#### Scenario: User completes generation
- **WHEN** the generation workflow finishes successfully
- **THEN** the system exports a `.docx` file that opens normally
- **AND** the major anchor slots are filled with generated content
- **AND** the user is expected to perform manual review before final delivery

### Requirement: Experimental modules are separated from phase-one commitment

The repository MAY retain audit, vision, optimization, batching, and alternate-model modules, but phase-one implementation SHALL treat them as hidden, optional, or out-of-scope rather than core commitments.

#### Scenario: Repository still contains experimental modules
- **WHEN** a developer inspects the codebase after phase-one scope reduction
- **THEN** core generation does not depend on `core.visual_auditor`, `core.document_optimizer`, or `core.template_vision` to succeed in the default path
- **AND** these modules are documented as hidden, experimental, or deferred capabilities
