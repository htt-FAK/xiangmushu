import sqlite3

from fastapi.testclient import TestClient

import config
import server
from core.auth import create_access_token, get_or_create_user, init_db
from core.billing import (
    TokenUsage,
    calculate_cost_cny,
    load_user_api_key,
    record_billing,
)
from core.generation_sessions import session_manager


def _auth_headers(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def test_billing_calculation_and_summary_scoped_by_user(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user_a = get_or_create_user("a@example.com", db_path=str(db_path))
    user_b = get_or_create_user("b@example.com", db_path=str(db_path))

    assert calculate_cost_cny("qwen-plus", 1000, 500) == 0.0018
    record_billing(user_a.id, "qwen-plus", TokenUsage(input_tokens=1000, output_tokens=500), str(db_path))
    record_billing(user_b.id, "qwen-plus", TokenUsage(input_tokens=1000, output_tokens=1000), str(db_path))

    with TestClient(server.app) as client:
        response = client.get("/api/billing/summary", headers=_auth_headers(user_a))

    assert response.status_code == 200
    data = response.json()
    assert data["input_tokens"] == 1000
    assert data["output_tokens"] == 500
    assert data["generation_count"] == 1
    assert data["cost_cny"] == 0.0018


def test_user_api_key_is_encrypted_statused_and_deleted(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "USER_API_KEY_ENCRYPTION_KEY", "stable-test-secret")
    monkeypatch.setattr(server, "validate_user_api_key", lambda api_key: {
        "ok": True,
        "code": "ok",
        "message": "API Key 验证成功，可用于后续生成。",
        "retryable": False,
        "validated_model": "qwen3.6-flash",
        "probes": [{"ok": True, "model": "qwen3.6-flash", "code": "ok", "message": "ok"}],
    })
    init_db(str(db_path))
    user = get_or_create_user("key@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    with TestClient(server.app) as client:
        empty = client.get("/api/user/apikey", headers=headers)
        saved = client.post("/api/user/apikey", json={"api_key": "sk-test-secret"}, headers=headers)
        status = client.get("/api/user/apikey", headers=headers)

    assert empty.status_code == 200
    assert empty.json()["has_key"] is False
    assert saved.status_code == 200
    assert saved.json()["has_key"] is True
    assert status.json()["has_key"] is True
    assert load_user_api_key(user.id, str(db_path)) == "sk-test-secret"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT encrypted_api_key FROM user_api_keys WHERE user_id = ?", (user.id,)).fetchone()
    assert row is not None
    assert "sk-test-secret" not in row[0]

    with TestClient(server.app) as client:
        deleted = client.delete("/api/user/apikey", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["has_key"] is False
    assert load_user_api_key(user.id, str(db_path)) is None


def test_user_api_key_save_requires_validation(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "USER_API_KEY_ENCRYPTION_KEY", "stable-test-secret")
    init_db(str(db_path))
    user = get_or_create_user("validated@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    monkeypatch.setattr(server, "validate_user_api_key", lambda api_key: {
        "ok": False,
        "code": "invalid_api_key",
        "message": "API Key 无效，请检查是否复制完整或输入错误。",
        "retryable": False,
        "validated_model": None,
        "probes": [],
    })

    with TestClient(server.app) as client:
        response = client.post("/api/user/apikey", json={"api_key": "bad-key"}, headers=headers)

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_api_key"
    assert load_user_api_key(user.id, str(db_path)) is None


def test_user_api_key_validation_endpoint_returns_probe_result(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("probe@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    monkeypatch.setattr(server, "validate_user_api_key", lambda api_key: {
        "ok": True,
        "code": "ok",
        "message": "API Key 验证成功，可用于后续生成。",
        "retryable": False,
        "validated_model": "qwen3.6-flash",
        "probes": [{"ok": True, "model": "qwen3.6-flash", "code": "ok", "message": "ok"}],
    })

    with TestClient(server.app) as client:
        response = client.post("/api/user/apikey/validate", json={"api_key": "good-key"}, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["validated_model"] == "qwen3.6-flash"


def test_generation_session_start_and_recovery_contract(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("session@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    session_manager._sessions.clear()
    session_manager._active_by_user.clear()
    session_manager._latest_by_user.clear()

    monkeypatch.setattr(server, "_resolve_generation_request", lambda current_user, params: {"resolved": True})

    def fake_runner(session_id, current_user, params, resolved):
        session_manager.append_event(session_id, {"type": "task", "index": 0, "total": 1, "chapter": "摘要"})
        session_manager.append_event(session_id, {"type": "chunk", "index": 0, "text": "测试内容"})
        session_manager.append_event(session_id, {"type": "progress", "index": 0, "total": 1})
        session_manager.append_event(session_id, {"type": "done", "download": "/api/download/test.docx", "billing": {"records": [], "input_tokens": 0, "output_tokens": 0, "cost_cny": 0}, "billing_summary": {"input_tokens": 0, "output_tokens": 0, "cost_cny": 0, "generation_count": 0}})

    monkeypatch.setattr(server, "_run_generation_session", fake_runner)

    class ImmediateThread:
        def __init__(self, target=None, args=(), daemon=None):
            self._target = target
            self._args = args

        def start(self):
            if self._target:
                self._target(*self._args)

    monkeypatch.setattr(server.threading, "Thread", ImmediateThread)

    with TestClient(server.app) as client:
        create = client.post(
            "/api/generate/sessions",
            headers=headers,
            files={},
            data={
                "slug": "kb1",
                "template": "demo.docx",
                "word_limit": "300",
                "top_k": "4",
                "max_distance": "1.25",
                "enable_web": "false",
                "use_stream": "true",
                "enable_audit": "false",
                "enable_visual_audit": "false",
                "custom_instructions": "",
            },
        )
        assert create.status_code == 200
        session_id = create.json()["session_id"]

        active = client.get("/api/generate/sessions/active", headers=headers)
        snapshot = client.get(f"/api/generate/sessions/{session_id}", headers=headers)

    assert active.status_code == 200
    assert snapshot.status_code == 200
    assert active.json()["session"]["session_id"] == session_id
    assert snapshot.json()["session"]["status"] == "done"
    assert snapshot.json()["session"]["outputs"][0]["text"] == "测试内容"
