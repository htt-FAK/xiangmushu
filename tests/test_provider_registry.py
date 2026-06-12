from __future__ import annotations

from core import provider_registry


def test_sanitize_user_model_choices_falls_back_when_model_disabled(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(
        provider_registry,
        "list_catalog_rows",
        lambda include_disabled=False: [
            {
                "id": 1,
                "role": "main_writer",
                "model": "qwen3.7-plus",
                "provider_id": 10,
                "provider_code": "dashscope",
                "provider_name": "DashScope",
                "config": {},
            }
        ],
    )
    monkeypatch.setattr(
        provider_registry,
        "default_model_for_role",
        lambda role: ("qwen3.7-plus", "dashscope"),
    )

    clean, warnings = provider_registry.sanitize_user_model_choices({"main_writer": "deepseek-v4-pro"})

    assert clean == {"main_writer": "qwen3.7-plus"}
    assert "main_writer" in warnings


def test_model_options_map_marks_unavailable_selected_model(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(
        provider_registry,
        "list_catalog_rows",
        lambda include_disabled=False: [
            {
                "id": 1,
                "role": "main_writer",
                "model": "qwen3.7-plus",
                "display_name": "Qwen 3.7 Plus",
                "provider_id": 10,
                "provider_code": "dashscope",
                "provider_name": "DashScope",
                "config": {},
            }
        ],
    )
    monkeypatch.setattr(
        provider_registry,
        "load_user_model_choices",
        lambda user_id: {"main_writer": "deepseek-v4-pro"},
    )

    options = provider_registry.model_options_map_for_user(7)

    assert options["main_writer"]["options"][0]["model"] == "qwen3.7-plus"
    assert options["main_writer"]["selected_unavailable"]["model"] == "deepseek-v4-pro"


def test_resolve_role_choice_uses_registry_backed_provider(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(
        provider_registry,
        "load_user_model_choices",
        lambda user_id: {"main_writer": "qwen3.7-plus"},
    )
    monkeypatch.setattr(
        provider_registry,
        "available_models_for_role",
        lambda role: [
            {
                "model": "qwen3.7-plus",
                "provider_code": "dashscope",
                "config": {"temperature_hint": "stable"},
            }
        ],
    )
    monkeypatch.setattr(
        provider_registry,
        "default_model_for_role",
        lambda role: ("qwen3.7-plus", "dashscope"),
    )

    resolved = provider_registry.resolve_role_choice("main_writer", 7)

    assert resolved["model"] == "qwen3.7-plus"
    assert resolved["provider_code"] == "dashscope"
    assert resolved["source"] == "user:main_writer"
    assert resolved["extra_body"]["temperature_hint"] == "stable"

