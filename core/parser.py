from dataclasses import dataclass, field
from typing import List
from docx import Document
import re


@dataclass
class Section:
    level: int
    title: str
    content: str = ""
    tables: List[List[List[str]]] = field(default_factory=list)


@dataclass
class ParsedDocument:
    filename: str
    sections: List[Section] = field(default_factory=list)
    raw_tables: List[List[List[str]]] = field(default_factory=list)


class DocumentParser:
    """解析 Word 文档，按标题层级提取章节和表格。"""

    # 兼容：即使样式不是 Heading，文本匹配这些模式也视为标题
    _TITLE_PATTERN = re.compile(r"^(第?[一二三四五六七八九十\d]+[、.．]\s*|(\d+\.)+\s*)")

    def parse(self, file_path: str) -> ParsedDocument:
        doc = Document(file_path)
        filename = file_path.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]

        sections: List[Section] = []
        current_section = Section(level=0, title="文档开头")
        sections.append(current_section)

        # 先收集所有表格，记录它们在 XML 中的位置，用于判断归属
        table_elements = list(doc.tables)
        table_positions = self._map_table_positions(doc)

        # 解析段落
        for para in doc.paragraphs:
            style_name = para.style.name if para.style else ""
            text = para.text.strip()

            if not text:
                continue

            is_heading = False
            heading_level = 0

            # 判断是否为标题
            if style_name.startswith("Heading"):
                is_heading = True
                try:
                    heading_level = int(style_name.replace("Heading", "").strip())
                except ValueError:
                    heading_level = 1
            elif self._TITLE_PATTERN.match(text) and len(text) < 80:
                # 兼容非标准标题样式
                is_heading = True
                heading_level = 1

            if is_heading:
                current_section = Section(level=heading_level, title=text)
                sections.append(current_section)
            else:
                if current_section.content:
                    current_section.content += "\n"
                current_section.content += text

        # 把表格分配到对应的章节
        all_tables_raw = []
        for tbl in doc.tables:
            table_data = []
            for row in tbl.rows:
                row_data = [cell.text.strip() for cell in row.cells]
                table_data.append(row_data)
            all_tables_raw.append(table_data)

        # 简单策略：把表格按顺序附加到 sections
        # 通过 XML 中的位置判断表格属于哪个段落区间
        for idx, table_data in enumerate(all_tables_raw):
            assigned = False
            for si in range(len(sections) - 1, 0, -1):
                # 简化：把表格追加到最近的标题 section
                sections[si].tables.append(table_data)
                assigned = True
                break
            if not assigned and sections:
                sections[0].tables.append(table_data)

        # 如果第一个 section 没有实际内容，移除
        if sections[0].level == 0 and not sections[0].content and not sections[0].tables:
            sections = sections[1:]

        return ParsedDocument(
            filename=filename,
            sections=sections,
            raw_tables=all_tables_raw,
        )

    def _map_table_positions(self, doc: Document):
        """记录每个表格在文档 XML 元素中的大致位置。"""
        positions = []
        table_idx = 0
        para_idx = 0
        body = doc.element.body
        for child in body:
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if tag == "tbl":
                positions.append(("table", table_idx, para_idx))
                table_idx += 1
            elif tag == "p":
                para_idx += 1
        return positions
