## 1. 数据结构与配置基础

- [x] 1.1 新增 `core/style_models.py`：定义 `RunStyle` dataclass（font_ascii, font_east_asia, size_pt, bold, italic, color_rgb）和 `TemplateStyleProfile` dataclass（body 样式、heading_styles map、table_cell_style、column_widths、line_spacing、first_line_indent_pt、cover_protected），含 JSON 序列化/反序列化方法
- [x] 1.2 新增 `core/fill_intent.py`：定义 `FillIntent` 枚举（FILL / LABEL / READ_ONLY / USER_INPUT）和 `TableSemanticType` 枚举（LABEL_VALUE_PAIR / DATA_GRID / INNOVATION_TRIPLE / RUBRIC_SCORING / COVER_INFO / UNKNOWN）
- [x] 1.3 `config.py` 新增配置项：`APPLY_TEMPLATE_STYLE`（默认 True）、`NORMAL_HEADING_THRESHOLD`（默认 50）、`PRESERVE_ORIGINAL_COLUMN_WIDTHS`（默认 True）、`PROMPT_TEMPLATE_VERSION`（默认 "v2.1"）、`MIN_COLUMN_WIDTH_DXA`（默认 500）

## 2. Normal-Heading 检测模块

- [x] 2.1 新增 `core/normal_heading_detector.py`：实现 `score_normal_heading(para) -> int` 函数，包含 7 个加权信号（字号≥14pt +30、加粗 +25、中文编号模式 +35、位于表格前 +10、全段粗体 +15、style 含"标题" +40、短文本≤30字 +10）
- [x] 2.2 `core/normal_heading_detector.py`：实现 `classify_heading(para, threshold) -> Optional[int]` 函数，返回 heading level（1-3）或 None；level 推断基于编号深度（"一、"=1, "1.1"=2, "1.1.1"=3）
- [x] 2.3 `core/normal_heading_detector.py`：实现 `find_all_headings(doc, threshold) -> list[(para_index, level)]`，遍历文档所有段落返回检测到的标题列表
- [x] 2.4 修改 `core/filler.py` `_collect_chapter_region()`：当 `heading_level_from_style()` 对所有段落返回 None 时，调用 `find_all_headings()` 获取 Normal-style 标题列表，用其作为章节边界；Heading style 优先级高于 Normal-heading 检测结果
- [x] 2.5 单元测试：`tests/test_normal_heading_detector.py`，覆盖中文编号标题、十进制编号标题、非标题正文、短粗体段落不误判等场景

## 3. 模板样式提取模块

- [x] 3.1 新增 `core/template_style_extractor.py`：实现 `extract_style_profile(docx_path) -> TemplateStyleProfile`，先用 python-docx API 读取 `run.font.{name,size,bold,italic,color}`，fallback 到 XML 解析 `w:rFonts/@w:eastAsia`、`w:sz/@w:val`、`w:b` 等
- [x] 3.2 `core/template_style_extractor.py`：实现 `_resolve_style_chain(style, styles_xml) -> RunStyle`，解析 styles.xml 的 basedOn 继承链，合并显式覆盖和继承属性
- [x] 3.3 `core/template_style_extractor.py`：实现 `_extract_column_widths(doc) -> dict[int, list[int]]`，从每个 table 第一行的 `w:tcW` XML 提取 dxa 值，保留 gridSpan 信息
- [x] 3.4 `core/template_style_extractor.py`：实现 `_detect_heading_styles(doc, headings) -> dict[int, RunStyle]`，接收 normal_heading_detector 的输出，统计各层级标题的字体规格
- [x] 3.5 `core/template_style_extractor.py`：实现样式缓存机制——以 `{abspath(docx_path)}|{mtime}` 为 key，缓存到 `data/.cache/template_styles/{key}.json`，参照 `template_vision.py` 的缓存模式
- [x] 3.6 单元测试：`tests/test_template_style_extractor.py`，用 `智能体应用开发实践.docx` 和创新计划书模板验证提取结果

## 4. 表格语义分析模块

