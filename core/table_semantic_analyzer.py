"""表格语义分析器：分类表格结构类型并标注各单元格填写意图。

解决「什么该写什么不该写」的核心问题：
- 封面表/评分表 → 整表 READ_ONLY（不应被 LLM 改写）
- 标签-值表 → col 0 LABEL，col 1 FILL（只填内容列）
- 创新点三列表 → row 0 LABEL，数据行 col 0 LABEL，cols 1-2 FILL
- 数据网表 → row 0 LABEL，数据行 FILL（空）/ LABEL（非空）
- 未知类型 → 回退到旧 cell_needs_fill() 逻辑

.. note::
   python-docx 1.x 的 ``_Cell._tc`` 对象身份在连续访问间不稳定
   （GC 导致 ``id()`` 轮换），因此统一使用物理 XML 单元格
   ``tr.findall(qn("w:tc"))`` 迭代，保证去重逻辑可靠。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from docx.oxml.ns import qn

from core.fill_intent import (
    COVER_KEYWORDS,
    FillIntent,
    INNOVATION_HEADERS_HINTS,
    LABEL_COLUMN_RATIO_THRESHOLD,
    RUBRIC_KEYWORDS,
    TableSemanticType,
)
from core.template_slots import cell_needs_fill

_LOG = logging.getLogger(__name__)

# 表头文本长度上限，超出视为非表头
_HEADER_TEXT_MAX_LEN = 20


@dataclass
class TableAnalysis:
    """表格语义分析结果，由 ``analyze_table`` 返回。

    Attributes:
        table_index: 表格在文档中的 0-based 索引。
        table_type: 表格整体结构类型。
        fill_intents: ``{(row, col): FillIntent}`` 映射，
            仅包含第一个物理单元格（合并格不重复标注）。
        chapter: 表格所在章节名称。
        n_rows: 逻辑行数。
        n_cols: 逻辑列数（row 0 的单元格数）。
    """

    table_index: int
    table_type: TableSemanticType
    fill_intents: dict[tuple[int, int], FillIntent] = field(default_factory=dict)
    chapter: str = ""
    n_rows: int = 0
    n_cols: int = 0


# ---------------------------------------------------------------------------
# 内部工具函数：直接操作 XML <w:tc>，避免 python-docx _Cell 身份不稳定
# ---------------------------------------------------------------------------

def _tc_text(tc: Any) -> str:
    """从 <w:tc> XML 元素直接提取纯文本，无需经过 _Cell 包装。"""
    try:
        parts = [t.text for t in tc.iter(qn("w:t")) if t.text]
        return " ".join(parts).strip()
    except Exception:
        return ""


def _tc_grid_span(tc: Any) -> int:
    """读取 <w:tc> 的 gridSpan 值（默认 1）。"""
    tcPr = tc.find(qn("w:tcPr"))
    if tcPr is None:
        return 1
    gs = tcPr.find(qn("w:gridSpan"))
    if gs is None:
        return 1
    val = gs.get(qn("w:val"))
    if val is None:
        return 1
    try:
        return max(1, int(val))
    except (ValueError, TypeError):
        return 1


def _tc_width(tc: Any) -> int:
    """读取 <w:tc> 的 w:tcW 宽度值（dxa / pct），缺失或 auto 返回 0。"""
    tcPr = tc.find(qn("w:tcPr"))
    if tcPr is None:
        return 0
    tcW = tcPr.find(qn("w:tcW"))
    if tcW is None:
        return 0
    w_attr = tcW.get(qn("w:w"))
    if not w_attr or w_attr == "auto":
        return 0
    try:
        return int(w_attr)
    except (ValueError, TypeError):
        return 0


def _tc_is_bold(tc: Any) -> bool:
    """检查 <w:tc> 首 run 是否为粗体。"""
    try:
        for rPr in tc.iter(qn("w:rPr")):
            b = rPr.find(qn("w:b"))
            if b is not None:
                val = b.get(qn("w:val"))
                # w:b 存在且 val 不是 "0"/"false" 视为粗体
                if val is None or val not in ("0", "false"):
                    return True
    except Exception:
        pass
    return False


def _is_empty(text: str) -> bool:
    return not (text or "").strip()


def _is_short(text: str, threshold: int = _HEADER_TEXT_MAX_LEN) -> bool:
    return len(text.strip()) <= threshold


def _physical_tcs(table_row: Any) -> list[Any]:
    """获取行元素的物理 <w:tc> 子元素列表。"""
    return table_row._tr.findall(qn("w:tc"))


def _row0_physical_widths(table: Any) -> list[int]:
    """读取第一行物理单元格宽度（``w:tcW/@w:w``）。"""
    if not table.rows:
        return []
    return [_tc_width(tc) for tc in _physical_tcs(table.rows[0])]


def _log_col_count(table: Any) -> int:
    """逻辑列数（row 0 cells 数）。"""
    if not table.rows:
        return 0
    try:
        return len(table.rows[0].cells)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# classify_table_type
# ---------------------------------------------------------------------------

def classify_table_type(table: Any) -> TableSemanticType:
    """按首次匹配规则分类表格结构类型。

    优先级：COVER_INFO → RUBRIC_SCORING → INNOVATION_TRIPLE
    → LABEL_VALUE_PAIR → DATA_GRID → UNKNOWN。

    使用物理 XML 单元格（``tr.findall("w:tc")``）提取文本，
    避免 python-docx ``_Cell`` 包装的 ``id()`` 不稳定问题。
    """
    if not table.rows:
        return TableSemanticType.UNKNOWN

    row_count = len(table.rows)
    col_count = _log_col_count(table)

    # 用物理 XML 单元格提取全部文本（对 COVER_INFO 检测使用）
    all_text_parts: list[str] = []
    try:
        for row in table.rows:
            for tc in _physical_tcs(row):
                t = _tc_text(tc)
                if t:
                    all_text_parts.append(t)
    except Exception:
        return TableSemanticType.UNKNOWN

    all_text = " ".join(all_text_parts)

    # 1. COVER_INFO: ≥2 cover keywords present
    cover_hits = sum(1 for kw in COVER_KEYWORDS if kw in all_text)
    if cover_hits >= 2:
        _LOG.debug("classify: COVER_INFO (hits=%d)", cover_hits)
        return TableSemanticType.COVER_INFO

    # 2. RUBRIC_SCORING: row 0 col 0 contains rubric keyword AND ≤ 5 rows total
    row0_first_tc = _physical_tcs(table.rows[0])[0] if _physical_tcs(table.rows[0]) else None
    row0_cell0_text = _tc_text(row0_first_tc) if row0_first_tc is not None else ""
    if row0_cell0_text and any(kw in row0_cell0_text for kw in RUBRIC_KEYWORDS) and row_count <= 5:
        _LOG.debug("classify: RUBRIC_SCORING (header=%r rows=%d)", row0_cell0_text, row_count)
        return TableSemanticType.RUBRIC_SCORING

    # 3. INNOVATION_TRIPLE: exactly 3 cols AND ≥2 of row0 headers match innovation hints
    if col_count == 3 and table.rows:
        row0_tcs = _physical_tcs(table.rows[0])
        row0_texts = [_tc_text(tc) for tc in row0_tcs]
        matched_headers = sum(
            1 for text in row0_texts
            if text and any(hint in text for hint in INNOVATION_HEADERS_HINTS)
        )
        if matched_headers >= 2:
            _LOG.debug("classify: INNOVATION_TRIPLE (matched=%d/3)", matched_headers)
            return TableSemanticType.INNOVATION_TRIPLE

    # 4. LABEL_VALUE_PAIR: exactly 2 cols AND col 0 width < threshold of total
    if col_count == 2 and table.rows:
        widths = _row0_physical_widths(table)
        if len(widths) >= 2:
            total_w = sum(widths)
            col0_w = widths[0]
            if total_w > 0 and (col0_w / total_w) < LABEL_COLUMN_RATIO_THRESHOLD:
                _LOG.debug(
                    "classify: LABEL_VALUE_PAIR (col0=%.1f%% total=%d)",
                    col0_w / total_w * 100,
                    total_w,
                )
                return TableSemanticType.LABEL_VALUE_PAIR

    # 5. DATA_GRID: ≥3 cols, row 0 is header (bold or short text), majority data rows empty
    if col_count >= 3 and row_count >= 2:
        row0_tcs = _physical_tcs(table.rows[0])
        row0_is_header = all(
            _tc_is_bold(tc) or _is_short(_tc_text(tc))
            for tc in row0_tcs
        )
        if row0_is_header:
            data_rows = row_count - 1
            empty_rows = sum(
                1
                for r in range(1, row_count)
                if all(_is_empty(_tc_text(tc)) for tc in _physical_tcs(table.rows[r]))
            )
            if data_rows > 0 and (empty_rows / data_rows) >= 0.5:
                _LOG.debug(
                    "classify: DATA_GRID (empty=%d/%d data rows)",
                    empty_rows,
                    data_rows,
                )
                return TableSemanticType.DATA_GRID

    _LOG.debug("classify: UNKNOWN")
    return TableSemanticType.UNKNOWN


# ---------------------------------------------------------------------------
# annotate_fill_intents
# ---------------------------------------------------------------------------

def annotate_fill_intents(
    table: Any,
    table_type: TableSemanticType,
) -> dict[tuple[int, int], FillIntent]:
    """标注每个单元格的填写意图。

    使用物理 XML 单元格（``tr.findall("w:tc")``）迭代，
    通过 ``gridSpan`` 推算逻辑列号；合并格只标注第一个物理单元格。
    """
    if not table.rows:
        return {}

    intents: dict[tuple[int, int], FillIntent] = {}
    row_count = len(table.rows)

    for r in range(row_count):
        logical_col = 0
        for tc in _physical_tcs(table.rows[r]):
            raw = _tc_text(tc)
            is_fillable = _is_empty(raw) or cell_needs_fill(raw)
            c = logical_col

            if table_type.is_read_only:
                # COVER_INFO / RUBRIC_SCORING → ALL = READ_ONLY
                intents[(r, c)] = FillIntent.READ_ONLY

            elif table_type == TableSemanticType.LABEL_VALUE_PAIR:
                if c == 0:
                    intents[(r, c)] = FillIntent.LABEL
                else:
                    intents[(r, c)] = FillIntent.FILL if is_fillable else FillIntent.LABEL

            elif table_type == TableSemanticType.INNOVATION_TRIPLE:
                if r == 0:
                    intents[(r, c)] = FillIntent.LABEL
                elif c == 0:
                    intents[(r, c)] = FillIntent.LABEL
                else:
                    intents[(r, c)] = FillIntent.FILL if is_fillable else FillIntent.LABEL

            elif table_type == TableSemanticType.DATA_GRID:
                if r == 0:
                    intents[(r, c)] = FillIntent.LABEL
                else:
                    intents[(r, c)] = FillIntent.FILL if is_fillable else FillIntent.LABEL

            else:
                # UNKNOWN → cell_needs_fill() fallback
                intents[(r, c)] = FillIntent.FILL if is_fillable else FillIntent.LABEL

            # Advance logical column by gridSpan (skip continuation cols)
            logical_col += _tc_grid_span(tc)

    _LOG.debug(
        "annotate_fill_intents: type=%s n_intents=%d",
        table_type.value,
        len(intents),
    )
    return intents


# ---------------------------------------------------------------------------
# analyze_table
# ---------------------------------------------------------------------------

def analyze_table(
    table: Any,
    table_index: int,
    chapter: str,
) -> TableAnalysis:
    """分析表格语义，返回完整 TableAnalysis。

    Args:
        table: ``python-docx`` Table 对象。
        table_index: 表格在文档中的 0-based 索引。
        chapter: 表格所在章节名称。

    Returns:
        ``TableAnalysis`` 包含类型、意图标注、行列数等。
    """
    table_type = classify_table_type(table)
    fill_intents = annotate_fill_intents(table, table_type)
    n_rows = len(table.rows) if table.rows else 0
    n_cols = _log_col_count(table)

    analysis = TableAnalysis(
        table_index=table_index,
        table_type=table_type,
        fill_intents=fill_intents,
        chapter=chapter,
        n_rows=n_rows,
        n_cols=n_cols,
    )
    _LOG.info(
        "analyze_table idx=%d type=%s rows=%d cols=%d intents=%d chapter=%r",
        table_index,
        table_type.value,
        n_rows,
        n_cols,
        len(fill_intents),
        chapter,
    )
    return analysis
