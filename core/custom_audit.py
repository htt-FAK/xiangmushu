"""Per-user custom OpenAI-compatible audit model.

This module lets a user register their own OpenAI-compatible endpoint
(base_url + model_id + api_key) to use in place of the platform default
``AUDIT_TEXT_MODEL`` during ``ContentAuditor`` audit passes on generated
text segments.

Two persistence paths:
  * MySQL:     ``user_custom_audit_models`` table (see
               ``migrations/mysql/005_user_custom_audit_models.sql``)
  * SQLite:    ``user_custom_audit_models`` inline-DDL created on demand
               via :func:`_ensure_sqlite_table` (mirrors the MySQL schema).

The api_key is encrypted at rest with the same primitive used elsewhere
in the project (``core.billing.encrypt_api_key`` / ``decrypt_api_key``).
"""
from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from core.auth import iso, utc_now
from core.billing import decrypt_api_key, encrypt_api_key
from core.db import mysql_enabled, mysql_transaction

_LOG = logging.getLogger(__name__)

_SQLITE_TABLE = """
CREATE TABLE IF NOT EXISTS user_custom_audit_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id BIGINT NOT NULL UNIQUE,
    name VARCHAR(64) NOT NULL,
    base_url VARCHAR(512) NOT NULL,
    model_id VARCHAR(128) NOT NULL,
    encrypted_api_key TEXT NOT NULL,
    api_key_hint VARCHAR(32) NULL,
    status VARCHAR(16) NOT NULL DEFAULT 'untested',
    validated_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

_SQLITE_TABLE_CREATED: bool = False


@dataclass(frozen=True)
class UserCustomAuditModel:
    id: int
    user_id: int
    name: str
    base_url: str
    model_id: str
    encrypted_api_key: str
    api_key_hint: str | None
    status: str  # "untested" | "validated" | "failed"
    validated_at: str | None  # ISO-8601 or None
    created_at: str | None
    updated_at: str | None

    def api_key_preview(self) -> str:
        return self.api_key_hint or "****"

    def decrypted_api_key(self) -> str:
        return decrypt_api_key(self.encrypted_api_key)

    def as_public_dict(self) -> dict[str, Any]:
        """Return a representation safe for HTTP responses (api_key redacted)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "base_url": self.base_url,
            "model_id": self.model_id,
            "api_key_preview": self.api_key_preview(),
            "status": self.status,
            "validated_at": self.validated_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def _build_key_hint(api_key: str) -> str:
    """Return a redacted preview (first-4 + '...' + last-4) suitable for UI display."""
    value = (api_key or "").strip()
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"


def _encrypt_api_key(plaintext: str) -> str:
    value = (plaintext or "").strip()
    if not value:
        raise ValueError("API key is required")
    return encrypt_api_key(value)


def _decrypt_api_key(ciphertext: str) -> str:
    return decrypt_api_key(ciphertext)


# ---------------------------------------------------------------------------
# SQLite inline-DDL
# ---------------------------------------------------------------------------

def _ensure_sqlite_table() -> None:
    """Create the SQLite mirror table once per process when MySQL is disabled."""
    global _SQLITE_TABLE_CREATED
    if _SQLITE_TABLE_CREATED:
        return
    if mysql_enabled():
        _SQLITE_TABLE_CREATED = True
        return
    from core import billing as _billing_shim  # reuse its sqlite connection helper

    with _billing_shim._connect() as conn:  # noqa: SLF001 - module-private helper reused intentionally
        conn.executescript(_SQLITE_TABLE)
    _SQLITE_TABLE_CREATED = True


def _sqlite_connect():
    """Return a sqlite3 context manager matching billing module's style."""
    from core import billing as _billing_shim

    _ensure_sqlite_table()
    return _billing_shim._connect()  # noqa: SLF001 - module-private helper reused intentionally


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

def _row_to_model(row: dict[str, Any]) -> UserCustomAuditModel:
    return UserCustomAuditModel(
        id=int(row["id"]),
        user_id=int(row["user_id"]),
        name=str(row["name"]),
        base_url=str(row["base_url"]),
        model_id=str(row["model_id"]),
        encrypted_api_key=str(row["encrypted_api_key"]),
        api_key_hint=row.get("api_key_hint") or None,
        status=str(row.get("status") or "untested"),
        validated_at=iso(row["validated_at"]) if row.get("validated_at") else None,
        created_at=iso(row["created_at"]) if row.get("created_at") else None,
        updated_at=iso(row["updated_at"]) if row.get("updated_at") else None,
    )