- [x] 4.1 新增 `core/table_semantic_analyzer.py`：实现 `classify_table_type(table) -> TableSemanticType`，依次检测覆盖表(关键词匹配)、评分表(评分/评价关键词)、三列创新表、标签-值对(2列+列宽<40%)、数据网格(≥3列+空数据行)，默认 UNKNOWN
- [x] 4.2 `core/table_semantic_analyzer.py`：实现 `annotate_fill_intents(table, table_type) -> dict[(row,col), FillIntent]`，为每个单元格标注 fill_intent；LABEL 列（col 0 of label-value 对）、READ_ONLY（封面/评分表所有格）、FILL（内容格）、gridSpan 保护（只占首物理格）
- [x] 4.3 `core/table_semantic_analyzer.py`：实现 `analyze_table(table, table_index, chapter) -> TableAnalysis`，整合 type + fill_intents 为单一返回对象，供 filler 和 generator 共用
- [x] 4.4 修改 `core/filler.py` `_fill_table_cell()`：在填表前检查 `fill_intent`，LABEL 和 READ_ONLY 直接跳过，不写入内容；仅 FILL 类型执行写入
- [x] 4.5 修改 `core/table_slot_expand.py` `scan_table_fill_tasks()`：调用 `annotate_fill_intents()` 过滤，只对 `fill_intent == FILL` 的单元格生成 FillTask
- [x] 4.6 单元测试：`tests/test_table_semantic_analyzer.py`，覆盖创新计划书所有 9 个表格的分类结果验证，以及封面表/评分表不被误填

## 5. 智能样式回填集成

- [x] 5.1 新增 `core/smart_style.py`：实现 `merge_style(profile: TemplateStyleProfile, overrides: dict | None) -> TemplateStyleProfile`，三级优先级合并（user_overrides > template > system_default），返回新 profile
- [x] 5.2 `core/smart_style.py`：实现 `apply_smart_style(para, merged_profile, heading_detector=None)`，根据段落的 heading level（优先 style name，fallback Normal-heading 评分）选择 RunStyle 写入 run.rPr；表格段落使用 `table_cell_style`
- [x] 5.3 修改 `core/filler.py` `_set_paragraph_text_keep_style()`：当 `APPLY_TEMPLATE_STYLE=True` 时，用 `apply_smart_style()` 替代当前硬编码的 `build_rPr_for_paragraph()`；`APPLY_TEMPLATE_STYLE=False` 保留旧逻辑
- [x] 5.4 修改 `core/filler.py` `_set_cell_text_keep_style()`：当 `APPLY_TEMPLATE_STYLE=True` 时，优先从 `merged_profile.table_cell_style` 取样式，而非 `_sample_cell_rPr()` 采样（采样仍作为 fallback）
- [x] 5.5 修改 `core/filler.py` `fill_template()` 末尾的 `apply_document_typography()` 调用：`APPLY_TEMPLATE_STYLE=True` 时改为调用 `apply_smart_style_to_document(doc, merged_profile)`（逐段调用 `apply_smart_style`），保留封面保护逻辑；`False` 时保留旧的全局覆盖
- [x] 5.6 单元测试：`tests/test_smart_style.py`，验证 style 合并三级优先级；用创新计划书模板验证回填后字体保持仿宋_GB2312 而非宋体

## 6. 列宽保护（表格格式保留增强）

- [x] 6.1 修改 `core/filler.py` `_ensure_table_readability()`：当 `PRESERVE_ORIGINAL_COLUMN_WIDTHS=True` 时，跳过列宽覆盖逻辑（不调 `cell.width = col_w`），仅修复 `noWrap` 移除和 `vAlign=top` 设置
- [x] 6.2 `core/filler.py` `_ensure_table_readability()`：新增最小列宽保护——当某列宽度 < `MIN_COLUMN_WIDTH_DXA` 时，扩展到 500 dxa 并从相邻列减去等量宽度，保持总宽度不变
- [x] 6.3 `core/filler.py` `_ensure_table_readability()`：新增 gridSpan 安全处理——检测含 `gridSpan` 的单元格，调整 width 时不拆分合并格
- [x] 6.4 集成测试：用创新计划书模板生成后打开 Word，截图比对列宽与原始模板的差异（视觉验证）

## 7. 上下文增强生成

