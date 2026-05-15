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
from core.docx_typography import (
    apply_document_typography,
    apply_rPr_to_run,
    build_body_rPr,
    build_rPr_for_paragraph,
    heading_level_from_style,
)
from core.fill_task import FillTask


class WordFiller:
    """将生成内容回填到 Word：支持 {{锚点}} 精确替换 + 传统占位符。"""

    _PLACEHOLDER_PATTERNS = [
        re.compile(r"请在此填写"),
        re.compile(r"在此填写"),
        re.compile(r"请在此"),
        re.compile(r"填写.{0,8}正文"),
        re.compile(r"（\s*请[^）]{0,16}填写[^）]*）"),
        re.compile(r"请填写"),
        re.compile(r"（\s*）"),
        re.compile(r"\(\s*\)"),
        re.compile(r"_{3,}"),
        re.compile(r"待填写"),
        re.compile(r"待补充"),
        re.compile(r"此处填写"),
    ]

    _PURE_HINT_MAX_LEN = 40

    @staticmethod
    def _chapter_text_compact(chapter: str) -> str:
        return re.sub(r"\s+", "", chapter or "")

    @classmethod
    def _heading_matches_chapter(cls, target_chapter: str, para_text: str) -> bool:
        """章节标题与任务名比对（去空白），解决「摘要」任务无法命中「摘  要」标题的问题。"""
        ta = cls._chapter_text_compact(target_chapter)
        tb = cls._chapter_text_compact(para_text)
        if not ta or not tb:
            return False
        if ta in tb:
            return True
        if len(tb) >= 2 and tb in ta:
            return True
        return False

    @classmethod
    def _is_abstract_chapter(cls, target_chapter: str) -> bool:
        return "摘要" in cls._chapter_text_compact(target_chapter)

    @staticmethod
    def _strip_leading_abstract_label(content: str) -> str:
        """去掉模型在正文里重复的「摘要」标题行（已有独立 Heading 时避免正文段再以宋体小四重复）。"""
        if not content:
            return content
        s = content.strip()
        # 勿匹配「摘要成稿…」等正文词：仅当「摘…要」后接冒号、换行或多空格时再剥
        s = re.sub(r"^摘\s*要(\s*[:：]\s*|\s*\n+|\s{2,})", "", s)
        s = re.sub(r"^【\s*摘\s*要\s*】\s*", "", s)
        return s.strip()

    @classmethod
    def _looks_like_writing_rubric(cls, text: str) -> bool:
        """「撰写要求」+ 分条 bullet 类写作说明（无占位符），与说明段同级用于候选打分。"""
        t = (text or "").strip()
        head = t[:100]
        if len(t) < 18:
            return False
        # 已成稿的长摘要：勿当 rubric
        if len(t) > 400:
            looks_done = (
                "本项目" in t
                or "本系统" in t
                or "系统旨在" in t
                or "系统实现了" in t
            )
            has_rubric_header = bool(
                re.search(r"(撰写要求|写作说明|摘要要求)", head)
                or re.search(
                    r"用\s*\d+\s*[—\-~～]\s*\d+\s*字", head
                )
            )
            if looks_done and not has_rubric_header:
                return False
        if re.match(r"^\s*(撰写要求|写作说明|摘要要求)", t):
            return True
        bullet_marks = "•·●◦‣⁃"
        n_bullets = sum(t.count(c) for c in bullet_marks)
        n_bullets += len(re.findall(r"(?m)^\s*[-*+－—]\s+\S", t))
        if n_bullets >= 2 and len(t) < 900:
            rubric_kw = (
                "300",
                "500",
                "概述",
                "真实场景",
                "目标用户",
                "创新点",
                "不足",
                "核心能力",
                "工作流",
                "知识库",
                "演示",
                "插件",
                "数据库",
            )
            if sum(1 for k in rubric_kw if k in t) >= 2:
                return True
        return False

    @classmethod
    def _looks_like_template_guidance(cls, text: str) -> bool:
        """模板「说明……建议……」或「撰写要求」类填写指引（无占位符），与占位同级、优先于空段。"""
        t = (text or "").strip()
        if len(t) < 18 or len(t) > 1200:
            return False
        if cls._text_has_placeholder(t):
            return False
        if cls._is_pure_hint_line(t):
            return False
        if cls._looks_like_writing_rubric(t):
            return True
        starters = (
            "说明",
            "描述",
            "列出",
            "填写",
            "简述",
            "阐述",
            "介绍",
            "应从",
            "需说明",
            "请围绕",
            "围绕",
        )
        if not any(t.startswith(s) for s in starters):
            return False
        markers = (
            "建议",
            "避免",
            "至少",
            "不得",
            "模板",
            "示例",
            "字数",
            "几点",
            "层次",
            "展开",
            "格式",
        )
        return any(m in t for m in markers)

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

        s = re.sub(r"资料\s*\d+\s*[：:]\s*_+", "", s)
        s = re.sub(r"_{4,}", "", s)
        s = re.sub(r"[\r\n]+", " ", s)
        s = re.sub(r"\s{2,}", " ", s).strip()

        cap = max_chars if max_chars is not None else max(20, int(word_limit * 1.5))
        if (word_limit or 120) <= 45:
            cap = min(cap, 60)
        if len(s) > cap:
            s = s[:cap].rstrip("，。,. ")
        return s

    @classmethod
    def _text_has_placeholder(cls, text: str) -> bool:
        if not text:
            return False
        return any(p.search(text) for p in cls._PLACEHOLDER_PATTERNS)

    @classmethod
    def _is_pure_hint_line(cls, text: str) -> bool:
        """整段几乎全是填写指引（如「（请在此填写摘要正文）」），不含大段说明。"""
        t = (text or "").strip()
        if not t or len(t) > cls._PURE_HINT_MAX_LEN:
            return False
        if not cls._text_has_placeholder(t):
            return False
        span = cls._first_placeholder_span(t)
        if not span:
            return False
        start, end = span
        remainder = (t[:start] + t[end:]).strip()
        remainder_clean = re.sub(
            r"[（）()\s_。，,、：:【】《》\[\]「」]", "", remainder
        )
        remainder_clean = re.sub(r"(摘要|正文|此处|的)+", "", remainder_clean)
        return len(remainder_clean) <= 2

    @staticmethod
    def _para_heading_level(para: Paragraph) -> Optional[int]:
        if not para.style:
            return None
        return heading_level_from_style(para.style.name or "")

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
            if task.task_type == "paragraph" and self._is_abstract_chapter(
                task.target_chapter or ""
            ):
                content = self._strip_leading_abstract_label(content)
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

        self._sweep_residual_hint_paragraphs(doc)

        if getattr(config, "ADJUST_TABLE_READABILITY", True):
            for table in doc.tables:
                self._ensure_table_readability(table)

        if getattr(config, "APPLY_UNIFIED_TYPOGRAPHY", True):
            apply_document_typography(doc)

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
        for r in para.runs:
            if (r.text or "").strip() and r._r.rPr is not None:
                return deepcopy(r._r.rPr)
        for r in para.runs:
            if r._r.rPr is not None:
                return deepcopy(r._r.rPr)
        return None

    @staticmethod
    def _clear_cell_body_keep_tcPr(cell) -> None:
        tc = cell._tc
        for child in list(tc):
            if child.tag == qn("w:tcPr"):
                continue
            tc.remove(child)

    @staticmethod
    def _set_paragraph_text_keep_style(para: Paragraph, text: str) -> None:
        """写入整段文本并应用统一宋体规格（按段落样式分档）。"""
        rpr = build_rPr_for_paragraph(para)
        for r in para.runs:
            r.text = ""
        if para.runs:
            run = para.runs[0]
            run.text = text
            apply_rPr_to_run(run, rpr)
        else:
            nr = para.add_run(text)
            apply_rPr_to_run(nr, rpr)

    @staticmethod
    def _set_cell_text_keep_style(cell, text: str) -> None:
        """清空单元格正文但保留 tcPr，写入单段并应用正文宋体小四。"""
        WordFiller._clear_cell_body_keep_tcPr(cell)
        p = cell.add_paragraph()
        run = p.add_run(text or "")
        apply_rPr_to_run(run, build_body_rPr())

    @staticmethod
    def _replace_once_in_paragraph(para: Paragraph, anchor: str, content: str):
        if anchor not in para.text:
            return
        merged = para.text.replace(anchor, content, 1)
        WordFiller._set_paragraph_text_keep_style(para, merged)

    @staticmethod
    def _set_paragraph_plain(para: Paragraph, text: str):
        WordFiller._set_paragraph_text_keep_style(para, text)

    @staticmethod
    def _first_placeholder_span(
        text: str, anchor: Optional[str] = None
    ) -> Optional[Tuple[int, int]]:
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

    def _collect_chapter_scope(
        self, doc: Document, target_chapter: str
    ) -> Tuple[int, List[int]]:
        """返回 (章节标题段落下标, 本章内后续段落下标列表)。"""
        paras = doc.paragraphs
        start_idx = -1
        chapter_lvl: Optional[int] = 1

        for i, para in enumerate(paras):
            t = para.text.strip()
            if target_chapter and self._heading_matches_chapter(target_chapter, t):
                start_idx = i
                chapter_lvl = self._para_heading_level(para) or 1
                break

        if start_idx < 0:
            return -1, []

        scope: List[int] = []
        for j in range(start_idx + 1, len(paras)):
            para = paras[j]
            t = para.text.strip()
            lvl = self._para_heading_level(para)
            if lvl is not None and lvl <= (chapter_lvl or 1) and t:
                break
            scope.append(j)
        return start_idx, scope

    def _score_paragraph_candidate(
        self, para: Paragraph, para_text_hint: str
    ) -> int:
        text = para.text.strip()
        if para_text_hint and para_text_hint in (para.text or ""):
            return 3
        if self._text_has_placeholder(text):
            return 2
        if self._looks_like_template_guidance(text):
            return 2
        if not text:
            return 1
        return 0

    def _clear_pure_hint_paragraph(self, para: Paragraph) -> None:
        if self._is_pure_hint_line(para.text or ""):
            self._set_paragraph_text_keep_style(para, "")

    def _clear_adjacent_pure_hints(self, doc: Document, filled_idx: int) -> None:
        paras = doc.paragraphs
        for j in (filled_idx - 1, filled_idx + 1):
            if 0 <= j < len(paras):
                self._clear_pure_hint_paragraph(paras[j])

    def _sweep_residual_hint_paragraphs(self, doc: Document) -> None:
        """邻接清理未覆盖的独立提示行，回填结束后再扫一遍正文段落。"""
        for para in doc.paragraphs:
            self._clear_pure_hint_paragraph(para)

    def _write_paragraph_content(
        self, para: Paragraph, content: str, hint: Dict[str, Any]
    ) -> None:
        text = para.text or ""
        mode = (hint.get("replace_mode") or "").strip().lower()

        if self._is_pure_hint_line(text):
            self._set_paragraph_text_keep_style(para, content)
            return

        if mode == "placeholder_only":
            if not self._fill_paragraph_placeholder_only(para, content, hint):
                self._set_paragraph_text_keep_style(para, content)
            return

        # 混排说明+占位：无显式 full 时先尝试只换占位
        if self._text_has_placeholder(text) and len(text) > self._PURE_HINT_MAX_LEN:
            if "说明" in text or len(text) > 60:
                if self._fill_paragraph_placeholder_only(para, content, hint):
                    return

        self._set_paragraph_text_keep_style(para, content)

    def _fill_paragraph(self, doc: Document, task: FillTask, content: str):
        hint = task.location_hint or {}
        para_text_hint = (hint.get("paragraph_text") or "").strip()
        paras = doc.paragraphs

        if not task.target_chapter:
            # 无章节：按原逻辑找第一个占位/空段
            for para in paras:
                text = para.text.strip()
                if self._text_has_placeholder(text) or (
                    para_text_hint and para_text_hint in (para.text or "")
                ):
                    self._write_paragraph_content(para, content, hint)
                    return
                if not text:
                    self._write_paragraph_content(para, content, hint)
                    return
            return

        _start, scope = self._collect_chapter_scope(doc, task.target_chapter)
        if not scope:
            return

        best_idx = -1
        best_score = 0
        for idx in scope:
            sc = self._score_paragraph_candidate(paras[idx], para_text_hint)
            if sc > best_score:
                best_score = sc
                best_idx = idx

        if best_idx < 0 or best_score == 0:
            return

        target_para = paras[best_idx]
        self._write_paragraph_content(target_para, content, hint)

        if best_score <= 2:
            self._clear_adjacent_pure_hints(doc, best_idx)

    def _fill_table_cell(self, doc: Document, task: FillTask, content: str):
        hint = task.location_hint or {}
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

        mode = (hint.get("replace_mode") or "").strip().lower()
        cell_text = cell.text or ""
        if mode == "placeholder_only" and self._text_has_placeholder(cell_text):
            span = self._first_placeholder_span(cell_text)
            if span:
                start, end = span
                new_text = cell_text[:start] + content + cell_text[end:]
                self._set_cell_text_keep_style(cell, new_text)
                try:
                    table.autofit = False
                except Exception:
                    pass
                return

        self._set_cell_text_keep_style(cell, content)
        try:
            table.autofit = False
        except Exception:
            pass

    def _ensure_table_readability(self, table) -> None:
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
