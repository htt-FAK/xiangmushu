from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import config
from core.artifacts import put_bytes
from core.auth import get_or_create_user, init_db, set_password, update_user_preferences
from core.billing import save_user_api_key
from core.db import ensure_configured_database, mysql_transaction
from core.generation_sessions import session_manager
from core.knowledge_repo import create_knowledge_base


EMAIL = "playwright@example.com"
PASSWORD = "Playwright123"


def main() -> int:
    ensure_configured_database()
    init_db()
    config.STORAGE_PROVIDER = "local"

    user = get_or_create_user(EMAIL)
    password_hash = set_password(PASSWORD)
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE users
                SET password_hash = %s, is_verified = 1, preferred_language = 'zh'
                WHERE id = %s
                """,
                (password_hash, user.id),
            )
            cur.execute("DELETE FROM user_model_choices WHERE user_id = %s", (user.id,))
            cur.execute(
                """
                INSERT INTO user_model_choices(user_id, module_key, provider_id, model_catalog_id, provider_code, model_id)
                VALUES(%s, 'main_writer', NULL, NULL, 'deepseek', 'deepseek-v4-pro')
                """,
                (user.id,),
            )
    update_user_preferences(user.id, language="zh", model_choices={"fast_writer": "qwen3.6-flash"})
    save_user_api_key(
        user.id,
        "playwright-demo-key",
        validation={"ok": True, "code": "ok", "message": "demo", "validated_model": "qwen3.7-plus", "probes": []},
    )

    slug = create_knowledge_base(user.id, "Playwright Demo KB", "playwright_demo")
    session = session_manager.create_session(
        user.id,
        {"slug": slug, "template": "playwright-demo.docx", "word_limit": 300},
    )
    doc = put_bytes(
        "playwright doc placeholder",
        owner_user_id=user.id,
        artifact_type="generated_doc",
        original_filename="playwright-demo.docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        metadata={"session_id": session.session_id, "surface": "playwright_demo"},
    )
    report = put_bytes(
        json.dumps({"ok": True}, ensure_ascii=False),
        owner_user_id=user.id,
        artifact_type="quality_report",
        original_filename="playwright-demo-report.json",
        content_type="application/json",
        metadata={"session_id": session.session_id, "surface": "playwright_demo"},
    )
    session_manager.append_event(session.session_id, {"type": "task", "index": 0, "total": 1, "chapter": "Demo"})
    session_manager.append_event(session.session_id, {"type": "chunk", "index": 0, "text": "Playwright demo output"})
    session_manager.append_event(
        session.session_id,
        {
            "type": "done",
            "download": f"/api/artifacts/{doc.artifact_uuid}/download",
            "report_download": f"/api/artifacts/{report.artifact_uuid}/download",
            "artifact_id": doc.artifact_uuid,
            "report_artifact_id": report.artifact_uuid,
            "report_summary": f"Playwright demo summary {int(time.time())}",
            "billing": {
                "records": [
                    {"model": "qwen3.7-plus", "input_tokens": 88, "output_tokens": 166, "cost_cny": 0.402}
                ],
                "input_tokens": 88,
                "output_tokens": 166,
                "cost_cny": 0.402,
            },
            "billing_summary": {
                "input_tokens": 88,
                "output_tokens": 166,
                "cost_cny": 0.402,
                "generation_count": 1,
            },
        },
    )
    print(json.dumps({"ok": True, "email": EMAIL, "password": PASSWORD, "slug": slug}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

