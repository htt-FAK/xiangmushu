## Context

当前系统（智能文档生成系统 xiangmushu）的核心管线为：

```
模板(.docx) → template_analyzer → List[FillTask]
                                    ↓
              vector_store + generator.py(LLM) → 生成内容
                                    ↓
              filler.py + docx_typography.py → 输出 .docx
```

**现状问题**（基于创新计划书模板 + 智能体模板深度分析）：

| 问题 | 代码位置 | 现象 |
|------|---------|------|
| 章节标题无法识别 | `filler.py:_collect_chapter_region()` 依赖 `heading_level_from_style()` | Normal style 模板的"一、二、三"标题被忽略，导致整个文档被视为一个章节 |
| 表格列宽强制等分 | `filler.py:_ensure_table_readability()` 硬编码 `6.35/ncols` | 标签列（如"项目痛点" 11mm）被撑爆至等宽，布局崩溃 |
| 全局字体覆盖 | `docx_typography.py:apply_document_typography()` | 模板原有的仿宋_GB2312、Times New Roman 等被统一覆盖为宋体 |
| 表格语义不解 | `filler.py:_fill_table_cell()` 无标签列识别 | 标签列（"项目实施方案"）有时被误填内容，内容列有时被留空 |
| LLM 上下文不足 | `generator.py:SYSTEM_PROMPT` 仅说"项目申报文档" | LLM 不知道是"创新创业书"还是"智能体申报"，内容偏题 |
| 用户无法配置样式 | 硬编码 `SZ_BODY=24, _FONT_ASCII="SimSun"` | 所有输出文档格式一致，无法适配不同模板要求 |

**核心约束**：
- 必须向后兼容——已有模板（智能体模板 `智能体应用开发实践.docx`）在旧逻辑下已能运行
- 不引入新的 Python 依赖（python-docx 已具备完整 XML 操作能力）
- 保持 python-docx 作为唯一 .docx 操作库

## Goals / Non-Goals

**Goals:**
- 正确处理 Normal style 标题（覆盖 80%+ 真实模板）
- 表格回填保留原始列宽、字体、颜色，不再强制等分
- 模板的原始样式设计在回填后完整保留
- LLM Prompt 注入文档类型和章节层级，减少内容偏题
- 提供可扩展的样式提取架构，支持未来更多模板类型
- 用户可通过前端覆盖部分格式偏好

**Non-Goals:**
- 不支持 .doc 格式（仅 .docx，旧格式由 LibreOffice 转换后入库）
- 不引入 docxtemplater / Carbone 等外部模板引擎（保持 python-docx 栈）
- 不实现所见即所得的格式编辑器（仅支持预设选项）
- 不处理 .docx 内的图片、嵌入对象的样式（仅关注文字排版）

## Decisions

### Decision 1: 样式提取 — XML 解析 vs python-docx API

**选择**: 双轨制——优先 python-docx high-level API，缺失时降级到 XML 直接解析

**理由**:
- python-docx 的 `run.font` API 能覆盖 80% 的常见属性（name, size, bold, italic, color）
- 但部分属性（如 eastAsia 字体、w:rFonts 的 cs 属性）需要直接读 XML
- `styles.xml` 的样式继承链（basedOn）python-docx 不完整暴露，需 XML 级解析
- 已有 `docx_typography.py` 中大量 XML 操作先例，团队熟悉这个模式

**替代方案**:
- 纯 python-docx API：无法获取基于 `w:rFonts` 的东亚字体，也无法获取 styles.xml 中的完整继承链
- 纯 XML 解析：开发量大，且 python-docx 对象模型在某些属性上比裸 XML 更方便

### Decision 2: Normal-Heading 检测 — 规则引擎 vs 机器学习

**选择**: 加权规则引擎（多信号融合），非 ML

**理由**:
- 模板数量有限（几十种），不需要通用化解决方案
- 规则可审计、可调试、可快速修改
- ML 模型会引入训练和维护成本，且在这个规模下 overkill

**信号设计**（加权评分，阈值可配置）:

```
信号                    权重    触发条件
─────────────────────────────────────────────────
字号 ≥ 14pt (SZ≥28)     +30    run.font.size >= Pt(14)
加粗                      +25    any(run.font.bold for run in runs)
编号模式匹配              +35    r"^[一二三四五六七八九十]+[、.．]" 或 r"^\d+\.\d+"
位于表格之前              +10    下一兄弟元素是 w:tbl
全段粗体（非混排）         +15    len(runs)==1 或 all runs bold
段落 style 含"标题"        +40    style.name 含 "标题" 或 "Heading"（兜底）
短文本（≤30字）           +10    len(text.strip()) <= 30
```

阈值默认 50，可在 `config.py` 通过 `NORMAL_HEADING_THRESHOLD` 调整。

### Decision 3: 表格语义分析 — 结构模式匹配

**选择**: 基于结构的语义分类器，不依赖 LLM

**理由**:
- 表格结构是确定性的（列数、行数、是否有 gridSpan/vMerge）
- LLM 对表格结构的理解不稳定（容易误判合并单元格）
- 结构匹配足够覆盖现有模板类型

**识别的表格类型**:

```
类型                  判断条件                                     示例
─────────────────────────────────────────────────────────────────────
label_value_pair     col_count == 2, col[0] 宽度 < 40%           项目基本信息表
                     OR col[0] 内容为短标签
data_grid            col_count >= 3, row[0] 为表头               团队成员表
                     AND 数据行全空
innovation_triple    col_count == 3, row[0] 含"创新/实现/应用"    三列创新表
rubric_scoring       col[0] 含"评分/评价", row_count <= 5        评分表 → 只读
cover_info           含封面关键词(学号/姓名/学院)                 封面表 → 只读
```

