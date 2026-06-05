from dataclasses import dataclass
from typing import List
from core.parser import ParsedDocument
import uuid


@dataclass
class Chunk:
    id: str
    text: str
    metadata: dict
    seq: int = 0
    page: int = 1
    source_type: str = "docx"
    content_format: str = "text"


class Chunker:
    """语义块：支持重叠滑动窗口，避免硬截断。"""

    MAX_CONTENT_LEN = 700
    OVERLAP_LEN = 120

    def chunk(self, doc: ParsedDocument) -> List[Chunk]:
        if getattr(doc, "blocks", None):
            return self._chunk_from_blocks(doc)
        return self._chunk_from_sections(doc)

    def _chunk_from_blocks(self, doc: ParsedDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        seq = 0

        for block_idx, block in enumerate(doc.blocks):
            text = (block.text or "").strip()
            if not text:
                continue
            if block.block_type == "heading":
                continue

            pieces = self._pieces_for_block(block)
            for piece_idx, piece in enumerate(pieces):
                meta = {
                    "source": doc.filename,
                    "chapter": block.chapter or "全文",
                    "type": block.block_type,
                    "page": int(block.page or 1),
                    "seq": seq,
                    "block_index": block_idx,
                    "piece_index": piece_idx,
                    "source_type": block.source_type or doc.kb_source_type or "docx",
                    "content_format": block.content_format or "text",
                    "ref_id": self._build_ref_id(doc.filename, seq, int(block.page or 1)),
                }
                if block.table_index is not None:
                    meta["table_index"] = int(block.table_index)
                if block.table_header:
                    meta["table_header"] = block.table_header
                if doc.kb_source_type:
                    meta["kb_source"] = doc.kb_source_type
                if block.metadata:
                    meta.update(block.metadata)
                chunks.append(
                    Chunk(
                        id=str(uuid.uuid4()),
                        text=piece,
                        metadata=meta,
                        seq=seq,
                        page=int(block.page or 1),
                        source_type=str(meta["source_type"]),
                        content_format=str(meta["content_format"]),
                    )
                )
                seq += 1
        return chunks

    def _chunk_from_sections(self, doc: ParsedDocument) -> List[Chunk]:
        chunks: List[Chunk] = []
        seq = 0

        for section in doc.sections:
            if section.content.strip():
                base = f"{section.title}\n{section.content.strip()}"
                for piece_idx, piece in enumerate(self._split_with_overlap(base)):
                    meta = {
                        "source": doc.filename,
                        "chapter": section.title,
                        "type": "text",
                        "page": 1,
                        "seq": seq,
                        "piece_index": piece_idx,
                        "source_type": doc.kb_source_type or "docx",
                        "content_format": "text",
                        "ref_id": self._build_ref_id(doc.filename, seq, 1),
                    }
                    if doc.kb_source_type:
                        meta["kb_source"] = doc.kb_source_type
                    chunks.append(
                        Chunk(
                            id=str(uuid.uuid4()),
                            text=piece,
                            metadata=meta,
                            seq=seq,
                            page=1,
                            source_type=doc.kb_source_type or "docx",
                            content_format="text",
                        )
                    )
                    seq += 1

            for t_idx, table in enumerate(section.tables):
                table_text = self._table_to_text(table)
                if not table_text.strip():
                    continue
                header = " | ".join(table[0]) if table else ""
                block_like = type("BlockLike", (), {})()
                block_like.text = f"{section.title}\n表格内容：\n{table_text}"
                block_like.chapter = section.title
                block_like.page = 1
                block_like.block_type = "table"
                block_like.source_type = doc.kb_source_type or "docx"
                block_like.content_format = "markdown"
                block_like.table_index = t_idx
                block_like.table_header = header
                block_like.metadata = {}
                for piece_idx, piece in enumerate(self._pieces_for_block(block_like)):
                    meta = {
                        "source": doc.filename,
                        "chapter": section.title,
                        "type": "table",
                        "table_index": t_idx,
                        "page": 1,
                        "seq": seq,
                        "piece_index": piece_idx,
                        "source_type": doc.kb_source_type or "docx",
                        "content_format": "markdown",
                        "ref_id": self._build_ref_id(doc.filename, seq, 1),
                    }
                    if header:
                        meta["table_header"] = header
                    if doc.kb_source_type:
                        meta["kb_source"] = doc.kb_source_type
                    chunks.append(
                        Chunk(
                            id=str(uuid.uuid4()),
                            text=piece,
                            metadata=meta,
                            seq=seq,
                            page=1,
                            source_type=doc.kb_source_type or "docx",
                            content_format="markdown",
                        )
                    )
                    seq += 1
        return chunks

    def _pieces_for_block(self, block) -> List[str]:
        if block.block_type == "table":
            return self._split_table_block(
                str(block.text or ""),
                str(getattr(block, "table_header", "") or ""),
            )
        return self._split_with_overlap(str(block.text or ""))

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

    def _split_table_block(self, text: str, header: str) -> List[str]:
        body = (text or "").strip()
        if len(body) <= self.MAX_CONTENT_LEN * 2:
            return [body]

        lines = [line for line in body.splitlines() if line.strip()]
        if len(lines) <= 3:
            return self._split_with_overlap(body)

        prefix_lines = [lines[0]]
        if header and header not in lines[0]:
            prefix_lines.append(header)
        data_lines = lines[1:]
        prefix = "\n".join(prefix_lines).strip()

        pieces: List[str] = []
        bucket: List[str] = []
        bucket_len = len(prefix)
        for line in data_lines:
            line_len = len(line) + 1
            if bucket and bucket_len + line_len > self.MAX_CONTENT_LEN:
                pieces.append((prefix + "\n" + "\n".join(bucket)).strip())
                bucket = []
                bucket_len = len(prefix)
            bucket.append(line)
            bucket_len += line_len
        if bucket:
            pieces.append((prefix + "\n" + "\n".join(bucket)).strip())
        return pieces or [body]

    @staticmethod
    def _table_to_text(table: List[List[str]]) -> str:
        if not table:
            return ""
        lines = []
        for row in table:
            lines.append(" | ".join(row))
        return "\n".join(lines)

    @staticmethod
    def _build_ref_id(source: str, seq: int, page: int) -> str:
        return f"{source}#{page}-{seq}"
