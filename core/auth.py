from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import random
import re
import smtplib
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

import config
from core.db import ensure_configured_database, mysql_enabled, mysql_transaction
from core.provider_registry import load_user_model_choices, save_user_model_choices

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODE_RE = re.compile(r"^\d{6}$")


class AuthError(Exception):
    """Raised when authentication data is invalid."""


class InvalidEmailError(AuthError):
    """Raised when an email address fails validation."""


class InvalidCodeError(AuthError):
    """Raised when a verification code cannot be consumed."""


class InvalidTokenError(AuthError):
    """Raised when a JWT token is invalid or expired."""


class InvalidPasswordError(AuthError):
    """Raised when a password is missing or does not match."""


class InvalidLanguageError(AuthError):
    """Raised when a language preference is invalid."""


@dataclass(frozen=True)
class User:
    id: int
    email: str
    created_at: str
    last_login_at: str | None


@dataclass(frozen=True)
class VerificationCode:
    email: str
    code: str
    expires_at: str


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def normalize_email(email: str) -> str:
    normalized = (email or "").strip().lower()
    if not EMAIL_RE.match(normalized):
        raise InvalidEmailError("Invalid email address")
    return normalized


def generate_code() -> str:
    return f"{random.SystemRandom().randint(0, 999999):06d}"


def _secret_bytes(secret: str | None = None) -> bytes:
    value = (secret or config.AUTH_JWT_SECRET or "").encode("utf-8")
    if not value:
        raise AuthError("JWT secret is not configured")
    return value


def _code_hash(email: str, code: str, secret: str | None = None) -> str:
    payload = f"{email}:{code}".encode("utf-8")
    return hmac.new(_secret_bytes(secret), payload, hashlib.sha256).hexdigest()


def set_password(password: str) -> str:
    value = password or ""
    if not value:
        raise InvalidPasswordError("Password is required")
    iterations = 260_000
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", value.encode("utf-8"), salt, iterations)
    return "$".join(
        [
            "pbkdf2_sha256",
            str(iterations),
            _b64url(salt),
            _b64url(digest),
        ]
    )


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password or not password_hash:
        return False
    try:
        algorithm, iterations_raw, salt_raw, digest_raw = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
        salt = _b64url_decode(salt_raw)
        expected = _b64url_decode(digest_raw)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(expected, actual)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + padding).encode("ascii"))


