from __future__ import annotations

from core.fill_task import FillTask
from core.web_search_agent import SessionWebEvidenceCache, fetch_web_evidence


def _task() -> FillTask:
    return FillTask(
        task_id="t-web",
        target_chapter="政策背景",
        task_type="paragraph",
        description="搜索数字经济政策支持信息",
        location_hint={},
        word_limit=200,
    )


def test_firecrawl_happy_path_maps_to_web_facts(monkeypatch):
    mock_results = [
        {"title": "数字经济政策概述", "url": "https://example.test/policy", "content": "支持信息"},
        {"title": "地方细则", "url": "https://example.test/local", "content": ""},
    ]

    def fake_search(query: str, *, limit=None, timeout=None):
        return list(mock_results)

    monkeypatch.setattr("core.web_search_agent.search_web_evidence", fake_search)

    result = fetch_web_evidence(object(), _task())

    assert len(result.facts) == 2
    assert result.facts[0].claim == "支持信息"
    assert result.facts[0].source == "https://example.test/policy"
    assert result.facts[0].confidence == "unknown"
    assert result.facts[0].use_for == []
    assert result.facts[1].claim == "地方细则"
    assert result.facts[1].source == "https://example.test/local"


def test_firecrawl_error_path_sets_error(monkeypatch):
    def raise_error(query: str, *, limit=None, timeout=None):
        raise RuntimeError("firecrawl unreachable")

    monkeypatch.setattr("core.web_search_agent.search_web_evidence", raise_error)

    result = fetch_web_evidence(object(), _task())

    assert result.facts == []
    assert result.error == "firecrawl unreachable"


def test_firecrawl_returns_empty_on_no_results(monkeypatch):
    def empty_search(query: str, *, limit=None, timeout=None):
        return []

    monkeypatch.setattr("core.web_search_agent.search_web_evidence", empty_search)

    result = fetch_web_evidence(object(), _task())

    assert result.facts == []
    assert result.error == ""


def test_firecrawl_model_is_firecrawl_keyless_and_usage_is_none(monkeypatch):
    mock_results = [{"title": "t", "url": "https://u", "content": "c"}]

    def fake_search(query: str, *, limit=None, timeout=None):
        return list(mock_results)

    monkeypatch.setattr("core.web_search_agent.search_web_evidence", fake_search)

    result = fetch_web_evidence(object(), _task())

    assert result.model == "firecrawl-keyless"
    assert result.usage is None


def test_session_web_evidence_cache_reuses_result(monkeypatch):
    calls = 0

    def fake_search(query: str, *, limit=None, timeout=None):
        nonlocal calls
        calls += 1
        return [{"title": "t", "url": "https://u", "content": "c"}]

    monkeypatch.setattr("core.web_search_agent.search_web_evidence", fake_search)
    cache = SessionWebEvidenceCache()

    first = fetch_web_evidence(object(), _task(), cache=cache)
    second = fetch_web_evidence(object(), _task(), cache=cache)

    assert calls == 1
    assert first.cached is False
    assert second.cached is True
    assert second.facts[0].claim == "c"
