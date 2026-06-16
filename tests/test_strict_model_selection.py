from __future__ import annotations

import uuid
from types import SimpleNamespace

from core.content_auditor import ContentAuditor
from core.fill_task import FillTask
from core.generator import ContentGenerator


def test_content_generator_strict_model_selection_disables_fallback_chain():
    generator = ContentGenerator.__new__(ContentGenerator)
    generator._strict_model_selection = True

    models = generator._candidate_models(
        "deepseek-v4-pro",
        route_meta={"generation_tier": "large"},
    )

    assert models == ["deepseek-v4-pro"]


def test_content_auditor_strict_model_selection_only_calls_selected_model(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr("core.content_auditor.config.AUDIT_LLM_MODEL", "qwen3.6-flash")
    monkeypatch.setattr("core.content_auditor.config.openai_client_for_chat", lambda: object())

    def fake_chat(_client, **kwargs):
        calls.append(str(kwargs["model"]))
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=""),
                )
            ]
        )

    monkeypatch.setattr("core.content_auditor.chat_completions_create", fake_chat)

    auditor = ContentAuditor(
        model_overrides={"audit": "deepseek-v4-flash"},
        strict_model_selection=True,
    )
    task = FillTask(
        task_id=str(uuid.uuid4()),
        target_chapter="摘要",
        task_type="paragraph",
        description="写一段摘要",
        location_hint={},
        word_limit=120,
    )

    result = auditor.audit(
        task,
        "测试草稿",
        "测试资料",
        None,
        {"kb_hits": 1, "native_web_search": False},
    )

    assert calls == ["deepseek-v4-flash"]
    assert result.parse_ok is False
    assert result.issues
