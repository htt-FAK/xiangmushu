from __future__ import annotations

import json
from typing import Any

import config
from core.db import mysql_enabled, mysql_transaction


ROLE_DEFAULTS: dict[str, dict[str, Any]] = {
    "main_writer": {
        "label": "Main writing",
        "description": "Final paragraph and table-cell content writer.",
        "default_model": getattr(config, "MAIN_WRITER_MODEL", "") or getattr(config, "LARGE_LLM_MODEL", "") or "qwen3.7-plus",
        "provider_code": "dashscope",
    },
    "fast_writer": {
        "label": "Fast fill",
        "description": "Low-cost short content, strong-RAG paragraphs, and table fast fill.",
        "default_model": getattr(config, "FAST_WRITER_MODEL", "") or getattr(config, "SMALL_LLM_MODEL", "") or "qwen3.6-flash",
        "provider_code": "dashscope",
    },
    "web_search": {
        "label": "Web search",
        "description": "Search and extract structured web evidence; not final prose.",
        "default_model": getattr(config, "WEB_SEARCH_MODEL", "") or getattr(config, "VISION_WEB_MODEL", "") or "qwen3.7-plus",
        "provider_code": "dashscope",
        "extra_body": {"enable_search": True},
    },
    "vision_layout": {
        "label": "Template vision",
        "description": "Template image, screenshot, and layout understanding.",
        "default_model": getattr(config, "VISION_LAYOUT_MODEL", "") or getattr(config, "TEMPLATE_VISION_MODEL", "") or "qwen3.7-plus",
        "provider_code": "dashscope",
    },
    "template_planner": {
        "label": "Template planning",
        "description": "Turn template structure and visual profile into FillTasks.",
        "default_model": getattr(config, "TEMPLATE_PLANNER_MODEL", "") or getattr(config, "TEMPLATE_ANALYZE_MODEL", "") or "qwen3.6-flash",
        "provider_code": "dashscope",
    },
    "audit_text": {
        "label": "Content audit",
        "description": "Model-based review of generated text against task evidence.",
        "default_model": getattr(config, "AUDIT_TEXT_MODEL", "") or getattr(config, "AUDIT_LLM_MODEL", "") or "qwen3.6-flash",
        "provider_code": "dashscope",
    },
    "embedding": {
        "label": "Embedding",
        "description": "Knowledge-base embedding and vector retrieval.",
        "default_model": getattr(config, "EMBEDDING_MODEL", "") or "text-embedding-v4",
        "provider_code": "dashscope",
    },
}


def _json_value(raw: Any) -> Any:
    if raw in (None, "", b""):
        return None
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8", errors="ignore")
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None
    return None


def _role_config_from_legacy(role: str) -> dict[str, Any]:
    cfg = dict(ROLE_DEFAULTS.get(role) or {})
    legacy = config.USER_MODEL_OPTIONS.get(role) or {}
    cfg["label"] = legacy.get("label") or cfg.get("label") or role
    cfg["description"] = legacy.get("description") or cfg.get("description") or ""
    return cfg


def _legacy_model_options() -> dict[str, dict[str, Any]]:
    return {str(key): dict(value) for key, value in getattr(config, "USER_MODEL_OPTIONS", {}).items()}


def registry_enabled() -> bool:
    return mysql_enabled()


def list_provider_rows(include_disabled: bool = True) -> list[dict[str, Any]]:
    if not registry_enabled():
        return []
    query = """
        SELECT id, code, display_name, provider_type, base_url, auth_mode,
               supports_openai_compat, supports_streaming, supports_search, supports_vision,
               enabled, config_json
        FROM model_providers
    """
    params: list[Any] = []
    if not include_disabled:
        query += " WHERE enabled = 1"
    query += " ORDER BY id ASC"
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        items.append(
            {
                "id": int(row["id"]),
                "code": str(row["code"]),
                "display_name": str(row["display_name"]),
                "provider_type": str(row["provider_type"] or "openai_compatible"),
                "base_url": str(row["base_url"] or ""),
                "auth_mode": str(row["auth_mode"] or "api_key"),
                "supports_openai_compat": bool(row.get("supports_openai_compat")),
                "supports_streaming": bool(row.get("supports_streaming")),
                "supports_search": bool(row.get("supports_search")),
                "supports_vision": bool(row.get("supports_vision")),
                "enabled": bool(row.get("enabled")),
                "config": _json_value(row.get("config_json")) or {},
            }
        )
    return items


