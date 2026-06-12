from __future__ import annotations

from core.fill_task import FillTask
from core.web_search_agent import SessionWebEvidenceCache, fetch_web_evidence, parse_web_evidence


def _task() -> FillTask:
    return FillTask(
        task_id="t-web",
        target_chapter="政策背景",
        task_type="paragraph",
        description="搜索数字经济政策支持信息",
        location_hint={},
        word_limit=200,
    )


def test_parse_web_evidence_json_fence():
    raw = """```json
{"facts":[{"claim":"政策支持数字经济。","source":"https://example.test","confidence":"high","use_for":["policy"]}],"gaps":["未找到地方细则"]}
```"""

    facts, gaps = parse_web_evidence(raw)

    assert facts[0].claim == "政策支持数字经济。"
    assert facts[0].source == "https://example.test"
    assert gaps == ["未找到地方细则"]


def test_fetch_web_evidence_uses_web_search_profile(monkeypatch):
    calls: list[dict] = []

    class _Message:
        content = '{"facts":[{"claim":"公开政策支持转型。","source":"s","confidence":"high"}],"gaps":[]}'

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    def fake_chat(*args, **kwargs):
        calls.append(kwargs)
        return _Response()

    monkeypatch.setattr("core.web_search_agent.chat_completions_create", fake_chat)
    monkeypatch.setattr("core.model_router._model_choices_for_user", lambda user_id: {"web_search": "search-model"})

    result = fetch_web_evidence(object(), _task(), user_id=7)

    assert result.facts[0].claim == "公开政策支持转型。"
    assert calls[0]["model"] == "search-model"
    assert calls[0]["extra_body"]["enable_search"] is True


def test_session_web_evidence_cache_reuses_result(monkeypatch):
    calls = 0

    class _Message:
        content = '{"facts":[{"claim":"事实。"}],"gaps":[]}'

    class _Choice:
        message = _Message()

    class _Response:
        choices = [_Choice()]

    def fake_chat(*args, **kwargs):
        nonlocal calls
        calls += 1
        return _Response()

    monkeypatch.setattr("core.web_search_agent.chat_completions_create", fake_chat)
    cache = SessionWebEvidenceCache()

    first = fetch_web_evidence(object(), _task(), cache=cache)
    second = fetch_web_evidence(object(), _task(), cache=cache)

    assert calls == 1
    assert first.cached is False
    assert second.cached is True
    assert second.facts[0].claim == "事实。"
