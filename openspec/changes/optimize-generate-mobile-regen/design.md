## Context

`GeneratePage` currently couples generation controls, live output state, and option list rendering inside one page component. The page already consumes a streaming `/api/generate` endpoint and renders each section through `OutputBlock`, but it only supports full-run generation and uses a single stacked rail layout for knowledge bases and templates across all breakpoints.

This change is frontend-only and must preserve the current backend contract. That creates two implementation constraints:

1. Chapter regeneration has to be orchestrated on the client by reusing the existing generation entrypoint and merging the returned chapter content back into the current output list.
2. Mobile option browsing has to reuse the current visual language and component structure rather than introducing a separate mobile surface.

## Goals / Non-Goals

**Goals:**
- Add a per-section regenerate action that updates only the targeted output block and preserves the rest of the page state.
- Keep the live output card visual style consistent while exposing clear loading/disabled feedback for a single regenerating chapter.
- Add mobile search for templates and knowledge bases with client-side name filtering.
- Present filtered mobile option lists in a two-column card grid while keeping desktop behavior effectively unchanged.
- Preserve TypeScript safety and compile cleanliness.

**Non-Goals:**
- No backend API or event schema changes.
- No redesign of the desktop Generate page information architecture.
- No change to download, billing, or acceptance flows beyond keeping them compatible with partial regeneration.
- No attempt to persist draft state outside the current page session.

## Decisions

### Decision: Model section regeneration as page-level orchestration

The page will own regeneration state for each output block, keyed by chapter index. `OutputBlock` stays presentational and receives an optional action slot plus visual state for regeneration. This keeps page-side knowledge of generation params, stream handling, and merged output data in one place.

Why this over adding network logic inside `OutputBlock`:
- `GeneratePage` already owns the source of truth for outputs, progress, billing, and abort handling.
- Regeneration must preserve global selections (`slug`, `template`, instructions, quality mode) and merge only one block.
- It avoids duplicating endpoint wiring inside a reusable display component.

Alternative considered:
- Create a dedicated hook per output card. Rejected because the current stream handling is page-scoped and would require extra synchronization for billing, error banners, and concurrent requests.

### Decision: Reuse the existing generate endpoint with client-side chapter reconciliation

Because backend APIs cannot change, the frontend will invoke the existing generator with the current selections and interpret streamed `task/route/chunk/audit/progress/done/error` events. The client will capture the chapter text for each streamed task and keep only the matching chapter result for the requested section, then merge that block into the current `outputs` array.

Why this works:
- The stream already identifies chapters by `task` events and per-index updates.
- The page can correlate the requested block by chapter title and only replace that block when the stream finishes.
- Existing request parameters and type definitions remain valid.

Trade-off:
- The backend still performs a full generation pass, so the UI promise is scoped to “only this chapter is updated” rather than reduced server workload. This is acceptable under the no-API-change constraint and should be stated in the UX through local loading feedback rather than a global reset.

### Decision: Split full-run and section-run state

The page will keep full-run state (`running`, `currentTask`, `progress`, etc.) separate from section-run state (`regeneratingIndex`, block-level pending state, section abort controller if needed). During section regeneration the page must not clear all outputs, downloads, or billing summary.

Why:
- Full-run semantics require a page reset; section regeneration must not.
- Separate state avoids accidentally showing the whole page as “running” when only one block is refreshing.

Alternative considered:
- Reuse the existing `running` boolean for all generation activity. Rejected because it would disable the page too aggressively and would break the “other chapters remain usable” requirement.

### Decision: Extend OptionRail with optional mobile search and layout modes

`OptionRail` will accept optional search props and render an inline input above the list on mobile. It will also switch to a two-column card grid under the mobile breakpoint while preserving the current single-column rail on desktop.

Why:
- The rail component already encapsulates item rendering and active styling.
- Search behavior is identical for templates and knowledge bases, so a single implementation avoids duplicate filtering logic.
- Keeping the same button cards and tonal styling preserves the established Generate page look.

Alternative considered:
- Implement separate mobile-only selector components. Rejected because it would duplicate selection markup and risk style drift.

## Risks / Trade-offs

- Full backend regeneration cost remains for section refreshes → Mitigation: limit UI impact to the targeted block and avoid resetting the rest of the run state.
- Chapter correlation may be ambiguous if duplicate chapter names exist → Mitigation: prefer index targeting first and only use chapter name matching inside the section run when necessary.
- Added mobile filtering state could drift between rails → Mitigation: keep one search query per rail in `GeneratePage` and derive filtered arrays with `useMemo`.
- More state branches in `GeneratePage` increase complexity → Mitigation: centralize stream event handling in helper functions and keep `OutputBlock` presentational.

## Migration Plan

1. Add OpenSpec requirements and tasks for Generate page interactions.
2. Extend frontend types/components to support block-level actions and pending state.
3. Refactor `GeneratePage` stream handling so full runs and section runs share event normalization but update different slices of state.
4. Add mobile search/filter/grid behavior to `OptionRail` and pass filtered template/knowledge-base data from `GeneratePage`.
5. Run `npm run build` to validate TypeScript and bundling.
6. Ship as a frontend-only change with no migration or rollback requirement beyond reverting the commit if needed.

## Open Questions

1. Section regeneration still issues a full generate request because the API cannot be changed; the implementation will scope the UX to partial replacement. If later backend support appears, the page orchestration can swap to a true section endpoint without redesigning the UI.
