## ADDED Requirements

### Requirement: Role-based model routing
The system SHALL resolve every LLM or multimodal call through a role-based model router before calling the provider, except for embedding calls that use the embedding role configuration directly.

#### Scenario: Main writer role resolves default model
- **WHEN** a generation task needs final paragraph or table-cell content and the user has not chosen a main writing model
- **THEN** the router SHALL resolve the `main_writer` role to `deepseek-v4-pro` as the primary model with configured fallbacks

#### Scenario: User-selected role model is preserved
- **WHEN** a user has selected a model for a supported role
- **THEN** the router SHALL use the user's selected model as the primary model for that role

#### Scenario: Router returns traceable decision metadata
- **WHEN** the router resolves a model call
- **THEN** the resolved profile SHALL include the role, primary model, fallback models, temperature, provider flags, and routing reason

### Requirement: Main writer owns final content
The system SHALL use the main writer flow as the only producer of final document paragraph and table-cell content.

#### Scenario: Web enrichment is enabled
- **WHEN** web enrichment is enabled for a task
- **THEN** the web search branch agent SHALL return structured web evidence and the main writer SHALL produce the final content using that evidence

#### Scenario: Vision layout evidence exists
- **WHEN** visual layout evidence exists for a task
- **THEN** the visual branch agent SHALL provide layout evidence and the main writer SHALL produce the final text

### Requirement: Branch agents produce evidence or verification only
Branch agents SHALL NOT produce final document body text. They SHALL produce structured evidence, layout notes, template plans, compressed summaries, or audit findings.

#### Scenario: Web branch returns search facts
- **WHEN** the web branch is invoked
- **THEN** it SHALL return facts with source metadata, confidence or gap notes when available, and intended usage hints

#### Scenario: Audit branch reviews generated output
- **WHEN** the audit branch is invoked after content generation
- **THEN** it SHALL review the task, generated text, and evidence pack without becoming the original writer of that content

### Requirement: Evidence packs reduce repeated prompt context
The system SHALL construct compact evidence packs for generation sessions and tasks instead of repeatedly sending full knowledge-base recall to every task by default.

#### Scenario: Multiple tasks share project context
- **WHEN** a generation session has multiple FillTasks that share common knowledge-base facts
- **THEN** the system SHALL make those common facts available through session evidence and avoid duplicating the full source material in every task prompt

#### Scenario: Task prompt is assembled
- **WHEN** the main writer prompt is assembled for a task
- **THEN** it SHALL include only the task evidence pack and relevant session evidence within the configured token or character budget

### Requirement: Web evidence is combined with knowledge-base evidence
The system SHALL combine web evidence and knowledge-base evidence into the evidence pack before final writing. Knowledge-base evidence SHALL remain preferred when it conflicts with web evidence unless the task explicitly requires current public information.

#### Scenario: Knowledge base and web facts agree
- **WHEN** both knowledge-base and web evidence support the same claim
- **THEN** the evidence pack SHALL present the claim once with references to the available sources

#### Scenario: Knowledge base and web facts conflict
- **WHEN** web evidence conflicts with knowledge-base evidence
- **THEN** the evidence pack SHALL mark the conflict and the main writer SHALL prefer the knowledge-base fact by default

### Requirement: Template vision and template planning are separate roles
The system SHALL separate template visual understanding from template planning, with independent model roles and trace/billing metadata.

#### Scenario: User selects a visual layout model
- **WHEN** a user selects the template visual model before template analysis
- **THEN** that selection SHALL apply to visual layout understanding and SHALL NOT implicitly select the template planning model

#### Scenario: Planner receives visual profile
- **WHEN** visual layout understanding produces a profile
- **THEN** the template planner SHALL consume the profile as input evidence while resolving its own model role independently

### Requirement: Generation traces expose agent roles
Generation traces and session events SHALL expose role-based routing metadata for evidence search, main writing, and audit.

#### Scenario: Route event emitted
- **WHEN** a task route event is emitted during generation
- **THEN** the event SHALL include the resolved writer role, writer model, evidence-pack summary, and whether web evidence was used

#### Scenario: Quality report saved
- **WHEN** a quality report is saved after generation
- **THEN** the report SHALL include the role/model used for final writing and any branch-agent roles that contributed evidence or audit findings
