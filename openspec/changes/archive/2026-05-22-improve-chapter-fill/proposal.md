## Why

申报类 Word 模板在「摘要」等章节常含「摘要：在以下填写…」「撰写要求」等**填写指引行**，但当前 `WordFiller` 主要识别「请在此填写 / ____」类占位；未识别的提示段在章节打分中为 0 分，成稿常被写入其下方的空段，导致**提示行残留、正文叠在下面**，回填观感差且不符合交付预期。

## What Changes

- **Phase 1（识别与清扫）**：扩展段落占位/提示模式（含「在以下填写」、`XXXX` 等）；新增「章节填写指引行」判定；提高其在章节内的候选优先级；回填结束后清扫未覆盖的指引行。
- **Phase 2（章节单正文槽）**：对「摘要」等单正文章节，在章节 scope 内选定唯一正文写入目标，并清空同章内的冗余提示行、撰写要求段与多余空段（保留标题、关键词等固定段）。
- **上游（可选、本变更可先做最小集）**：`TemplateAnalyzer` 提示中对独立提示行标注 `replace_mode: full`；`location_hint` 支持来自模板视觉的 `full_replace` 策略。
- **测试**：在 `smoke_test_models` 增加「摘要：在以下填写…」类 offline 用例，与现有「请在此填写」摘要用例并列回归。
- 不改动表格单元格既有 `clean_table_answer` 逻辑；不 **BREAKING** `FillTask` 对外字段（仅扩展 `location_hint` 可选键）。

## Capabilities

### New Capabilities

- `chapter-paragraph-fill`: 章节级段落回填契约——提示行识别与清除、正文槽选择、摘要章单段成稿、与 `replace_mode` / 全篇 sweep 行为。

### Modified Capabilities

<!-- 无：hello-page 与段落回填正交，不修改其需求 -->

## Impact

- **核心**：`core/filler.py`（占位模式、打分、`_fill_paragraph`、章节 scope 分类与清扫）。
- **可选**：`core/template_analyzer.py`（分析 prompt / `replace_mode` 启发式）。
- **测试**：`smoke_test_models.py`；`docs/测试与验收.md` 可增补段落回填验收项。
- **依赖**：无新第三方包；生成与审核流水线接口不变。
