from typing import Any, Dict, List, Optional, Tuple
import re
from copy import deepcopy

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph

import config
from core.fill_task import FillTask


class WordFiller:
    """将生成内容回填到 Word：支持 {{锚点}} 精确替换 + 传统占位符。"""

    _PLACEHOLDER_PATTERNS = [
        re.compile(r"请填写"),
        re.compile(r"（\s*）"),
        re.compile(r"\(\s*\)"),
        re.compile(r"_{3,}"),
        re.compile(r"待填写"),
        re.compile(r"待补充"),
        re.compile(r"此处填写"),
    ]

    @staticmethod
    def strip_markdown_light(text: str) -> str:
        if not text:
            return ""
        s = text.replace("\r\n", "\n")
        s = re.sub(r"^#{1,6}\s*", "", s, flags=re.MULTILINE)
        s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)
        s = re.sub(r"\*([^*]+)\*", r"\1", s)
        s = re.sub(r"^\s*[-*+]\s+", "", s, flags=re.MULTILINE)
        s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
        return s.strip()

    @staticmethod
    def clean_table_answer(
        text: str,
        word_limit: int = 120,
        max_chars: Optional[int] = None,
    ) -> str:
        """对表格单元格答案做深度清洗：去前缀、占位/下划线噪声、换行压平、超长截断。"""
        if not text:
            return ""
        s = text.strip()

        _TABLE_PREFIXES = [
            r"^(答案|答|填写内容|该单元格应填写|该格填写|应填写|内容)：?\s*",
            r"^(根据参考资料[，,]?|根据上述资料[，,]?|根据检索片段[，,]?)",
            r"^(综上所述[，,]?|综合来看[，,]?)",
            r"^(以下是|如下|答：)\s*",
        ]
        for pattern in _TABLE_PREFIXES:
            s = re.sub(pattern, "", s, flags=re.IGNORECASE).strip()

        # 「资料2：____」类骨架行
        s = re.sub(r"资料\s*\d+\s*[：:]\s*_+", "", s)
        s = re.sub(r"_{4,}", "", s)
        # 换行压成空格，避免单元格内堆叠
        s = re.sub(r"[\r\n]+", " ", s)
        s = re.sub(r"\s{2,}", " ", s).strip()

        cap = max_chars if max_chars is not None else max(20, int(word_limit * 1.5))
        if (word_limit or 120) <= 45:
            cap = min(cap, 60)
        if len(s) > cap:
            s = s[:cap].rstrip("，。,. ")
        return s

    def fill_template(
        self,
        template_path: str,
        tasks: List[FillTask],
        contents: List[str],
        output_path: str,
    ):
        doc = Document(template_path)

        for task, raw in zip(tasks, contents):
            content = self.strip_markdown_light(raw)
            anchor = task.location_hint.get("anchor")
            if anchor:
                self._replace_anchor_everywhere(doc, anchor, content)
                continue
            if task.task_type == "table_cell":
                wl = int(task.word_limit or 120)
                tight = min(60, max(25, wl * 2)) if wl <= 45 else None
                content = self.clean_table_answer(content, wl, max_chars=tight)
                self._fill_table_cell(doc, task, content)
            else:
                self._fill_paragraph(doc, task, content)

        if getattr(config, "ADJUST_TABLE_READABILITY", True):
            for table in doc.tables:
                self._ensure_table_readability(table)

        doc.save(output_path)

    def _replace_anchor_everywhere(self, doc: Document, anchor: str, content: str):
        for para in doc.paragraphs:
            self._replace_once_in_paragraph(para, anchor, content)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        self._replace_once_in_paragraph(para, anchor, content)

    @staticmethod
    def _sample_rPr_from_paragraph(para: Paragraph):
        """取段落中第一个带样式的 rPr（优先非空 run），用于回填时克隆。"""
        for r in para.runs:
            if (r.text or "").strip() and r._r.rPr is not None:
                return deepcopy(r._r.rPr)
        for r in para.runs:
            if r._r.rPr is not None:
                return deepcopy(r._r.rPr)
        return None

    @staticmethod
    def _sample_rPr_from_cell(cell) -> Optional[object]:
        for p in cell.paragraphs:
            rp = WordFiller._sample_rPr_from_paragraph(p)
            if rp is not None:
                return rp
        return None

    @staticmethod
    def _clear_cell_body_keep_tcPr(cell) -> None:
        tc = cell._tc
        for child in list(tc):
            if child.tag == qn("w:tcPr"):
                continue
            tc.remove(child)

    @staticmethod
    def _apply_rPr_to_run(run, rpr) -> None:
        if rpr is None:
            return
        clone = deepcopy(rpr)
        el = run._r
        if el.rPr is not None:
            el.remove(el.rPr)
        el.insert(0, clone)

    @staticmethod
    def _set_paragraph_text_keep_style(para: Paragraph, text: str) -> None:
        """写入整段文本并尽量保留原字号/字体（基于首段样式样本）。"""
        rpr = WordFiller._sample_rPr_from_paragraph(para)
        for r in para.runs:
            r.text = ""
        if para.runs:
            run = para.runs[0]
            run.text = text
            WordFiller._apply_rPr_to_run(run, rpr)
        else:
            nr = para.add_run(text)
            WordFiller._apply_rPr_to_run(nr, rpr)

    @staticmethod
    def _set_cell_text_keep_style(cell, text: str) -> None:
        """清空单元格正文但保留 tcPr，写入单段并克隆原单元格样式。"""
        rpr = WordFiller._sample_rPr_from_cell(cell)
        WordFiller._clear_cell_body_keep_tcPr(cell)
        p = cell.add_paragraph()
        run = p.add_run(text or "")
        WordFiller._apply_rPr_to_run(run, rpr)

    @staticmethod
    def _replace_once_in_paragraph(para: Paragraph, anchor: str, content: str):
        """仅替换段落中首次出现的锚点字面量（语义同 placeholder_only，走样式保留写回）。"""
        if anchor not in para.text:
            return
        merged = para.text.replace(anchor, content, 1)
        WordFiller._set_paragraph_text_keep_style(para, merged)

    @staticmethod
    def _set_paragraph_plain(para: Paragraph, text: str):
        """兼容旧名：与 keep_style 行为一致。"""
        WordFiller._set_paragraph_text_keep_style(para, text)

    @staticmethod
    def _first_placeholder_span(
        text: str, anchor: Optional[str] = None
    ) -> Optional[Tuple[int, int]]:
        """返回第一个待替换占位在 text 中的 (start, end)；无则 None。

        顺序：先按 _PLACEHOLDER_PATTERNS 列表中**首个能匹配**的模式；若 location_hint
        提供 anchor 且该字面量出现在 text 中，则使用该子串区间（与「仅换锚点」语义一致）。
        """
        for pat in WordFiller._PLACEHOLDER_PATTERNS:
            m = pat.search(text)
            if m:
                return (m.start(), m.end())
        if anchor:
            a = str(anchor).strip()
            if a and a in text:
                i = text.index(a)
                return (i, i + len(a))
        return None

    @staticmethod
    def _fill_paragraph_placeholder_only(
        para: Paragraph, content: str, hint: Dict[str, Any]
    ) -> bool:
        """同段内只替换第一个占位，保留前后说明。成功返回 True，无占位返回 False。"""
        full = para.text or ""
        anchor = hint.get("anchor")
        anchor_s = str(anchor).strip() if anchor else None
        span = WordFiller._first_placeholder_span(full, anchor=anchor_s or None)
        if span is None:
            return False
        start, end = span
        new_text = full[:start] + (content or "") + full[end:]
        WordFiller._set_paragraph_text_keep_style(para, new_text)
        return True

    def _fill_paragraph(self, doc: Document, task: FillTask, content: str):
        hint = task.location_hint
        para_text_hint = hint.get("paragraph_text", "")

        found_chapter = False
        for para in doc.paragraphs:
            text = para.text.strip()

            if task.target_chapter and task.target_chapter in text:
                found_chapter = True
                continue

            if not found_chapter and task.target_chapter:
                continue

            is_placeholder = False
            for pat in self._PLACEHOLDER_PATTERNS:
                if pat.search(text):
                    is_placeholder = True
                    break

            if para_text_hint and para_text_hint in text:
                is_placeholder = True

            if is_placeholder or (not text and found_chapter):
                mode = (hint.get("replace_mode") or "full").strip().lower()
                if mode == "placeholder_only":
                    if not WordFiller._fill_paragraph_placeholder_only(
                        para, content, hint
                    ):
                        self._set_paragraph_text_keep_style(para, content)
                else:
                    self._set_paragraph_text_keep_style(para, content)
                return

    def _fill_table_cell(self, doc: Document, task: FillTask, content: str):
        hint = task.location_hint
        table_idx = hint.get("table_index", 0)
        row_idx = hint.get("row", 0)
        col_idx = hint.get("col", 0)

        if table_idx >= len(doc.tables):
            return
        table = doc.tables[table_idx]
        if row_idx >= len(table.rows):
            return
        row = table.rows[row_idx]
        if col_idx >= len(row.cells):
            return
        cell = row.cells[col_idx]

        self._set_cell_text_keep_style(cell, content)
        try:
            table.autofit = False
        except Exception:
            pass

    def _ensure_table_readability(self, table) -> None:
        """加宽列、固定布局、允许换行，减轻单元格文字被压成极窄条后截断观感。"""
        try:
            rows = table.rows
            if not rows:
                return
            ncols = len(rows[0].cells)
            if ncols <= 0:
                return
        except Exception:
            return

        try:
            table.autofit = False
        except Exception:
            pass

        tbl = table._tbl
        tblPr = tbl.tblPr
        if tblPr is None:
            tblPr = OxmlElement("w:tblPr")
            tbl.insert(0, tblPr)

        tl = tblPr.find(qn("w:tblLayout"))
        if tl is None:
            tl = OxmlElement("w:tblLayout")
            tl.set(qn("w:type"), "fixed")
            tblPr.append(tl)
        else:
            tl.set(qn("w:type"), "fixed")

        tblW = tblPr.find(qn("w:tblW"))
        if tblW is None:
            tblW = OxmlElement("w:tblW")
            tblPr.append(tblW)
        tblW.set(qn("w:w"), "5000")
        tblW.set(qn("w:type"), "pct")

        usable = 6.35
        try:
            col_w = Inches(usable / ncols)
        except Exception:
            return

        for row in rows:
            for cell in row.cells:
                try:
                    cell.width = col_w
                    cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP
                except Exception:
                    pass
                tc = cell._tc
                tcPr = tc.tcPr
                if tcPr is None:
                    tcPr = OxmlElement("w:tcPr")
                    tc.insert(0, tcPr)
                for nw in tcPr.findall(qn("w:noWrap")):
                    tcPr.remove(nw)
                for child in list(tcPr):
                    if child.tag == qn("w:vAlign"):
                        tcPr.remove(child)
                valign = OxmlElement("w:vAlign")
                valign.set(qn("w:val"), "top")
                tcPr.append(valign)
