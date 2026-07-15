"""多列表格扫槽：处理纵向合并单元格，并为创新点三列表补全任务。"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any, Dict, List, Tuple

from core.fill_intent import FillIntent
from core.fill_task import FillTask
from core.table_semantic_analyzer import analyze_table
from core.template_slots import cell_needs_fill

_LOG = logging.getLogger(__name__)

ANCHOR_PATTERN = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")


def _header_cells(table: Any) -> List[str]:
    if not table.rows:
        return []
    return [(c.text or "").strip() for c in table.rows[0].cells]


def _cell_plain(cell) -> str:
    return (cell.text or "").strip().replace("\n", " ")


def first_row_for_cell_tc(table: Any, row: int, col: int) -> int:
    """纵向合并时返回该物理单元格首次出现的行号。"""
    if row >= len(table.rows) or col >= len(table.rows[row].cells):
        return row
    tc_id = id(table.rows[row].cells[col]._tc)
    for ri in range(len(table.rows)):
        if col >= len(table.rows[ri].cells):
            continue
        if id(table.rows[ri].cells[col]._tc) == tc_id:
            return ri
    return row


def is_innovation_style_table(table: Any) -> bool:
    if not table.rows:
        return False
    headers = [_cell_plain(c) for c in table.rows[0].cells]
    if len(headers) < 3:
        return False
    return any("创新" in h for h in headers)


def word_limit_for_column_header(header: str) -> int:
    h = header or ""
    if "创新点" in h:
        return 55
    if "实现" in h:
        return 75
    if "应用" in h or "价值" in h or "证据" in h:
        return 75
    return 80


def max_chars_for_column_header(header: str) -> int:
    wl = word_limit_for_column_header(header)
    return min(100, max(40, int(wl * 1.4)))


def scan_table_fill_tasks(
    table: Any,
    table_index: int,
    chapter: str,
) -> List[FillTask]:
    """
    扫描单表待填格；按物理单元格去重（纵向合并只占一行一列锚点）。

    task 4.5 集成：通过 analyze_table 获取 fill_intent，
    仅对意图为 FILL 的单元格生成 FillTask，跳过 LABEL / READ_ONLY。
    """
    if not table.rows:
        return []

    # Semantic analysis (task 4.5)
    analysis = analyze_table(table, table_index, chapter)
    fill_intents = analysis.fill_intents

    headers = _header_cells(table)
    innovation = is_innovation_style_table(table)
    physical: Dict[Tuple[int, int, int], FillTask] = {}

    for r, row in enumerate(table.rows):
        row_seen: set[int] = set()
        for c, cell in enumerate(row.cells):
            tc_id = id(cell._tc)
            if tc_id in row_seen:
                continue
            row_seen.add(tc_id)

            # Skip cells that are not FILL per semantic analysis (task 4.5)
            cell_intent = fill_intents.get((r, c), FillIntent.LABEL)
            if cell_intent != FillIntent.FILL:
                continue

            raw = cell.text or ""
            if ANCHOR_PATTERN.search(raw):
                continue
            # Keep cell_needs_fill as secondary guard
            if not cell_needs_fill(raw):
                continue
            if r == 0 and c < len(headers):
                hdr = headers[c]
                if hdr and raw.strip() == hdr.strip() and not cell_needs_fill(hdr):
                    continue

            anchor_r = first_row_for_cell_tc(table, r, c)
            key = (table_index, anchor_r, c)
            if key in physical:
                continue

            hdr = headers[c] if c < len(headers) else ""
            desc = f"{hdr}：{raw[:36]}".strip("：")[:80] if hdr else raw[:80]
            wl = word_limit_for_column_header(hdr) if innovation else 80

            hint: Dict[str, Any] = {
                "table_index": table_index,
                "row": anchor_r,
                "col": c,
                "fill_intent": cell_intent.value,
            }
            if innovation and anchor_r < r and c > 0:
                hint["merged_column"] = True
                hint["display_row"] = r

            physical[key] = FillTask(
                task_id=str(uuid.uuid4()),
                target_chapter=chapter,
                task_type="table_cell",
                description=desc,
                location_hint=hint,
                word_limit=wl,
            )

    return list(physical.values())


def merged_column_batch_note(table: Any, row: int, col: int) -> str:
    """纵向合并列在批量生成时的额外说明。"""
    anchor = first_row_for_cell_tc(table, row, col)
    if anchor == row:
        return ""
    n_data = sum(
        1
        for ri in range(1, len(table.rows))
        if ri < len(table.rows) and col < len(table.rows[ri].cells)
    )
    return (
        f"（本列在 Word 中纵向合并，锚点行={anchor}；"
        f"请用不超过 {n_data} 行、每行≤60字，分别对应各行「创新点N」写本列内容。）"
    )
