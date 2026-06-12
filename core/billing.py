from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
from dataclasses import dataclass
from typing import Any

import config
from core.auth import iso, utc_now
from core.db import mysql_enabled, mysql_transaction


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0


def normalize_usage(usage: Any) -> TokenUsage:
    if usage is None:
        return TokenUsage()
    if isinstance(usage, dict):
        prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    else:
        prompt = getattr(usage, "prompt_tokens", getattr(usage, "input_tokens", 0))
        completion = getattr(usage, "completion_tokens", getattr(usage, "output_tokens", 0))
    try:
        input_tokens = max(0, int(prompt or 0))
    except (TypeError, ValueError):
        input_tokens = 0
    try:
        output_tokens = max(0, int(completion or 0))
    except (TypeError, ValueError):
        output_tokens = 0
    return TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens)


def calculate_cost_cny(model: str, input_tokens: int, output_tokens: int) -> float:
    price = getattr(config, "AI_MODEL_PRICING", {}).get(model or "", {})
    input_price = float(price.get("input", 0) or 0)
    output_price = float(price.get("output", 0) or 0)
    return round((input_tokens / 1000 * input_price) + (output_tokens / 1000 * output_price), 8)


def init_billing_db(db_path: str | None = None) -> None:
    with sqlite3.connect(db_path or config.AUTH_DB_PATH) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS billing_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost_cny REAL NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_billing_records_user_created
            ON billing_records(user_id, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_api_keys (
                user_id INTEGER PRIMARY KEY,
                encrypted_api_key TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )
        conn.commit()


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    init_billing_db(db_path)
    conn = sqlite3.connect(db_path or config.AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _use_mysql(db_path: str | None = None) -> bool:
    return db_path is None and mysql_enabled()


def _default_provider_id(conn) -> int | None:
    return _provider_id_for_code(conn, "dashscope")


def _provider_id_for_code(conn, provider_code: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM model_providers WHERE code = %s LIMIT 1", (provider_code,))
        row = cur.fetchone()
    return int(row["id"]) if row else None


def record_billing(
    user_id: int,
    model: str,
    usage: TokenUsage,
    db_path: str | None = None,
    generation_session_id: int | None = None,
    generated_article_id: int | None = None,
    module_key: str | None = None,
    provider_code: str = "dashscope",
) -> dict[str, Any] | None:
    if usage.input_tokens <= 0 and usage.output_tokens <= 0:
        return None
    cost = calculate_cost_cny(model, usage.input_tokens, usage.output_tokens)
    created_at = iso(utc_now())
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO billing_records(
                        owner_user_id, generation_session_id, generated_article_id,
                        provider_code, model, module_key, input_tokens, output_tokens, cost_cny, created_at
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        generation_session_id,
                        generated_article_id,
                        provider_code,
                        model or "",
                        module_key,
                        usage.input_tokens,
                        usage.output_tokens,
                        cost,
                        utc_now().replace(tzinfo=None),
                    ),
                )
                record_id = int(cur.lastrowid)
        return {
            "id": record_id,
            "model": model or "",
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "cost_cny": cost,
            "created_at": created_at,
        }
    with _connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO billing_records(user_id, model, input_tokens, output_tokens, cost_cny, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (user_id, model or "", usage.input_tokens, usage.output_tokens, cost, created_at),
        )
        conn.commit()
        record_id = int(cursor.lastrowid)
    return {
        "id": record_id,
        "model": model or "",
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
        "cost_cny": cost,
        "created_at": created_at,
    }


def billing_summary(user_id: int, db_path: str | None = None) -> dict[str, Any]:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(input_tokens), 0) AS input_tokens,
                        COALESCE(SUM(output_tokens), 0) AS output_tokens,
                        COALESCE(SUM(cost_cny), 0) AS cost_cny,
                        COUNT(*) AS generation_count
                    FROM billing_records
                    WHERE owner_user_id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        return {
            "input_tokens": int(row["input_tokens"] or 0),
            "output_tokens": int(row["output_tokens"] or 0),
            "cost_cny": round(float(row["cost_cny"] or 0), 8),
            "generation_count": int(row["generation_count"] or 0),
        }
    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                COALESCE(SUM(input_tokens), 0) AS input_tokens,
                COALESCE(SUM(output_tokens), 0) AS output_tokens,
                COALESCE(SUM(cost_cny), 0) AS cost_cny,
                COUNT(*) AS generation_count
            FROM billing_records
            WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
    return {
        "input_tokens": int(row["input_tokens"] or 0),
        "output_tokens": int(row["output_tokens"] or 0),
        "cost_cny": round(float(row["cost_cny"] or 0), 8),
        "generation_count": int(row["generation_count"] or 0),
    }


def _fernet_key(secret: str | None = None) -> bytes:
    raw = (secret or config.USER_API_KEY_ENCRYPTION_KEY or "").strip()
    if raw:
        try:
            decoded = base64.urlsafe_b64decode(raw.encode("ascii"))
            if len(decoded) == 32:
                return raw.encode("ascii")
        except Exception:
            pass
    digest = hashlib.sha256(raw.encode("utf-8") or os.urandom(32)).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_api_key(api_key: str) -> str:
    value = (api_key or "").strip()
    if not value:
        raise ValueError("API key is required")
    try:
        from cryptography.fernet import Fernet

        return "fernet:" + Fernet(_fernet_key()).encrypt(value.encode("utf-8")).decode("ascii")
    except Exception:
        key = hashlib.sha256(_fernet_key()).digest()
        nonce = os.urandom(16)
        stream = hashlib.pbkdf2_hmac("sha256", key, nonce, 1000, dklen=len(value.encode("utf-8")))
        cipher = bytes(a ^ b for a, b in zip(value.encode("utf-8"), stream))
        mac = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        return "simple:" + base64.urlsafe_b64encode(nonce + mac + cipher).decode("ascii")


def decrypt_api_key(encrypted: str) -> str:
    if encrypted.startswith("fernet:"):
        from cryptography.fernet import Fernet

        return Fernet(_fernet_key()).decrypt(encrypted.removeprefix("fernet:").encode("ascii")).decode("utf-8")
    if encrypted.startswith("simple:"):
        payload = base64.urlsafe_b64decode(encrypted.removeprefix("simple:").encode("ascii"))
        nonce, mac, cipher = payload[:16], payload[16:48], payload[48:]
        key = hashlib.sha256(_fernet_key()).digest()
        expected = hmac.new(key, nonce + cipher, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected):
            raise ValueError("Invalid encrypted API key")
        stream = hashlib.pbkdf2_hmac("sha256", key, nonce, 1000, dklen=len(cipher))
        return bytes(a ^ b for a, b in zip(cipher, stream)).decode("utf-8")
    raise ValueError("Unsupported encrypted API key")


def save_user_api_key(
    user_id: int,
    api_key: str,
    db_path: str | None = None,
    validation: dict[str, Any] | None = None,
    provider_code: str = "dashscope",
) -> None:
    now = iso(utc_now())
    encrypted = encrypt_api_key(api_key)
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            provider_id = _provider_id_for_code(conn, provider_code)
            if provider_id is None:
                raise RuntimeError("Default model provider is missing; run MySQL migrations first.")
            key_hint = None
            value = (api_key or "").strip()
            if value:
                key_hint = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "****"
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO provider_credentials(
                        owner_user_id, provider_id, encrypted_api_key, key_hint, status,
                        validation_json, validated_at, created_at, updated_at
                    )
                    VALUES(%s, %s, %s, %s, 'validated', %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        encrypted_api_key = VALUES(encrypted_api_key),
                        key_hint = VALUES(key_hint),
                        status = VALUES(status),
                        validation_json = VALUES(validation_json),
                        validated_at = VALUES(validated_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        user_id,
                        provider_id,
                        encrypted,
                        key_hint,
                        json.dumps(validation or {}, ensure_ascii=False),
                        utc_now().replace(tzinfo=None),
                        utc_now().replace(tzinfo=None),
                        utc_now().replace(tzinfo=None),
                    ),
                )
        return
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO user_api_keys(user_id, encrypted_api_key, created_at, updated_at)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                encrypted_api_key = excluded.encrypted_api_key,
                updated_at = excluded.updated_at
            """,
            (user_id, encrypted, now, now),
        )
        conn.commit()


def get_user_api_key_status(user_id: int, db_path: str | None = None) -> dict[str, Any]:
    return get_provider_api_key_status(user_id, "dashscope", db_path=db_path)


def get_provider_api_key_status(user_id: int, provider_code: str, db_path: str | None = None) -> dict[str, Any]:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            provider_id = _provider_id_for_code(conn, provider_code)
            if provider_id is None:
                return {
                    "has_key": False,
                    "validated": False,
                    "created_at": None,
                    "updated_at": None,
                    "key_preview": None,
                }
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT encrypted_api_key, key_hint, status, created_at, updated_at
                    FROM provider_credentials
                    WHERE owner_user_id = %s AND provider_id = %s
                    """,
                    (user_id, provider_id),
                )
                row = cur.fetchone()
        if row is None:
            return {
                "has_key": False,
                "validated": False,
                "created_at": None,
                "updated_at": None,
                "key_preview": None,
            }
        created_at = row.get("created_at")
        updated_at = row.get("updated_at")
        return {
            "has_key": True,
            "validated": str(row.get("status") or "") == "validated",
            "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
            "key_preview": row.get("key_hint") or "****",
        }
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT encrypted_api_key, created_at, updated_at FROM user_api_keys WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return {
            "has_key": False,
            "validated": False,
            "created_at": None,
            "updated_at": None,
            "key_preview": None,
        }
    preview = None
    try:
        decrypted = decrypt_api_key(str(row["encrypted_api_key"]))
        if decrypted and len(decrypted) > 8:
            preview = f"{decrypted[:4]}{'*' * (len(decrypted) - 8)}{decrypted[-4:]}"
        elif decrypted:
            preview = "****"
    except Exception:
        preview = "****"
    return {
        "has_key": True,
        "validated": True,
        "created_at": str(row["created_at"]),
        "updated_at": str(row["updated_at"]),
        "key_preview": preview,
    }


def load_user_api_key(user_id: int, db_path: str | None = None) -> str | None:
    return load_provider_api_key(user_id, "dashscope", db_path=db_path)


def load_provider_api_key(user_id: int, provider_code: str, db_path: str | None = None) -> str | None:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            provider_id = _provider_id_for_code(conn, provider_code)
            if provider_id is None:
                return None
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT encrypted_api_key
                    FROM provider_credentials
                    WHERE owner_user_id = %s AND provider_id = %s
                    """,
                    (user_id, provider_id),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return decrypt_api_key(str(row["encrypted_api_key"]))
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT encrypted_api_key FROM user_api_keys WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        return None
    return decrypt_api_key(str(row["encrypted_api_key"]))


def delete_user_api_key(user_id: int, db_path: str | None = None) -> None:
    delete_provider_api_key(user_id, "dashscope", db_path=db_path)


def delete_provider_api_key(user_id: int, provider_code: str, db_path: str | None = None) -> None:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            provider_id = _provider_id_for_code(conn, provider_code)
            if provider_id is None:
                return
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM provider_credentials WHERE owner_user_id = %s AND provider_id = %s",
                    (user_id, provider_id),
                )
        return
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM user_api_keys WHERE user_id = ?", (user_id,))
        conn.commit()