def get_by_user_id(user_id: int) -> UserCustomAuditModel | None:
    """Fetch the user's custom audit model record, or ``None`` if absent.

    The MySQL SELECT is covered by a single-row UNIQUE index on user_id so
    lookup cost is O(1). A single read per auditor instantiation is cheap;
    call sites cache the resolved client within a single generation session.
    """
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, user_id, name, base_url, model_id, encrypted_api_key,
                           api_key_hint, status, validated_at, created_at, updated_at
                    FROM user_custom_audit_models
                    WHERE user_id = %s
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_model(row)

    with _sqlite_connect() as conn:
        conn.row_factory = None  # type: ignore[attr-defined]
        cur = conn.cursor()
        cur.execute(
            "SELECT id, user_id, name, base_url, model_id, encrypted_api_key, "
            "api_key_hint, status, validated_at, created_at, updated_at "
            "FROM user_custom_audit_models WHERE user_id = ? LIMIT 1",
            (user_id,),
        )
        cols = (
            "id", "user_id", "name", "base_url", "model_id", "encrypted_api_key",
            "api_key_hint", "status", "validated_at", "created_at", "updated_at",
        )
        row = cur.fetchone()
        if row is None:
            return None
        return _row_to_model(dict(zip(cols, row)))


def save(
    user_id: int,
    *,
    name: str,
    base_url: str,
    model_id: str,
    plaintext_api_key: str,
    status: str = "validated",
) -> UserCustomAuditModel:
    """Encrypt + persist a custom audit model record for the given user.

    Upserts (one record per user). Returns the freshly-persisted record.
    The caller is responsible for validating the model (via probe_custom_model)
    BEFORE invoking this function; this function does not run a probe itself.
    """
    encrypted = _encrypt_api_key(plaintext_api_key)
    hint = _build_key_hint(plaintext_api_key)
    now_naive = utc_now().replace(tzinfo=None)

    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO user_custom_audit_models(
                        user_id, name, base_url, model_id, encrypted_api_key,
                        api_key_hint, status, validated_at, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        base_url = VALUES(base_url),
                        model_id = VALUES(model_id),
                        encrypted_api_key = VALUES(encrypted_api_key),
                        api_key_hint = VALUES(api_key_hint),
                        status = VALUES(status),
                        validated_at = VALUES(validated_at),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        user_id, name, base_url, model_id, encrypted, hint, status,
                        now_naive, now_naive, now_naive,
                    ),
                )
                cur.execute(
                    """
                    SELECT id, user_id, name, base_url, model_id, encrypted_api_key,
                           api_key_hint, status, validated_at, created_at, updated_at
                    FROM user_custom_audit_models WHERE user_id = %s LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
        return _row_to_model(row)

    with _sqlite_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT id FROM user_custom_audit_models WHERE user_id = ?",
            (user_id,),
        )
        existing = cur.fetchone()
        if existing is None:
            cur.execute(
                "INSERT INTO user_custom_audit_models"
                "(user_id, name, base_url, model_id, encrypted_api_key, api_key_hint, status, validated_at, created_at, updated_at)"
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, name, base_url, model_id, encrypted, hint, status,
                 iso(now_naive), iso(now_naive), iso(now_naive)),
            )
            inserted_id = cur.lastrowid
        else:
            cur.execute(
                "UPDATE user_custom_audit_models SET name = ?, base_url = ?, model_id = ?, "
                "encrypted_api_key = ?, api_key_hint = ?, status = ?, validated_at = ?, updated_at = ? "
                "WHERE user_id = ?",
                (name, base_url, model_id, encrypted, hint, status,
                 iso(now_naive), iso(now_naive), user_id),
            )
            inserted_id = int(existing[0])
        conn.commit()
        return get_by_user_id(user_id) or _row_to_model({
            "id": inserted_id,
            "user_id": user_id,
            "name": name,
            "base_url": base_url,
            "model_id": model_id,
            "encrypted_api_key": encrypted,
            "api_key_hint": hint,
            "status": status,
            "validated_at": iso(now_naive),
            "created_at": iso(now_naive),
            "updated_at": iso(now_naive),
        })


def delete_by_user_id(user_id: int) -> bool:
    """Delete the user's custom audit model record. Returns True if a row was removed."""
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "DELETE FROM user_custom_audit_models WHERE user_id = %s",
                    (user_id,),
                )
                return cur.rowcount > 0
    with _sqlite_connect() as conn:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM user_custom_audit_models WHERE user_id = ?",
            (user_id,),
        )
        deleted = cur.rowcount > 0
        conn.commit()
        return deleted


# ---------------------------------------------------------------------------
# URL / SSRF validation
# ---------------------------------------------------------------------------

_SSRF_PRIVATE_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.IPv4Network("127.0.0.0/8"),
    ipaddress.IPv4Network("10.0.0.0/8"),
    ipaddress.IPv4Network("172.16.0.0/12"),
    ipaddress.IPv4Network("192.168.0.0/16"),
    ipaddress.IPv4Network("169.254.0.0/16"),  # link-local (includes AWS metadata @ .169.254.169.254)
    ipaddress.IPv6Network("::1/128"),
    ipaddress.IPv6Network("fc00::/7"),   # unique-local
    ipaddress.IPv6Network("fe80::/10"),  # link-local
]


