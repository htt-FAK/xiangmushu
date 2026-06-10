## Why

The current Generate page only supports full-run generation and a single long option list layout. That creates unnecessary cost and wait time when users only want to regenerate one weak chapter, and it makes template or knowledge-base selection cumbersome on mobile devices.

## What Changes

- Add chapter-scoped regeneration from each output block so users can rerun one section without resetting the rest of the page state.
- Add mobile search and filtering to the Generate page option rails so users can quickly narrow templates and knowledge bases by name.
- Switch mobile option lists to a touch-friendly two-column card grid while keeping the desktop list behavior unchanged.

## Capabilities

### New Capabilities
- `generate-page-interactions`: Frontend interaction requirements for chapter-level regeneration and mobile-first option browsing on the Generate page.

### Modified Capabilities

- None.

## Impact

- Affected code: `frontend/src/pages/GeneratePage.tsx`, `frontend/src/components/OutputBlock.tsx`, `frontend/src/components/ui.tsx`, `frontend/src/i18n.ts`, and related frontend types/helpers.
- APIs: no backend API contract changes; the frontend must compose with the existing generation endpoint.
- Dependencies/systems: frontend-only interaction and layout work, plus TypeScript build verification.
