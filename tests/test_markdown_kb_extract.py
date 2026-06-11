from core.kb_extract import path_to_parsed_document


def test_markdown_file_can_be_parsed_into_kb_document(tmp_path):
    md_path = tmp_path / "sample.md"
    md_path.write_text("# 产品简介\n\n这是第一段。\n\n## 核心能力\n\n支持知识库入库。", encoding="utf-8")

    doc = path_to_parsed_document(str(md_path), original_name="sample.md")

    assert doc.filename == "sample.md"
    assert doc.kb_source_type == "markdown"
    assert len(doc.blocks) >= 2
    assert doc.blocks[0].source_type == "markdown"
    assert doc.blocks[0].content_format == "markdown"
    assert "产品简介" in doc.sections[0].content or "产品简介" in doc.blocks[0].text
