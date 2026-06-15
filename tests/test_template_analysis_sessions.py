from __future__ import annotations

from fastapi.testclient import TestClient

import config
import server
from core.auth import create_access_token, get_or_create_user, init_db
from core.template_analysis_sessions import TemplateAnalysisSession, TemplateAnalysisSessionManager


def test_template_analysis_session_accumulates_logs_and_billing():
    manager = TemplateAnalysisSessionManager()
    session = manager.create_session(3, {"template": "demo.docx", "vision_model": "vision-a", "planner_model": "plan-a"})

    manager.append_event(session.session_id, {"type": "status", "phase": "prepare", "message": "Preparing template"})
    manager.append_event(
        session.session_id,
        {
            "type": "billing",
            "billing": {"model": "vision-a", "input_tokens": 12, "output_tokens": 4, "cost_cny": 0.01},
        },
    )
    manager.append_event(
        session.session_id,
        {
            "type": "done",
            "message": "Analysis complete",
            "template": "demo.docx",
            "tasks": [{"target_chapter": "One", "word_limit": 120}],
            "mode": "anchor",
            "vision_status": "ready",
        },
    )

    snapshot = session.snapshot()

    assert snapshot["status"] == "done"
    assert snapshot["currentPhase"] == "done"
    assert snapshot["tasks"][0]["target_chapter"] == "One"
    assert snapshot["billing"]["input_tokens"] == 12
    assert len(snapshot["logs"]) == 2


def test_template_analysis_session_marks_error_and_releases_active_slot():
    manager = TemplateAnalysisSessionManager()
    session = manager.create_session(9, {"template": "broken.docx"})

    manager.append_event(
        session.session_id,
        {"type": "error", "error": {"code": "boom", "message": "Template analysis failed", "retryable": True}},
    )

    snapshot = session.snapshot()

    assert snapshot["status"] == "error"
    assert snapshot["last_error"]["code"] == "boom"
    assert manager.get_active_session(9) is None


def test_template_analysis_session_manager_recovers_persisted_snapshot(monkeypatch):
    manager = TemplateAnalysisSessionManager()
    persisted = TemplateAnalysisSession(
        session_id="tmpl_persisted",
        user_id=7,
        params={"template": "demo.docx", "vision_model": "vision-a", "planner_model": "plan-a"},
        status="done",
        current_phase="done",
        status_message="Analysis complete",
        template="demo.docx",
        mode="anchor",
        vision_status="ready",
        tasks=[{"target_chapter": "One", "word_limit": 120}],
        billing={"records": [], "input_tokens": 12, "output_tokens": 4, "cost_cny": 0.01},
        logs=[{"phase": "done", "message": "Analysis complete", "created_at": "2026-06-14T00:00:00Z"}],
    )
    monkeypatch.setattr("core.template_analysis_sessions._load_persisted_session", lambda user_id, session_id: persisted)
    monkeypatch.setattr("core.template_analysis_sessions._latest_persisted_session_key", lambda user_id: "tmpl_persisted")

    loaded = manager.get_session_for_user(7, "tmpl_persisted")
    latest = manager.get_latest_session(7)

    assert loaded is not None
    assert loaded.snapshot()["template"] == "demo.docx"
    assert loaded.snapshot()["status"] == "done"
    assert latest is loaded


def test_template_analysis_session_endpoints_recover_persisted_snapshot(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("tmpl@example.com", db_path=str(db_path))
    headers = {"Authorization": f"Bearer {create_access_token(user)}"}

    manager = server.template_analysis_session_manager
    manager._sessions.clear()
    manager._active_by_user.clear()
    manager._latest_by_user.clear()

    persisted = TemplateAnalysisSession(
        session_id="tmpl_persisted",
        user_id=user.id,
        params={"template": "demo.docx", "vision_model": "vision-a", "planner_model": "plan-a"},
        status="done",
        current_phase="done",
        status_message="Analysis complete",
        template="demo.docx",
        mode="anchor",
        vision_status="ready",
        tasks=[{"target_chapter": "One", "word_limit": 120}],
        billing={"records": [], "input_tokens": 12, "output_tokens": 4, "cost_cny": 0.01},
        logs=[{"phase": "done", "message": "Analysis complete", "created_at": "2026-06-14T00:00:00Z"}],
    )
    monkeypatch.setattr("core.template_analysis_sessions._load_persisted_session", lambda user_id, session_id: persisted)
    monkeypatch.setattr("core.template_analysis_sessions._latest_persisted_session_key", lambda user_id: "tmpl_persisted")

    with TestClient(server.app) as client:
        active = client.get("/api/template/analyze/sessions/active", headers=headers)
        snapshot = client.get("/api/template/analyze/sessions/tmpl_persisted", headers=headers)

    assert active.status_code == 200
    assert snapshot.status_code == 200
    assert active.json()["session"]["session_id"] == "tmpl_persisted"
    assert snapshot.json()["session"]["tasks"][0]["target_chapter"] == "One"
