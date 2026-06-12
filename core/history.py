from __future__ import annotations

import json
import logging
from typing import Any

from core.db import mysql_enabled, mysql_transaction

LOG = logging.getLogger(__name__)


def _json(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False)


def _model_usage_from_billing(billing: dict[str, Any] | None) -> list[dict[str, Any]]:
    usage: dict[str, dict[str, Any]] = {}
    for record in (billing or {}).get("records") or []:
        model = str((record or {}).get("model") or "unknown")
        item = usage.setdefault(model, {"model": model, "inputTokens": 0, "outputTokens": 0, "costCny": 0.0})
        item["inputTokens"] += int((record or {}).get("input_tokens") or 0)
        item["outputTokens"] += int((record or {}).get("output_tokens") or 0)
        item["costCny"] = round(float(item["costCny"]) + float((record or {}).get("cost_cny") or 0), 8)
    return sorted(usage.values(), key=lambda item: item["inputTokens"] + item["outputTokens"], reverse=True)


def _history_status(session_status: str, snapshot: dict[str, Any]) -> str:
    if session_status == "error":
        return "failed"
    checks = snapshot.get("post_fill_checks") or {}
    if isinstance(checks, dict) and checks.get("ok") is False:
        return "review"
    return "completed"


def persist_session_created(session) -> None:
    if not mysql_enabled():
        return
    snapshot = session.snapshot()
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO generation_sessions(
                    session_key, owner_user_id, status, progress_percent, current_task, params_json, result_json, created_at
                )
                VALUES(%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    status = VALUES(status),
                    current_task = VALUES(current_task),
                    params_json = VALUES(params_json),
                    result_json = VALUES(result_json)
                """,
                (
                    session.session_id,
                    session.user_id,
                    session.status,
                    0,
                    session.current_task,
                    _json(session.params),
                    _json(snapshot),
                ),
            )


def persist_session_snapshot(session) -> None:
    if not mysql_enabled():
        return
    snapshot = session.snapshot()
    progress = snapshot.get("progress") or {}
    total = int(progress.get("total") or 0)
    done = int(progress.get("done") or 0)
    percent = round((done / total * 100), 2) if total > 0 else 0
    billing = snapshot.get("billing") or {}
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE generation_sessions
                SET status = %s,
                    progress_percent = %s,
                    current_task = %s,
                    params_json = %s,
                    result_json = %s,
                    error_summary = %s,
                    input_tokens = %s,
                    output_tokens = %s,
                    cost_cny = %s,
                    completed_at = CASE WHEN %s IN ('done', 'error') THEN CURRENT_TIMESTAMP ELSE completed_at END
                WHERE session_key = %s AND owner_user_id = %s
                """,
                (
                    session.status,
                    percent,
                    session.current_task,
                    _json(session.params),
                    _json(snapshot),
                    _json(snapshot.get("last_error")) if snapshot.get("last_error") else None,
                    int(billing.get("input_tokens") or 0),
                    int(billing.get("output_tokens") or 0),
                    float(billing.get("cost_cny") or 0),
                    session.status,
                    session.session_id,
                    session.user_id,
                ),
            )
    if session.status in {"done", "error"}:
        persist_generated_article(session)


def persist_generated_article(session) -> None:
    snapshot = session.snapshot()
    params = snapshot.get("params") or {}
    billing = snapshot.get("billing") or {}
    title = str(params.get("template") or snapshot.get("download") or session.session_id)
    status = _history_status(session.status, snapshot)
    model_usage = _model_usage_from_billing(billing)
    metadata = {
        "session_id": session.session_id,
        "download": snapshot.get("download") or "",
        "report_download": snapshot.get("report_download") or "",
        "artifact_id": snapshot.get("artifact_id") or "",
        "report_artifact_id": snapshot.get("report_artifact_id") or "",
        "report_summary": snapshot.get("report_summary") or "",
        "post_fill_checks": snapshot.get("post_fill_checks"),
        "visual_score": snapshot.get("visual_score"),
    }
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM generation_sessions WHERE session_key = %s", (session.session_id,))
            session_row = cur.fetchone()
            generation_session_id = int(session_row["id"]) if session_row else None
            cur.execute(
                """
                SELECT id FROM generated_articles
                WHERE owner_user_id = %s AND generation_session_id <=> %s
                LIMIT 1
                """,
                (session.user_id, generation_session_id),
            )
            existing = cur.fetchone()
            if existing:
                article_id = int(existing["id"])
                cur.execute(
                    """
                    UPDATE generated_articles
                    SET title = %s, summary = %s, status = %s, template_name = %s,
                        knowledge_base_slug = %s, input_tokens = %s, output_tokens = %s,
                        cost_cny = %s, model_usage_json = %s, metadata_json = %s
                    WHERE id = %s
                    """,
                    (
                        title,
                        snapshot.get("report_summary") or "",
                        status,
                        params.get("template"),
                        params.get("slug"),
                        int(billing.get("input_tokens") or 0),
                        int(billing.get("output_tokens") or 0),
                        float(billing.get("cost_cny") or 0),
                        json.dumps(model_usage, ensure_ascii=False),
                        json.dumps(metadata, ensure_ascii=False),
                        article_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO generated_articles(
                        owner_user_id, generation_session_id, title, summary, status, template_name,
                        knowledge_base_slug, input_tokens, output_tokens, cost_cny, model_usage_json, metadata_json
                    )
                    VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session.user_id,
                        generation_session_id,
                        title,
                        snapshot.get("report_summary") or "",
                        status,
                        params.get("template"),
                        params.get("slug"),
                        int(billing.get("input_tokens") or 0),
                        int(billing.get("output_tokens") or 0),
                        float(billing.get("cost_cny") or 0),
                        json.dumps(model_usage, ensure_ascii=False),
                        json.dumps(metadata, ensure_ascii=False),
                    ),
                )
                article_id = int(cur.lastrowid)
            for artifact_uuid in [metadata.get("artifact_id"), metadata.get("report_artifact_id")]:
                if artifact_uuid:
                    cur.execute(
                        "UPDATE artifact_objects SET generated_article_id = %s WHERE artifact_uuid = %s AND owner_user_id = %s",
                        (article_id, artifact_uuid, session.user_id),
                    )


