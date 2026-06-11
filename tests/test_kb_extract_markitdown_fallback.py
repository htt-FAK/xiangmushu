"""Backend tests for MarkItDown fallback KB ingestion."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import config
import server
from core.auth import create_access_token, get_or_create_user
from core.kb_extract import (
    is_supported_kb_extension,
    path_to_parsed_document,
)


def test_is_supported_kb_extension_recognizes_whitelist() -> None:
    for ext in [".txt", ".csv", ".html", ".htm", ".xlsx", ".xls", ".doc"]:
        assert is_supported_kb_extension(ext) is True
    for ext in [".pdf", ".docx", ".pptx", ".md", ".markdown", ".png", ".jpg"]:
        assert is_supported_kb_extension(ext) is True
    for ext in [".zip", ".exe", ".bin", ".tar", ""]:
        assert is_supported_kb_extension(ext) is False


def test_txt_file_ingested_via_markitdown_fallback(tmp_path) -> None:
    p = tmp_path / "sample.txt"
    p.write_text("# Title\n\nThis is plain text content.", encoding="utf-8")
    doc = path_to_parsed_document(str(p), original_name="sample.txt")
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 1
    body = "\n\n".join(b.text for b in doc.blocks)
    assert "Title" in body or "plain text" in body


def test_csv_file_ingested_via_markitdown_fallback(tmp_path) -> None:
    p = tmp_path / "sample.csv"
    p.write_text("name,age\nAlice,30\nBob,25\n", encoding="utf-8")
    doc = path_to_parsed_document(str(p), original_name="sample.csv")
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 1
    body = "\n\n".join(b.text for b in doc.blocks)
    assert "Alice" in body or "name" in body


def test_html_file_ingested_via_markitdown_fallback(tmp_path) -> None:
    p = tmp_path / "sample.html"
    p.write_text(
        "<html><body><h1>Hello</h1><p>Some HTML content</p></body></html>",
        encoding="utf-8",
    )
    doc = path_to_parsed_document(str(p), original_name="sample.html")
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 1
    body = "\n\n".join(b.text for b in doc.blocks)
    assert "Hello" in body or "HTML" in body


def test_htm_file_ingested_via_markitdown_fallback(tmp_path) -> None:
    p = tmp_path / "sample.htm"
    p.write_text(
        "<html><body><h2>Page</h2><p>HTM body here</p></body></html>",
        encoding="utf-8",
    )
    doc = path_to_parsed_document(str(p), original_name="sample.htm")
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 1
    body = "\n\n".join(b.text for b in doc.blocks)
    assert "Page" in body or "HTM" in body


def test_xlsx_file_ingested_via_markitdown_fallback(tmp_path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Metric", "Value"])
    ws.append(["Revenue", "1000"])
    ws.append(["Cost", "300"])
    p = tmp_path / "sample.xlsx"
    wb.save(p)
    doc = path_to_parsed_document(str(p), original_name="sample.xlsx")
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 1
    body = "\n\n".join(b.text for b in doc.blocks)
    assert "Revenue" in body or "Metric" in body


def test_xls_file_uses_markitdown_fallback(tmp_path, monkeypatch) -> None:
    import core.kb_extract as kex

    p = tmp_path / "sample.xls"
    p.write_bytes(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x00")  # xls-like bytes
    monkeypatch.setattr(
        kex,
        "_convert_with_markitdown",
        lambda path: "# XLS Sheet\n\n| col1 | col2 |\n|---|---|\n| a | b |",
    )
    doc = path_to_parsed_document(str(p), original_name="sample.xls")
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 1
    body = "\n\n".join(b.text for b in doc.blocks)
    assert "col1" in body or "a" in body


def test_doc_file_uses_markitdown_fallback(tmp_path, monkeypatch) -> None:
    import core.kb_extract as kex

    p = tmp_path / "sample.doc"
    p.write_bytes(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1\x00\x00")  # ole-like bytes
    monkeypatch.setattr(
        kex,
        "_convert_with_markitdown",
        lambda path: "# From Old Word\n\nThis is converted DOC text.",
    )
    doc = path_to_parsed_document(str(p), original_name="sample.doc")
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 1
    body = "\n\n".join(b.text for b in doc.blocks)
    assert "Word" in body or "DOC" in body


def test_unknown_extension_raises_value_error(tmp_path) -> None:
    p = tmp_path / "evil.zip"
    p.write_bytes(b"\x00\x01\x02")
    assert is_supported_kb_extension(".zip") is False
    with pytest.raises(ValueError, match="不支持的文件类型"):
        path_to_parsed_document(str(p), original_name="evil.zip")


def test_upload_unsupported_file_does_not_persist(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "HISTORICAL_DIR", str(tmp_path))
    user = get_or_create_user("kb_format_test@example.com")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(server.app) as client:
        resp = client.post(
            "/api/kb/upload",
            headers=headers,
            files=[("files", ("evil.zip", b"fake-zip-content", "application/zip"))],
            data={"slug": "kb1"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["results"], "Expected non-empty results array"
    result = body["results"][0]
    assert result["ok"] is False
    assert result.get("unsupported_format") is True
    assert "不支持" in result["error"]
    # File must NOT have been written to HISTORICAL_DIR
    written = [p.name for p in tmp_path.iterdir()]
    assert "evil.zip" not in written


def test_upload_supported_file_still_writes_to_disk(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(config, "HISTORICAL_DIR", str(tmp_path))
    user = get_or_create_user("kb_format_test2@example.com")
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(server.app) as client:
        resp = client.post(
            "/api/kb/upload",
            headers=headers,
            files=[("files", ("note.txt", b"hello world", "text/plain"))],
            data={"slug": "kb1"},
        )

    assert resp.status_code == 200
    body = resp.json()
    result = body["results"][0]
    assert result.get("unsupported_format") is not True
    # File must have been written to disk
    written = [p.name for p in tmp_path.iterdir()]
    assert any(name.endswith(".txt") for name in written)