- [x] 7.1 新增 `core/document_type_detector.py`：实现 `infer_document_type(template_path, explicit_type=None) -> str`，从文件名推断（"创新计划书" → "创新创业计划书"，"申报书" → "项目申报书"）；explicit_type 非空时直接返回
- [x] 7.2 新增 `core/chapter_path_builder.py`：实现 `build_chapter_path(target_chapter, all_headings) -> str`，构建章节层级路径（如 "五、项目实施方案 > 项目实施方案"）
- [x] 7.3 修改 `core/generator.py` `SYSTEM_PROMPT` 系列：在 prompt 头部新增动态注入占位符 `{document_type_block}` `{chapter_path_block}` `{table_role_block}`，由 `_build_chat_request()` 填充
- [x] 7.4 修改 `core/generator.py` `_build_chat_request()` 和 `prepare_bundle_from_evidence()`：调用 `infer_document_type()` 和 `build_chapter_path()`，注入到 prompt 对应占位符；表格任务额外注入 `table_role_block`（来自 `table_semantic_analyzer`）
- [x] 7.5 `core/generator.py` 新增 `prompt_version` 字段写入 `route_meta`，便于追踪 prompt 版本
- [x] 7.6 单元测试：验证创新计划书模板的 document_type 推断为 "创新创业计划书"；章节路径构建正确

## 8. 用户格式偏好（API + 前端）

- [x] 8.1 新增 `core/format_overrides.py`：实现 `FormatOverrides` Pydantic model，字段包括 `body_font_ascii`, `body_font_east_asia`, `body_size_pt`(8-24), `body_bold`, `heading_size_delta_pt`(-4~4), `line_spacing`(1-2.5), `first_line_indent_pt`(0-48)；含验证器
- [x] 8.2 修改 `server.py` `/api/generate` 路由：在请求体中新增可选 `format_overrides: FormatOverrides | None` 字段；传递给 `fill_template()` 调用链
- [x] 8.3 修改 `server.py` `_run_generation_session()`：将 `format_overrides` 与 `TemplateStyleProfile` 合并（调用 `merge_style()`），传入 filler
- [x] 8.4 前端 `frontend/src/components/GeneratePage.tsx`（或对应文件）：新增"格式设置"折叠面板，含字体下拉（宋体/黑体/楷体/仿宋/微软雅黑）、字号滑块（10-18pt）、行距下拉（1/1.25/1.5/2.0）、"恢复模板默认"按钮
- [x] 8.5 前端格式设置状态管理：将用户选择的格式偏好存入 localStorage（key=`format_prefs_{template_id}`），生成时序列化为 `format_overrides` 并附在 API 请求体中
- [x] 8.6 单元测试：`tests/test_format_overrides.py`，验证 Pydantic 校验（边界值、无效值返回 400）；集成测试：API 携带 format_overrides 生成文档后验证字体

## 9. 迁移开关与回归测试

- [x] 9.1 `config.py` 最终确认：`APPLY_TEMPLATE_STYLE`、`PRESERVE_ORIGINAL_COLUMN_WIDTHS`、`NORMAL_HEADING_THRESHOLD` 三项开关均可通过环境变量覆盖，默认值为新逻辑
- [x] 9.2 新增 `tests/test_doc_gen_revamp_e2e.py`：端到端测试，用创新计划书模板走完整管线（analyze → generate → fill → save），断言：① 所有 FillTask target_chapter 正确，② 输出文档列宽与模板一致，③ 正文字体为仿宋_GB2312，④ 封面表和评分表未被修改，⑤ 无残留填写提示行
- [x] 9.3 新增 `tests/test_backward_compat.py`：使用智能体模板（`智能体应用开发实践.docx`）验证 `APPLY_TEMPLATE_STYLE=False` + `PRESERVE_ORIGINAL_COLUMN_WIDTHS=False` 时输出与旧逻辑完全一致
- [x] 9.4 更新 `smoke_test_models.py --offline`：新增 Normal-heading 检测、表格语义分类、样式提取三个离线断言
- [x] 9.5 运行 `pytest --cov=core` 确保所有新增和修改模块有测试覆盖，覆盖率不低于现有基线