def _json_b64(payload: dict[str, Any]) -> str:
    return _b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def init_db(db_path: str | None = None) -> None:
    if _use_mysql(db_path):
        ensure_configured_database()
    path = Path(db_path or config.AUTH_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT,
                preferred_language TEXT DEFAULT 'zh',
                created_at TEXT NOT NULL,
                last_login_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS email_verification_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                code_hash TEXT NOT NULL,
                password_hash TEXT,
                expires_at TEXT NOT NULL,
                consumed_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        user_columns = {
            str(row[1]) for row in conn.execute("PRAGMA table_info(users)").fetchall()
        }
        if "password_hash" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN password_hash TEXT")
        if "preferred_language" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN preferred_language TEXT DEFAULT 'zh'")
        if "model_choices" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN model_choices TEXT DEFAULT NULL")
        code_columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(email_verification_codes)").fetchall()
        }
        if "password_hash" not in code_columns:
            conn.execute("ALTER TABLE email_verification_codes ADD COLUMN password_hash TEXT")
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_email_verification_codes_email_created
            ON email_verification_codes(email, created_at DESC)
            """
        )
        conn.commit()
    from core.billing import init_billing_db
    from core.audit_log import init_audit_db

    init_audit_db(str(path))
    init_billing_db(str(path))


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    init_db(db_path)
    conn = sqlite3.connect(db_path or config.AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _use_mysql(db_path: str | None = None) -> bool:
    return db_path is None and mysql_enabled()


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=int(row["id"]),
        email=str(row["email"]),
        created_at=str(row["created_at"]),
        last_login_at=row["last_login_at"],
    )


def _mysql_row_to_user(row: dict[str, Any]) -> User:
    created_at = row.get("created_at")
    last_login_at = row.get("last_login_at")
    return User(
        id=int(row["id"]),
        email=str(row["email"]),
        created_at=created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
        last_login_at=(
            last_login_at.isoformat() if hasattr(last_login_at, "isoformat") else (str(last_login_at) if last_login_at else None)
        ),
    )


def _mysql_json(value: Any) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return {}


def _mysql_timestamp(dt: datetime) -> datetime:
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _parse_db_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return parse_iso(str(value))


def _normalize_language(language: str) -> str:
    value = (language or "").strip().lower()
    if value not in {"zh", "en"}:
        raise InvalidLanguageError("Language must be 'zh' or 'en'")
    return value


def get_user_by_email(email: str, db_path: str | None = None) -> User | None:
    normalized = normalize_email(email)
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
        return _mysql_row_to_user(row) if row else None
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
    return _row_to_user(row) if row else None


def get_password_hash(email: str, db_path: str | None = None) -> str:
    normalized = normalize_email(email)
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT password_hash FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
        return str(row["password_hash"] or "") if row else ""
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?",
            (normalized,),
        ).fetchone()
    return str(row["password_hash"] or "") if row else ""


def get_user_preferences(user_id: int, db_path: str | None = None) -> dict:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(p.preferred_language, u.preferred_language, 'zh') AS preferred_language,
                           COALESCE(p.model_choices_json, u.model_choices_json) AS model_choices_json
                    FROM users u
                    LEFT JOIN user_preferences p ON p.user_id = u.id
                    WHERE u.id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        if row is None:
            raise AuthError("User not found")
        language = str(row.get("preferred_language") or "zh")
        if language not in {"zh", "en"}:
            language = "zh"
        model_choices = _mysql_json(row.get("model_choices_json"))
        registry_choices = load_user_model_choices(user_id)
        if registry_choices:
            model_choices = registry_choices
        return {"language": language, "model_choices": model_choices}
    with _connect(db_path) as conn:
        row = conn.execute(
            "SELECT preferred_language, model_choices FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    if row is None:
        raise AuthError("User not found")
    language = str(row["preferred_language"] or "zh")
    if language not in {"zh", "en"}:
        language = "zh"
    result: dict = {"language": language}
    raw_mc = row["model_choices"] if "model_choices" in row.keys() else None
    if raw_mc:
        try:
            result["model_choices"] = json.loads(raw_mc)
        except (ValueError, TypeError):
            result["model_choices"] = {}
    else:
        result["model_choices"] = {}
    return result


def update_user_preferences(
    user_id: int,
    language: str | None = None,
    model_choices: dict | None = None,
    db_path: str | None = None,
) -> dict:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(p.preferred_language, u.preferred_language, 'zh') AS preferred_language,
                           COALESCE(p.model_choices_json, u.model_choices_json) AS model_choices_json
                    FROM users u
                    LEFT JOIN user_preferences p ON p.user_id = u.id
                    WHERE u.id = %s
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                if row is None:
                    raise AuthError("User not found")
                new_lang = _normalize_language(language) if language else str(row.get("preferred_language") or "zh")
                warnings: dict[str, str] = {}
                if model_choices is not None:
                    new_mc, warnings = save_user_model_choices(user_id, model_choices)
                else:
                    new_mc = _mysql_json(row.get("model_choices_json"))
                encoded = json.dumps(new_mc, ensure_ascii=False)
                cur.execute(
                    """
                    INSERT INTO user_preferences(user_id, preferred_language, model_choices_json)
                    VALUES(%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        preferred_language = VALUES(preferred_language),
                        model_choices_json = VALUES(model_choices_json)
                    """,
                    (user_id, new_lang, encoded),
                )
                cur.execute(
                    "UPDATE users SET preferred_language = %s, model_choices_json = %s WHERE id = %s",
                    (new_lang, encoded, user_id),
                )
        result = {"language": new_lang, "model_choices": new_mc}
        if warnings:
            result["warnings"] = warnings
        return result
    with _connect(db_path) as conn:
        # Fetch current values
        row = conn.execute(
            "SELECT preferred_language, model_choices FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            raise AuthError("User not found")

        new_lang = _normalize_language(language) if language else str(row["preferred_language"] or "zh")
        new_mc = model_choices if model_choices is not None else (
            json.loads(row["model_choices"]) if row["model_choices"] else {}
        )

        conn.execute(
            "UPDATE users SET preferred_language = ?, model_choices = ? WHERE id = ?",
            (new_lang, json.dumps(new_mc, ensure_ascii=False), user_id),
        )
        conn.commit()
    return {"language": new_lang, "model_choices": new_mc}


def get_user_by_id(user_id: int, db_path: str | None = None) -> User | None:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
        return _mysql_row_to_user(row) if row else None
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_or_create_user(email: str, db_path: str | None = None) -> User:
    normalized = normalize_email(email)
    now = iso(utc_now())
    if _use_mysql(db_path):
        now_dt = _mysql_timestamp(utc_now())
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users(email, preferred_language, created_at, last_login_at)
                    VALUES(%s, 'zh', %s, %s)
                    ON DUPLICATE KEY UPDATE last_login_at = VALUES(last_login_at)
                    """,
                    (normalized, now_dt, now_dt),
                )
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
        if row is None:
            raise AuthError("Failed to load authenticated user")
        return _mysql_row_to_user(row)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users(email, created_at, last_login_at)
            VALUES(?, ?, ?)
            ON CONFLICT(email) DO UPDATE SET last_login_at = excluded.last_login_at
            """,
            (normalized, now, now),
        )
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        conn.commit()
    if row is None:
        raise AuthError("Failed to load authenticated user")
    return _row_to_user(row)


def _create_user_with_password(
    email: str,
    password_hash: str,
    db_path: str | None = None,
) -> User:
    normalized = normalize_email(email)
    now = iso(utc_now())
    if _use_mysql(db_path):
        now_dt = _mysql_timestamp(utc_now())
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users(email, password_hash, preferred_language, is_verified, created_at, last_login_at)
                    VALUES(%s, %s, 'zh', 1, %s, %s)
                    """,
                    (normalized, password_hash, now_dt, now_dt),
                )
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
        if row is None:
            raise AuthError("Failed to load authenticated user")
        return _mysql_row_to_user(row)
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO users(email, password_hash, created_at, last_login_at)
            VALUES(?, ?, ?, ?)
            """,
            (normalized, password_hash, now, now),
        )
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        conn.commit()
    if row is None:
        raise AuthError("Failed to load authenticated user")
    return _row_to_user(row)


def create_verification_code(
    email: str,
    *,
    password: str | None = None,
    code: str | None = None,
    ttl_minutes: int | None = None,
    db_path: str | None = None,
) -> VerificationCode:
    normalized = normalize_email(email)
    code_value = code or generate_code()
    if not CODE_RE.match(code_value):
        raise InvalidCodeError("Verification code must be six digits")
    pending_password_hash = set_password(password) if password is not None else None
    expires_at = utc_now() + timedelta(minutes=ttl_minutes or config.AUTH_CODE_TTL_MINUTES)
    if _use_mysql(db_path):
        now_dt = _mysql_timestamp(utc_now())
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO email_verification_codes(email, code_hash, password_hash, purpose, expires_at, created_at)
                    VALUES(%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        normalized,
                        _code_hash(normalized, code_value),
                        pending_password_hash,
                        "register" if pending_password_hash else "login",
                        _mysql_timestamp(expires_at),
                        now_dt,
                    ),
                )
        return VerificationCode(email=normalized, code=code_value, expires_at=iso(expires_at))
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO email_verification_codes(email, code_hash, password_hash, expires_at, created_at)
            VALUES(?, ?, ?, ?, ?)
            """,
            (
                normalized,
                _code_hash(normalized, code_value),
                pending_password_hash,
                iso(expires_at),
                iso(utc_now()),
            ),
        )
        conn.commit()
    return VerificationCode(email=normalized, code=code_value, expires_at=iso(expires_at))


