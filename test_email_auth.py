import sqlite3
import sys
import types

import pytest
from fastapi.testclient import TestClient

import config
from core.auth import (
    InvalidCodeError,
    consume_verification_code,
    create_access_token,
    create_verification_code,
    get_or_create_user,
    init_db,
    user_from_token,
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
    init_db(str(db_path))
    return db_path


def count_users(db_path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def test_verified_email_creates_one_case_insensitive_user(auth_db):
    create_verification_code("User@Example.com", code="123456", db_path=str(auth_db))
    first = consume_verification_code(" user@example.com ", "123456", db_path=str(auth_db))

    create_verification_code("USER@example.com", code="654321", db_path=str(auth_db))
    second = consume_verification_code("user@example.com", "654321", db_path=str(auth_db))

    assert first.id == second.id
    assert first.email == "user@example.com"
    assert count_users(auth_db) == 1


def test_latest_code_supersedes_older_code(auth_db):
    create_verification_code("user@example.com", code="111111", db_path=str(auth_db))
    create_verification_code("user@example.com", code="222222", db_path=str(auth_db))

    with pytest.raises(InvalidCodeError):
        consume_verification_code("user@example.com", "111111", db_path=str(auth_db))

    user = consume_verification_code("user@example.com", "222222", db_path=str(auth_db))
    assert user.email == "user@example.com"


def test_jwt_round_trip_loads_user(auth_db):
    user = get_or_create_user("user@example.com", db_path=str(auth_db))
    token = create_access_token(user)

    loaded = user_from_token(token, db_path=str(auth_db))

    assert loaded.id == user.id
    assert loaded.email == "user@example.com"


def test_auth_api_issues_token_and_me_returns_user(auth_db):
    create_verification_code("user@example.com", code="123456", db_path=str(auth_db))

    with TestClient(server.app) as client:
        response = client.post(
            "/api/auth/verify-code",
            json={"email": "user@example.com", "code": "123456"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

        me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "user@example.com"


def test_request_code_rejects_invalid_email_and_protected_api_requires_token(auth_db):
    with TestClient(server.app) as client:
        bad_email = client.post("/api/auth/request-code", json={"email": "not-an-email"})
        assert bad_email.status_code == 422

        protected = client.get("/api/kb/list")
        assert protected.status_code == 401
