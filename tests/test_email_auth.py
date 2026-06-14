import sqlite3
import sys
import types

import pytest
from fastapi.testclient import TestClient

import config
from core.auth import (
    ACTIVE_ACCOUNT,
    ChallengeSupersededError,
    RECOVERY_CHALLENGE,
    SIGNUP_CHALLENGE,
    UNVERIFIED_ACCOUNT,
    authenticate_user,
    create_access_token,
    create_verification_code,
    get_account_state,
    get_or_create_user,
    init_db,
    reset_password_with_token,
    set_password,
    start_password_recovery,
    start_signup,
    user_from_token,
    verify_password,
    verify_password_recovery_code,
    verify_signup_code,
)

generator_stub = types.ModuleType("core.generator")


class ContentGenerator:
    pass


generator_stub.ContentGenerator = ContentGenerator
sys.modules.setdefault("core.generator", generator_stub)

vector_store_stub = types.ModuleType("core.vector_store")


class VectorStore:
    def __init__(self, *args, **kwargs):
        pass


vector_store_stub.VectorStore = VectorStore
sys.modules.setdefault("core.vector_store", vector_store_stub)

import server


@pytest.fixture()
def auth_db(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.sqlite3"
    monkeypatch.setattr(config, "AUTH_DB_PATH", str(db_path))
    monkeypatch.setattr(config, "AUTH_JWT_SECRET", "test-secret")
    monkeypatch.setattr(config, "AUTH_CODE_TTL_MINUTES", 10)
    monkeypatch.setattr(config, "AUTH_JWT_EXPIRE_MINUTES", 30)
    monkeypatch.setattr("core.auth.generate_code", lambda: "123456")
    monkeypatch.setattr(server, "send_verification_email", lambda email, code, purpose="register": None)
    monkeypatch.setattr(server, "rate_limiter", server.SimpleRateLimiter())
    init_db(str(db_path))
    return db_path


def count_users(db_path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def password_hash_for(db_path, email: str) -> str | None:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE email = ?", (email,)).fetchone()
    return row[0] if row else None


def audit_actions(db_path) -> list[str]:
    with sqlite3.connect(db_path) as conn:
        return [str(row[0]) for row in conn.execute("SELECT action FROM audit_logs ORDER BY id").fetchall()]


def test_password_hash_round_trip():
    password_hash = set_password("correct horse battery staple")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_signup_verification_activates_pending_user_case_insensitively(auth_db):
    start_signup("User@Example.com", "secret-1", code="123456", db_path=str(auth_db))

    assert get_account_state("user@example.com", str(auth_db)) == UNVERIFIED_ACCOUNT

    first = verify_signup_code(" user@example.com ", "123456", db_path=str(auth_db))
    assert first.email == "user@example.com"
    assert get_account_state("USER@example.com", str(auth_db)) == ACTIVE_ACCOUNT
    assert count_users(auth_db) == 1
    assert verify_password("secret-1", password_hash_for(auth_db, "user@example.com"))


def test_latest_signup_code_supersedes_older_code(auth_db):
    start_signup("user@example.com", "secret-1", code="111111", db_path=str(auth_db))
    start_signup("user@example.com", "secret-1", code="222222", db_path=str(auth_db))

    with pytest.raises(ChallengeSupersededError):
        verify_signup_code("user@example.com", "111111", db_path=str(auth_db))

    user = verify_signup_code("user@example.com", "222222", db_path=str(auth_db))
    assert user.email == "user@example.com"


def test_password_login_requires_verified_account(auth_db):
    start_signup("user@example.com", "secret-1", code="123456", db_path=str(auth_db))

    with pytest.raises(Exception):
        authenticate_user("user@example.com", "secret-1", db_path=str(auth_db))

    verify_signup_code("user@example.com", "123456", db_path=str(auth_db))
    user = authenticate_user("user@example.com", "secret-1", db_path=str(auth_db))
    assert user.email == "user@example.com"


def test_password_recovery_requires_recovery_challenge(auth_db):
    start_signup("user@example.com", "old-pass1", code="123456", db_path=str(auth_db))
    user = verify_signup_code("user@example.com", "123456", db_path=str(auth_db))

    start_password_recovery("user@example.com", code="654321", db_path=str(auth_db))
    recovery_token = verify_password_recovery_code("user@example.com", "654321", db_path=str(auth_db))
    reset_user = reset_password_with_token("user@example.com", recovery_token, "new-pass1", db_path=str(auth_db))

    assert reset_user.id == user.id
    assert verify_password("new-pass1", password_hash_for(auth_db, "user@example.com"))


def test_jwt_round_trip_loads_user(auth_db):
    user = get_or_create_user("user@example.com", db_path=str(auth_db))
    token = create_access_token(user)
    loaded = user_from_token(token, db_path=str(auth_db))

    assert loaded.id == user.id
    assert loaded.email == "user@example.com"


def test_auth_identify_routes_account_states(auth_db):
    start_signup("pending@example.com", "secret-1", code="123456", db_path=str(auth_db))
    get_or_create_user("active@example.com", db_path=str(auth_db))

    with TestClient(server.app) as client:
        missing = client.post("/api/auth/identify", json={"email": "unknown@example.com"})
        pending = client.post("/api/auth/identify", json={"email": "pending@example.com"})
        active = client.post("/api/auth/identify", json={"email": "active@example.com"})

    assert missing.status_code == 200
    assert missing.json()["account_state"] == "unknown_email"
    assert pending.json()["account_state"] == "existing_unverified"
    assert active.json()["account_state"] == "existing_verified"


def test_signup_api_issues_token_and_me_returns_user(auth_db):
    with TestClient(server.app) as client:
        start = client.post("/api/auth/signup/start", json={"email": "user@example.com", "password": "secret-1"})
        assert start.status_code == 200
        verify = client.post("/api/auth/signup/verify", json={"email": "user@example.com", "code": "123456"})
        assert verify.status_code == 200
        token = verify.json()["access_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "user@example.com"

    assert "REGISTER_SUCCESS" in audit_actions(auth_db)


def test_recovery_api_issues_token_and_allows_new_password(auth_db):
    start_signup("user@example.com", "old-pass1", code="123456", db_path=str(auth_db))
    verify_signup_code("user@example.com", "123456", db_path=str(auth_db))

    with TestClient(server.app) as client:
        start = client.post("/api/auth/recovery/start", json={"email": "user@example.com"})
        assert start.status_code == 200
        verify = client.post("/api/auth/recovery/verify", json={"email": "user@example.com", "code": "123456"})
        assert verify.status_code == 200
        recovery_token = verify.json()["recovery_token"]

        complete = client.post(
            "/api/auth/recovery/complete",
            json={"email": "user@example.com", "recovery_token": recovery_token, "new_password": "new-pass1"},
        )
        assert complete.status_code == 200
        token = complete.json()["access_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "user@example.com"

        old_login = client.post("/api/auth/login", json={"email": "user@example.com", "password": "old-pass1"})
        assert old_login.status_code == 401

        new_login = client.post("/api/auth/login", json={"email": "user@example.com", "password": "new-pass1"})
        assert new_login.status_code == 200

    actions = audit_actions(auth_db)
    assert "PASSWORD_RESET_SUCCESS" in actions
    assert "LOGIN_FAILED" in actions
    assert "LOGIN_SUCCESS" in actions


def test_upload_endpoints_reject_files_over_size_limit(auth_db, monkeypatch):
    monkeypatch.setattr(config, "UPLOAD_MAX_SIZE_MB", 0)
    user = get_or_create_user("user@example.com", db_path=str(auth_db))
    token = create_access_token(user)
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(server.app) as client:
        kb_response = client.post(
            "/api/kb/upload",
            headers=headers,
            data={"slug": "kb1"},
            files={"files": ("too-large.txt", b"x", "text/plain")},
        )
        template_response = client.post(
            "/api/template/analyze",
            headers=headers,
            files={"file": ("too-large.docx", b"x", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )

    assert kb_response.status_code == 413
    assert kb_response.json()["detail"] == "文件大小超过限制（最大 0MB）"
    assert template_response.status_code == 413
    assert template_response.json()["detail"] == "文件大小超过限制（最大 0MB）"


def test_request_code_rate_limits_same_email(auth_db):
    with TestClient(server.app) as client:
        first = client.post("/api/auth/signup/start", json={"email": "user@example.com", "password": "secret-1"})
        second = client.post("/api/auth/signup/start", json={"email": "USER@example.com", "password": "secret-1"})

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["detail"] == server.RATE_LIMIT_MESSAGE


def test_request_code_rejects_invalid_email_and_protected_api_requires_token(auth_db):
    with TestClient(server.app) as client:
        bad_email = client.post("/api/auth/identify", json={"email": "not-an-email"})
        assert bad_email.status_code == 422

        protected = client.get("/api/kb/list")
        assert protected.status_code == 401
