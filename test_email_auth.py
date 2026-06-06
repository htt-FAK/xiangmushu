import sqlite3
import sys
import types

import pytest
from fastapi.testclient import TestClient

import config
from core.auth import (
    InvalidCodeError,
    InvalidPasswordError,
    consume_verification_code,
    create_access_token,
    create_verification_code,
    get_or_create_user,
    init_db,
    set_password,
    user_from_token,
    verify_password,
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
    monkeypatch.setattr(server, "send_verification_email", lambda email, code: None)
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


def test_password_hash_round_trip():
    password_hash = set_password("correct horse battery staple")

    assert password_hash.startswith("pbkdf2_sha256$")
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_verified_email_creates_one_case_insensitive_user(auth_db):
    create_verification_code("User@Example.com", password="secret-1", code="123456", db_path=str(auth_db))
    first = consume_verification_code(" user@example.com ", "123456", "secret-1", db_path=str(auth_db))

    create_verification_code("USER@example.com", code="654321", db_path=str(auth_db))
    second = consume_verification_code("user@example.com", "654321", "secret-1", db_path=str(auth_db))

    assert first.id == second.id
    assert first.email == "user@example.com"
    assert count_users(auth_db) == 1
    assert verify_password("secret-1", password_hash_for(auth_db, "user@example.com"))


def test_latest_code_supersedes_older_code(auth_db):
    create_verification_code("user@example.com", password="secret-1", code="111111", db_path=str(auth_db))
    create_verification_code("user@example.com", password="secret-1", code="222222", db_path=str(auth_db))

    with pytest.raises(InvalidCodeError):
        consume_verification_code("user@example.com", "111111", "secret-1", db_path=str(auth_db))

    user = consume_verification_code("user@example.com", "222222", "secret-1", db_path=str(auth_db))
    assert user.email == "user@example.com"


def test_password_must_match_for_login(auth_db):
    create_verification_code("user@example.com", password="secret-1", code="123456", db_path=str(auth_db))
    consume_verification_code("user@example.com", "123456", "secret-1", db_path=str(auth_db))

    create_verification_code("user@example.com", code="654321", db_path=str(auth_db))
    with pytest.raises(InvalidPasswordError):
        consume_verification_code("user@example.com", "654321", "wrong-password", db_path=str(auth_db))


def test_jwt_round_trip_loads_user(auth_db):
    user = get_or_create_user("user@example.com", db_path=str(auth_db))
    token = create_access_token(user)

    loaded = user_from_token(token, db_path=str(auth_db))

    assert loaded.id == user.id
    assert loaded.email == "user@example.com"


def test_auth_api_issues_token_and_me_returns_user(auth_db):
    create_verification_code("user@example.com", password="secret-1", code="123456", db_path=str(auth_db))

    with TestClient(server.app) as client:
        response = client.post(
            "/api/auth/verify-code",
            json={"email": "user@example.com", "password": "secret-1", "code": "123456"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "user@example.com"


def test_verify_code_rejects_weak_password(auth_db):
    create_verification_code("user@example.com", password="short1", code="123456", db_path=str(auth_db))

    with TestClient(server.app) as client:
        response = client.post(
            "/api/auth/verify-code",
            json={"email": "user@example.com", "password": "short1", "code": "123456"},
        )

        assert response.status_code == 400
        assert "密码" in response.json()["detail"]


def test_request_code_rate_limits_same_email(auth_db):
    with TestClient(server.app) as client:
        first = client.post(
            "/api/auth/request-code",
            json={"email": "user@example.com", "password": "secret-1"},
        )
        second = client.post(
            "/api/auth/request-code",
            json={"email": "USER@example.com", "password": "secret-1"},
        )

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.json()["detail"] == server.RATE_LIMIT_MESSAGE


def test_request_code_rejects_invalid_email_and_protected_api_requires_token(auth_db):
    with TestClient(server.app) as client:
        bad_email = client.post("/api/auth/request-code", json={"email": "not-an-email"})
        assert bad_email.status_code == 422

        protected = client.get("/api/kb/list")
        assert protected.status_code == 401
