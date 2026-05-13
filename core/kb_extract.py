"""知识库多格式解析：docx / pdf / pptx / 图片（视觉模型）→ ParsedDocument。"""
from __future__ import annotations

import mimetypes
import os
from typing import Optional

from core.parser import DocumentParser, ParsedDocument, Section


def _synthetic_doc(filename: str, body: str, kb_source_type: str) -> ParsedDocument:
    text = (body or "").strip()
    if not text:
        text = "（未能提取到有效文本内容）"
    sec = Section(level=0, title="全文", content=text)
    return ParsedDocument(
        filename=filename,
        sections=[sec],
        raw_tables=[],
        kb_source_type=kb_source_type,
    )


def _extract_pdf_text(path: str) -> str:
    from pypdf import PdfReader

    reader = PdfReader(path)
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n\n".join(parts)


def _extract_pptx_text(path: str) -> str:
    from pptx import Presentation

    prs = Presentation(path)
    parts: list[str] = []
    for i, slide in enumerate(prs.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text:
                lines.append(shape.text.strip())
        if lines:
            parts.append(f"【第{i}页】\n" + "\n".join(lines))
    return "\n\n".join(parts)


def _guess_mime(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("image/"):
        return mime
    ext = os.path.splitext(path)[1].lower()
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(ext, "application/octet-stream")


def path_to_parsed_document(path: str, original_name: Optional[str] = None) -> ParsedDocument:
    """
    根据扩展名解析为 ParsedDocument，供 Chunker 使用。
    original_name 用于展示与 metadata.source（默认取 path 的 basename）。
    """
    name = original_name or os.path.basename(path)
    ext = os.path.splitext(path)[1].lower()

    if ext == ".docx":
        return DocumentParser().parse(path)

    if ext == ".pdf":
        text = _extract_pdf_text(path)
        if not (text or "").strip():
            text = (
                "（本 PDF 未提取到文本层，可能为纯扫描件。请导出为图片后上传，"
                "或使用带文字层的 PDF。）"
            )
        return _synthetic_doc(name, text, "pdf")

    if ext == ".pptx":
        text = _extract_pptx_text(path)
        if not (text or "").strip():
            text = "（未从 PPTX 提取到文本，可能幻灯片主要为图片；可导出为图片后上传以启用视觉解析。）"
        return _synthetic_doc(name, text, "pptx")

    if ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        from core.vision_extract import describe_image_bytes

        with open(path, "rb") as f:
            raw = f.read()
        mime = _guess_mime(path)
        text = describe_image_bytes(raw, mime)
        doc = _synthetic_doc(name, f"【图片视觉解析】{name}\n\n{text}", "image_vision")
        return doc

    raise ValueError(f"不支持的文件类型: {ext}")
