## 1. Phase 1 — Hint recognition and scoring

- [x] 1.1 Add regex patterns to `_PLACEHOLDER_PATTERNS` (在以下填写, XXXX, etc.)
- [x] 1.2 Implement `_looks_like_fill_instruction_line()` in `core/filler.py`
- [x] 1.3 Bump `_score_paragraph_candidate` for instruction lines to priority 3
- [x] 1.4 Extend `_sweep_residual_hint_paragraphs` to clear instruction lines
- [x] 1.5 Honor `location_hint` `fill_strategy` / `full_replace` in `_write_paragraph_content`

## 2. Phase 2 — Abstract single body slot

- [x] 2.1 Add `_classify_scope_paragraph()` helpers (hint, rubric, keyword, empty, other)
- [x] 2.2 Implement `_clear_non_body_scope_paragraphs()` for abstract chapters after write
- [x] 2.3 Wire body-slot clearing from `_fill_paragraph` when target is 摘要/Abstract

## 3. Tests and docs

- [x] 3.1 Add `_offline_filler_abstract_instruction_below_fill()` smoke test (在以下填写)
- [x] 3.2 Register new test in `_run_all_offline()` list
- [x] 3.3 Add acceptance bullet to `docs/测试与验收.md` for instruction-line removal

## 4. Optional upstream

- [x] 4.1 Extend `TemplateAnalyzer` JSON prompt for standalone instruction → `replace_mode: full`
- [x] 4.2 Heuristic in `_apply_replace_mode_heuristics` for「在以下填写」lines