def consume_verification_code(
    email: str,
    code: str,
    password: str | None = None,
    db_path: str | None = None,
) -> User:
    normalized = normalize_email(email)
    if not CODE_RE.match(code or ""):
        raise InvalidCodeError("Invalid verification code")
    pending_password_hash: str | None = None
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM email_verification_codes
                    WHERE email = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (normalized,),
                )
                row = cur.fetchone()
                if row is None or row.get("consumed_at") is not None:
                    raise InvalidCodeError("Invalid verification code")
                if _parse_db_time(row["expires_at"]) <= utc_now():
                    raise InvalidCodeError("Invalid verification code")
                expected = str(row["code_hash"])
                actual = _code_hash(normalized, code)
                if not hmac.compare_digest(expected, actual):
                    raise InvalidCodeError("Invalid verification code")
                pending_password_hash = row.get("password_hash")
                cur.execute(
                    "UPDATE email_verification_codes SET consumed_at = %s WHERE id = %s",
                    (_mysql_timestamp(utc_now()), row["id"]),
                )

        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                user_row = cur.fetchone()
                if user_row is not None:
                    stored_password_hash = user_row.get("password_hash")
                    if not verify_password(password or "", stored_password_hash):
                        raise InvalidCodeError("Invalid verification code")
                    cur.execute(
                        "UPDATE users SET last_login_at = %s WHERE id = %s",
                        (_mysql_timestamp(utc_now()), user_row["id"]),
                    )
                    cur.execute("SELECT * FROM users WHERE id = %s", (user_row["id"],))
                    updated = cur.fetchone()
                    if updated is None:
                        raise AuthError("Failed to load authenticated user")
                    return _mysql_row_to_user(updated)

        if not pending_password_hash or not verify_password(password or "", pending_password_hash):
            raise InvalidCodeError("Invalid verification code")
        return _create_user_with_password(normalized, pending_password_hash, db_path)

    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM email_verification_codes
            WHERE email = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        if row is None or row["consumed_at"] is not None:
            raise InvalidCodeError("Invalid verification code")
        if parse_iso(str(row["expires_at"])) <= utc_now():
            raise InvalidCodeError("Invalid verification code")
        expected = str(row["code_hash"])
        actual = _code_hash(normalized, code)
        if not hmac.compare_digest(expected, actual):
            raise InvalidCodeError("Invalid verification code")
        pending_password_hash = row["password_hash"]
        conn.execute(
            "UPDATE email_verification_codes SET consumed_at = ? WHERE id = ?",
            (iso(utc_now()), row["id"]),
        )
        conn.commit()

    with _connect(db_path) as conn:
        user_row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        if user_row is not None:
            stored_password_hash = user_row["password_hash"]
            if not verify_password(password or "", stored_password_hash):
                raise InvalidCodeError("Invalid verification code")
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (iso(utc_now()), user_row["id"]),
            )
            updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_row["id"],)).fetchone()
            conn.commit()
            if updated is None:
                raise AuthError("Failed to load authenticated user")
            return _row_to_user(updated)

    if not pending_password_hash or not verify_password(password or "", pending_password_hash):
        raise InvalidCodeError("Invalid verification code")
    return _create_user_with_password(normalized, pending_password_hash, db_path)


