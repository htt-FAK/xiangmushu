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


class EmailExistsError(AuthError):
    """Raised when an email already belongs to an active account."""


class EmailNotFoundError(AuthError):
    """Raised when an email does not belong to a usable account."""


class AccountNotVerifiedError(AuthError):
    """Raised when an account exists but is not verified yet."""


class AccountRestrictedError(AuthError):
    """Raised when an account is not allowed to continue auth flows."""


class ChallengeExpiredError(InvalidCodeError):
    """Raised when an auth challenge has expired."""


class ChallengeSupersededError(InvalidCodeError):
    """Raised when an older challenge has been replaced by a newer one."""


class ChallengeConsumedError(InvalidCodeError):
    """Raised when an auth challenge has already been used."""


class ChallengePurposeError(InvalidCodeError):
    """Raised when a challenge is used for the wrong auth purpose."""


class RecoveryTokenError(AuthError):
    """Raised when a password recovery token is invalid."""


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
    is_verified: bool = True
    is_active: bool = True


@dataclass(frozen=True)
class VerificationCode:
    email: str
    code: str
    expires_at: str


SIGNUP_CHALLENGE = "signup_verify"
RECOVERY_CHALLENGE = "password_recovery"
MAGIC_LOGIN_CHALLENGE = "magic_login"
ACTIVE_ACCOUNT = "existing_verified"
UNVERIFIED_ACCOUNT = "existing_unverified"
UNKNOWN_ACCOUNT = "unknown_email"
RESTRICTED_ACCOUNT = "restricted"


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


def _challenge_hash(email: str, purpose: str, code: str, secret: str | None = None) -> str:
    payload = f"{purpose}:{email}:{code}".encode("utf-8")
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
                is_active INTEGER NOT NULL DEFAULT 1,
                is_verified INTEGER NOT NULL DEFAULT 0,
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
                purpose TEXT NOT NULL DEFAULT 'signup_verify',
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
        if "is_active" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_active INTEGER NOT NULL DEFAULT 1")
        if "is_verified" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_verified INTEGER NOT NULL DEFAULT 0")
        if "model_choices" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN model_choices TEXT DEFAULT NULL")
        conn.execute(
            "UPDATE users SET is_verified = 1 WHERE password_hash IS NOT NULL AND last_login_at IS NOT NULL"
        )
        conn.execute("UPDATE users SET is_active = 1 WHERE is_active IS NULL")
        code_columns = {
            str(row[1])
            for row in conn.execute("PRAGMA table_info(email_verification_codes)").fetchall()
        }
        if "password_hash" not in code_columns:
            conn.execute("ALTER TABLE email_verification_codes ADD COLUMN password_hash TEXT")
        if "purpose" not in code_columns:
            conn.execute(
                f"ALTER TABLE email_verification_codes ADD COLUMN purpose TEXT NOT NULL DEFAULT '{SIGNUP_CHALLENGE}'"
            )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_email_verification_codes_email_created
            ON email_verification_codes(email, created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_email_verification_codes_email_purpose_created
            ON email_verification_codes(email, purpose, created_at DESC)
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
        is_verified=_row_bool(row, "is_verified", default=bool(row["password_hash"] and row["last_login_at"])),
        is_active=_row_bool(row, "is_active", default=True),
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
        is_verified=_row_bool(row, "is_verified", default=bool(row.get("password_hash") and last_login_at)),
        is_active=_row_bool(row, "is_active", default=True),
    )


def _row_bool(row: Any, key: str, *, default: bool = False) -> bool:
    value = _row_get(row, key, default)
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return bool(int(value)) if isinstance(value, (int, str)) and str(value).isdigit() else bool(value)


def _row_get(row: Any, key: str, default: Any = None) -> Any:
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except Exception:
        return default


