"""可选联网检索（Tavily）。未配置 API Key 时返回空列表。"""
from __future__ import annotations

import json
from typing import Any, List
from urllib import request, error

import config


def search_web(query: str, max_results: int = 5) -> List[dict[str, Any]]:
    """
    返回 [{"title": str, "url": str, "content": str}, ...]
    """
    key = (config.TAVILY_API_KEY or "").strip()
    if not key:
        return []

    body = json.dumps(
        {
            "api_key": key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_answer": False,
        }
    ).encode("utf-8")

    req = request.Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return []

    out: List[dict[str, Any]] = []
    for item in data.get("results") or []:
        title = (item.get("title") or "").strip()
        url = (item.get("url") or "").strip()
        content = (item.get("content") or item.get("snippet") or "").strip()
        if content or title:
            out.append({"title": title, "url": url, "content": content})
    return out
