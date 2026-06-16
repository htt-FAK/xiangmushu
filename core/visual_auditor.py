"""视觉审核模块：支持结构化文本审核（无需 LibreOffice）和文档保护检测。"""
from __future__ import annotations

import json
import logging
import os
import re
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree as ET

import config
from core.dashscope_chat import chat_completions_create

_LOG = logging.getLogger(__name__)

# Word 命名空间
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
}


@dataclass
class VisualAuditResult:
    """视觉审核结果"""
    score: int = 0  # 总分 0-100
    watermark_score: int = 0  # 水印完整性 0-20
    format_score: int = 0  # 格式正确性 0-20
    content_score: int = 0  # 内容充实度 0-20
    table_score: int = 0  # 表格规范性 0-20
    layout_score: int = 0  # 排版美观度 0-20
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    parse_ok: bool = True
    # 保护检测
    protected_elements: List[str] = field(default_factory=list)  # 检测到的保护元素
    cover_modified: bool = False  # 封面是否被修改
    rating_table_modified: bool = False  # 评分表是否被修改


@dataclass
class DocumentStructure:
    """文档结构信息"""
    total_paragraphs: int = 0
    total_tables: int = 0
    total_words: int = 0
    has_watermark: bool = False
    watermark_text: str = ""
    header_content: List[str] = field(default_factory=list)
    footer_content: List[str] = field(default_factory=list)
    cover_elements: List[str] = field(default_factory=list)  # 封面元素
    rating_tables: List[str] = field(default_factory=list)  # 评分表
    sample_paragraphs: List[str] = field(default_factory=list)
    table_structures: List[Dict] = field(default_factory=list)
    styles_info: Dict[str, str] = field(default_factory=dict)


class DocxStructureExtractor:
    """docx 结构提取器：无需 LibreOffice，直接解析 XML。"""

    @staticmethod
    def extract(docx_path: str) -> DocumentStructure:
        """提取文档结构信息。"""
        struct = DocumentStructure()

        if not os.path.exists(docx_path):
            return struct

        try:
            with zipfile.ZipFile(docx_path, 'r') as zf:
                # 读取 document.xml
                if 'word/document.xml' in zf.namelist():
                    with zf.open('word/document.xml') as f:
                        tree = ET.parse(f)
                        root = tree.getroot()
                        struct = DocxStructureExtractor._parse_document(root, struct)

                # 读取 header/footer
                for name in zf.namelist():
                    if name.startswith('word/header') and name.endswith('.xml'):
                        with zf.open(name) as f:
                            tree = ET.parse(f)
                            header_text = DocxStructureExtractor._extract_text(tree.getroot())
                            struct.header_content.append(header_text)
                    elif name.startswith('word/footer') and name.endswith('.xml'):
                        with zf.open(name) as f:
                            tree = ET.parse(f)
                            footer_text = DocxStructureExtractor._extract_text(tree.getroot())
                            struct.footer_content.append(footer_text)

        except Exception as e:
            _LOG.warning("文档结构提取失败: %s", e)

        return struct

    @staticmethod
    def _parse_document(root: ET.Element, struct: DocumentStructure) -> DocumentStructure:
        """解析 document.xml 内容。"""
        body = root.find('.//w:body', NAMESPACES)
        if body is None:
            return struct

        # 提取所有段落
        paragraphs = body.findall('.//w:p', NAMESPACES)
        struct.total_paragraphs = len(paragraphs)

        # 提取前 N 个段落作为样本
        sample_count = 0
        for para in paragraphs:
            text = DocxStructureExtractor._extract_paragraph_text(para)
            if text.strip():
                if sample_count < 10:
                    struct.sample_paragraphs.append(text[:200])
                    sample_count += 1
                struct.total_words += len(text)

        # 检测封面（前3个段落）
        cover_paras = paragraphs[:3] if len(paragraphs) >= 3 else paragraphs
        for para in cover_paras:
            text = DocxStructureExtractor._extract_paragraph_text(para)
            if text.strip():
                struct.cover_elements.append(text[:100])

        # 检测评分表关键词
        for para in paragraphs:
            text = DocxStructureExtractor._extract_paragraph_text(para)
            if any(kw in text for kw in ["评分", "评分表", "评价", "打分", "得分", "总分"]):
                struct.rating_tables.append(text[:100])

        # 提取表格
        tables = body.findall('.//w:tbl', NAMESPACES)
        struct.total_tables = len(tables)

        for table in tables:
            table_info = DocxStructureExtractor._extract_table_info(table)
            struct.table_structures.append(table_info)

            # 检测评分表
            table_text = table_info.get("text", "")
            if any(kw in table_text for kw in ["评分", "评价", "打分", "得分", "总分", "等级"]):
                struct.rating_tables.append(f"表格: {table_text[:100]}")

        # 检测水印（通过 header/footer）
        struct.has_watermark = bool(struct.header_content or struct.footer_content)

        return struct

    @staticmethod
    def _extract_text(element: ET.Element) -> str:
        """提取元素中的所有文本。"""
        texts = []
        for t in element.iter():
            if t.text and t.text.strip():
                texts.append(t.text.strip())
        return " ".join(texts)

    @staticmethod
    def _extract_paragraph_text(para: ET.Element) -> str:
        """提取段落文本。"""
        texts = []
        for t in para.findall('.//w:t', NAMESPACES):
            if t.text:
                texts.append(t.text)
        return "".join(texts)

    @staticmethod
    def _extract_table_info(table: ET.Element) -> Dict[str, Any]:
        """提取表格信息。"""
        rows = table.findall('.//w:tr', NAMESPACES)
        row_count = len(rows)
        col_count = 0
        if rows:
            first_row_cells = rows[0].findall('.//w:tc', NAMESPACES)
            col_count = len(first_row_cells)

        # 提取表格文本
        texts = []
        for row in rows:
            row_texts = []
            for cell in row.findall('.//w:tc', NAMESPACES):
                cell_text = DocxStructureExtractor._extract_paragraph_text(cell)
                row_texts.append(cell_text)
            texts.append(" | ".join(row_texts))

        return {
            "rows": row_count,
            "cols": col_count,
            "text": "\n".join(texts),
        }


