## MODIFIED Requirements

### Requirement: Recognize chapter fill-instruction lines

The filler SHALL classify a paragraph as a fill-instruction line when it matches extended placeholder patterns or chapter-specific guidance patterns, including but not limited to: 「在以下填写」「以下填写」、`XXXX`/`××××` sequences, and lines matching `摘要[:：].{0,40}(填写|以下|空白)` without substantive draft content.

#### Scenario: Instruction line with 在以下填写

- **WHEN** a paragraph text is `摘要：在以下填写正文，字数 300–500 字。`
- **THEN** the filler treats the paragraph as a fill-instruction line (not a zero-score ordinary paragraph)

#### Scenario: Instruction line with XXXX placeholder

- **WHEN** a paragraph contains `XXXX` as the only substantive placeholder token
- **THEN** the filler treats the paragraph as containing a replaceable placeholder

#### Scenario: Label-value table cell instruction line (NEW)
- **WHEN** a table cell in column 0 of a LABEL_VALUE_PAIR table contains `"项目实施方案（含时间安排）"` with no placeholder patterns
- **THEN** the filler SHALL classify this cell as `fill_intent=LABEL` and NOT treat it as a fill-instruction line

### Requirement: Prefer instruction line as chapter body write target

For chapter-scoped paragraph tasks, the filler SHALL score fill-instruction lines at least equal to placeholder-bearing paragraphs so generated body text replaces the instruction line rather than an empty paragraph below it.

#### Scenario: Abstract chapter with instruction and empty paragraph

- **WHEN** a chapter scope contains an instruction line and a subsequent empty paragraph
- **THEN** the filler writes generated content to the instruction line (or clears the empty paragraph after write) and the exported document does not retain the instruction substring

### Requirement: Chapter region collection supports Normal-style headings (NEW)

The chapter region collection logic (`_collect_chapter_region`) SHALL use the normal-heading detector to identify chapter boundaries when no `Heading 1/2/3` style paragraphs are found in the document.

#### Scenario: Normal-style chapter boundary detected
- **WHEN** `_collect_chapter_region()` is called for chapter `"五、项目实施方案、技术路线及可行性分析"`
  AND the document has no Heading-style paragraphs
  AND the normal-heading detector identifies `"五、..."` as heading score 80 and `"六、..."` as heading score 85
- **THEN** the returned `para_scope` SHALL contain exactly the paragraphs between "五、" and "六、" (exclusive)
  AND `table_scope` SHALL contain tables in the same region

#### Scenario: Heading style takes priority over normal-heading detector
- **WHEN** a document has both Heading 1 styled paragraphs ("Heading 1" style) and Normal-style bold paragraphs
- **THEN** `_collect_chapter_region()` SHALL use the Heading 1 paragraphs as chapter boundaries
  AND the normal-heading detector SHALL NOT override explicit heading styles

#### Scenario: Fallback to whole document when no headings detectable
- **WHEN** neither Heading-style nor normal-heading scoring identifies any chapter boundaries
- **THEN** `_collect_chapter_region()` SHALL return all body paragraphs as the chapter scope (full document treated as single chapter)
  AND a warning SHALL be logged indicating no chapter boundaries were found

### Requirement: Right-column content detection for label-value tables (NEW)

For LABEL_VALUE_PAIR tables, the filler SHALL write generated content to column 1 (the value/content column) and SHALL NOT overwrite column 0 (the label column).

#### Scenario: Generated content written to value column only
- **WHEN** a FillTask targets a LABEL_VALUE_PAIR table row where column 0 = `"项目痛点"` and column 1 is empty
- **THEN** generated content SHALL be written to column 1
  AND column 0 text `"项目痛点"` SHALL remain unchanged

#### Scenario: Multi-row label-value table correctly filled
- **WHEN** a LABEL_VALUE_PAIR table has 3 rows: (项目痛点, empty), (项目创新点, empty), (项目实施方案, empty)
- **THEN** each row's column 1 SHALL be filled with the corresponding generated content
  AND no cross-contamination between rows SHALL occur

### Requirement: Single body slot for abstract-like chapters

For chapters whose compact title contains「摘要」, the filler SHALL designate at most one body slot paragraph within the chapter scope, write generated content there, and clear other non-reserved paragraphs classified as hint, rubric, or redundant empty within the same scope.

#### Scenario: Abstract with rubric and instruction

- **WHEN** a chapter titled「摘  要」contains a fill-instruction line, a「撰写要求」rubric paragraph, and an empty line
- **THEN** the exported document contains one body paragraph with generated abstract text, does not contain the instruction or rubric text, and preserves heading and keyword lines outside the body slot policy

#### Scenario: Keyword line preserved

- **WHEN** a chapter scope includes a paragraph starting with「关键词」
- **THEN** that paragraph text is unchanged by abstract body-slot clearing

### Requirement: Post-fill sweep removes residual instructions

After all fill tasks complete, the filler SHALL scan body paragraphs and clear any remaining fill-instruction lines that were not overwritten.

#### Scenario: Missed instruction during task loop

- **WHEN** an instruction line was not selected as a task target
- **THEN** the post-fill sweep removes or empties that line so it does not appear in the output document

### Requirement: Label-value table label cells protected from sweep (NEW)

The post-fill sweep SHALL NOT clear text from cells classified as `fill_intent=LABEL` even if they contain text that partially matches fill-instruction patterns.

#### Scenario: Label cell with instruction-like text preserved
- **WHEN** a LABEL cell contains `"项目实施方案（含时间安排）"` which contains "安排" — a word that might pattern-match guidance keywords
- **THEN** the post-fill sweep SHALL NOT clear this cell
  AND its original text SHALL be preserved in the output

### Requirement: Existing placeholder-only behavior preserved

When `location_hint.replace_mode` is `placeholder_only` and a recognizable placeholder span exists, the filler SHALL replace only the placeholder span and preserve leading instructional text unless `full_replace` is set in `location_hint`.

#### Scenario: Mixed 说明 plus 请填写

- **WHEN** a paragraph contains fixed left-side 说明 and a「请填写」placeholder span
- **THEN** only the placeholder span is replaced with generated content

#### Scenario: Full replace hint

- **WHEN** `location_hint` includes `fill_strategy` or `replace_mode` indicating full replace for an instruction-only line
- **THEN** the entire paragraph is replaced with generated content

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
