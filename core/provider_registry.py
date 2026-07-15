from __future__ import annotations

import json
import logging
import re
from typing import Any

import config
from core.db import mysql_enabled, mysql_transaction, get_custom_models_by_user

LOG = logging.getLogger(__name__)


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

UI_ROLE_KEYS: tuple[str, ...] = (
    "main_writer",
    "fast_writer",
    "vision_layout",
    "template_planner",
    "audit_text",
    "embedding",
)

ROLE_LEGACY_SEED_MODULES: dict[str, str] = {
    "main_writer": "generation",
    "fast_writer": "lightweight",
    "vision_layout": "vision",
    "template_planner": "lightweight",
    "audit_text": "audit",
}

_ROLE_CAPABILITY_MAP: dict[str, tuple[str, ...]] = {
    "main_writer": ("text",),
    "fast_writer": ("text",),
    "vision_layout": ("text", "vision"),
    "template_planner": ("text",),
    "audit_text": ("text",),
    "embedding": ("embedding",),
}

_ROLE_LEGACY_ALIASES: dict[str, tuple[str, ...]] = {
    "main_writer": ("text-gen",),
    "fast_writer": ("small-llm",),
    "vision_layout": ("vision",),
    "template_planner": ("text-gen",),
    "audit_text": ("audit",),
    "embedding": ("embedding",),
}

KNOWN_MODEL_DISPLAY_NAMES: dict[str, str] = {
    "qwen3.7-plus": "Qwen 3.7 Plus",
    "qwen3.7-max": "Qwen 3.7 Max",
    "qwen3.6-plus": "Qwen 3.6 Plus",
    "qwen3.6-flash": "Qwen 3.6 Flash",
    "qwen3.6-35b-a3b": "Qwen 3.6 35B A3B",
    "qwen3.5-plus": "Qwen 3.5 Plus",
    "qwen3.5-flash": "Qwen 3.5 Flash",
    "deepseek-v4-pro": "DeepSeek V4 Pro",
    "deepseek-v4-flash": "DeepSeek V4 Flash",
    "deepseek-chat": "DeepSeek Chat",
    "deepseek-reasoner": "DeepSeek Reasoner",
    "mimo-v2.5-pro": "MiMo V2.5 Pro",
    "mimo-v2.5-pro-ultraspeed": "MiMo V2.5 Pro UltraSpeed",
    "mimo-v2.5": "MiMo V2.5",
    "text-embedding-v4": "Text Embedding V4",
}

