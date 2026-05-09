from dataclasses import dataclass
from typing import List
from core.parser import ParsedDocument
import uuid


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict


class Chunker:
    """将解析后的文档切分为语义块。"""

    MAX_CONTENT_LEN = 800

    def chunk(self, doc: ParsedDocument) -> List[Chunk]:
        chunks: List[Chunk] = []

        for idx, section in enumerate(doc.sections):
            # 文本 chunk
            if section.content.strip():
                text = f"{section.title}\n{section.content}"
                # 截断过长内容
                if len(text) > self.MAX_CONTENT_LEN:
                    text = text[: self.MAX_CONTENT_LEN]
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        text=text,
                        metadata={
                            "source": doc.filename,
                            "chapter": section.title,
                            "type": "text",
                        },
                    )
                )

            # 表格 chunk
            for t_idx, table in enumerate(section.tables):
                table_text = self._table_to_text(table)
                if not table_text.strip():
                    continue
                text = f"{section.title}\n表格内容：\n{table_text}"
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        text=text,
                        metadata={
                            "source": doc.filename,
                            "chapter": section.title,
                            "type": "table",
                            "table_index": t_idx,
                        },
                    )
                )

        return chunks

    @staticmethod
    def _table_to_text(table: List[List[str]]) -> str:
        if not table:
            return ""
        lines = []
        for row in table:
            lines.append(" | ".join(row))
        return "\n".join(lines)