STRUCTURED_AUDIT_SYSTEM = """你是文档质量审核专家。请根据提供的 Word 文档结构化信息进行质量评估。

评分维度（每项 0-20 分）：
1. 水印完整性：页眉/页脚中是否包含水印信息（文字或图片水印）
2. 格式正确性：文档是否有合理的段落结构、字体设置
3. 内容充实度：各章节内容是否充实，有无明显空白或过于简短
4. 表格规范性：表格结构是否完整、内容是否规范
5. 排版美观度：整体结构是否合理，有无明显排版问题

保护检测规则：
- 封面保护：检测封面元素（标题、日期、单位等）是否被意外修改
- 评分表保护：检测评分表、评价表是否被意外填充或修改
- 格式保护：检测原有格式是否被保留

输出要求：
- 只输出一个 JSON 对象，不要 Markdown 围栏
- 必须包含以下键：
  - score: 总分 (0-100)
  - watermark_score: 水印完整性 (0-20)
  - format_score: 格式正确性 (0-20)
  - content_score: 内容充实度 (0-20)
  - table_score: 表格规范性 (0-20)
  - layout_score: 排版美观度 (0-20)
  - issues: 字符串数组，列出发现的问题
  - suggestions: 字符串数组，列出改进建议
  - protected_elements: 字符串数组，列出的保护元素（如水印、评分表）
  - cover_modified: 布尔值，封面是否被修改
  - rating_table_modified: 布尔值，评分表是否被修改
- 不要输出 JSON 以外的任何文字"""


