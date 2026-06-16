# phase-one-module-layering Specification

## Purpose

Document explicit module layering for phase-one scope reduction: phase-one primary modules, phase-two hidden modules, and out-of-scope experimental modules.

## Requirements

### Requirement: Phase-one module layering is explicit

The repository SHALL document phase-one modules, phase-two hidden modules, and out-of-scope modules as three explicit layers for the scope-reduction change.

#### Scenario: Developer reviews the change scope
- **WHEN** a developer reads the phase-one scope reduction change
- **THEN** the module list is clearly divided into three layers
- **AND** each module is assigned to exactly one primary layer for the purpose of this change

### Requirement: Phase-one modules remain in the primary workflow

The phase-one layer SHALL include only the modules required for knowledge base ingestion, anchor template analysis, segmented generation, Word fill, and export.

#### Scenario: Main workflow execution
- **WHEN** the user performs the main workflow from knowledge base management to generation preview
- **THEN** the workflow depends on the phase-one layer modules only
- **AND** it does not require visual audit, auto-optimization, batch generation, or template vision to succeed in the default path

### Requirement: Hidden modules are not part of the default UI contract

The phase-two hidden layer SHALL contain modules that may remain in the repository but SHALL NOT be exposed as required controls or default promises in the phase-one UI.

#### Scenario: User opens the sidebar and template page
- **WHEN** the user views the normal phase-one UI
- **THEN** hidden-layer capabilities are not shown as required controls
- **AND** their existence does not alter the visible recommended workflow

### Requirement: Out-of-scope modules are excluded from phase-one commitments

Modules that depend on visual audit, automatic repair loops, or complex multimodal template inference SHALL be treated as out-of-scope for phase one.

#### Scenario: Developer inspects experimental modules
- **WHEN** the developer inspects `core.visual_auditor`, `core.document_optimizer`, or `core.template_vision`
- **THEN** these modules are documented as deferred or experimental
- **AND** the default phase-one workflow does not depend on them to produce editable Word output

### Requirement: Module layering must be reflected in implementation tasks

The implementation task list for the scope-reduction change SHALL include a module-layering step that records which files remain in phase one, which are hidden, and which are moved out of the primary workflow.

#### Scenario: Implementation planning
- **WHEN** the team reviews the change tasks
- **THEN** the tasks include a module-layering checkpoint before any UI or workflow refactor is finalized
- **AND** the checklist can be used to verify that the code changes match the documented scope boundaries
