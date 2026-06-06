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
