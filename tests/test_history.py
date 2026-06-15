from __future__ import annotations

from core import history


def test_history_articles_payload_marks_backend_unavailable_on_query_error(monkeypatch):
    monkeypatch.setattr(history, "mysql_enabled", lambda: True)

    def raise_query(*args, **kwargs):
        raise RuntimeError("db unavailable")

    monkeypatch.setattr(history, "list_history_articles", raise_query)

    payload = history.history_articles_payload(5, status="completed", query="demo")

    assert payload["articles"] == []
    assert payload["summary"]["count"] == 0
    assert payload["availability"]["available"] is False
    assert payload["availability"]["source"] == "unavailable"
    assert "warning" in payload["availability"]


def test_history_articles_payload_summary_matches_returned_articles(monkeypatch):
    monkeypatch.setattr(history, "mysql_enabled", lambda: True)
    monkeypatch.setattr(
        history,
        "list_history_articles",
        lambda user_id, *, status="all", query="": [
            {
                "id": "1",
                "title": "Demo",
                "template": "demo.docx",
                "knowledgeBase": "kb",
                "createdAt": "2026-06-14T00:00:00Z",
                "status": "completed",
                "inputTokens": 10,
                "outputTokens": 5,
                "costCny": 0.12,
                "modelUsage": [{"model": "qwen", "inputTokens": 10, "outputTokens": 5, "costCny": 0.12}],
            }
        ],
    )

    payload = history.history_articles_payload(5)

    assert payload["availability"]["available"] is True
    assert payload["summary"]["count"] == 1
    assert payload["summary"]["totalTokens"] == 15
