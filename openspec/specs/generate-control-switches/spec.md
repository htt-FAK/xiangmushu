# generate-control-switches Specification

## Purpose
TBD - created by archiving change kb-formats-and-generate-redesign. Update Purpose after archive.
## Requirements
### Requirement: Generate page exposes three explicit control switches

The Generate page SHALL expose three explicit user-controlled switches — “联网补充” / web enrichment, “内容审核” / content audit, and “视觉审核” / visual audit — positioned below the “生成质量” quality-mode selector. Each switch SHALL be directly tied to the corresponding `enableWeb / enableAudit / enableVisualAudit` generation parameter used in `/api/generate` requests.

#### Scenario: User toggles web enrichment
- **WHEN** a user toggles the web enrichment switch before starting generation
- **THEN** the subsequent generation request SHALL send `enable_web` matching the switch state

#### Scenario: User toggles content audit
- **WHEN** a user toggles the content audit switch before starting generation
- **THEN** the subsequent generation request SHALL send `enable_audit` matching the switch state

#### Scenario: User toggles visual audit
- **WHEN** a user toggles the visual audit switch before starting generation
- **THEN** the subsequent generation request SHALL send `enable_visual_audit` matching the switch state

### Requirement: Switch defaults follow the smart defaults, but user overrides win

When the selected knowledge base or template changes, the three switches SHALL be initialised from the existing `recommendedConfig` smart defaults (web enrichment on when knowledge base is sparse; content audit on for complex templates; visual audit on by default). As soon as the user manually toggles any switch in the current page session, subsequent `recommendedConfig` changes SHALL NOT overwrite the user's explicit selection.

#### Scenario: Initial state matches smart defaults
- **WHEN** a user opens `/generate` and selects a sparse knowledge base and a complex-named template
- **THEN** the three switches SHALL default to web enrichment on, content audit on, visual audit on

#### Scenario: User override is preserved across selection changes
- **WHEN** a user disables content audit manually and then switches template
- **THEN** the content audit switch SHALL remain disabled after the selection change

### Requirement: Streaming output switch is not exposed

The existing `useStream` parameter SHALL remain a constant set to `true` and SHALL NOT be exposed as a user-visible switch in the Generate page.

#### Scenario: Streaming is always enabled
- **WHEN** a user starts generation from `/generate`
- **THEN** the request SHALL send `use_stream=true` regardless of any other settings

#### Scenario: No streaming switch rendered
- **WHEN** a user inspects the Generate page UI
- **THEN** no switch labelled “流式输出 / Streaming output” SHALL be visible

### Requirement: Switches are disabled while generation is running

While an active generation is in progress (`busy` state), all three control switches SHALL be visibly disabled and SHALL NOT accept user input, the same as the other setup controls.

#### Scenario: Generation running
- **WHEN** an active session is running and the page reports `busy=true`
- **THEN** the web enrichment, content audit, and visual audit switches SHALL all be disabled

