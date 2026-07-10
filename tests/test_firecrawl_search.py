from __future__ import annotations

import json
from typing import Any

from core.firecrawl_search import search_web_evidence


def _sse_body(result_payload: dict[str, Any]) -> str:
    inner = {"jsonrpc": "2.0", "id": 1, "result": result_payload}
    return f"data: {json.dumps(inner)}\n\n"


def _inner_success(web_items: list[dict[str, str]]) -> dict[str, Any]:
    inner_json = json.dumps({"success": True, "data": {"web": web_items}})
    return {
        "content": [{"text": inner_json}],
    }


def _make_mock_client(status: int = 200, ct: str = "application/json", text: str = "", *, raise_exc: Exception | None = None):
    class _Response:
        def __init__(self):
            self.status_code = status
            self.headers = {"content-type": ct}
            self.text = text

    class _Client:
        def __init__(self):
            self.last_headers: dict[str, str] | None = None
            self.last_json: Any = None
            self.last_url: str = ""

        def post(self, url: str, *, json: Any = None, headers: dict | None = None, timeout: float = 30) -> _Response:
            self.last_url = url
            self.last_json = json
            self.last_headers = headers
            if raise_exc is not None:
                raise raise_exc
            return _Response()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    return _Client()


def test_sse_happy_path_extracts_web_items(monkeypatch):
    web_items = [
        {"title": "数字经济政策", "url": "https://example.test/policy", "description": "支持信息"},
        {"title": "地方细则", "url": "https://example.test/local", "content": "落地指南"},
    ]
    body = _sse_body(_inner_success(web_items))
    mock_client = _make_mock_client(status=200, ct="text/event-stream", text=body)
    monkeypatch.setattr("core.firecrawl_search.httpx.Client", lambda: mock_client)
    monkeypatch.setattr("config.FIRECRAWL_ENABLED", True)

    result = search_web_evidence("数字经济")

    assert len(result) == 2
    assert result[0]["title"] == "数字经济政策"
    assert result[0]["url"] == "https://example.test/policy"
    assert result[0]["content"] == "支持信息"
    assert result[1]["title"] == "地方细则"
    assert result[1]["content"] == "落地指南"


def test_jsonrpc_error_envelope_returns_empty(monkeypatch):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "rate limited"}})
    mock_client = _make_mock_client(status=200, ct="application/json", text=body)
    monkeypatch.setattr("core.firecrawl_search.httpx.Client", lambda: mock_client)
    monkeypatch.setattr("config.FIRECRAWL_ENABLED", True)

    result = search_web_evidence("test query")

    assert result == []


def test_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr("config.FIRECRAWL_ENABLED", False)

    result = search_web_evidence("test query")

    assert result == []


def test_request_exception_returns_empty(monkeypatch):
    mock_client = _make_mock_client(raise_exc=ConnectionError("network unreachable"))
    monkeypatch.setattr("core.firecrawl_search.httpx.Client", lambda: mock_client)
    monkeypatch.setattr("config.FIRECRAWL_ENABLED", True)

    result = search_web_evidence("test query")

    assert result == []


def test_no_authorization_header(monkeypatch):
    body = _sse_body(_inner_success([{"title": "t", "url": "https://u"}]))
    mock_client = _make_mock_client(status=200, ct="text/event-stream", text=body)
    monkeypatch.setattr("core.firecrawl_search.httpx.Client", lambda: mock_client)
    monkeypatch.setattr("config.FIRECRAWL_ENABLED", True)

    search_web_evidence("test query")

    assert "Authorization" not in (mock_client.last_headers or {})
    assert "authorization" not in (mock_client.last_headers or {})


def test_sse_error_in_data_line_returns_empty(monkeypatch):
    error_envelope = {"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "boom"}}
    body = f"data: {json.dumps(error_envelope)}\n\n"
    mock_client = _make_mock_client(status=200, ct="text/event-stream", text=body)
    monkeypatch.setattr("core.firecrawl_search.httpx.Client", lambda: mock_client)
    monkeypatch.setattr("config.FIRECRAWL_ENABLED", True)

    result = search_web_evidence("test query")

    assert result == []


def test_http_non_200_returns_empty(monkeypatch):
    mock_client = _make_mock_client(status=500, ct="text/plain", text="Internal Server Error")
    monkeypatch.setattr("core.firecrawl_search.httpx.Client", lambda: mock_client)
    monkeypatch.setattr("config.FIRECRAWL_ENABLED", True)

    result = search_web_evidence("test query")

    assert result == []
