from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config  # noqa: E402
from core.db import ensure_configured_database, mysql_enabled, mysql_transaction  # noqa: E402


def _parse_time(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _json_or_none(value: Any) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    try:
        json.loads(str(value))
        return str(value)
    except Exception:
        return None


def _sqlite_rows(db_path: Path, table: str) -> list[sqlite3.Row]:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        if not exists:
            return []
        return list(conn.execute(f"SELECT * FROM {table}").fetchall())


def _default_provider_id(conn) -> int | None:
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM model_providers WHERE code = %s LIMIT 1", ("dashscope",))
        row = cur.fetchone()
    return int(row["id"]) if row else None


def migrate(db_path: Path, *, apply: bool) -> dict[str, Any]:
    users = _sqlite_rows(db_path, "users")
    keys = _sqlite_rows(db_path, "user_api_keys")
    billing = _sqlite_rows(db_path, "billing_records")
    audit = _sqlite_rows(db_path, "audit_logs")

    result: dict[str, Any] = {
        "source": str(db_path),
        "apply": apply,
        "users": len(users),
        "user_api_keys": len(keys),
        "billing_records": len(billing),
        "audit_events": len(audit),
        "inserted": {"users": 0, "preferences": 0, "user_api_keys": 0, "billing_records": 0, "audit_events": 0},
        "skipped": {"billing_records": 0, "audit_events": 0},
    }
    if not apply:
        return result
    if not mysql_enabled():
        raise RuntimeError("Set PERSISTENCE_MODE=mysql before applying SQLite-to-MySQL migration.")
    ensure_configured_database()

    with mysql_transaction() as conn:
        provider_id = _default_provider_id(conn)
        if provider_id is None:
            raise RuntimeError("Default dashscope provider is missing; run MySQL migrations first.")
        with conn.cursor() as cur:
            for row in users:
                cur.execute(
                    """
                    INSERT INTO users(id, email, password_hash, preferred_language, model_choices_json, created_at, last_login_at)
                    VALUES(%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        password_hash = COALESCE(VALUES(password_hash), password_hash),
                        preferred_language = VALUES(preferred_language),
                        model_choices_json = VALUES(model_choices_json),
                        last_login_at = COALESCE(VALUES(last_login_at), last_login_at)
                    """,
                    (
                        int(row["id"]),
                        str(row["email"]).lower().strip(),
                        row["password_hash"] if "password_hash" in row.keys() else None,
                        row["preferred_language"] if "preferred_language" in row.keys() else "zh",
                        _json_or_none(row["model_choices"] if "model_choices" in row.keys() else None),
                        _parse_time(row["created_at"]),
                        _parse_time(row["last_login_at"] if "last_login_at" in row.keys() else None),
                    ),
                )
                result["inserted"]["users"] += int(cur.rowcount > 0)
                cur.execute(
                    """
                    INSERT INTO user_preferences(user_id, preferred_language, model_choices_json)
                    VALUES(%s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        preferred_language = VALUES(preferred_language),
                        model_choices_json = VALUES(model_choices_json)
                    """,
                    (
                        int(row["id"]),
                        row["preferred_language"] if "preferred_language" in row.keys() else "zh",
                        _json_or_none(row["model_choices"] if "model_choices" in row.keys() else None),
                    ),
                )
                result["inserted"]["preferences"] += int(cur.rowcount > 0)

            for row in keys:
                cur.execute(
                    """
                    INSERT INTO provider_credentials(
                        owner_user_id, provider_id, encrypted_api_key, status, created_at, updated_at
                    )
                    VALUES(%s, %s, %s, 'validated', %s, %s)
                    ON DUPLICATE KEY UPDATE
                        encrypted_api_key = VALUES(encrypted_api_key),
                        status = VALUES(status),
                        updated_at = VALUES(updated_at)
                    """,
                    (
                        int(row["user_id"]),
                        provider_id,
                        row["encrypted_api_key"],
                        _parse_time(row["created_at"]),
                        _parse_time(row["updated_at"]),
                    ),
                )
                result["inserted"]["user_api_keys"] += int(cur.rowcount > 0)

            for row in billing:
                cur.execute(
                    """
                    SELECT id FROM billing_records
                    WHERE owner_user_id = %s AND model = %s AND input_tokens = %s
                      AND output_tokens = %s AND cost_cny = %s AND created_at = %s
                    LIMIT 1
                    """,
                    (
                        int(row["user_id"]),
                        row["model"],
                        int(row["input_tokens"] or 0),
                        int(row["output_tokens"] or 0),
                        float(row["cost_cny"] or 0),
                        _parse_time(row["created_at"]),
                    ),
                )
                if cur.fetchone():
                    result["skipped"]["billing_records"] += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO billing_records(
                        owner_user_id, provider_id, provider_code, model,
                        input_tokens, output_tokens, cost_cny, created_at
                    )
                    VALUES(%s, %s, 'dashscope', %s, %s, %s, %s, %s)
                    """,
                    (
                        int(row["user_id"]),
                        provider_id,
                        row["model"],
                        int(row["input_tokens"] or 0),
                        int(row["output_tokens"] or 0),
                        float(row["cost_cny"] or 0),
                        _parse_time(row["created_at"]),
                    ),
                )
                result["inserted"]["billing_records"] += 1

            for row in audit:
                created_at = _parse_time(row["created_at"])
                cur.execute(
                    """
                    SELECT id FROM audit_events
                    WHERE owner_user_id <=> %s AND action = %s AND created_at = %s
                    LIMIT 1
                    """,
                    (row["user_id"], row["action"], created_at),
                )
                if cur.fetchone():
                    result["skipped"]["audit_events"] += 1
                    continue
                cur.execute(
                    """
                    INSERT INTO audit_events(owner_user_id, email, action, ip_address, user_agent, detail_json, created_at)
                    VALUES(%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        row["user_id"],
                        row["email"],
                        row["action"],
                        row["ip_address"],
                        row["user_agent"],
                        _json_or_none(row["detail"]),
                        created_at,
                    ),
                )
                result["inserted"]["audit_events"] += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate current SQLite auth/billing/audit data to MySQL.")
    parser.add_argument("--sqlite", default=config.AUTH_DB_PATH, help="Path to auth.sqlite3.")
    parser.add_argument("--apply", action="store_true", help="Apply changes. Default is dry-run only.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    try:
        result = migrate(Path(args.sqlite), apply=args.apply)
        ok = True
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        ok = False

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("SQLite to MySQL migration")
        for key, value in result.items():
            print(f"{key}: {value}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