def _account_state_from_row(row: Any) -> str:
    if row is None:
        return UNKNOWN_ACCOUNT
    if not _row_bool(row, "is_active", default=True):
        return RESTRICTED_ACCOUNT
    if _row_bool(row, "is_verified", default=bool(_row_get(row, "password_hash") and _row_get(row, "last_login_at"))):
        return ACTIVE_ACCOUNT
    return UNVERIFIED_ACCOUNT


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
        try:
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
            warnings: dict[str, str] = {}
            try:
                registry_choices = load_user_model_choices(user_id)
                if registry_choices:
                    model_choices = registry_choices
            except Exception as exc:
                logger.warning("Falling back to JSON-backed model choices for user %s: %s", user_id, exc)
                warning = "数据库连接降级：无法通过注册表验证，显示为最后一次保存的配置"
                warnings = {role: warning for role in model_choices}
            result = {"language": language, "model_choices": model_choices}
            if warnings:
                result["warnings"] = warnings
            return result
        except Exception as db_exc:
            logger.exception("MySQL connection failed in get_user_preferences for user %s", user_id)
            warnings = {"database": "数据库连接异常：无法连接至 MySQL 数据库。配置暂以降级默认值运行。"}
            return {"language": "zh", "model_choices": {}, "warnings": warnings}
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
                    INSERT INTO users(email, preferred_language, is_active, is_verified, created_at, last_login_at)
                    VALUES(%s, 'zh', 1, 1, %s, %s)
                    ON DUPLICATE KEY UPDATE last_login_at = VALUES(last_login_at), is_active = 1, is_verified = 1
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
            INSERT INTO users(email, is_active, is_verified, created_at, last_login_at)
            VALUES(?, 1, 1, ?, ?)
            ON CONFLICT(email) DO UPDATE SET last_login_at = excluded.last_login_at, is_active = 1, is_verified = 1
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
            INSERT INTO users(email, password_hash, is_active, is_verified, created_at, last_login_at)
            VALUES(?, ?, 1, 1, ?, ?)
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
    purpose: str = SIGNUP_CHALLENGE,
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
    challenge_hash = _challenge_hash(normalized, purpose, code_value)
    if purpose == SIGNUP_CHALLENGE and pending_password_hash:
        _create_or_update_pending_user(normalized, pending_password_hash, db_path)
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
                        challenge_hash,
                        pending_password_hash,
                        purpose,
                        _mysql_timestamp(expires_at),
                        now_dt,
                    ),
                )
        return VerificationCode(email=normalized, code=code_value, expires_at=iso(expires_at))
    with _connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO email_verification_codes(email, code_hash, password_hash, purpose, expires_at, created_at)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (
                normalized,
                challenge_hash,
                pending_password_hash,
                purpose,
                iso(expires_at),
                iso(utc_now()),
            ),
        )
        conn.commit()
    return VerificationCode(email=normalized, code=code_value, expires_at=iso(expires_at))


def get_account_state(email: str, db_path: str | None = None) -> str:
    normalized = normalize_email(email)
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
        return _account_state_from_row(row)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
    return _account_state_from_row(row)


def _ensure_signup_allowed(email: str, db_path: str | None = None) -> str:
    normalized = normalize_email(email)
    state = get_account_state(normalized, db_path)
    if state == ACTIVE_ACCOUNT:
        raise EmailExistsError("Email already registered")
    if state == RESTRICTED_ACCOUNT:
        raise AccountRestrictedError("Account is restricted")
    return normalized


def _ensure_recovery_allowed(email: str, db_path: str | None = None) -> str:
    normalized = normalize_email(email)
    state = get_account_state(normalized, db_path)
    if state == UNKNOWN_ACCOUNT:
        raise EmailNotFoundError("Email is not registered")
    if state == RESTRICTED_ACCOUNT:
        raise AccountRestrictedError("Account is restricted")
    if state == UNVERIFIED_ACCOUNT:
        raise AccountNotVerifiedError("Account is not verified")
    return normalized


