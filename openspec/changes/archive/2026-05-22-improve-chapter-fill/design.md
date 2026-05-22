## Context

`WordFiller._fill_paragraph` selects one paragraph per chapter via `_score_paragraph_candidate` (hint match 3, placeholder/rubric 2, empty 1, other 0). `_PLACEHOLDER_PATTERNS` and `_is_pure_hint_line` (max 40 chars) miss申报模板口语如「摘要：在以下填写…」。`_sweep_residual_hint_paragraphs` only clears `_is_pure_hint_line`. Smoke tests cover「请在此填写」but not「在以下填写」.

## Goals / Non-Goals

**Goals:**

- Phase 1: New patterns + `_looks_like_fill_instruction_line()` + scoring bump + sweep uses new classifier.
- Phase 2: `_apply_abstract_body_slot()` (or generic `_apply_single_body_slot` for 摘要-only first) after write in `_fill_paragraph`.
- Optional: `template_analyzer` prompt line for `replace_mode: full` on standalone instruction lines; honor `location_hint["fill_strategy"] == "full_replace"`.
- Offline smoke: `摘要：在以下填写` fixture.

**Non-Goals:**

- Table cell hint logic changes.
- Multi-body chapters (e.g. 第三章 with many subsections) in Phase 2—only 摘要/Abstract title match.
- ContentAuditor / generator prompt changes (future).

## Decisions

1. **Extend regex list in `WordFiller`** rather than LLM classify at fill time — deterministic, testable, matches existing architecture.

2. **`_looks_like_fill_instruction_line`** separate from `_is_pure_hint_line` — allows longer lines (e.g. ≤120 chars) and title-prefixed patterns without breaking pure-hint 40-char rule.

3. **Scoring: instruction line → 3** — ties `paragraph_text` hint priority; beats empty (1).

4. **Abstract body slot** — after `_write_paragraph_content` on chosen idx, iterate scope and clear paragraphs classified as `hint|rubric|empty` except `keyword|heading|body_written`. Reserved prefixes: `关键词`, `Key words`, `Abstract` heading already outside scope.

5. **`full_replace` in location_hint** — if set, `_write_paragraph_content` skips `placeholder_only` partial replace (already mostly full for rubric/guidance; explicit for analyzer).

**Alternatives considered:**

- *Delete all non-heading text in chapter* — too aggressive for 说明性固定段.
- *Only sweep, no scoring* — leaves wrong write target during main loop.

## Risks / Trade-offs

- **[Risk] False positive on short说明段** → require `填写|以下|XXXX` markers; exclude paragraphs >400 chars with 本项目/本系统.
- **[Risk] 摘要章误删合法固定说明** → keyword/reserved list; body slot only when `_is_abstract_chapter`.
- **[Risk] placeholder_only 混排** → unchanged path when span found.

## Migration Plan

Ship Phase 1+2 together in one release; no data migration. Rollback: revert `filler.py` + smoke test. Users re-export documents.

## Open Questions

- Whether to extend single-body-slot to「引言」「项目概述」— defer until templates catalogued.