def provider_by_code(provider_code: str) -> dict[str, Any] | None:
    code = str(provider_code or "").strip().lower()
    if not code:
        return None
    for row in list_provider_rows(include_disabled=True):
        if row["code"] == code:
            return row
    return None


def provider_code_for_model(model: str) -> str:
    mid = str(model or "").strip().lower()
    if not mid:
        return "dashscope"
    if registry_enabled():
        catalog = list_catalog_rows(include_disabled=True)
        for item in catalog:
            if str(item["model"]).lower() == mid:
                return str(item["provider_code"])
    if mid.startswith("deepseek"):
        return "deepseek"
    return "dashscope"


def list_catalog_rows(include_disabled: bool = False) -> list[dict[str, Any]]:
    if not registry_enabled():
        return []
    query = """
        SELECT mc.id, mc.model_id, mc.display_name, mc.role_key, mc.enabled,
               mc.input_price_per_1k, mc.output_price_per_1k, mc.context_window, mc.config_json,
               mp.id AS provider_id, mp.code AS provider_code, mp.display_name AS provider_name,
               mp.base_url, mp.enabled AS provider_enabled, mp.supports_search, mp.supports_vision
        FROM model_catalog mc
        JOIN model_providers mp ON mp.id = mc.provider_id
    """
    if not include_disabled:
        query += " WHERE mc.enabled = 1 AND mp.enabled = 1"
    query += " ORDER BY mc.role_key ASC, mc.id ASC"
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        config_json = _json_value(row.get("config_json")) or {}
        items.append(
            {
                "id": int(row["id"]),
                "model": str(row["model_id"]),
                "display_name": str(row["display_name"]),
                "role": str(row["role_key"]),
                "enabled": bool(row.get("enabled")),
                "provider_id": int(row["provider_id"]),
                "provider_code": str(row["provider_code"]),
                "provider_name": str(row["provider_name"]),
                "provider_enabled": bool(row.get("provider_enabled")),
                "base_url": str(row.get("base_url") or ""),
                "supports_search": bool(row.get("supports_search")),
                "supports_vision": bool(row.get("supports_vision")),
                "input_price_per_1k": float(row["input_price_per_1k"] or 0),
                "output_price_per_1k": float(row["output_price_per_1k"] or 0),
                "context_window": int(row["context_window"]) if row.get("context_window") else None,
                "config": config_json,
            }
        )
    return items


def available_models_for_role(role: str) -> list[dict[str, Any]]:
    role_key = str(role or "").strip()
    if not registry_enabled():
        return []
    return [item for item in list_catalog_rows(include_disabled=False) if item["role"] == role_key]


def model_options_map_for_user(user_id: int | None = None) -> dict[str, dict[str, Any]]:
    if not registry_enabled():
        return _legacy_model_options()
    result: dict[str, dict[str, Any]] = {}
    by_role: dict[str, list[dict[str, Any]]] = {}
    for item in list_catalog_rows(include_disabled=False):
        by_role.setdefault(item["role"], []).append(item)

    saved = load_user_model_choices(user_id) if user_id is not None else {}
    for role, cfg in ROLE_DEFAULTS.items():
        role_cfg = _role_config_from_legacy(role)
        models = by_role.get(role, [])
        options: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in models:
            option = {
                "model": item["model"],
                "label": item["display_name"],
                "provider_code": item["provider_code"],
                "provider_name": item["provider_name"],
                "recommended": item["model"] == role_cfg.get("default_model"),
            }
            dedupe_key = (str(option["provider_code"]), str(option["model"]))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            options.append(option)
        if not options:
            legacy = _legacy_model_options().get(role)
            if legacy:
                result[role] = legacy
            continue

        selected = str(saved.get(role) or "").strip()
        if selected and all(str(item["model"]) != selected for item in options):
            result[role] = {
                "label": role_cfg["label"],
                "description": role_cfg["description"],
                "options": options,
                "selected_unavailable": {
                    "model": selected,
                    "reason": "Selected model is disabled or unavailable.",
                },
            }
            continue

        result[role] = {
            "label": role_cfg["label"],
            "description": role_cfg["description"],
            "options": options,
        }
    return result


def default_model_for_role(role: str) -> tuple[str, str]:
    role_key = str(role or "").strip()
    if registry_enabled():
        models = available_models_for_role(role_key)
        if models:
            preferred = _role_config_from_legacy(role_key).get("default_model")
            for item in models:
                if item["model"] == preferred:
                    return str(item["model"]), str(item["provider_code"])
            first = models[0]
            return str(first["model"]), str(first["provider_code"])
    cfg = ROLE_DEFAULTS.get(role_key) or {}
    return str(cfg.get("default_model") or ""), str(cfg.get("provider_code") or "dashscope")