def audit_document_visual(
    docx_path: str,
    max_pages: int = 4,
    zoom: float = 1.5,
    model_override: str | None = None,
    strict_model_selection: bool = False,
) -> VisualAuditResult:
    """对生成的 Word 文档进行视觉审核（结构化文本审核，无需 LibreOffice）。

    Args:
        docx_path: Word 文档路径
        max_pages: 最大审核页数（结构化审核中忽略）
        zoom: PDF 转图片的缩放比例（结构化审核中忽略）

    Returns:
        VisualAuditResult: 视觉审核结果
    """
    if not config.VISUAL_AUDIT_ENABLED:
        _LOG.info("视觉审核已禁用")
        return VisualAuditResult(score=100, parse_ok=True)

    try:
        # 1. 提取文档结构
        struct = DocxStructureExtractor.extract(docx_path)
        _LOG.info("文档结构提取完成: %s 段落, %s 表格, %s 字",
                 struct.total_paragraphs, struct.total_tables, struct.total_words)

        # 2. 构建结构化描述
        doc_description = _build_document_description(struct)

        # 3. 调用 LLM 进行审核
        messages = [
            {"role": "system", "content": STRUCTURED_AUDIT_SYSTEM},
            {"role": "user", "content": doc_description},
        ]

        _LOG.info("开始结构化视觉审核")
        # Use the configured visual audit model, then one fallback on empty output.
        client = config.openai_client_for_chat()
        model = (model_override or "").strip() or config.VISUAL_AUDIT_MODEL

        resp = chat_completions_create(
            client,
            model=model,
            messages=messages,
            temperature=0.2,
            stream=False,
            max_tokens=2048,
        )

        ch0 = resp.choices[0] if resp.choices else None
        raw = (ch0.message.content if ch0 and ch0.message else "") or ""
        if not raw.strip() and not strict_model_selection:
            fallback_model = (getattr(config, "VISUAL_AUDIT_FALLBACK_MODEL", "") or "").strip()
            if fallback_model and fallback_model != model:
                _LOG.warning("visual_audit_empty_primary model=%s fallback=%s", model, fallback_model)
                resp = chat_completions_create(
                    client,
                    model=fallback_model,
                    messages=messages,
                    temperature=0.2,
                    stream=False,
                    max_tokens=2048,
                )
                ch0 = resp.choices[0] if resp.choices else None
                raw = (ch0.message.content if ch0 and ch0.message else "") or ""

        # 4. 解析结果
        return _parse_visual_audit_response(raw)

    except Exception as e:
        _LOG.error("视觉审核异常: %s", e)
        return VisualAuditResult(
            score=0,
            issues=[f"视觉审核异常: {e}"],
            parse_ok=False,
        )


def _build_document_description(struct: DocumentStructure) -> str:
    """构建文档结构化描述。"""
    parts = [
        "【Word 文档结构化信息】",
        "",
        f"文档概况:",
        f"- 总段落数: {struct.total_paragraphs}",
        f"- 总表格数: {struct.total_tables}",
        f"- 总字数: 约 {struct.total_words} 字",
        f"- 有水印: {'是' if struct.has_watermark else '否'}",
        "",
    ]

    if struct.header_content:
        parts.append("【页眉内容】")
        for i, header in enumerate(struct.header_content[:2]):
            parts.append(f"页眉 {i+1}: {header[:200]}")
        parts.append("")

    if struct.footer_content:
        parts.append("【页脚内容】")
        for i, footer in enumerate(struct.footer_content[:2]):
            parts.append(f"页脚 {i+1}: {footer[:200]}")
        parts.append("")

    if struct.cover_elements:
        parts.append("【封面元素】（应保护，不应修改）")
        for elem in struct.cover_elements:
            parts.append(f"- {elem}")
        parts.append("")

    if struct.rating_tables:
        parts.append("【评分表/评价表】（应保护，不应填充或修改）")
        for table in struct.rating_tables:
            parts.append(f"- {table}")
        parts.append("")

    if struct.sample_paragraphs:
        parts.append("【内容抽样】")
        for i, para in enumerate(struct.sample_paragraphs[:5]):
            parts.append(f"段落 {i+1}: {para[:150]}")
        parts.append("")

    if struct.table_structures:
        parts.append("【表格结构】")
        for i, table in enumerate(struct.table_structures[:3]):
            parts.append(f"表格 {i+1}: {table['rows']}行×{table['cols']}列")
            parts.append(f"内容: {table['text'][:200]}")
        parts.append("")

    parts.append("【审核要求】")
    parts.append("1. 检查封面元素是否被意外修改（标题、日期、单位等）")
    parts.append("2. 检查评分表/评价表是否被意外填充")
    parts.append("3. 检查水印是否保留")
    parts.append("4. 检查内容充实度和格式规范性")
    parts.append("5. 检查整体排版是否合理")

    return "\n".join(parts)


