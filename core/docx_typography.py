"""Word 回填统一字体：宋体 + 正文小四、标题一二三级加粗规格。"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Optional

import config
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt
from docx.text.paragraph import Paragraph

# 半磅单位 w:sz（pt * 2）
SZ_BODY = 24  # 小四 12pt
SZ_H1 = 30  # 小三 15pt
SZ_H2 = 28  # 四号 14pt
SZ_H3 = 24  # 小四 12pt

_FONT_ASCII = "SimSun"
_FONT_EAST_ASIA = "宋体"


def heading_level_from_style(style_name: str) -> Optional[int]:
    if not style_name:
        return None
    s = style_name.strip()
    m = re.match(r"(?i)heading\s*(\d+)", s)
    if m:
        return int(m.group(1))
    m = re.match(r"标题\s*(\d+)", s)
    if m:
        return int(m.group(1))
    if s in ("Heading 1", "标题 1", "Heading1"):
        return 1
    if s in ("Heading 2", "标题 2", "Heading2"):
        return 2
    if s in ("Heading 3", "标题 3", "Heading3"):
        return 3
    return None


def _make_rPr(sz_half: int, *, bold: bool = False) -> OxmlElement:
    rpr = OxmlElement("w:rPr")
    rfonts = OxmlElement("w:rFonts")
    rfonts.set(qn("w:ascii"), _FONT_ASCII)
    rfonts.set(qn("w:hAnsi"), _FONT_ASCII)
    rfonts.set(qn("w:eastAsia"), _FONT_EAST_ASIA)
    rpr.append(rfonts)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(sz_half))
    rpr.append(sz)
    sz_cs = OxmlElement("w:szCs")
    sz_cs.set(qn("w:val"), str(sz_half))
    rpr.append(sz_cs)
    if bold:
        b = OxmlElement("w:b")
        rpr.append(b)
        b_cs = OxmlElement("w:bCs")
        rpr.append(b_cs)
    return rpr


def build_rPr_for_paragraph(para: Paragraph) -> OxmlElement:
    """按段落样式返回统一 rPr（正文/表格默认小四宋体）。"""
    style_name = para.style.name if para.style else ""
    lvl = heading_level_from_style(style_name or "")
    if lvl is None:
        t = (para.text or "").strip()
        if re.match(r"^摘\s*要\s*$", t):
            lvl = 1
    if lvl == 1:
        return _make_rPr(SZ_H1, bold=True)
    if lvl == 2:
        return _make_rPr(SZ_H2, bold=True)
    if lvl == 3:
        return _make_rPr(SZ_H3, bold=True)
    return _make_rPr(SZ_BODY, bold=False)


def build_body_rPr() -> OxmlElement:
    return deepcopy(_make_rPr(SZ_BODY, bold=False))


def apply_rPr_to_run(run, rpr: OxmlElement) -> None:
    clone = deepcopy(rpr)
    el = run._r
    if el.rPr is not None:
        el.remove(el.rPr)
    el.insert(0, clone)


def apply_typography_to_paragraph(para: Paragraph) -> None:
    rpr = build_rPr_for_paragraph(para)
    for run in para.runs:
        apply_rPr_to_run(run, rpr)


def apply_document_typography(doc: Document) -> None:
    """全文档段落与表格单元格 run 统一宋体字号。"""
    for para in doc.paragraphs:
        if not para.runs and not (para.text or "").strip():
            continue
        apply_typography_to_paragraph(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    if not para.runs and not (para.text or "").strip():
                        continue
                    apply_typography_to_paragraph(para)
    apply_body_first_line_indent(doc)


def apply_body_first_line_indent(doc: Document) -> None:
    """正文段落首行缩进（不处理标题行、摘要标题、表格内段落）。"""
    pt_val = float(getattr(config, "BODY_FIRST_LINE_INDENT_PT", 0) or 0)
    if pt_val <= 0:
        return
    for para in doc.paragraphs:
        style_name = para.style.name if para.style else ""
        if heading_level_from_style(style_name or "") is not None:
            continue
        t = (para.text or "").strip()
        if re.match(r"^摘\s*要\s*$", t):
            continue
        if not t:
            continue
        ex = para.paragraph_format.first_line_indent
        if ex is not None:
            try:
                if ex.pt and float(ex.pt) > 0.01:
                    continue
            except (TypeError, ValueError, AttributeError):
                pass
        para.paragraph_format.first_line_indent = Pt(pt_val)