def reset_password_with_code(
    email: str,
    code: str,
    new_password: str,
    db_path: str | None = None,
) -> User:
    normalized = normalize_email(email)
    if not CODE_RE.match(code or ""):
        raise InvalidCodeError("Invalid verification code")

    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM email_verification_codes
                    WHERE email = %s AND consumed_at IS NULL
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """,
                    (normalized,),
                )
                row = cur.fetchone()
                if row is None:
                    raise InvalidCodeError("Invalid verification code")
                if _parse_db_time(row["expires_at"]) <= utc_now():
                    raise InvalidCodeError("Invalid verification code")
                expected = str(row["code_hash"])
                actual = _code_hash(normalized, code)
                if not hmac.compare_digest(expected, actual):
                    raise InvalidCodeError("Invalid verification code")

                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                user_row = cur.fetchone()
                if user_row is None:
                    raise InvalidCodeError("Invalid verification code")

                cur.execute(
                    """
                    UPDATE users
                    SET password_hash = %s, is_verified = 1, last_login_at = %s
                    WHERE id = %s
                    """,
                    (set_password(new_password), _mysql_timestamp(utc_now()), user_row["id"]),
                )
                cur.execute(
                    "UPDATE email_verification_codes SET consumed_at = %s WHERE id = %s",
                    (_mysql_timestamp(utc_now()), row["id"]),
                )
                cur.execute("SELECT * FROM users WHERE id = %s", (user_row["id"],))
                updated = cur.fetchone()
        if updated is None:
            raise AuthError("Failed to load authenticated user")
        return _mysql_row_to_user(updated)

    with _connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT * FROM email_verification_codes
            WHERE email = ? AND consumed_at IS NULL
            ORDER BY created_at DESC, id DESC
            LIMIT 1
            """,
            (normalized,),
        ).fetchone()
        if row is None:
            raise InvalidCodeError("Invalid verification code")
        if parse_iso(str(row["expires_at"])) <= utc_now():
            raise InvalidCodeError("Invalid verification code")
        expected = str(row["code_hash"])
        actual = _code_hash(normalized, code)
        if not hmac.compare_digest(expected, actual):
            raise InvalidCodeError("Invalid verification code")

        user_row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        if user_row is None:
            raise InvalidCodeError("Invalid verification code")

        conn.execute(
            """
            UPDATE users
            SET password_hash = ?, last_login_at = ?
            WHERE id = ?
            """,
            (set_password(new_password), iso(utc_now()), user_row["id"]),
        )
        conn.execute(
            "UPDATE email_verification_codes SET consumed_at = ? WHERE id = ?",
            (iso(utc_now()), row["id"]),
        )
        updated = conn.execute("SELECT * FROM users WHERE id = ?", (user_row["id"],)).fetchone()
        conn.commit()

    if updated is None:
        raise AuthError("Failed to load authenticated user")
    return _row_to_user(updated)


