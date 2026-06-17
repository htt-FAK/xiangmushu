import sqlite3

from fastapi.testclient import TestClient

import config
import server
from core.auth import create_access_token, get_or_create_user, init_db
from core.billing import TokenUsage, calculate_cost_cny, load_provider_api_key_validation, load_user_api_key, record_billing
from core.generation_sessions import GenerationSession, GenerationSessionManager, session_manager


def _auth_headers(user):
    return {"Authorization": f"Bearer {create_access_token(user)}"}


def _ok_validation(api_key, provider_code="dashscope", user_id=None):
    return {
        "ok": True,
        "code": "ok",
        "message": "ok",
        "retryable": False,
        "validated_model": "deepseek-v4-flash" if provider_code == "deepseek" else "qwen3.6-flash",
        "provider_code": provider_code,
        "probes": [{"ok": True, "model": "probe", "code": "ok", "message": "ok"}],
    }


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
    assert data["generation_count"] == 0
    assert data["cost_cny"] == 0.0018


def test_billing_summary_recomputes_cost_for_unpriced_model_records(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("cost@example.com", db_path=str(db_path))

    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO billing_records(user_id, model, input_tokens, output_tokens, cost_cny, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user.id, "qwen3.5-plus", 1000, 500, 0.0, "2026-06-16T00:00:00+00:00"),
        )
        conn.commit()

    from core.billing import billing_summary

    summary = billing_summary(user.id, str(db_path))
    assert summary["input_tokens"] == 1000
    assert summary["output_tokens"] == 500
    assert summary["generation_count"] == 0
    assert summary["cost_cny"] == calculate_cost_cny("qwen3.5-plus", 1000, 500)
    assert summary["cost_cny"] > 0