def _parse_visual_audit_response(raw: str) -> VisualAuditResult:
    """解析视觉审核的 JSON 响应。"""
    # 去掉 Markdown 围栏
    s = raw.strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            if s.lstrip().startswith("json"):
                s = s.lstrip()[4:].lstrip()

    try:
        data = json.loads(s.strip())
    except json.JSONDecodeError:
        _LOG.warning("视觉审核 JSON 解析失败: %r", raw[:200])
        return VisualAuditResult(
            score=0,
            issues=["视觉审核结果 JSON 解析失败"],
            parse_ok=False,
        )

    # 提取分数
    score = int(data.get("score", 0))
    watermark_score = int(data.get("watermark_score", 0))
    format_score = int(data.get("format_score", 0))
    content_score = int(data.get("content_score", 0))
    table_score = int(data.get("table_score", 0))
    layout_score = int(data.get("layout_score", 0))

    # 提取问题和建议
    issues = data.get("issues") or []
    if not isinstance(issues, list):
        issues = [str(issues)]
    issues = [str(x) for x in issues if str(x).strip()]

    suggestions = data.get("suggestions") or []
    if not isinstance(suggestions, list):
        suggestions = [str(suggestions)]
    suggestions = [str(x) for x in suggestions if str(x).strip()]

    # 提取保护检测信息
    protected_elements = data.get("protected_elements") or []
    if not isinstance(protected_elements, list):
        protected_elements = [str(protected_elements)]
    protected_elements = [str(x) for x in protected_elements if str(x).strip()]

    cover_modified = bool(data.get("cover_modified", False))
    rating_table_modified = bool(data.get("rating_table_modified", False))

    _LOG.info(
        "视觉审核完成: 总分=%s 水印=%s 格式=%s 内容=%s 表格=%s 排版=%s 问题数=%s 封面修改=%s 评分表修改=%s",
        score, watermark_score, format_score, content_score, table_score, layout_score,
        len(issues), cover_modified, rating_table_modified,
    )

    return VisualAuditResult(
        score=score,
        watermark_score=watermark_score,
        format_score=format_score,
        content_score=content_score,
        table_score=table_score,
        layout_score=layout_score,
        issues=issues,
        suggestions=suggestions,
        parse_ok=True,
        protected_elements=protected_elements,
        cover_modified=cover_modified,
        rating_table_modified=rating_table_modified,
    )


def should_optimize(result: VisualAuditResult) -> bool:
    """判断是否需要优化。

    Returns:
        True 如果分数低于通过线或存在严重问题或保护元素被修改
    """
    # 保护元素被修改，必须优化
    if result.cover_modified:
        _LOG.warning("封面被修改，需要优化")
        return True
    if result.rating_table_modified:
        _LOG.warning("评分表被修改，需要优化")
        return True

    if result.score < config.VISUAL_AUDIT_PASS_SCORE:
        return True
    # 任何单项低于 12 分也需要优化
    scores = [
        result.watermark_score,
        result.format_score,
        result.content_score,
        result.table_score,
        result.layout_score,
    ]
    if any(s < 12 for s in scores):
        return True
    return False


def build_optimization_prompt(result: VisualAuditResult) -> str:
    """根据视觉审核结果构建优化提示词。

    Args:
        result: 视觉审核结果

    Returns:
        优化提示词
    """
    parts = [
        "【视觉审核反馈】",
        f"总分: {result.score}/100 (通过线: {config.VISUAL_AUDIT_PASS_SCORE})",
        f"水印完整性: {result.watermark_score}/20",
        f"格式正确性: {result.format_score}/20",
        f"内容充实度: {result.content_score}/20",
        f"表格规范性: {result.table_score}/20",
        f"排版美观度: {result.layout_score}/20",
    ]

    # 保护元素警告
    if result.cover_modified:
        parts.append("\n【严重警告】封面被意外修改！")
        parts.append("要求：保留封面原有内容（标题、日期、单位等），不要填充或修改封面区域。")

    if result.rating_table_modified:
        parts.append("\n【严重警告】评分表/评价表被意外修改！")
        parts.append("要求：保留评分表原有结构，不要填充评分区域，只填写正文内容。")

    if result.protected_elements:
        parts.append("\n【保护元素】")
        for elem in result.protected_elements:
            parts.append(f"- {elem}")

    if result.issues:
        parts.append("\n【发现的问题】")
        for issue in result.issues:
            parts.append(f"- {issue}")

    if result.suggestions:
        parts.append("\n【改进建议】")
        for suggestion in result.suggestions:
            parts.append(f"- {suggestion}")

    parts.append("\n【优化要求】")
    parts.append("1. 保留封面所有原有内容，不要修改")
    parts.append("2. 保留评分表/评价表结构，不要填充评分区域")
    parts.append("3. 保留页眉页脚中的水印")
    parts.append("4. 保留原有格式和排版")
    parts.append("5. 只填充正文段落和指定表格单元格")

    return "\n".join(parts)