def _is_private_ip(ip_str: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable -> treat as disallowed
    if addr.is_loopback or addr.is_link_local or addr.is_private or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return True
    return any(addr in net for net in _SSRF_PRIVATE_NETWORKS)


def validate_base_url(url_str: str) -> tuple[str | None, str | None]:
    """Validate the user-provided base_url.

    Returns ``(None, None)`` when valid. Otherwise returns
    ``(error_kind, error_detail)`` where ``error_kind`` is one of
    ``url_format`` or ``ssrf_rejected``.
    """
    value = (url_str or "").strip()
    if not value:
        return "url_format", "base_url must be a non-empty URL"

    try:
        parsed = urlparse(value)
    except ValueError:
        return "url_format", "base_url is not a valid URL"

    if parsed.scheme not in ("http", "https"):
        return "url_format", f"base_url scheme must be http or https (got: {parsed.scheme or '<empty>'})"

    host = (parsed.hostname or "").strip()
    if not host:
        return "url_format", "base_url must include a host"

    # Quick hostname-based guard against well-known SSRF strings.
    low = host.lower()
    if low in {"localhost", "localhost.local", "localhost.localdomain", "ip6-localhost"}:
        return "ssrf_rejected", f"base_url host '{host}' is not allowed"

    # DNS resolve -> reject if the resolved IP is private / loopback / link-local.
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        # DNS failure — treated as ssrf_rejected (the name is either not
        # publicly routable or resolves to a non-TCP-only record set). We
        # deliberately do NOT fall through to the probe HTTP call.
        return "ssrf_rejected", f"base_url host '{host}' could not be resolved"
    except OSError as exc:
        _LOG.warning("getaddrinfo error for %s: %s", host, exc)
        return "ssrf_rejected", f"base_url host '{host}' could not be resolved"

    seen: set[str] = set()
    for family, _type, _proto, _canon, sockaddr in infos:
        addr_str = sockaddr[0]
        if addr_str in seen:
            continue
        seen.add(addr_str)
        if _is_private_ip(addr_str):
            return "ssrf_rejected", f"base_url host '{host}' resolved to a disallowed address"

    return None, None


# ---------------------------------------------------------------------------
# Probe wrapper
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    error_kind: str | None = None  # None on success
    error_detail: str | None = None
    validated_model: str | None = None

    def as_error_dict(self) -> dict[str, str]:
        return {"kind": self.error_kind or "unknown", "detail": self.error_detail or ""}


def probe_custom_model(*, base_url: str, model_id: str, api_key: str) -> ProbeResult:
    """Probe a user-submitted OpenAI-compatible model.

    Validates URL + SSRF guard first; then delegates to the existing
    ``core.api_key_validation.probe_api_key_model`` with a base_url
    override so that no provider-registry lookup is performed.
    """
    error, detail = validate_base_url(base_url)
    if error:
        return ProbeResult(ok=False, error_kind=error, error_detail=detail)

    model = (model_id or "").strip()
    if not model:
        return ProbeResult(
            ok=False,
            error_kind="model_not_found",
            error_detail="model_id must be a non-empty string",
        )

    key = (api_key or "").strip()
    if not key:
        return ProbeResult(
            ok=False,
            error_kind="auth",
            error_detail="api_key must be a non-empty string",
        )

    try:
        from core.api_key_validation import probe_api_key_model

        result = probe_api_key_model(
            api_key=key,
            model=model,
            base_url_override=base_url,
        )
    except Exception as exc:
        # IMPORTANT: do NOT include key or any part of the Authorization
        # header in the error detail; just the provider's classified reason.
        _LOG.warning("probe_custom_model failed for model=%s base=%s: %s", model, base_url, exc)
        try:
            from core.provider_errors import classify_provider_error
            classified = classify_provider_error(exc)
            kind = str(classified.get("code") or "network")
            mapped = {
                "invalid_api_key": "auth",
                "permission_denied": "auth",
                "quota_exceeded": "auth",
                "model_unavailable": "model_not_found",
                "network_error": "network",
                "timeout": "timeout",
            }.get(kind, "bad_response")
            return ProbeResult(
                ok=False,
                error_kind=mapped,
                error_detail=str(classified.get("message") or str(exc))[:400],
            )
        except Exception as inner:  # noqa: BLE001
            return ProbeResult(
                ok=False,
                error_kind="network",
                error_detail=str(inner)[:400] or "probe request failed",
            )

    if result.get("ok"):
        return ProbeResult(
            ok=True,
            validated_model=str(result.get("detail") or model),
        )
    # Provider-registry probe returned a structured failure; normalize.
    code = str(result.get("code") or "bad_response")
    mapped_kind = {
        "invalid_api_key": "auth",
        "permission_denied": "auth",
        "quota_exceeded": "auth",
        "model_unavailable": "model_not_found",
        "network_error": "network",
        "timeout": "timeout",
    }.get(code, "bad_response")
    return ProbeResult(
        ok=False,
        error_kind=mapped_kind,
        error_detail=str(result.get("message") or result.get("detail") or "probe returned failure")[:400],
    )
