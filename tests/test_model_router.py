from __future__ import annotations

from core.model_router import MAIN_WRITER, WEB_SEARCH, available_models_for_role, resolve_model_profile


def test_main_writer_defaults_to_qwen37_plus(monkeypatch):
    monkeypatch.setattr("core.model_router._model_choices_for_user", lambda user_id: {})

    profile = resolve_model_profile(MAIN_WRITER, user_id=7, routing_reason="test")

    assert profile.role == MAIN_WRITER
    assert profile.model == "qwen3.7-plus"
    assert profile.routing_reason == "test"
    assert "qwen3.7-plus" in profile.model_chain


def test_role_resolution_prefers_role_choice(monkeypatch):
    monkeypatch.setattr(
        "core.model_router._model_choices_for_user",
        lambda user_id: {"main_writer": "user-main", "generation": "legacy-main"},
    )

    profile = resolve_model_profile("generation", user_id=7)

    assert profile.role == MAIN_WRITER
    assert profile.model == "user-main"
    assert profile.source == "user:main_writer"


def test_role_resolution_falls_back_to_legacy_choice(monkeypatch):
    monkeypatch.setattr(
        "core.model_router._model_choices_for_user",
        lambda user_id: {"generation": "legacy-main"},
    )

    profile = resolve_model_profile(MAIN_WRITER, user_id=7)

    assert profile.model == "legacy-main"
    assert profile.source == "user:generation"


def test_fallback_chain_is_deduplicated(monkeypatch):
    monkeypatch.setattr("config.MAIN_WRITER_FALLBACK_MODEL_1", "same-model")
    monkeypatch.setattr("config.MAIN_WRITER_FALLBACK_MODEL_2", "same-model")
    monkeypatch.setattr("config.FALLBACK_LLM_MODEL_1", "fallback")
    monkeypatch.setattr("core.model_router._model_choices_for_user", lambda user_id: {"main_writer": "same-model"})

    profile = resolve_model_profile(MAIN_WRITER, user_id=7)

    assert profile.model_chain == ["same-model", "fallback", "qwen3.7-max"]


def test_web_search_profile_sets_enable_search(monkeypatch):
    monkeypatch.setattr("core.model_router._model_choices_for_user", lambda user_id: {})

    profile = resolve_model_profile(WEB_SEARCH, user_id=7)

    assert profile.role == WEB_SEARCH
    assert profile.extra_body["enable_search"] is True
    assert "qwen3.7-plus" in available_models_for_role(WEB_SEARCH)