def _create_or_update_pending_user(email: str, password_hash: str, db_path: str | None = None) -> None:
    normalized = normalize_email(email)
    now = iso(utc_now())
    if _use_mysql(db_path):
        now_dt = _mysql_timestamp(utc_now())
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
                if row is None:
                    cur.execute(
                        """
                        INSERT INTO users(email, password_hash, preferred_language, is_active, is_verified, created_at, last_login_at)
                        VALUES(%s, %s, 'zh', 1, 0, %s, NULL)
                        """,
                        (normalized, password_hash, now_dt),
                    )
                else:
                    if _account_state_from_row(row) == ACTIVE_ACCOUNT:
                        raise EmailExistsError("Email already registered")
                    cur.execute(
                        "UPDATE users SET password_hash = %s, is_active = 1, is_verified = 0 WHERE email = %s",
                        (password_hash, normalized),
                    )
        return
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO users(email, password_hash, preferred_language, is_active, is_verified, created_at, last_login_at)
                VALUES(?, ?, 'zh', 1, 0, ?, NULL)
                """,
                (normalized, password_hash, now),
            )
        else:
            if _account_state_from_row(row) == ACTIVE_ACCOUNT:
                raise EmailExistsError("Email already registered")
            conn.execute(
                "UPDATE users SET password_hash = ?, is_active = 1, is_verified = 0 WHERE email = ?",
                (password_hash, normalized),
            )
        conn.commit()


def start_signup(email: str, password: str, *, code: str | None = None, db_path: str | None = None) -> VerificationCode:
    normalized = _ensure_signup_allowed(email, db_path)
    password_hash = set_password(password)
    _create_or_update_pending_user(normalized, password_hash, db_path)
    return create_verification_code(
        normalized,
        password=password,
        purpose=SIGNUP_CHALLENGE,
        code=code,
        db_path=db_path,
    )


def resend_signup_verification(email: str, *, code: str | None = None, db_path: str | None = None) -> VerificationCode:
    normalized = normalize_email(email)
    state = get_account_state(normalized, db_path)
    if state == ACTIVE_ACCOUNT:
        raise EmailExistsError("Email already registered")
    if state == RESTRICTED_ACCOUNT:
        raise AccountRestrictedError("Account is restricted")
    password_hash = get_password_hash(normalized, db_path)
    if not password_hash:
        raise EmailNotFoundError("Signup is not in progress")
    return create_verification_code(
        normalized,
        purpose=SIGNUP_CHALLENGE,
        code=code,
        db_path=db_path,
    )


def _find_matching_challenge_sqlite(
    email: str,
    purpose: str,
    code: str,
    db_path: str | None = None,
) -> sqlite3.Row | None:
    with _connect(db_path) as conn:
        return conn.execute(
            "SELECT * FROM email_verification_codes WHERE email = ? AND purpose = ? AND code_hash = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (email, purpose, _challenge_hash(email, purpose, code)),
        ).fetchone()


def _find_matching_challenge_mysql(email: str, purpose: str, code: str) -> dict[str, Any] | None:
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM email_verification_codes WHERE email = %s AND purpose = %s AND code_hash = %s ORDER BY created_at DESC, id DESC LIMIT 1",
                (email, purpose, _challenge_hash(email, purpose, code)),
            )
            return cur.fetchone()


def _load_latest_challenge(email: str, purpose: str, db_path: str | None = None) -> Any:
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM email_verification_codes WHERE email = %s AND purpose = %s ORDER BY created_at DESC, id DESC LIMIT 1",
                    (email, purpose),
                )
                return cur.fetchone()
    with _connect(db_path) as conn:
        return conn.execute(
            "SELECT * FROM email_verification_codes WHERE email = ? AND purpose = ? ORDER BY created_at DESC, id DESC LIMIT 1",
            (email, purpose),
        ).fetchone()


def _challenge_mismatch_error(email: str, purpose: str, code: str, db_path: str | None = None) -> InvalidCodeError:
    matching = _find_matching_challenge_mysql(email, purpose, code) if _use_mysql(db_path) else _find_matching_challenge_sqlite(email, purpose, code, db_path)
    if matching is None:
        return InvalidCodeError("Invalid verification code")
    if _row_get(matching, "consumed_at") is not None:
        return ChallengeConsumedError("Challenge already consumed")
    expires_at = _parse_db_time(_row_get(matching, "expires_at"))
    if expires_at <= utc_now():
        return ChallengeExpiredError("Challenge expired")
    return ChallengeSupersededError("Challenge superseded by a newer request")


def _consume_challenge(email: str, purpose: str, code: str, db_path: str | None = None) -> Any:
    normalized = normalize_email(email)
    if not CODE_RE.match(code or ""):
        raise InvalidCodeError("Invalid verification code")
    latest = _load_latest_challenge(normalized, purpose, db_path)
    if latest is None:
        raise InvalidCodeError("Invalid verification code")
    if _row_get(latest, "consumed_at") is not None:
        raise ChallengeConsumedError("Challenge already consumed")
    if _parse_db_time(_row_get(latest, "expires_at")) <= utc_now():
        raise ChallengeExpiredError("Challenge expired")
    actual = _challenge_hash(normalized, purpose, code)
    expected = str(_row_get(latest, "code_hash"))
    if not hmac.compare_digest(expected, actual):
        raise _challenge_mismatch_error(normalized, purpose, code, db_path)
    challenge_id = _row_get(latest, "id")
    consumed_at = _mysql_timestamp(utc_now()) if _use_mysql(db_path) else iso(utc_now())
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE email_verification_codes SET consumed_at = %s WHERE id = %s", (consumed_at, challenge_id))
    else:
        with _connect(db_path) as conn:
            conn.execute("UPDATE email_verification_codes SET consumed_at = ? WHERE id = ?", (consumed_at, challenge_id))
            conn.commit()
    return latest


def verify_signup_code(email: str, code: str, db_path: str | None = None) -> User:
    normalized = normalize_email(email)
    _consume_challenge(normalized, SIGNUP_CHALLENGE, code, db_path)
    now = _mysql_timestamp(utc_now()) if _use_mysql(db_path) else iso(utc_now())
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
                if row is None:
                    raise EmailNotFoundError("Signup is not in progress")
                if _account_state_from_row(row) == ACTIVE_ACCOUNT:
                    raise EmailExistsError("Email already registered")
                cur.execute(
                    "UPDATE users SET is_verified = 1, is_active = 1, last_login_at = %s WHERE email = %s",
                    (now, normalized),
                )
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                updated = cur.fetchone()
        if updated is None:
            raise AuthError("Failed to load authenticated user")
        return _mysql_row_to_user(updated)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        if row is None:
            raise EmailNotFoundError("Signup is not in progress")
        if _account_state_from_row(row) == ACTIVE_ACCOUNT:
            raise EmailExistsError("Email already registered")
        conn.execute(
            "UPDATE users SET is_verified = 1, is_active = 1, last_login_at = ? WHERE email = ?",
            (now, normalized),
        )
        updated = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        conn.commit()
    if updated is None:
        raise AuthError("Failed to load authenticated user")
    return _row_to_user(updated)


def start_password_recovery(email: str, *, code: str | None = None, db_path: str | None = None) -> VerificationCode:
    normalized = _ensure_recovery_allowed(email, db_path)
    return create_verification_code(normalized, purpose=RECOVERY_CHALLENGE, code=code, db_path=db_path)


def _create_signed_token(payload: dict[str, Any], *, secret: str | None = None) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing_input = f"{_json_b64(header)}.{_json_b64(payload)}"
    signature = hmac.new(_secret_bytes(secret), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _decode_signed_token(token: str, *, secret: str | None = None) -> dict[str, Any]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}"
        expected = hmac.new(_secret_bytes(secret), signing_input.encode("ascii"), hashlib.sha256).digest()
        actual = _b64url_decode(signature_b64)
        if not hmac.compare_digest(expected, actual):
            raise RecoveryTokenError("Invalid recovery token")
        payload = json.loads(_b64url_decode(payload_b64))
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise RecoveryTokenError("Invalid recovery token") from exc
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp <= int(utc_now().timestamp()):
        raise RecoveryTokenError("Recovery token expired")
    return payload


def verify_password_recovery_code(email: str, code: str, db_path: str | None = None) -> str:
    normalized = _ensure_recovery_allowed(email, db_path)
    _consume_challenge(normalized, RECOVERY_CHALLENGE, code, db_path)
    payload = {
        "email": normalized,
        "purpose": RECOVERY_CHALLENGE,
        "iat": int(utc_now().timestamp()),
        "exp": int((utc_now() + timedelta(minutes=config.AUTH_CODE_TTL_MINUTES)).timestamp()),
    }
    return _create_signed_token(payload)


def reset_password_with_token(email: str, recovery_token: str, new_password: str, db_path: str | None = None) -> User:
    normalized = normalize_email(email)
    payload = _decode_signed_token(recovery_token)
    if payload.get("purpose") != RECOVERY_CHALLENGE:
        raise RecoveryTokenError("Invalid recovery token purpose")
    if payload.get("email") != normalized:
        raise RecoveryTokenError("Recovery token email mismatch")
    state = get_account_state(normalized, db_path)
    if state == UNKNOWN_ACCOUNT:
        raise EmailNotFoundError("Email is not registered")
    password_hash = set_password(new_password)
    now = _mysql_timestamp(utc_now()) if _use_mysql(db_path) else iso(utc_now())
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET password_hash = %s, is_verified = 1, is_active = 1, last_login_at = %s WHERE email = %s",
                    (password_hash, now, normalized),
                )
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                updated = cur.fetchone()
        if updated is None:
            raise AuthError("Failed to load authenticated user")
        return _mysql_row_to_user(updated)
    with _connect(db_path) as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, is_verified = 1, is_active = 1, last_login_at = ? WHERE email = ?",
            (password_hash, now, normalized),
        )
        updated = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        conn.commit()
    if updated is None:
        raise AuthError("Failed to load authenticated user")
    return _row_to_user(updated)


def authenticate_user(email: str, password: str, db_path: str | None = None) -> User:
    normalized = normalize_email(email)
    state = get_account_state(normalized, db_path)
    if state == UNKNOWN_ACCOUNT:
        raise EmailNotFoundError("Email is not registered")
    if state == RESTRICTED_ACCOUNT:
        raise AccountRestrictedError("Account is restricted")
    if state == UNVERIFIED_ACCOUNT:
        raise AccountNotVerifiedError("Account is not verified")
    password_hash = get_password_hash(normalized, db_path)
    if not verify_password(password, password_hash):
        raise InvalidPasswordError("Email or password is incorrect")
    now = _mysql_timestamp(utc_now()) if _use_mysql(db_path) else iso(utc_now())
    if _use_mysql(db_path):
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE users SET last_login_at = %s WHERE email = %s", (now, normalized))
                cur.execute("SELECT * FROM users WHERE email = %s", (normalized,))
                row = cur.fetchone()
        if row is None:
            raise AuthError("Failed to load authenticated user")
        return _mysql_row_to_user(row)
    with _connect(db_path) as conn:
        conn.execute("UPDATE users SET last_login_at = ? WHERE email = ?", (now, normalized))
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        conn.commit()
    if row is None:
        raise AuthError("Failed to load authenticated user")
    return _row_to_user(row)


def consume_verification_code(
    email: str,
    code: str,
    password: str | None = None,
    db_path: str | None = None,
) -> User:
    return verify_signup_code(email, code, db_path)


def reset_password_with_code(
    email: str,
    code: str,
    new_password: str,
    db_path: str | None = None,
) -> User:
    recovery_token = verify_password_recovery_code(email, code, db_path)
    return reset_password_with_token(email, recovery_token, new_password, db_path)


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
