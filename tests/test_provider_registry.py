from __future__ import annotations

from core import provider_registry


class _CustomRow:
    def __init__(
        self,
        row_id: int,
        name: str,
        default_model_id: str,
        assigned_roles_json: list[str] | None = None,
        capabilities_json: list[str] | None = None,
    ):
        self.id = row_id
        self.name = name
        self.default_model_id = default_model_id
        self.assigned_roles_json = assigned_roles_json or []
        self.capabilities_json = capabilities_json or []


def test_sanitize_user_model_choices_falls_back_when_model_disabled(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(provider_registry, "get_custom_models_by_user", lambda user_id: [])
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

    assert clean == {"main_writer": "builtin:qwen3.7-plus"}
    assert "main_writer" in warnings


def test_sanitize_user_model_choices_allows_validated_supplemental_provider(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(provider_registry, "get_custom_models_by_user", lambda user_id: [])
    monkeypatch.setattr(
        provider_registry,
        "_catalog_rows_for_user",
        lambda user_id: [
            {
                "id": 1,
                "role": "main_writer",
                "model": "qwen3.7-plus",
                "provider_id": 10,
                "provider_code": "dashscope",
                "provider_name": "DashScope",
                "config": {},
            },
            {
                "id": 2,
                "role": "main_writer",
                "model": "deepseek-v4-pro",
                "provider_id": 11,
                "provider_code": "deepseek",
                "provider_name": "DeepSeek",
                "config": {},
            },
        ],
    )

    clean, warnings = provider_registry.sanitize_user_model_choices({"main_writer": "deepseek-v4-pro"}, user_id=7)

    assert clean == {"main_writer": "deepseek-v4-pro"}
    assert warnings == {}


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
        "_catalog_rows_for_user",
        lambda user_id: [
            {
                "role": "main_writer",
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


def test_model_options_map_falls_back_to_legacy_metadata_when_registry_read_fails(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)

    def raise_catalog(*args, **kwargs):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(provider_registry, "list_catalog_rows", raise_catalog)

    options = provider_registry.model_options_map_for_user(7)

    assert options["main_writer"]["source"] == "legacy_fallback"
    assert "warning" in options["main_writer"]
    assert "tiers" in options["main_writer"] or "options" in options["main_writer"]


def test_save_user_model_choices_preserves_selection_when_registry_is_degraded(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)

    def raise_catalog(*args, **kwargs):
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(provider_registry, "list_catalog_rows", raise_catalog)

    clean, warnings = provider_registry.save_user_model_choices(
        7,
        {"main_writer": "deepseek-v4-pro", "template_planner": "qwen3.6-flash"},
    )

    assert clean == {
        "main_writer": "deepseek-v4-pro",
        "template_planner": "qwen3.6-flash",
    }
    assert "main_writer" in warnings
    assert "template_planner" in warnings


def test_model_options_map_returns_all_registry_options_for_healthy_role(monkeypatch):
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
            },
            {
                "id": 2,
                "role": "main_writer",
                "model": "qwen3.7-max",
                "display_name": "Qwen 3.7 Max",
                "provider_id": 10,
                "provider_code": "dashscope",
                "provider_name": "DashScope",
                "config": {},
            },
            {
                "id": 3,
                "role": "fast_writer",
                "model": "qwen3.6-flash",
                "display_name": "Qwen 3.6 Flash",
                "provider_id": 10,
                "provider_code": "dashscope",
                "provider_name": "DashScope",
                "config": {},
            },
            {
                "id": 4,
                "role": "fast_writer",
                "model": "qwen3.5-flash",
                "display_name": "Qwen 3.5 Flash",
                "provider_id": 10,
                "provider_code": "dashscope",
                "provider_name": "DashScope",
                "config": {},
            },
        ],
    )
    monkeypatch.setattr(provider_registry, "load_user_model_choices", lambda user_id: {})

    options = provider_registry.model_options_map_for_user(7)

    assert [item["model"] for item in options["main_writer"]["options"]] == ["qwen3.7-plus", "qwen3.7-max"]
    assert [item["model"] for item in options["fast_writer"]["options"]] == ["qwen3.6-flash", "qwen3.5-flash"]
    assert options["main_writer"]["source"] == "registry"


def test_model_options_map_filters_supplemental_providers_by_user_keys(monkeypatch):
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
            },
            {
                "id": 2,
                "role": "main_writer",
                "model": "deepseek-v4-pro",
                "display_name": "DeepSeek V4 Pro",
                "provider_id": 11,
                "provider_code": "deepseek",
                "provider_name": "DeepSeek",
                "config": {},
            },
        ],
    )
    monkeypatch.setattr(provider_registry, "load_user_model_choices", lambda user_id: {})

    options = provider_registry.model_options_map_for_user(7)

    assert [item["model"] for item in options["main_writer"]["options"]] == ["qwen3.7-plus"]


