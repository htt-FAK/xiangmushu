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
    """语义块：支持重叠滑动窗口，避免硬截断。"""

    MAX_CONTENT_LEN = 700
    OVERLAP_LEN = 120

    def chunk(self, doc: ParsedDocument) -> List[Chunk]:
        chunks: List[Chunk] = []

        for section in doc.sections:
            if section.content.strip():
                base = f"{section.title}\n{section.content.strip()}"
                for piece in self._split_with_overlap(base):
                    meta = {
                        "source": doc.filename,
                        "chapter": section.title,
                        "type": "text",
                    }
                    if doc.kb_source_type:
                        meta["kb_source"] = doc.kb_source_type
                    chunks.append(
                        Chunk(
                            id=str(uuid.uuid4()),
                            text=piece,
                            metadata=meta,
                        )
                    )

            for t_idx, table in enumerate(section.tables):
                table_text = self._table_to_text(table)
                if not table_text.strip():
                    continue
                text = f"{section.title}\n表格内容：\n{table_text}"
                if len(text) > self.MAX_CONTENT_LEN * 2:
                    for piece in self._split_with_overlap(text):
                        meta = {
                            "source": doc.filename,
                            "chapter": section.title,
                            "type": "table",
                            "table_index": t_idx,
                        }
                        if doc.kb_source_type:
                            meta["kb_source"] = doc.kb_source_type
                        chunks.append(
                            Chunk(
                                id=str(uuid.uuid4()),
                                text=piece,
                                metadata=meta,
                            )
                        )
                else:
                    meta = {
                        "source": doc.filename,
                        "chapter": section.title,
                        "type": "table",
                        "table_index": t_idx,
                    }
                    if doc.kb_source_type:
                        meta["kb_source"] = doc.kb_source_type
                    chunks.append(
                        Chunk(
                            id=str(uuid.uuid4()),
                            text=text,
                            metadata=meta,
                        )
                    )

        return chunks

    def _split_with_overlap(self, text: str) -> List[str]:
        if len(text) <= self.MAX_CONTENT_LEN:
            return [text]

        pieces: List[str] = []
        start = 0
        n = len(text)
        while start < n:
            end = min(start + self.MAX_CONTENT_LEN, n)
            if end < n:
                cut = text.rfind("\n", start + self.MAX_CONTENT_LEN // 2, end)
                if cut == -1 or cut <= start:
                    cut = text.rfind("。", start + self.MAX_CONTENT_LEN // 2, end)
                if cut == -1 or cut <= start:
                    cut = text.rfind("；", start + self.MAX_CONTENT_LEN // 2, end)
                if cut > start:
                    end = cut + 1
            piece = text[start:end].strip()
            if piece:
                pieces.append(piece)
            if end >= n:
                break
            start = max(end - self.OVERLAP_LEN, start + 1)
        return pieces if pieces else [text[: self.MAX_CONTENT_LEN]]

    @staticmethod
    def _table_to_text(table: List[List[str]]) -> str:
        if not table:
            return ""
        lines = []
        for row in table:
            lines.append(" | ".join(row))
        return "\n".join(lines)