**每个单元格标注 `fill_intent`**:
- `FILL`: 需要 LLM 生成内容
- `LABEL`: 仅作为标签，不填
- `READ_ONLY`: 封面/评分等不应修改
- `USER_INPUT`: 用户手动填写（如姓名、学号）

### Decision 4: 样式回填策略 — TemplateStyleProfile 优先 + 用户覆盖

**选择**: 三级样式优先级：用户覆盖 > 模板原始样式 > 系统默认

```
用户格式偏好 (format_overrides API 参数)
         ↓ 覆盖
TemplateStyleProfile (从模板提取)
         ↓ 兜底
SystemDefaults (宋体小四, 保留作为最终防线)
```

**TemplateStyleProfile 数据结构**:

```python
@dataclass
class TemplateStyleProfile:
    body_font_ascii: str           # 正文西文字体
    body_font_east_asia: str       # 正文东亚字体
    body_size_pt: float            # 正文字号
    body_bold: bool                # 正文是否粗体
    heading_styles: dict[int, RunStyle]  # {level: RunStyle}
    default_line_spacing: float    # 默认行距
    first_line_indent_pt: float    # 首行缩进
    table_cell_style: RunStyle     # 表格默认样式
    column_widths: dict[int, list[int]]  # {table_index: [col_widths_dxa]}
    cover_protected: bool          # 是否保护封面

@dataclass
class RunStyle:
    font_ascii: str
    font_east_asia: str
    size_pt: float
    bold: bool | None
    italic: bool | None
    color_rgb: str | None
```

### Decision 5: 上下文增强 — 文档类型自动推断 + Prompt 注入

**选择**: 从模板名称 + 内容自动推断文档类型，注入到 System Prompt

**理由**:
- 用户选择模板时已经隐含了文档类型
- 在 Prompt 中注入"这是一份创新创业计划书"能显著提升 LLM 输出相关性
- 章节层级路径（如"五、> 项目实施方案、技术路线及可行性分析 > 项目实施方案"）能让 LLM 精确理解上下文

**注入格式**:
```
你是项目申报文档撰写专家。

⚠️ 文档类型：创新创业计划书
📍 当前章节路径：五、项目实施方案、技术路线及可行性分析 > 项目实施方案
📋 表格角色：本格的列标题为"项目实施方案（含时间安排）"，请撰写具体的实施方案和时间安排。

严格规则：
1. 所有内容须来自【参考资料】，无据不编造...
```

### Decision 6: 列宽保护 — 保留原始 dxa 值

**选择**: 回填时完全不调用 `_ensure_table_readability()` 的列宽覆盖逻辑

**理由**:
- 模板设计者已经设置了合理的列宽（标签列窄，内容列宽）
- 强制等分只对所有列宽度接近的情况有效
- 现有 `_ensure_table_readability()` 对封面表和评分表已做了保护判断，但内容表仍被破坏

**策略**:
- 新增 `PRESERVE_ORIGINAL_COLUMN_WIDTHS` 配置项（默认 True）
- True: 完全保留原始列宽，仅修复 noWrap 和 vAlign
- False: 回退到旧的等宽逻辑（向后兼容）

## Risks / Trade-offs

**[Risk] Normal-heading 检测误判** → 误将正文段落识别为标题
- **Mitigation**: 多信号加权而非单信号判断；阈值可配置；检测结果会打印调试日志供排查

**[Risk] 新模板类型不在已知表格类型中** → 表格语义分析返回 `UNKNOWN`，回退到旧逻辑
- **Mitigation**: `UNKNOWN` 类型不改变现有行为；逐步扩展类型库

**[Risk] 向后兼容性风险** → 已有用户习惯了"全宋体"输出
- **Mitigation**: 新增 `APPLY_TEMPLATE_STYLE=true/false` 配置项；false 时保留旧逻辑；灰度上线

**[Trade-off] 样式提取复杂度 vs 输出质量** → 双轨制（API + XML）增加了代码复杂度
- **Rationale**: 纯 API 方案在东亚字体场景下不完整；长期来看这是必要的复杂度

**[Trade-off] 列宽保护后表格可能溢出** → 保留超窄列宽可能导致内容被挤出
- **Mitigation**: 设置最小列宽阈值（<500 dxa 时自动扩展到 500 dxa）

## Migration Plan

```
Phase 1 (2周): 新增模块 + 配置开关（不改变现有行为）
  ├── template_style_extractor.py (新)
  ├── normal_heading_detector.py (新)
  ├── table_semantic_analyzer.py (新)
  └── 所有新逻辑默认 disabled，保留旧路径

Phase 2 (1周): 灰度验证
  ├── 用创新计划书模板 + 智能体模板双轨跑
  ├── 比对新旧输出质量（visual_audit 评分）
  └── 修复 Phase 1 发现的问题

Phase 3 (1周): 切换默认 + 前端 UI
  ├── APPLY_TEMPLATE_STYLE 默认 True
  ├── 前端格式偏好 UI 上线
  └── 文档和用户指引更新

Rollback: 任何阶段可通过环境变量回退旧逻辑
```

## Open Questions

1. **表格类型扩展机制**: 是否需要支持用户自定义表格类型规则（如 YAML 配置）？还是代码中硬编码即可？
2. **样式缓存策略**: TemplateStyleProfile 是否需要缓存到磁盘（类似 template_vision 的缓存机制）？每次生成时重新提取是否有性能影响？
3. **多模板混合**: 一个生成会话中是否会用到多个模板？如果是，样式冲突如何解决？