def test_user_api_key_is_encrypted_statused_and_deleted(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "USER_API_KEY_ENCRYPTION_KEY", "stable-test-secret")
    monkeypatch.setattr(server, "validate_user_api_key", _ok_validation)
    init_db(str(db_path))
    user = get_or_create_user("key@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    with TestClient(server.app) as client:
        empty = client.get("/api/user/apikey", headers=headers)
        saved = client.post("/api/user/apikey", json={"api_key": "sk-test-secret"}, headers=headers)
        status = client.get("/api/user/apikey", headers=headers)

    assert empty.status_code == 200
    assert empty.json()["providers"]["dashscope"]["has_key"] is False
    assert saved.status_code == 200
    assert saved.json()["providers"]["dashscope"]["has_key"] is True
    assert status.json()["providers"]["dashscope"]["has_key"] is True
    assert load_user_api_key(user.id, str(db_path)) == "sk-test-secret"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT encrypted_api_key FROM user_api_keys WHERE user_id = ?", (user.id,)).fetchone()
    assert row is not None
    assert "sk-test-secret" not in row[0]

    with TestClient(server.app) as client:
        deleted = client.delete("/api/user/apikey", headers=headers)

    assert deleted.status_code == 200
    assert deleted.json()["providers"]["dashscope"]["has_key"] is False
    assert load_user_api_key(user.id, str(db_path)) is None


def test_provider_specific_api_key_status_and_delete(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "USER_API_KEY_ENCRYPTION_KEY", "stable-test-secret")
    monkeypatch.setattr(server, "validate_user_api_key", _ok_validation)
    init_db(str(db_path))
    user = get_or_create_user("provider@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    with TestClient(server.app) as client:
        saved = client.post("/api/user/apikey", json={"api_key": "sk-deepseek", "provider_code": "deepseek"}, headers=headers)
        status = client.get("/api/user/apikey", headers=headers)
        deleted = client.request("DELETE", "/api/user/apikey?provider_code=deepseek", headers=headers)

    assert saved.status_code == 200
    assert status.json()["providers"]["deepseek"]["has_key"] is True
    assert status.json()["providers"]["dashscope"]["has_key"] is False
    assert deleted.status_code == 200
    assert deleted.json()["providers"]["deepseek"]["has_key"] is False


def test_user_api_key_save_requires_validation(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "USER_API_KEY_ENCRYPTION_KEY", "stable-test-secret")
    init_db(str(db_path))
    user = get_or_create_user("validated@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    monkeypatch.setattr(server, "validate_user_api_key", lambda api_key, provider_code="dashscope": {
        "ok": False,
        "code": "invalid_api_key",
        "message": "invalid",
        "retryable": False,
        "validated_model": None,
        "provider_code": provider_code,
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

    monkeypatch.setattr(server, "validate_user_api_key", _ok_validation)

    with TestClient(server.app) as client:
        response = client.post("/api/user/apikey/validate", json={"api_key": "good-key"}, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["validated_model"] == "qwen3.6-flash"


def test_user_api_key_validation_endpoint_surfaces_quota_message(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("quota@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    monkeypatch.setattr(server, "validate_user_api_key", lambda api_key, provider_code="dashscope": {
        "ok": False,
        "code": "quota_exceeded",
        "message": "quota exhausted",
        "retryable": False,
        "validated_model": None,
        "provider_code": provider_code,
        "probes": [
            {
                "ok": False,
                "model": "qwen3.6-flash",
                "code": "quota_exceeded",
                "message": "quota exhausted",
                "detail": "429 insufficient_quota: balance exhausted",
                "retryable": False,
            }
        ],
    })

    with TestClient(server.app) as client:
        response = client.post("/api/user/apikey/validate", json={"api_key": "quota-key"}, headers=headers)

    assert response.status_code == 422
    data = response.json()
    assert data["code"] == "quota_exceeded"
    assert "quota" in data["message"]
    assert data["retryable"] is False


def test_user_apikey_test_endpoint_validates_saved_provider_key(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "USER_API_KEY_ENCRYPTION_KEY", "stable-test-secret")
    monkeypatch.setattr(server, "validate_user_api_key", _ok_validation)
    init_db(str(db_path))
    user = get_or_create_user("test-endpoint@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    with TestClient(server.app) as client:
        saved = client.post("/api/user/apikey", json={"api_key": "sk-deepseek", "provider_code": "deepseek"}, headers=headers)
        tested = client.post("/api/user/apikey/test", json={"provider_code": "deepseek"}, headers=headers)

    assert saved.status_code == 200
    assert tested.status_code == 200
    data = tested.json()
    assert data["ok"] is True
    assert data["validation"]["provider_code"] == "deepseek"
    assert data["providers"]["deepseek"]["validated"] is True
    validation = load_provider_api_key_validation(user.id, "deepseek", str(db_path))
    assert validation.get("ok") is True


def test_user_apikey_test_endpoint_requires_saved_key(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("test-empty-provider@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    with TestClient(server.app) as client:
        tested = client.post("/api/user/apikey/test", json={"provider_code": "mimo"}, headers=headers)

    assert tested.status_code == 422
    data = tested.json()
    assert data["code"] == "invalid_api_key"
    assert data["provider_code"] == "mimo"


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


def test_generation_session_can_be_terminated(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    init_db(str(db_path))
    user = get_or_create_user("terminate@example.com", db_path=str(db_path))
    headers = _auth_headers(user)

    session_manager._sessions.clear()
    session_manager._active_by_user.clear()
    session_manager._latest_by_user.clear()

    monkeypatch.setattr(server, "_resolve_generation_request", lambda current_user, params: {"resolved": True})
    monkeypatch.setattr(server, "_run_generation_session", lambda session_id, current_user, params, resolved: None)

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

        terminated = client.post(f"/api/generate/sessions/{session_id}/terminate", headers=headers)
        active = client.get("/api/generate/sessions/active", headers=headers)
        snapshot = client.get(f"/api/generate/sessions/{session_id}", headers=headers)

    assert terminated.status_code == 200
    assert terminated.json()["ok"] is True
    assert terminated.json()["session"]["status"] == "terminated"
    assert snapshot.status_code == 200
    assert snapshot.json()["session"]["status"] == "terminated"
    assert snapshot.json()["session"]["last_error"]["code"] == "terminated"
    assert active.status_code == 200
    assert active.json()["session"]["status"] == "terminated"


def test_generation_session_manager_recovers_persisted_snapshot(monkeypatch):
    manager = GenerationSessionManager()
    persisted = GenerationSession(
        session_id="gen_persisted",
        user_id=7,
        params={"template": "demo.docx"},
        status="done",
        current_step="done",
        download="/api/artifacts/a/download",
    )
    monkeypatch.setattr("core.generation_sessions._load_persisted_session", lambda user_id, session_id: persisted)
    monkeypatch.setattr("core.generation_sessions._latest_persisted_session_key", lambda user_id: "gen_persisted")

    loaded = manager.get_session_for_user(7, "gen_persisted")
    latest = manager.get_latest_session(7)

    assert loaded is not None
    assert loaded.snapshot()["download"] == "/api/artifacts/a/download"
    assert latest is loaded
