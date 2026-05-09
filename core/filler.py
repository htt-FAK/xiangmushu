from typing import List
from docx import Document
from core.template_analyzer import FillTask
import re


class WordFiller:
    """将生成内容回填到 Word 模板。"""

    # 常见的占位符模式
    _PLACEHOLDER_PATTERNS = [
        re.compile(r"请填写"),
        re.compile(r"（\s*）"),
        re.compile(r"\(\s*\)"),
        re.compile(r"_{3,}"),
        re.compile(r"待填写"),
        re.compile(r"待补充"),
        re.compile(r"此处填写"),
    ]

    def fill_template(
        self,
        template_path: str,
        tasks: List[FillTask],
        contents: List[str],
        output_path: str,
    ):
        doc = Document(template_path)

        # 逐个任务回填
        for task, content in zip(tasks, contents):
            if task.task_type == "table_cell":
                self._fill_table_cell(doc, task, content)
            else:
                self._fill_paragraph(doc, task, content)

        doc.save(output_path)

    def _fill_paragraph(self, doc: Document, task: FillTask, content: str):
        """段落填充：找到章节标题后第一个含占位符的段落，替换。"""
        hint = task.location_hint
        para_text_hint = hint.get("paragraph_text", "")

        found_chapter = False
        for para in doc.paragraphs:
            text = para.text.strip()

            # 定位到目标章节
            if task.target_chapter and task.target_chapter in text:
                found_chapter = True
                continue

            if not found_chapter and task.target_chapter:
                continue

            # 在目标章节下找占位符段落
            is_placeholder = False
            for pat in self._PLACEHOLDER_PATTERNS:
                if pat.search(text):
                    is_placeholder = True
                    break

            # 或者匹配 hint 中的关键词
            if para_text_hint and para_text_hint in text:
                is_placeholder = True

            if is_placeholder or (not text and found_chapter):
                # 替换内容，保留第一个 run 的格式
                if para.runs:
                    # 清除所有 run
                    for run in para.runs:
                        run.text = ""
                    para.runs[0].text = content
                else:
                    para.text = content
                return

    def _fill_table_cell(self, doc: Document, task: FillTask, content: str):
        """表格填充：根据 location_hint 定位单元格。"""
        hint = task.location_hint
        table_idx = hint.get("table_index", 0)
        row_idx = hint.get("row", 0)
        col_idx = hint.get("col", 0)

        if table_idx < len(doc.tables):
            table = doc.tables[table_idx]
            if row_idx < len(table.rows):
                row = table.rows[row_idx]
                if col_idx < len(row.cells):
                    cell = row.cells[col_idx]
                    # 保留格式，替换文本
                    for para in cell.paragraphs:
                        for pat in self._PLACEHOLDER_PATTERNS:
                            if pat.search(para.text):
                                if para.runs:
                                    for run in para.runs:
                                        run.text = ""
                                    para.runs[0].text = content
                                else:
                                    para.text = content
                                return
                        # 如果没有占位符但单元格为空
                        if not para.text.strip():
                            if para.runs:
                                para.runs[0].text = content
                            else:
                                para.text = content
                            return
