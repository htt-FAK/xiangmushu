## Why

当前文档生成系统在真实模板（如创新计划书）上存在严重格式崩塌问题。核心根因是系统对 Word 文档的样式继承机制缺失——所有段落标题依赖 `Heading 1/2/3` style 识别，但实际模板几乎全部使用 `Normal` style + 内联格式；回填后全局强制覆盖为宋体，摧毁了模板原有的字体设计；表格列宽被强制等分，导致标签列被撑爆。这些问题叠加导致"有些写得好，有些写得不好"的不稳定输出，严重制约产品可用性。

## What Changes

- **BREAKING** `core/docx_typography.py`：移除全局硬编码宋体覆盖逻辑，改为从模板 XML 动态提取样式规格（字体、字号、字号层级、颜色），回填时遵循模板原始样式而非覆盖
- **NEW** `core/template_style_extractor.py`：新增模板样式提取模块——解析 .docx 中 styles.xml、每个段落/单元格的 inline rPr，构建完整的 `TemplateStyleProfile`（含标题层级检测、正文样式、表格样式、列宽比例等）
- **NEW** `core/normal_heading_detector.py`：新增 Normal-style 标题检测——当段落无 Heading style 时，通过字号(bold/size)、编号模式（一、二、三、1.1、2.1）、上下文位置等多信号判断是否为章节标题
- **BREAKING** `core/filler.py`：重构回填引擎——① 表格回填改为语义感知（识别"标签列 vs 内容列"），② 列宽保留原始比例不再强制等分，③ 段落回填根据 TemplateStyleProfile 匹配样式，④ 新增 skip/fill 决策逻辑避免误填
- **NEW** `core/table_semantic_analyzer.py`：新增表格语义分析模块——识别表格结构类型（表单型 label-value、数据型多列表、创新型三列表等），为每个单元格标注 fill_intent（应填/不应填/标签/只读）
- **改进** `core/generator.py`：增强 Prompt 上下文注入——将文档类型（创新计划书/申报书/结课报告）、章节完整层级路径、表格语义角色注入 System Prompt，解决"内容与章节偏题"问题
- **NEW** 用户侧格式偏好配置——生成前允许用户覆盖模板默认样式（选择字体、字号、行距等），通过前端 UI 传入 → 后端合并到 TemplateStyleProfile

## Capabilities

### New Capabilities
- `template-style-extraction`: 从 .docx 模板自动提取完整样式档案（字体/字号/颜色/粗细/段落间距/列宽比例），替代硬编码排版规则
- `normal-heading-detection`: 检测 Normal style 下的章节标题（通过字号+粗体+编号模式+位置等多信号融合），解决 80%+ 真实模板无法识别章节边界的问题
- `table-semantic-analysis`: 分析表格的语义结构（标签-值对型、数据列举型、创新型三列表等），为每个单元格标注 fill_intent，避免误填标签列
- `smart-style-filling`: 基于 TemplateStyleProfile 的智能回填——段落/表格写入时匹配最相近的模板样式，保留原始字体设计而非全局覆盖
- `user-format-preferences`: 用户生成前可配置格式偏好（字体/字号/行距覆盖），通过 UI → API → StyleProfile 合并链路生效
- `context-aware-generation`: 增强生成 Prompt 上下文——注入文档类型、章节完整路径、表格语义角色，解决 LLM 输出与章节偏题的问题

### Modified Capabilities
- `table-format-preservation`: 补充列宽保留要求——回填后保留原始列宽比例（不再强制等分），补充 gridSpan/vMerge 安全处理规则
- `chapter-paragraph-fill`: 补充 Normal-style 标题识别能力，扩展章节区域收集逻辑以支持非 Heading style 的模板

## Impact

- **核心后端模块**: `core/filler.py`、`core/docx_typography.py`、`core/generator.py` 需大幅重构
- **新增模块**: 4 个新模块（template_style_extractor, normal_heading_detector, table_semantic_analyzer, user_format_preferences 相关）
- **前端**: 生成页需新增格式配置 UI（字体选择器、字号输入、样式预览）
- **API**: `/api/generate` 端点新增 `format_overrides` 参数（可选，向后兼容）
- **依赖**: 无新增外部依赖，继续使用 python-docx（已具备 XML 操作能力）
- **向后兼容性**: `APPLY_UNIFIED_TYPOGRAPHY=False` 时保留旧逻辑作为 fallback；已生成的文档不受影响
- **模板兼容性**: 新架构兼容所有现有模板（智能体模板 + 创新计划书等 Normal-style 模板）