def load_user_model_choices(user_id: int | None) -> dict[str, str]:
    if user_id is None or not registry_enabled():
        return {}
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT module_key, model_id
                FROM user_model_choices
                WHERE user_id = %s
                ORDER BY module_key ASC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
    return {str(row["module_key"]): str(row["model_id"]) for row in rows if str(row.get("model_id") or "").strip()}


def sanitize_user_model_choices(choices: dict[str, str] | None) -> tuple[dict[str, str], dict[str, str]]:
    raw = {str(k): str(v) for k, v in (choices or {}).items() if str(v or "").strip()}
    if not registry_enabled():
        return raw, {}
    available: dict[str, set[str]] = {}
    for item in list_catalog_rows(include_disabled=False):
        available.setdefault(str(item["role"]), set()).add(str(item["model"]))
    clean: dict[str, str] = {}
    warnings: dict[str, str] = {}
    for role, model in raw.items():
        if role not in ROLE_DEFAULTS:
            continue
        if model in available.get(role, set()):
            clean[role] = model
            continue
        fallback_model, _ = default_model_for_role(role)
        if fallback_model:
            clean[role] = fallback_model
            warnings[role] = f"Selected model '{model}' is unavailable; fell back to '{fallback_model}'."
    return clean, warnings


def save_user_model_choices(user_id: int, choices: dict[str, str] | None) -> tuple[dict[str, str], dict[str, str]]:
    clean, warnings = sanitize_user_model_choices(choices)
    if not registry_enabled():
        return clean, warnings
    by_role = {item["role"]: item for item in list_catalog_rows(include_disabled=False)}
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_model_choices WHERE user_id = %s", (user_id,))
            for role, model in clean.items():
                catalog = by_role.get(role)
                if catalog is None or str(catalog["model"]) != model:
                    for candidate in list_catalog_rows(include_disabled=False):
                        if candidate["role"] == role and candidate["model"] == model:
                            catalog = candidate
                            break
                if catalog is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO user_model_choices(user_id, module_key, provider_id, model_catalog_id, provider_code, model_id)
                    VALUES(%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        role,
                        catalog["provider_id"],
                        catalog["id"],
                        catalog["provider_code"],
                        catalog["model"],
                    ),
                )
    return clean, warnings


def resolve_role_choice(role: str, user_id: int | None = None) -> dict[str, Any]:
    role_key = str(role or "").strip()
    default_model, default_provider = default_model_for_role(role_key)
    selected = ""
    source = "default"
    if user_id is not None:
        saved = load_user_model_choices(user_id)
        selected = str(saved.get(role_key) or "").strip()
        if selected:
            if not registry_enabled():
                return {"role": role_key, "model": selected, "provider_code": provider_code_for_model(selected), "source": f"user:{role_key}"}
            allowed = {item["model"]: item for item in available_models_for_role(role_key)}
            if selected in allowed:
                item = allowed[selected]
                return {
                    "role": role_key,
                    "model": selected,
                    "provider_code": str(item["provider_code"]),
                    "extra_body": dict(item.get("config") or {}),
                    "source": f"user:{role_key}",
                }
            source = f"fallback:{role_key}"
    extra_body = dict((ROLE_DEFAULTS.get(role_key) or {}).get("extra_body") or {})
    if registry_enabled():
        for item in available_models_for_role(role_key):
            if item["model"] == default_model:
                extra_body.update(dict(item.get("config") or {}))
                default_provider = str(item["provider_code"])
                break
    return {
        "role": role_key,
        "model": default_model,
        "provider_code": default_provider,
        "extra_body": extra_body,
        "source": source,
    }


def validation_candidate_models(provider_code: str = "dashscope") -> list[str]:
    provider = str(provider_code or "dashscope").strip().lower()
    if not registry_enabled():
        return []
    items = [item for item in list_catalog_rows(include_disabled=True) if str(item["provider_code"]) == provider]
    seen: set[str] = set()
    models: list[str] = []
    for item in items:
        model = str(item["model"] or "").strip()
        lowered = model.lower()
        if not model or "embedding" in lowered or "rerank" in lowered:
            continue
        if model in seen:
            continue
        seen.add(model)
        models.append(model)
    return models