def create_access_token(
    user: User,
    *,
    expires_minutes: int | None = None,
    secret: str | None = None,
) -> str:
    now = utc_now()
    exp = now + timedelta(minutes=expires_minutes or config.AUTH_JWT_EXPIRE_MINUTES)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
    }
    signing_input = f"{_json_b64(header)}.{_json_b64(payload)}"
    signature = hmac.new(_secret_bytes(secret), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def decode_access_token(token: str, *, secret: str | None = None) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(
            _secret_bytes(secret),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected, actual):
            raise InvalidTokenError("Invalid token signature")
        header = json.loads(_b64url_decode(header_b64))
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, json.JSONDecodeError, TypeError) as exc:
        raise InvalidTokenError("Invalid token") from exc
    if header.get("alg") != "HS256":
        raise InvalidTokenError("Invalid token algorithm")
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= int(utc_now().timestamp()):
        raise InvalidTokenError("Token has expired")
    return payload


def user_from_token(token: str, db_path: str | None = None) -> User:
    payload = decode_access_token(token)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError("Invalid token subject") from exc
    user = get_user_by_id(user_id, db_path)
    if user is None:
        raise InvalidTokenError("User no longer exists")
    return user


def send_verification_email(email: str, code: str, purpose: str = "register") -> None:
    if not config.AUTH_SMTP_HOST:
        logger.warning(
            "AUTH_SMTP_HOST is not configured; verification code for %s is %s",
            email,
            code,
        )
        return

    message = EmailMessage()
    subject_prefix = "重置密码验证码" if purpose == "reset_password" else "注册验证码"
    message["Subject"] = f"【项目书智能体】{subject_prefix} {code}"
    message["From"] = config.AUTH_SMTP_FROM or config.AUTH_SMTP_USERNAME
    message["To"] = email

    html_body = f"""\
<div style="font-family: -apple-system, 'Microsoft YaHei', sans-serif; max-width: 480px; margin: 0 auto; padding: 32px 24px; background: #ffffff; border-radius: 12px; border: 1px solid #e5e7eb;">
  <div style="text-align: center; margin-bottom: 24px;">
    <h1 style="margin: 0; font-size: 20px; color: #111827;">项目书智能体</h1>
    <p style="margin: 4px 0 0; font-size: 13px; color: #6b7280;">AI 驱动的项目文档生成平台</p>
  </div>
  <div style="background: #f9fafb; border-radius: 8px; padding: 24px; text-align: center; margin-bottom: 24px;">
    <p style="margin: 0 0 8px; font-size: 14px; color: #374151;">您的验证码是</p>
    <div style="font-size: 36px; font-weight: 700; letter-spacing: 8px; color: #111827; font-family: 'Courier New', monospace;">{code}</div>
    <p style="margin: 12px 0 0; font-size: 13px; color: #6b7280;">有效期 {config.AUTH_CODE_TTL_MINUTES} 分钟，请勿泄露给他人</p>
  </div>
  <p style="margin: 0; font-size: 12px; color: #9ca3af; text-align: center;">如非本人操作，请忽略此邮件。</p>
</div>"""

    message.set_content(f"您的验证码是 {code}，有效期 {config.AUTH_CODE_TTL_MINUTES} 分钟。")
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(config.AUTH_SMTP_HOST, config.AUTH_SMTP_PORT, timeout=15) as smtp:
        if config.AUTH_SMTP_USE_TLS:
            smtp.starttls()
        if config.AUTH_SMTP_USERNAME:
            smtp.login(config.AUTH_SMTP_USERNAME, config.AUTH_SMTP_PASSWORD)
        smtp.send_message(message)
