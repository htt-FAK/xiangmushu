from __future__ import annotations

import json
import os
import sys
import time
import uuid
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
from core.artifacts import put_bytes
from core.auth import get_or_create_user, init_db, update_user_preferences
from core.billing import save_user_api_key
from core.db import ensure_configured_database, mysql_enabled
from core.generation_sessions import session_manager
from core.history import history_summary, list_history_articles
from core.knowledge_repo import (
    create_knowledge_base,
    list_source_stats,
    replace_source_chunks,
    upsert_knowledge_source,
)


def _ok(message: str, **extra):
    payload = {"ok": True, "message": message}
    payload.update(extra)
    return payload


def main() -> int:
    ensure_configured_database()
    init_db()
    if not mysql_enabled():
        print(json.dumps({"ok": False, "error": "PERSISTENCE_MODE is not mysql"}, ensure_ascii=False))
        return 1
    config.STORAGE_PROVIDER = "local"

    stamp = int(time.time())
    user = get_or_create_user(f"smoke-{stamp}@example.com")
    prefs = update_user_preferences(
        user.id,
        language="zh",
        model_choices={"main_writer": "qwen3.7-plus", "fast_writer": "qwen3.6-flash"},
    )
    save_user_api_key(
        user.id,
        f"smoke-{uuid.uuid4().hex}",
        validation={
            "ok": True,
            "code": "ok",
            "message": "Smoke metadata save",
            "validated_model": "qwen3.7-plus",
            "probes": [],
        },
    )

    slug = create_knowledge_base(user.id, f"Smoke KB {stamp}", f"smoke_kb_{stamp}")
    source_artifact = put_bytes(
        "source content",
        owner_user_id=user.id,
        artifact_type="uploaded_source",
        original_filename="smoke-source.txt",
        content_type="text/plain",
        metadata={"slug": slug, "surface": "mysql_smoke"},
    )
    parsed_artifact = put_bytes(
        "# smoke\nhello mysql smoke\n",
        owner_user_id=user.id,
        artifact_type="source_markdown",
        original_filename="smoke-source.md",
        content_type="text/markdown; charset=utf-8",
        metadata={"slug": slug, "source_filename": "smoke-source.txt"},
    )
    source_record = upsert_knowledge_source(
        user.id,
        slug,
        "smoke-source.txt",
        original_artifact_uuid=source_artifact.artifact_uuid,
        parsed_artifact_uuid=parsed_artifact.artifact_uuid,
        content_type="text/plain",
        byte_size=14,
        status="uploaded",
        metadata={"surface": "mysql_smoke"},
    )
    assert source_record is not None
    chunks = [
        SimpleNamespace(
            id=f"smoke-chunk-{index}",
            metadata={
                "source": "smoke-source.txt",
                "knowledge_source_id": int(source_record["id"]),
                "knowledge_base_id": int(source_record["knowledge_base_id"]),
                "vector_collection_id": int(source_record["vector_collection_id"]),
                "knowledge_chunk_key": f"{source_record['id']}:{index}",
            },
        )
        for index in range(2)
    ]
    replace_source_chunks(
        int(source_record["id"]),
        int(source_record["knowledge_base_id"]),
        int(source_record["vector_collection_id"]),
        chunks,
    )
    kb_stats = list_source_stats(
        user.id,
        slug,
        collection_exists=True,
        vector_count=2,
        metadata_summary={"source_ids": [int(source_record["id"])], "chunk_keys": [f"{source_record['id']}:0", f"{source_record['id']}:1"]},
    )

    session = session_manager.create_session(
        user.id,
        {"slug": slug, "template": "smoke-template.docx", "word_limit": 300},
    )
    document_artifact = put_bytes(
        "docx-placeholder",
        owner_user_id=user.id,
        artifact_type="generated_doc",
        original_filename="smoke-output.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        metadata={"session_id": session.session_id},
    )
    report_artifact = put_bytes(
        json.dumps({"ok": True}, ensure_ascii=False),
        owner_user_id=user.id,
        artifact_type="quality_report",
        original_filename="smoke-report.json",
        content_type="application/json",
        metadata={"session_id": session.session_id},
    )
    session_manager.append_event(session.session_id, {"type": "task", "index": 0, "total": 1, "chapter": "Smoke"})
    session_manager.append_event(session.session_id, {"type": "chunk", "index": 0, "text": "Smoke output"})
    session_manager.append_event(
        session.session_id,
        {
            "type": "done",
            "download": f"/api/artifacts/{document_artifact.artifact_uuid}/download",
            "report_download": f"/api/artifacts/{report_artifact.artifact_uuid}/download",
            "artifact_id": document_artifact.artifact_uuid,
            "report_artifact_id": report_artifact.artifact_uuid,
            "report_summary": "Smoke summary",
            "billing": {
                "records": [
                    {
                        "model": "qwen3.7-plus",
                        "input_tokens": 120,
                        "output_tokens": 240,
                        "cost_cny": 0.576,
                    }
                ],
                "input_tokens": 120,
                "output_tokens": 240,
                "cost_cny": 0.576,
            },
            "billing_summary": {
                "input_tokens": 120,
                "output_tokens": 240,
                "cost_cny": 0.576,
                "generation_count": 1,
            },
        },
    )

    articles = list_history_articles(user.id)
    summary = history_summary(articles)
    print(
        json.dumps(
            _ok(
                "MySQL smoke test passed.",
                user_id=user.id,
                kb_slug=slug,
                preferences=prefs,
                kb_stats=kb_stats,
                history_count=len(articles),
                history_summary=summary,
                latest_article=articles[0] if articles else None,
            ),
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