def _article_from_row(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata_json") or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {}
    model_usage = row.get("model_usage_json") or []
    if isinstance(model_usage, str):
        try:
            model_usage = json.loads(model_usage)
        except Exception:
            model_usage = []
    created_at = row.get("created_at")
    return {
        "id": str(row["id"]),
        "title": str(row.get("title") or ""),
        "template": str(row.get("template_name") or ""),
        "knowledgeBase": str(row.get("knowledge_base_slug") or ""),
        "createdAt": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
        "status": str(row.get("status") or "completed"),
        "documentUrl": metadata.get("download") or None,
        "reportUrl": metadata.get("report_download") or None,
        "inputTokens": int(row.get("input_tokens") or 0),
        "outputTokens": int(row.get("output_tokens") or 0),
        "costCny": float(row.get("cost_cny") or 0),
        "modelUsage": model_usage if isinstance(model_usage, list) else [],
    }


def list_history_articles(user_id: int, *, status: str = "all", query: str = "") -> list[dict[str, Any]]:
    if not mysql_enabled():
        return []
    clauses = ["owner_user_id = %s", "deleted_at IS NULL"]
    params: list[Any] = [user_id]
    if status and status != "all":
        clauses.append("status = %s")
        params.append(status)
    if query:
        like = f"%{query}%"
        clauses.append("(title LIKE %s OR summary LIKE %s OR template_name LIKE %s OR knowledge_base_slug LIKE %s)")
        params.extend([like, like, like, like])
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT *
                FROM generated_articles
                WHERE {' AND '.join(clauses)}
                ORDER BY created_at DESC
                LIMIT 200
                """,
                tuple(params),
            )
            rows = cur.fetchall()
    return [_article_from_row(row) for row in rows]


def history_summary(articles: list[dict[str, Any]]) -> dict[str, Any]:
    input_tokens = sum(int(item.get("inputTokens") or 0) for item in articles)
    output_tokens = sum(int(item.get("outputTokens") or 0) for item in articles)
    cost = sum(float(item.get("costCny") or 0) for item in articles)
    usage: dict[str, dict[str, Any]] = {}
    for article in articles:
        for item in article.get("modelUsage") or []:
            model = str(item.get("model") or "unknown")
            current = usage.setdefault(model, {"model": model, "inputTokens": 0, "outputTokens": 0, "costCny": 0.0})
            current["inputTokens"] += int(item.get("inputTokens") or 0)
            current["outputTokens"] += int(item.get("outputTokens") or 0)
            current["costCny"] = round(float(current["costCny"]) + float(item.get("costCny") or 0), 8)
    return {
        "count": len(articles),
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "totalTokens": input_tokens + output_tokens,
        "costCny": round(cost, 8),
        "modelUsage": sorted(usage.values(), key=lambda item: item["inputTokens"] + item["outputTokens"], reverse=True),
    }


def load_session_snapshot(user_id: int, session_key: str) -> dict[str, Any] | None:
    if not mysql_enabled():
        return None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT result_json
                FROM generation_sessions
                WHERE owner_user_id = %s AND session_key = %s
                """,
                (user_id, session_key),
            )
            row = cur.fetchone()
    if not row or not row.get("result_json"):
        return None
    value = row["result_json"]
    if isinstance(value, dict):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return None


def latest_session_key(user_id: int) -> str | None:
    if not mysql_enabled():
        return None
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT session_key
                FROM generation_sessions
                WHERE owner_user_id = %s
                ORDER BY updated_at DESC, created_at DESC
                LIMIT 1
                """,
                (user_id,),
            )
            row = cur.fetchone()
    return str(row["session_key"]) if row else None
