## ADDED Requirements

### Requirement: Detect chapter headings in Normal-style paragraphs

The system SHALL identify paragraph-level chapter headings even when those paragraphs use `Normal` style instead of `Heading 1/2/3` styles, by applying a weighted multi-signal scoring model.

#### Scenario: Chinese numbered heading detected
- **WHEN** a Normal-style paragraph contains text `"一、项目基本信息"` with font size ≥ 14pt and bold runs
- **THEN** the normal-heading detector SHALL score this paragraph ≥ 80 (above the default threshold of 50) AND classify it as a chapter heading at level 1

#### Scenario: Decimal numbered sub-heading detected
- **WHEN** a Normal-style paragraph contains `"5.2 技术路线"` with bold formatting
- **THEN** the detector SHALL classify it as a level-2 heading

#### Scenario: Short bold paragraph not misclassified
- **WHEN** a Normal-style paragraph contains `"项目经费预算"` in bold but has no numbering pattern and is followed by a table
- **THEN** the detector SHALL still classify it as a heading (score boosted by table-proximity signal and bold+short-text signals)

#### Scenario: Regular body paragraph not misclassified as heading
- **WHEN** a paragraph contains `"本项目旨在开发一套智能文档生成系统，解决当前申报文档填写效率低、格式不一致的问题。"` with no bold and size 12pt
- **THEN** the detector SHALL score this paragraph below threshold AND NOT classify it as a heading

### Requirement: Weighted signal scoring model

The system SHALL compute a heading-likelihood score as the sum of weighted signal activations, with a configurable threshold determining the final classification.

#### Scenario: Signal weights produce correct classification
- **WHEN** signals are: bold(+25), numbering pattern(+35), short text ≤30 chars(+10), preceded by table(+10)
- **THEN** the total score SHALL be 80, exceeding default threshold 50 → classified as heading

#### Scenario: Missing critical signals prevent false positive
- **WHEN** a paragraph has only short text(+10) and no other signals
- **THEN** the score SHALL be 10, below threshold → NOT classified as heading

### Requirement: Configurable threshold

The system SHALL expose a `NORMAL_HEADING_THRESHOLD` configuration parameter (default 50) allowing operators to tune sensitivity without code changes.

#### Scenario: Threshold raised to reduce false positives
- **WHEN** `NORMAL_HEADING_THRESHOLD` is set to `70`
- **THEN** paragraphs scoring between 50-69 SHALL NOT be classified as headings

#### Scenario: Threshold lowered for aggressive detection
- **WHEN** `NORMAL_HEADING_THRESHOLD` is set to `30`
- **THEN** paragraphs with only numbering pattern(+35) SHALL be classified as headings

### Requirement: Integration with chapter region collection

The system SHALL integrate normal-heading detection into `_collect_chapter_region()`, using detected headings as chapter boundaries when no Heading-style paragraphs are found.

#### Scenario: Chapter region correctly bounded by normal headings
- **WHEN** `_collect_chapter_region()` is called for chapter `"五、项目实施方案"` and the next normal-heading is `"六、项目定位"`
- **THEN** the returned `para_scope` SHALL include only paragraphs between "五、" and "六、" (exclusive of "六、")
- **AND** `table_scope` SHALL include only tables in that same region

#### Scenario: Hybrid Heading-style + Normal-style document
- **WHEN** some sections use Heading 1 style and others use Normal+bold+numbering
- **THEN** the system SHALL use whichever heading type is actually present, mixing is allowed
