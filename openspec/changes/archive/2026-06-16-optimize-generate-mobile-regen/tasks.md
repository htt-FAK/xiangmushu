## 1. Section Regeneration

- [x] 1.1 Extend `frontend/src/components/OutputBlock.tsx` to support a regenerate action area and block-level pending feedback without changing the existing content layout.
- [x] 1.2 Refactor `frontend/src/pages/GeneratePage.tsx` stream handling so a section regeneration request can reuse existing generate parameters, update only one output block, and preserve other page artifacts/state.

## 2. Mobile Option Browsing

- [x] 2.1 Update `frontend/src/components/ui.tsx` and `frontend/src/pages/GeneratePage.tsx` so OptionRail supports mobile search inputs and client-side filtering for template and knowledge-base lists.
- [x] 2.2 Update `frontend/src/pages/GeneratePage.tsx` OptionRail rendering to use a two-column card grid on mobile while preserving the current desktop rail layout and touch target sizing.

## 3. Verification

- [x] 3.1 Add or update any frontend i18n/type wiring needed by the new interactions in `frontend/src/i18n.ts` and related TypeScript definitions.
- [x] 3.2 Run `npm run build`, fix any TypeScript/build issues, and review the final diff before committing.
