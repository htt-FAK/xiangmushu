## Context

The current workbench has one stable interaction pattern worth preserving: document generation keeps a bounded main surface and pushes complete trace details into a dedicated overlay. The surrounding surfaces do not yet follow that pattern.

- Template analysis uses blocking request/response APIs and renders the full task list inline, which makes the page grow with result size and prevents progressive feedback during long vision/planning steps.
- History already has backend persistence and APIs, but the frontend still treats mock data as the default and silently falls back to it when the backend is empty or unavailable.
- Model options are registry-backed in MySQL mode, but frontend and backend behavior do not distinguish between "one option is all that exists" and "the registry query degraded, so only a default survived."

This change crosses frontend UX, API behavior, and persistence-backed registry access, so it benefits from a design before implementation.

```text
Desired interaction shape

Main workbench surface
  ├─ bounded summary / current state
  ├─ compact preview items
  └─ "View details" action

Detail surface
  ├─ full streamed trace
  ├─ long-form lists and diagnostics
  └─ item-level actions

Data truth policy
  ├─ backend data available  -> show backend truth
  ├─ backend empty           -> show empty state
  └─ backend unavailable     -> show degraded/error state, never silent mock
```

## Goals / Non-Goals

**Goals:**
- Bring template analysis onto the same bounded-summary plus detail-trace interaction model as generation.
- Preserve a readable Generate main page by explicitly allowing bounded inline previews while keeping the drawer as the complete trace surface.
- Make history records use backend truth in normal operation and distinguish empty, degraded, and filtered states.
- Ensure settings/model-selection surfaces expose the real set of available models for each role, or clearly signal that the system is in a degraded fallback mode.
- Define fallback behavior that keeps model choice UX functional even when registry-backed MySQL reads fail.

**Non-Goals:**
- Redesign the core generation workflow, billing model, or provider-routing architecture beyond the requirements needed to stabilize these surfaces.
- Introduce new model providers or new pricing/catalog administration flows.
- Replace existing history persistence tables or rework generated-article storage semantics.
- Implement app code in this change artifact set; this document only defines the approach.

## Decisions

### 1. Template analysis will gain session-style progress and a dedicated detail surface

Template analysis will move from a one-shot response model to a session/event model that mirrors generation at the interaction level, while keeping event semantics analysis-specific. The main page will show:
- active template and models,
- bounded progress/status summary,
- compact task preview cards or counts,
- a "view details" action.

The detail surface will render the full streamed analysis trace, phase logs, and complete task list.

Why this over a pure blocking request:
- it matches the interaction pattern users already understand from generation,
- it removes long blank waits during vision/planner work,
- it keeps the page height stable.

Alternative considered:
- Keep blocking analysis and only hide the final task list behind a drawer.
  Rejected because it still leaves long-running work opaque and does not satisfy the request for streamed detail visibility.

### 2. Generate will keep a bounded inline overview, not an unbounded trace

The current product direction is not "main page has nothing until you open details." It is "main page gives confidence quickly without becoming the trace." The spec will therefore be updated so the Generate page may render a bounded, read-only inline overview of outputs, but the complete streamed trace and per-section regeneration stay in the detail drawer.

Why this over reverting to a strict banner-only page:
- users benefit from seeing the current chapters/results at a glance,
- the bounded container solves the scroll-growth problem,
- it aligns with the same summary/detail pattern we want for template analysis.

Alternative considered:
- Revert to banner-only inline state.
  Rejected because it hides too much useful context from the main workbench.

### 3. History will treat backend responses as source of truth and mock data as explicit development-only behavior

The history page will stop using silent mock fallback in production behavior. Instead:
- backend returns data -> render those records and backend summary,
- backend returns empty -> show empty state,
- backend is unavailable or degraded -> show explicit unavailable/error state and retry affordance.

If mock data remains useful for local UI development, it should be behind an explicit development flag or story/demo path, never the default runtime fallback.

Why this over the current mock-first behavior:
- silent fallback hides real persistence failures,
- users cannot tell whether they have no records or the system failed to load them,
- aggregate usage becomes untrustworthy if mock and real data are mixed.

### 4. Registry-backed model options will become health-aware and preserve multi-option role choices

`/api/user/model-options` and preference-loading flows will expose not just option lists but also the data source state:
- registry-backed,
- legacy fallback,
- unavailable/degraded warning.

When registry data is healthy, the backend will return all enabled options for each role. When registry access fails, the backend will fall back to legacy configured role options rather than collapsing to a hard-coded single default. The response will include warning/source metadata so the frontend can explain the degraded mode.

Preference persistence will also support degraded operation by preserving stable role-to-model identifiers in JSON-backed preferences when registry-reference writes are unavailable, instead of silently discarding the user's choice.

Why this over hard-failing settings:
- users still need to inspect and adjust model choices during outages,
- the current "single option" symptom is more confusing than an explicit degraded warning,
- legacy config already contains richer role option sets.

Alternative considered:
- Return 500 for any registry failure and let settings fail closed.
  Rejected because it makes model-choice recovery harder and obscures which parts of the system remain usable.

### 5. History and model APIs will surface degradation explicitly

The affected APIs should return structured warnings or source metadata rather than relying on implicit frontend heuristics. This keeps the UI honest and testable.

Candidate examples:
- history list response includes backend summary for the active filter set and optional unavailability metadata,
- model-option response includes source/warning metadata per role or for the full response,
- template-analysis session response includes phase/state metadata needed for reconnect and detail rendering.

## Risks / Trade-offs

- [New template-analysis session flow adds backend/frontend complexity] -> Reuse generation-session conventions where possible, but keep analysis event types narrower than generation chunk events.
- [Fallback-to-legacy model options can mask registry drift] -> Always surface degraded-state metadata and avoid pretending fallback options are registry-backed.
- [History empty vs unavailable requires API and UI coordination] -> Add explicit response shapes and acceptance scenarios for both cases.
- [Two detail surfaces may diverge visually] -> Reuse shared bounded-summary/detail-drawer patterns and shared preview card components where practical.
- [Preference persistence during degraded registry mode may create temporary mismatch with relational tables] -> Treat JSON-backed role/model identifiers as the compatibility source until registry writes recover, then reconcile on the next healthy save.

## Migration Plan

1. Add template-analysis session/progress endpoints and frontend session state without removing the existing analysis endpoint immediately.
2. Update Template Analysis UI to use bounded overview plus detail trace, then deprecate or reduce direct use of blocking endpoints.
3. Update History APIs and frontend loading states so backend truth, empty, and unavailable paths are distinct.
4. Update model-option and preference APIs to emit source/warning metadata and legacy fallback options when registry reads fail.
5. Roll out frontend settings/history badges and error states so degraded behavior is visible before removing any silent fallbacks.
6. After the new flows are verified, remove production-path silent mock fallback and unused template-analysis blocking UI paths.

## Open Questions

- Should template-analysis sessions reuse `core/generation_sessions.py` with a parallel event schema, or should they live in a dedicated analysis-session module that shares only transport conventions?
- Do we want history unavailability to be represented as a successful response with structured warnings, or as an HTTP error with a structured body that the frontend renders directly?
- Should degraded model-option saves write only JSON-backed preferences, or also queue reconciliation for `user_model_choices` rows once registry health returns?