SUPPORTED_PROVIDER_CODES: tuple[str, ...] = ("dashscope", "deepseek", "mimo")
ROLE_PROVIDER_MATRIX: dict[str, tuple[str, ...]] = {
    "main_writer": ("dashscope", "deepseek", "mimo"),
    "fast_writer": ("dashscope", "deepseek", "mimo"),
    "vision_layout": ("dashscope", "mimo"),
    "template_planner": ("dashscope", "deepseek", "mimo"),
    "audit_text": ("dashscope", "deepseek", "mimo"),
    "embedding": ("dashscope",),
}
STRICT_PROVIDER_ROLE_MODELS: dict[str, dict[str, tuple[str, ...]]] = {
    "deepseek": {
        "main_writer": ("deepseek-v4-pro", "deepseek-v4-flash"),
        "fast_writer": ("deepseek-v4-flash",),
        "template_planner": ("deepseek-v4-flash",),
        "audit_text": ("deepseek-v4-flash",),
    },
    "mimo": {
        "main_writer": ("mimo-v2.5-pro", "mimo-v2.5"),
        "fast_writer": ("mimo-v2.5",),
        "vision_layout": ("mimo-v2.5",),
        "template_planner": ("mimo-v2.5-pro", "mimo-v2.5"),
        "audit_text": ("mimo-v2.5-pro", "mimo-v2.5"),
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


def _flatten_option_models(cfg: dict[str, Any] | None) -> list[str]:
    items = dict(cfg or {})
    models: list[str] = []
    seen: set[str] = set()
    for group in (items.get("tiers") or {}).values():
        for item in group:
            model = str((item or {}).get("model") or "").strip()
            if not model or model in seen:
                continue
            seen.add(model)
            models.append(model)
    for item in items.get("options") or []:
        model = str((item or {}).get("model") or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        models.append(model)
    return models


def _provider_code_for_seed_model(model: str) -> str | None:
    value = str(model or "").strip().lower()
    if not value:
        return None
    if value.startswith("deepseek-"):
        return "deepseek"
    if value.startswith("mimo-"):
        return "mimo"
    if value.startswith("qwen") or value.startswith("text-embedding"):
        return "dashscope"
    return None


def _title_token(token: str) -> str:
    if not token:
        return token
    if token.lower() in {"v4", "v3", "a3b"}:
        return token.upper()
    if re.fullmatch(r"\d+b", token.lower()):
        return token.upper()
    if token.lower().startswith("qwen"):
        suffix = token[4:]
        return f"Qwen {suffix}".strip()
    if token.lower() == "deepseek":
        return "DeepSeek"
    return token.capitalize()


def model_display_name(model: str) -> str:
    value = str(model or "").strip()
    if not value:
        return ""
    known = KNOWN_MODEL_DISPLAY_NAMES.get(value.lower())
    if known:
        return known
    parts = re.split(r"[-_]+", value)
    titled = [_title_token(part) for part in parts if part]
    return " ".join(titled) or value


def role_seed_model_ids(role: str) -> list[str]:
    role_key = str(role or "").strip()
    direct = _flatten_option_models(_legacy_model_options().get(role_key))
    if direct:
        models = list(direct)
    else:
        legacy_module = ROLE_LEGACY_SEED_MODULES.get(role_key, "")
        models = _flatten_option_models(_legacy_model_options().get(legacy_module))
    default_model = str((ROLE_DEFAULTS.get(role_key) or {}).get("default_model") or "").strip()
    if default_model and default_model not in models:
        models.append(default_model)
    curated: dict[str, list[str]] = {
        "main_writer": ["qwen3.7-plus", "deepseek-v4-pro", "deepseek-v4-flash", "mimo-v2.5-pro", "mimo-v2.5"],
        "fast_writer": ["qwen3.6-flash", "deepseek-v4-flash", "mimo-v2.5"],
        "vision_layout": ["qwen3.7-plus", "mimo-v2.5"],
        "template_planner": ["qwen3.6-flash", "deepseek-v4-flash", "mimo-v2.5-pro", "mimo-v2.5"],
        "audit_text": ["qwen3.6-flash", "deepseek-v4-flash", "mimo-v2.5-pro", "mimo-v2.5"],
        "embedding": ["text-embedding-v4"],
    }
    for model in curated.get(role_key, []):
        if model not in models:
            models.append(model)
    return models


def _capabilities_for_seed_role(role: str) -> list[str]:
    role_key = str(role or "").strip()
    if role_key == "embedding":
        return ["embedding"]
    if role_key == "vision_layout":
        return ["text", "vision"]
    if role_key in {"main_writer", "fast_writer"}:
        return ["text", "streaming"]
    return ["text"]


def _supports_role_provider(role: str, provider_code: str) -> bool:
    return str(provider_code or "").strip().lower() in ROLE_PROVIDER_MATRIX.get(str(role or "").strip(), ())


def _seed_model_allowed_for_role(role: str, provider_code: str, model: str) -> bool:
    role_key = str(role or "").strip()
    code = str(provider_code or "").strip().lower()
    model_id = str(model or "").strip()
    if not model_id or not _supports_role_provider(role_key, code):
        return False
    strict = STRICT_PROVIDER_ROLE_MODELS.get(code)
    if strict is None:
        return True
    return model_id in strict.get(role_key, ())


def catalog_seed_candidates() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role in UI_ROLE_KEYS:
        role_cfg = ROLE_DEFAULTS.get(role) or {}
        role_config = dict(role_cfg.get("extra_body") or {})
        for model in role_seed_model_ids(role):
            provider_code = _provider_code_for_seed_model(model)
            if provider_code is None:
                continue
            if not _seed_model_allowed_for_role(role, provider_code, model):
                continue
            pricing = dict(getattr(config, "AI_MODEL_PRICING", {}).get(model) or {})
            rows.append(
                {
                    "role": role,
                    "provider_code": provider_code,
                    "model": model,
                    "display_name": model_display_name(model),
                    "capabilities": _capabilities_for_seed_role(role),
                    "input_price_per_1k": pricing.get("input"),
                    "output_price_per_1k": pricing.get("output"),
                    "context_window": None,
                    "config": dict(role_config),
                }
            )
    return rows


def _known_role_keys() -> set[str]:
    return set(ROLE_DEFAULTS) | {str(key) for key in getattr(config, "USER_MODEL_OPTIONS", {}).keys()}


def _registry_warning(message: str, exc: Exception | None = None) -> str:
    if exc is not None:
        LOG.warning("%s: %s", message, exc)
    return message


def _legacy_model_options_with_metadata(warning: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for role, cfg in _legacy_model_options().items():
        payload = dict(cfg)
        payload.setdefault("label", _role_config_from_legacy(role).get("label") or role)
        payload.setdefault("description", _role_config_from_legacy(role).get("description") or "")
        payload["source"] = "legacy_fallback"
        payload["warning"] = warning
        result[role] = payload
    for role, cfg in ROLE_DEFAULTS.items():
        if role in result:
            continue
        result[role] = {
            "label": cfg.get("label") or role,
            "description": cfg.get("description") or "",
            "options": [
                {
                    "model": cfg.get("default_model") or "",
                    "label": cfg.get("default_model") or "",
                    "provider_code": cfg.get("provider_code") or "dashscope",
                    "recommended": True,
                }
            ],
            "source": "legacy_fallback",
            "warning": warning,
        }
    return result


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
    if mid.startswith("mimo-"):
        return "mimo"
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
        query += " WHERE mc.enabled = 1"
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


def _user_provider_gate(user_id: int | None) -> dict[str, bool]:
    gates = {"dashscope": True, "deepseek": False, "mimo": False, "mimo_search": False}
    if user_id is None:
        return gates
    try:
        from core.billing import load_provider_api_key_validation, provider_api_key_status_map

        statuses = provider_api_key_status_map(user_id, SUPPORTED_PROVIDER_CODES)
        for provider_code in ("deepseek", "mimo"):
            item = statuses.get(provider_code) or {}
            gates[provider_code] = bool(item.get("has_key") and item.get("validated"))
        mimo_validation = load_provider_api_key_validation(user_id, "mimo")
        gates["mimo_search"] = bool(gates["mimo"] and mimo_validation.get("search_enabled"))
    except Exception:
        return gates
    return gates


def _catalog_rows_for_user(user_id: int | None) -> list[dict[str, Any]]:
    rows = list_catalog_rows(include_disabled=False)
    gates = _user_provider_gate(user_id)
    filtered: list[dict[str, Any]] = []
    for item in rows:
        role = str(item["role"])
        provider_code = str(item["provider_code"])
        if not _supports_role_provider(role, provider_code):
            continue
        if provider_code == "dashscope":
            filtered.append(item)
            continue
        if provider_code == "deepseek":
            if gates["deepseek"]:
                filtered.append(item)
            continue
        if provider_code == "mimo":
            if gates["mimo"]:
                filtered.append(item)
    return filtered


def _custom_model_options_for_role(
    role: str,
    custom_models: list[Any],
) -> list[dict[str, Any]]:
    """Return ModelOption dicts from *custom_models* that qualify for *role*.

    A custom model qualifies when:
    1. Its ``assigned_roles`` contains a legacy role alias that maps to *role*
       (see ``_ROLE_LEGACY_ALIASES``), OR
    2. Its ``capabilities`` contain ALL capabilities required by *role*
       (see ``_ROLE_CAPABILITY_MAP``).

    Returns an empty list when no models match.
    """
    role_key = str(role or "").strip()
    required_caps = set(_ROLE_CAPABILITY_MAP.get(role_key, ()))
    legacy_aliases = set(_ROLE_LEGACY_ALIASES.get(role_key, ()))
    options: list[dict[str, Any]] = []
    seen_model_ids: set[str] = set()
    for row in custom_models:
        # ``row`` is a ``CustomModel`` dataclass from core.db.
        model_id = str(row.default_model_id or "").strip()
        if not model_id or model_id in seen_model_ids:
            continue
        assigned = set(row.assigned_roles_json or [])
        capabilities = set(row.capabilities_json or [])
        role_match = bool(assigned & legacy_aliases)
        cap_match = required_caps and required_caps.issubset(capabilities)
        if not (role_match or cap_match):
            continue
        seen_model_ids.add(model_id)
        options.append(
            {
                "model": model_id,
                "label": f"{row.name} ({model_id})",
                "provider_code": "custom",
                "provider_name": "自定义 / Custom",
                "recommended": False,
                "source": "custom",
                "custom_model_id": row.id,
            }
        )
    return options


def model_options_map_for_user(user_id: int | None = None) -> dict[str, dict[str, Any]]:
    if not registry_enabled():
        return _legacy_model_options()
    try:
        catalog_rows = _catalog_rows_for_user(user_id)
    except Exception as exc:
        warning = _registry_warning("Model registry is unavailable; falling back to legacy model options.", exc)
        return _legacy_model_options_with_metadata(warning)
    result: dict[str, dict[str, Any]] = {}
    by_role: dict[str, list[dict[str, Any]]] = {}
    for item in catalog_rows:
        by_role.setdefault(item["role"], []).append(item)

    try:
        saved = load_user_model_choices(user_id) if user_id is not None else {}
        load_warning = ""
    except Exception as exc:
        saved = {}
        load_warning = _registry_warning("Saved model selections could not be loaded from the registry.", exc)
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
            "source": "registry",
        }
        if load_warning:
            result[role]["warning"] = load_warning

    # ── Merge custom models into each role's options (Task 4.1) ──────
    if user_id is not None:
        try:
            custom_models = get_custom_models_by_user(user_id)
            if custom_models:
                for role, entry in result.items():
                    custom_opts = _custom_model_options_for_role(role, custom_models)
                    if not custom_opts:
                        continue
                    # Guard: ``options`` key may be missing when the role
                    # fell back to ``_legacy_model_options()``; rebuild.
                    opts = list(entry.get("options") or [])
                    seen_ids: set[int] = {
                        int(o.get("custom_model_id"))
                        for o in opts
                        if o.get("custom_model_id") is not None
                    }
                    for co in custom_opts:
                        cid = co.get("custom_model_id")
                        if cid is not None and int(cid) in seen_ids:
                            continue
                        opts.append(co)
                        if cid is not None:
                            seen_ids.add(int(cid))
                    entry["options"] = opts
        except Exception as exc:  # noqa: BLE001 - DB/custom fetch failure
            LOG.warning(
                "model_options custom_merge user=%s err=%s",
                user_id, exc,
            )

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


def sanitize_user_model_choices(
    choices: dict[str, str] | None,
    user_id: int | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    known_roles = _known_role_keys()
    raw = {
        str(k): str(v)
        for k, v in (choices or {}).items()
        if str(k or "").strip() in known_roles and str(v or "").strip()
    }
    if not registry_enabled():
        return raw, {}
    try:
        catalog_rows = _catalog_rows_for_user(user_id)
    except Exception as exc:
        warning = _registry_warning(
            "模型注册表不可用：已直接保留您选择的模型，暂未校验可用状态",
            exc,
        )
        return raw, {role: warning for role in raw}
    available: dict[str, set[str]] = {}
    for item in catalog_rows:
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
            warnings[role] = f"所选模型 '{model}' 暂时不可用，已自动降级至默认模型 '{fallback_model}'"
    return clean, warnings


def save_user_model_choices(user_id: int, choices: dict[str, str] | None) -> tuple[dict[str, str], dict[str, str]]:
    clean, warnings = sanitize_user_model_choices(choices, user_id=user_id)
    if not registry_enabled():
        return clean, warnings
    try:
        catalog_rows = _catalog_rows_for_user(user_id)
    except Exception as exc:
        warning = _registry_warning(
            "模型注册表不可用：您的模型选择仅保存在本地 JSON 首选项中",
            exc,
        )
        merged = dict(warnings)
        for role in clean:
            merged.setdefault(role, warning)
        return clean, merged
    by_role = {item["role"]: item for item in catalog_rows}
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM user_model_choices WHERE user_id = %s", (user_id,))
            for role, model in clean.items():
                catalog = by_role.get(role)
                if catalog is None or str(catalog["model"]) != model:
                    for candidate in catalog_rows:
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
            allowed = {item["model"]: item for item in _catalog_rows_for_user(user_id) if item["role"] == role_key}
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
        for item in _catalog_rows_for_user(user_id):
            if item["role"] != role_key:
                continue
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
    items = [item for item in list_catalog_rows(include_disabled=False) if str(item["provider_code"]) == provider]
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
