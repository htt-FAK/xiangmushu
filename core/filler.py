from typing import List
import re
from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches
from docx.text.paragraph import Paragraph
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
                self._fill_table_cell(doc, task, content)
            else:
                self._fill_paragraph(doc, task, content)

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
    def _replace_once_in_paragraph(para: Paragraph, anchor: str, content: str):
        if anchor not in para.text:
            return
        merged = para.text.replace(anchor, content, 1)
        WordFiller._set_paragraph_plain(para, merged)

    @staticmethod
    def _set_paragraph_plain(para: Paragraph, text: str):
        """合并为单段文本：多行用换行保留在单段内（Word 软换行）。"""
        for r in para.runs:
            r.text = ""
        if para.runs:
            para.runs[0].text = text
        else:
            para.add_run(text)

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
                self._set_paragraph_plain(para, content)
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

        # 使用官方 cell.text：清空内容时保留 w:tcPr（列宽等），避免手写清 run 破坏版式
        cell.text = content
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
