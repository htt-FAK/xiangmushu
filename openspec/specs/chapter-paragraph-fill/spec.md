# chapter-paragraph-fill

Word 章节级段落回填：识别申报模板填写指引行、摘要单正文槽、回填后清扫与回归测试。

## Requirements

### Requirement: Recognize chapter fill-instruction lines

The filler SHALL classify a paragraph as a fill-instruction line when it matches extended placeholder patterns or chapter-specific guidance patterns, including but not limited to: 「在以下填写」「以下填写」、`XXXX`/`××××` sequences, and lines matching `摘要[:：].{0,40}(填写|以下|空白)` without substantive draft content.

#### Scenario: Instruction line with 在以下填写

- **WHEN** a paragraph text is `摘要：在以下填写正文，字数 300–500 字。`
- **THEN** the filler treats the paragraph as a fill-instruction line (not a zero-score ordinary paragraph)

#### Scenario: Instruction line with XXXX placeholder

- **WHEN** a paragraph contains `XXXX` as the only substantive placeholder token
- **THEN** the filler treats the paragraph as containing a replaceable placeholder

### Requirement: Prefer instruction line as chapter body write target

For chapter-scoped paragraph tasks, the filler SHALL score fill-instruction lines at least equal to placeholder-bearing paragraphs so generated body text replaces the instruction line rather than an empty paragraph below it.

#### Scenario: Abstract chapter with instruction and empty paragraph

- **WHEN** a chapter scope contains an instruction line and a subsequent empty paragraph
- **THEN** the filler writes generated content to the instruction line (or clears the empty paragraph after write) and the exported document does not retain the instruction substring

### Requirement: Single body slot for abstract-like chapters

For chapters whose compact title contains「摘要」, the filler SHALL designate at most one body slot paragraph within the chapter scope, write generated content there, and clear other non-reserved paragraphs classified as hint, rubric, or redundant empty within the same scope.

#### Scenario: Abstract with rubric and instruction

- **WHEN** a chapter titled「摘  要」contains a fill-instruction line, a「撰写要求」rubric paragraph, and an empty line
- **THEN** the exported document contains one body paragraph with generated abstract text, does not contain the instruction or rubric text, and preserves heading and keyword lines outside the body slot policy

#### Scenario: Keyword line preserved

- **WHEN** a chapter scope includes a paragraph starting with「关键词」
- **THEN** that paragraph text is unchanged by abstract body-slot clearing

#### Scenario: Abstract with rubric inside table cell

- **WHEN** a chapter titled「摘  要」contains a table whose cell holds「撰写要求」and bullet guidance, plus an empty paragraph below the table before「关键词」
- **THEN** the exported document clears rubric text from table cells, writes generated abstract into the body paragraph slot below the table, and preserves the keyword line

### Requirement: Post-fill sweep removes residual instructions

After all fill tasks complete, the filler SHALL scan body paragraphs and clear any remaining fill-instruction lines that were not overwritten.

#### Scenario: Missed instruction during task loop

- **WHEN** an instruction line was not selected as a task target
- **THEN** the post-fill sweep removes or empties that line so it does not appear in the output document

### Requirement: Existing placeholder-only behavior preserved

When `location_hint.replace_mode` is `placeholder_only` and a recognizable placeholder span exists, the filler SHALL replace only the placeholder span and preserve leading instructional text unless `full_replace` is set in `location_hint`.

#### Scenario: Mixed 说明 plus 请填写

- **WHEN** a paragraph contains fixed left-side说明 and a「请填写」placeholder span
- **THEN** only the placeholder span is replaced with generated content

#### Scenario: Full replace hint

- **WHEN** `location_hint` includes `fill_strategy` or `replace_mode` indicating full replace for an instruction-only line
- **THEN** the entire paragraph is replaced with generated content

### Requirement: Regression tests for abstract templates

The project SHALL include offline smoke tests that build a minimal docx with「摘  要」heading, a「摘要：在以下填写…」instruction line, and assert the filler output contains neither the instruction substring nor duplicate body stacked below an untouched instruction.

#### Scenario: Smoke test 在以下填写

- **WHEN** `smoke_test_models` offline filler tests run
- **THEN** the new abstract instruction-line test passes alongside existing「请在此填写」abstract tests

#### Scenario: Smoke test rubric in table

- **WHEN** `smoke_test_models` offline filler tests run
- **THEN** the abstract rubric-in-table test passes (rubric 1×1 table removed, body in paragraph below)

### Requirement: Bracket fill slots

The filler SHALL treat a paragraph matching `^【请在此填写…】$` as the highest-priority body slot in its chapter, SHALL NOT write body content into subsection headings (`^\d+\.\d+\s`), and SHALL full-replace the bracket line with generated content.

#### Scenario: Bracket line not subsection heading

- **WHEN** a chapter contains `6.1 核心收获` followed by `【请在此填写核心收获】`
- **THEN** generated content replaces the bracket line and the `6.1` heading text is unchanged

### Requirement: Task reconciliation with deterministic scan

The application SHALL merge LLM-analyzed tasks with programmatically scanned placeholder tasks so that missing paragraph/table slots are still generated and filled in any template docx.

#### Scenario: Scanner supplements analyzer

- **WHEN** the analyzer returns no tasks but the scanner finds `【请在此填写…】`
- **THEN** reconcile produces at least one FillTask for that slot
