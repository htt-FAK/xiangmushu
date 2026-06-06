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


def _connect(db_path: str | None = None) -> sqlite3.Connection:
    init_db(db_path)
    conn = sqlite3.connect(db_path or config.AUTH_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _row_to_user(row: sqlite3.Row) -> User:
    return User(
        id=int(row["id"]),
        email=str(row["email"]),
        created_at=str(row["created_at"]),
        last_login_at=row["last_login_at"],
    )


def get_user_by_email(email: str, db_path: str | None = None) -> User | None:
    normalized = normalize_email(email)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: int, db_path: str | None = None) -> User | None:
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_or_create_user(email: str, db_path: str | None = None) -> User:
    normalized = normalize_email(email)
    now = iso(utc_now())
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
            raise InvalidCodeError("Verification code has expired")
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
                raise InvalidPasswordError("Invalid email, password, or verification code")
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
        raise InvalidPasswordError("Invalid email, password, or verification code")
    return _create_user_with_password(normalized, pending_password_hash, db_path)


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


def send_verification_email(email: str, code: str) -> None:
    if not config.AUTH_SMTP_HOST:
        logger.warning(
            "AUTH_SMTP_HOST is not configured; verification code for %s is %s",
            email,
            code,
        )
        return

    message = EmailMessage()
    message["Subject"] = "Your verification code"
    message["From"] = config.AUTH_SMTP_FROM or config.AUTH_SMTP_USERNAME
    message["To"] = email
    message.set_content(f"Your verification code is {code}. It expires in {config.AUTH_CODE_TTL_MINUTES} minutes.")

    with smtplib.SMTP(config.AUTH_SMTP_HOST, config.AUTH_SMTP_PORT, timeout=15) as smtp:
        if config.AUTH_SMTP_USE_TLS:
            smtp.starttls()
        if config.AUTH_SMTP_USERNAME:
            smtp.login(config.AUTH_SMTP_USERNAME, config.AUTH_SMTP_PASSWORD)
        smtp.send_message(message)
