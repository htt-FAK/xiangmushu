"""Firecrawl keyless web search via hosted MCP (Streamable HTTP + SSE).

Single public entry: ``search_web_evidence``.  Talks to the Firecrawl MCP
endpoint with a bare JSON-RPC ``tools/call`` over plain HTTP — no SDK, no
API key, no async.  On every failure path returns ``[]`` and logs a warning.
"""
from __future__ import annotations

import json
import logging
from typing import Any

import httpx

import config

logger = logging.getLogger(__name__)

_JSONRPC_ID = 1
_MCP_METHOD = "tools/call"
_TOOL_NAME = "firecrawl_search"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_web_evidence(
    query: str,
    *,
    limit: int | None = None,
    timeout: float | None = None,
) -> list[dict[str, Any]]:
    """Call Firecrawl search via hosted MCP (keyless).

    Returns
    -------
    list of {"title": str, "url": str, "content": str}
        Same shape as legacy ``core.web_search:search_web``.
        On ANY failure (timeout, HTTP error, rate-limit, parse error,
        empty result, or ``config.FIRECRAWL_ENABLED=False``): returns ``[]``
        and logs a warning.  NEVER raises.
        Keyless — no auth credential is ever sent.
    """
    if not config.FIRECRAWL_ENABLED:
        return []

    effective_limit = limit if limit is not None else config.FIRECRAWL_SEARCH_LIMIT
    effective_timeout = timeout if timeout is not None else config.FIRECRAWL_TIMEOUT

    envelope: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": _JSONRPC_ID,
        "method": _MCP_METHOD,
        "params": {
            "name": _TOOL_NAME,
            "arguments": {"query": query, "limit": effective_limit},
        },
    }

    # Fresh client per call — avoids stale connection-pool state and
    # guarantees deterministic teardown of the underlying TCP socket.
    try:
        with httpx.Client() as client:
            response = client.post(
                config.FIRECRAWL_MCP_URL,
                json=envelope,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
                timeout=effective_timeout,
            )
    except Exception as exc:
        logger.warning("[firecrawl] request failed: %s", exc)
        return []

    if response.status_code != 200:
        logger.warning("[firecrawl] HTTP %d from MCP endpoint", response.status_code)
        return []

    ct = response.headers.get("content-type", "")
    body = response.text

    if "text/event-stream" in ct:
        return _parse_sse_stream(body)
    return _parse_jsonrpc_body(body)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------

def _parse_sse_stream(body: str) -> list[dict[str, Any]]:
    """Walk SSE lines, grab the first ``data:`` JSON-RPC envelope with a result."""
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        try:
            msg: Any = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            continue
        if not isinstance(msg, dict):
            continue
        # JSON-RPC error envelope
        if "error" in msg:
            logger.warning("[firecrawl] JSON-RPC error: %s", msg["error"])
            return []
        result = msg.get("result")
        if result is not None:
            return _extract_web_items(result)

    logger.warning("[firecrawl] SSE stream: no result envelope found")
    return []


def _parse_jsonrpc_body(body: str) -> list[dict[str, Any]]:
    """Parse a plain JSON-RPC 2.0 body (non-SSE content-type)."""
    try:
        msg: Any = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[firecrawl] body is not valid JSON")
        return []

    if not isinstance(msg, dict):
        logger.warning("[firecrawl] body is not a JSON object")
        return []

    if "error" in msg:
        logger.warning("[firecrawl] JSON-RPC error: %s", msg["error"])
        return []

    result = msg.get("result")
    if result is None:
        logger.warning("[firecrawl] envelope missing 'result' key")
        return []

    return _extract_web_items(result)


def _extract_web_items(result: Any) -> list[dict[str, Any]]:
    """Descend ``result.content[0].text`` → inner JSON → ``data.web``."""
    if not isinstance(result, dict):
        logger.warning("[firecrawl] result is not a dict")
        return []

    content_list = result.get("content")
    if not isinstance(content_list, list) or not content_list:
        logger.warning("[firecrawl] result.content is empty or not a list")
        return []

    first = content_list[0]
    if not isinstance(first, dict):
        logger.warning("[firecrawl] result.content[0] is not a dict")
        return []

    text_field = first.get("text")
    if not isinstance(text_field, str) or not text_field:
        logger.warning("[firecrawl] result.content[0].text is missing/empty")
        return []

    # Inner payload is an ESCAPED JSON string
    try:
        inner: Any = json.loads(text_field)
    except (json.JSONDecodeError, ValueError):
        logger.warning("[firecrawl] inner text field is not valid JSON")
        return []

    if not isinstance(inner, dict) or not inner.get("success"):
        logger.warning("[firecrawl] inner payload success=false")
        return []

    data_obj = inner.get("data")
    if not isinstance(data_obj, dict):
        logger.warning("[firecrawl] inner payload missing 'data'")
        return []

    web_list = data_obj.get("web")
    if not isinstance(web_list, list):
        logger.warning("[firecrawl] data.web is not a list")
        return []

    out: list[dict[str, Any]] = []
    for item in web_list:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        content = str(
            item.get("description") or item.get("content") or ""
        ).strip()
        if title or url:
            out.append({"title": title, "url": url, "content": content})

    if not out:
        logger.warning("[firecrawl] web list empty after filtering")
    return out
