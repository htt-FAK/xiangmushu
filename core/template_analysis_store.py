from __future__ import annotations

import json
import logging
from typing import Any

from core.db import mysql_enabled, mysql_transaction

LOG = logging.getLogger(__name__)


def _json(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _json_value(value: Any) -> Any:
    if value in (None, "", b""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return None


def persist_session_created(session) -> None:
    if not mysql_enabled():
        return
    snapshot = session.snapshot()
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO template_analysis_sessions(
                    session_key, owner_user_id, status, current_phase, status_message,
                    template_name, vision_model, planner_model, mode, vision_status,
                    params_json, result_json, billing_json, last_error_json, created_at
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    current_phase = VALUES(current_phase),
                    status_message = VALUES(status_message),
                    template_name = VALUES(template_name),
                    vision_model = VALUES(vision_model),
                    planner_model = VALUES(planner_model),
                    mode = VALUES(mode),
                    vision_status = VALUES(vision_status),
                    params_json = VALUES(params_json),
                    result_json = VALUES(result_json),
                    billing_json = VALUES(billing_json),
                    last_error_json = VALUES(last_error_json)
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.status,
                    session.current_phase,
                    session.status_message,
                    snapshot.get("template") or "",
                    snapshot.get("vision_model") or "",
                    snapshot.get("planner_model") or "",
                    snapshot.get("mode") or "",
                    snapshot.get("vision_status") or "",
                    _json(snapshot.get("params") or {}),
                    _json(snapshot),
                    _json(snapshot.get("billing")),
                    _json(snapshot.get("last_error")),
                ),
            )


def persist_session_snapshot(session) -> None:
    if not mysql_enabled():
        return
    snapshot = session.snapshot()
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE template_analysis_sessions
                SET status = %s,
                    current_phase = %s,
                    status_message = %s,
                    template_name = %s,
                    vision_model = %s,
                    planner_model = %s,
                    mode = %s,
                    vision_status = %s,
                    params_json = %s,
                    result_json = %s,
                    billing_json = %s,
                    last_error_json = %s,
                    completed_at = CASE WHEN %s IN ('done', 'error') THEN COALESCE(completed_at, CURRENT_TIMESTAMP) ELSE completed_at END
                WHERE session_key = %s AND owner_user_id = %s
                """,
                (
                    session.status,
                    session.current_phase,
                    session.status_message,
                    snapshot.get("template") or "",
                    snapshot.get("vision_model") or "",
                    snapshot.get("planner_model") or "",
                    snapshot.get("mode") or "",
                    snapshot.get("vision_status") or "",
                    _json(snapshot.get("params") or {}),
                    _json(snapshot),
                    _json(snapshot.get("billing")),
                    _json(snapshot.get("last_error")),
                    session.status,
                    session.session_id,
                    session.user_id,
                ),
            )


def load_session_snapshot(user_id: int, session_key: str) -> dict[str, Any] | None:
    if not mysql_enabled():
        return None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM template_analysis_sessions
                WHERE owner_user_id = %s AND session_key = %s
                LIMIT 1
                """,
                (user_id, session_key),
            )
            row = cur.fetchone()
    if not row:
        return None
    snapshot = _json_value(row.get("result_json")) or {}
    if not isinstance(snapshot, dict):
        snapshot = {}
    snapshot["session_id"] = str(row.get("session_key") or snapshot.get("session_id") or session_key)
    snapshot["user_id"] = int(row.get("owner_user_id") or snapshot.get("user_id") or user_id)
    snapshot["status"] = str(row.get("status") or snapshot.get("status") or "running")
    snapshot["currentPhase"] = str(row.get("current_phase") or snapshot.get("currentPhase") or "idle")
    snapshot["statusMessage"] = str(row.get("status_message") or snapshot.get("statusMessage") or "")
    snapshot["template"] = str(row.get("template_name") or snapshot.get("template") or "")
    snapshot["vision_model"] = str(row.get("vision_model") or snapshot.get("vision_model") or "")
    snapshot["planner_model"] = str(row.get("planner_model") or snapshot.get("planner_model") or "")
    snapshot["mode"] = str(row.get("mode") or snapshot.get("mode") or "")
    snapshot["vision_status"] = str(row.get("vision_status") or snapshot.get("vision_status") or "")
    snapshot["params"] = snapshot.get("params") or (_json_value(row.get("params_json")) or {})
    snapshot["tasks"] = list(snapshot.get("tasks") or [])
    snapshot["billing"] = snapshot.get("billing") or _json_value(row.get("billing_json"))
    snapshot["logs"] = list(snapshot.get("logs") or [])
    snapshot["last_error"] = snapshot.get("last_error") or _json_value(row.get("last_error_json"))
    created_at = row.get("created_at")
    updated_at = row.get("updated_at")
    snapshot["created_at"] = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or snapshot.get("created_at") or "")
    snapshot["updated_at"] = updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at or snapshot.get("updated_at") or "")
    snapshot["last_seq"] = int(snapshot.get("last_seq") or 0)
    return snapshot


def latest_session_key(user_id: int) -> str | None:
    if not mysql_enabled():
        return None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_key
                FROM template_analysis_sessions
                WHERE owner_user_id = %s
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
    return str(row["session_key"]) if row else None