def test_model_options_map_keeps_builtin_and_custom_same_model_id(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(
        provider_registry,
        "_catalog_rows_for_user",
        lambda user_id: [
            {
                "id": 1,
                "role": "main_writer",
                "model": "deepseek-v4-flash",
                "display_name": "DeepSeek V4 Flash",
                "provider_id": 11,
                "provider_code": "deepseek",
                "provider_name": "DeepSeek",
                "config": {},
            }
        ],
    )
    monkeypatch.setattr(provider_registry, "load_user_model_choices", lambda user_id: {})
    monkeypatch.setattr(
        provider_registry,
        "get_custom_models_by_user",
        lambda user_id: [
            _CustomRow(
                row_id=42,
                name="商汤 DeepSeek",
                default_model_id="deepseek-v4-flash",
                assigned_roles_json=["text-gen"],
                capabilities_json=["text"],
            )
        ],
    )

    options = provider_registry.model_options_map_for_user(7)
    main_options = options["main_writer"]["options"]

    assert len(main_options) == 2
    values = {item.get("value") for item in main_options}
    labels = {item.get("label") for item in main_options}
    assert "builtin:deepseek-v4-flash" in values
    assert "custom:42" in values
    assert "DeepSeek V4 Flash" in labels
    assert "商汤 DeepSeek" in labels


def test_sanitize_user_model_choices_accepts_custom_value(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(
        provider_registry,
        "_catalog_rows_for_user",
        lambda user_id: [
            {
                "id": 1,
                "role": "main_writer",
                "model": "deepseek-v4-flash",
                "provider_id": 11,
                "provider_code": "deepseek",
                "provider_name": "DeepSeek",
                "config": {},
            }
        ],
    )
    monkeypatch.setattr(
        provider_registry,
        "get_custom_models_by_user",
        lambda user_id: [
            _CustomRow(
                row_id=42,
                name="商汤 DeepSeek",
                default_model_id="deepseek-v4-flash",
                assigned_roles_json=["text-gen"],
                capabilities_json=["text"],
            )
        ],
    )

    clean, warnings = provider_registry.sanitize_user_model_choices(
        {"main_writer": "custom:42"},
        user_id=7,
    )

    assert clean == {"main_writer": "custom:42"}
    assert warnings == {}


def test_resolve_role_choice_prefers_custom_value(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(
        provider_registry,
        "load_user_model_choices",
        lambda user_id: {"main_writer": "custom:42"},
    )
    monkeypatch.setattr(
        provider_registry,
        "get_custom_models_by_user",
        lambda user_id: [
            _CustomRow(
                row_id=42,
                name="商汤 DeepSeek",
                default_model_id="deepseek-v4-flash",
                assigned_roles_json=["text-gen"],
                capabilities_json=["text"],
            )
        ],
    )
    monkeypatch.setattr(
        provider_registry,
        "_catalog_rows_for_user",
        lambda user_id: [
            {
                "role": "main_writer",
                "model": "deepseek-v4-flash",
                "provider_code": "deepseek",
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

    assert resolved["model"] == "deepseek-v4-flash"
    assert resolved["provider_code"] == "custom"
    assert resolved["custom_model_id"] == 42
    assert resolved["source"] == "user:main_writer"


def test_validation_candidate_models_excludes_disabled_legacy_rows(monkeypatch):
    monkeypatch.setattr(provider_registry, "registry_enabled", lambda: True)
    monkeypatch.setattr(
        provider_registry,
        "list_catalog_rows",
        lambda include_disabled=False: [
            {
                "model": "deepseek-v4-flash",
                "provider_code": "deepseek",
            },
            {
                "model": "deepseek-v4-pro",
                "provider_code": "deepseek",
            },
        ] if include_disabled is False else [
            {
                "model": "deepseek-chat",
                "provider_code": "deepseek",
            },
            {
                "model": "deepseek-reasoner",
                "provider_code": "deepseek",
            },
            {
                "model": "deepseek-v4-flash",
                "provider_code": "deepseek",
            },
            {
                "model": "deepseek-v4-pro",
                "provider_code": "deepseek",
            },
        ],
    )

    models = provider_registry.validation_candidate_models("deepseek")

    assert models == ["deepseek-v4-flash", "deepseek-v4-pro"]
