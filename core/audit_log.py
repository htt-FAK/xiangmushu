from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from core.db import mysql_enabled, mysql_transaction

logger = logging.getLogger(__name__)

LOGIN_SUCCESS = "LOGIN_SUCCESS"
LOGIN_FAILED = "LOGIN_FAILED"
REGISTER_SUCCESS = "REGISTER_SUCCESS"
PASSWORD_RESET_SUCCESS = "PASSWORD_RESET_SUCCESS"
PASSWORD_RESET_FAILED = "PASSWORD_RESET_FAILED"
CODE_REQUESTED = "CODE_REQUESTED"
FILE_UPLOADED = "FILE_UPLOADED"
API_KEY_SAVED = "API_KEY_SAVED"
API_KEY_DELETED = "API_KEY_DELETED"
ADMIN_ACCESS = "ADMIN_ACCESS"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_audit_db(db_path: str | None = None) -> None:
    path = Path(db_path or config.AUTH_DB_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                email TEXT,
                action TEXT NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                detail TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_created
            ON audit_logs(created_at DESC)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_logs_user_created
            ON audit_logs(user_id, created_at DESC)
            """
        )
        conn.commit()


def _use_mysql(db_path: str | None = None) -> bool:
    return db_path is None and mysql_enabled()


def log_audit(
    action: str,
    user_id: int | None = None,
    email: str | None = None,
    ip: str | None = None,
    ua: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    detail_text = json.dumps(detail, ensure_ascii=False, sort_keys=True) if detail is not None else None
    logger.info(
        "audit action=%s user_id=%s email=%s ip=%s detail=%s",
        action,
        user_id,
        email,
        ip,
        detail_text,
    )
    try:
        if _use_mysql():
            with mysql_transaction() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO audit_events(owner_user_id, email, action, ip_address, user_agent, detail_json, created_at)
                        VALUES(%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (user_id, email, action, ip, ua, detail_text, datetime.now(timezone.utc).replace(tzinfo=None)),
                    )
            return
        init_audit_db()
        with sqlite3.connect(config.AUTH_DB_PATH) as conn:
            conn.execute(
                """
                INSERT INTO audit_logs(user_id, email, action, ip_address, user_agent, detail, created_at)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, email, action, ip, ua, detail_text, _utc_now_iso()),
            )
            conn.commit()
    except Exception:
        logger.exception("Failed to write audit log")
