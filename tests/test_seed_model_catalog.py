from __future__ import annotations

import importlib.util
from pathlib import Path

from core import provider_registry

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "seed_model_catalog.py"
_SPEC = importlib.util.spec_from_file_location("seed_model_catalog_local", _SCRIPT_PATH)
assert _SPEC and _SPEC.loader
seed_model_catalog = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(seed_model_catalog)


def test_catalog_seed_candidates_prefer_role_specific_models_and_skip_unsupported(monkeypatch):
    monkeypatch.setattr(provider_registry, "UI_ROLE_KEYS", ("main_writer",))
    monkeypatch.setattr(
        provider_registry,
        "ROLE_DEFAULTS",
        {
            "main_writer": {
                "default_model": "qwen3.7-plus",
                "extra_body": {},
            }
        },
    )
    monkeypatch.setattr(
        provider_registry,
        "_legacy_model_options",
        lambda: {
            "main_writer": {
                "options": [
                    {"model": "deepseek-v4-pro"},
                    {"model": "glm-5.1"},
                ]
            },
            "generation": {
                "options": [
                    {"model": "qwen3.7-max"},
                ]
            },
        },
    )

    rows = provider_registry.catalog_seed_candidates()

    assert [item["model"] for item in rows] == ["deepseek-v4-pro", "qwen3.7-plus"]
    assert [item["provider_code"] for item in rows] == ["deepseek", "dashscope"]


def test_catalog_seed_candidates_fall_back_to_legacy_module_and_default(monkeypatch):
    monkeypatch.setattr(provider_registry, "UI_ROLE_KEYS", ("template_planner", "embedding"))
    monkeypatch.setattr(
        provider_registry,
        "ROLE_DEFAULTS",
        {
            "template_planner": {
                "default_model": "qwen3.6-flash",
                "extra_body": {},
            },
            "embedding": {
                "default_model": "text-embedding-v4",
                "extra_body": {},
            },
        },
    )
    monkeypatch.setattr(provider_registry, "ROLE_LEGACY_SEED_MODULES", {"template_planner": "lightweight"})
    monkeypatch.setattr(
        provider_registry,
        "_legacy_model_options",
        lambda: {
            "lightweight": {
                "options": [
                    {"model": "deepseek-v4-flash"},
                    {"model": "MiniMax-M2.5"},
                ]
            }
        },
    )

    rows = provider_registry.catalog_seed_candidates()

    assert [item["model"] for item in rows if item["role"] == "template_planner"] == [
        "deepseek-v4-flash",
        "qwen3.6-flash",
    ]
    assert [item["model"] for item in rows if item["role"] == "embedding"] == ["text-embedding-v4"]


def test_build_seed_plan_preserves_existing_disabled_state(monkeypatch):
    monkeypatch.setattr(seed_model_catalog, "mysql_enabled", lambda: True)
    monkeypatch.setattr(seed_model_catalog, "mysql_health_check", lambda: {"ok": True})
    monkeypatch.setattr(
        seed_model_catalog,
        "list_provider_rows",
        lambda include_disabled=True: [{"id": 11, "code": "dashscope", "enabled": True}],
    )
    monkeypatch.setattr(
        seed_model_catalog,
        "catalog_seed_candidates",
        lambda: [
            {
                "role": "main_writer",
                "provider_code": "dashscope",
                "model": "qwen3.7-plus",
                "display_name": "Qwen 3.7 Plus",
                "capabilities": ["text", "streaming"],
                "input_price_per_1k": 0.0008,
                "output_price_per_1k": 0.002,
                "context_window": None,
                "config": {},
            }
        ],
    )
    monkeypatch.setattr(
        seed_model_catalog,
        "_raw_catalog_rows",
        lambda: [
            {
                "id": 5,
                "provider_id": 11,
                "model_id": "qwen3.7-plus",
                "display_name": "Old Label",
                "role_key": "main_writer",
                "enabled": 0,
                "capabilities_json": ["text"],
                "input_price_per_1k": 0.0008,
                "output_price_per_1k": 0.002,
                "context_window": None,
                "config_json": {},
                "provider_code": "dashscope",
                "provider_enabled": 1,
            }
        ],
    )

    plan = seed_model_catalog.build_seed_plan()

    assert plan["counts"]["update"] == 1
    assert plan["operations"][0]["action"] == "update"
    assert plan["operations"][0]["enabled"] is False
