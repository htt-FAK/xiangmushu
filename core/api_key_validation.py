from __future__ import annotations

from typing import Any

import config
from core.dashscope_chat import direct_chat_completions_create
from core.provider_errors import classify_provider_error
from core.provider_registry import provider_by_code, validation_candidate_models as registry_validation_candidate_models

MIMO_PLUGIN_URL = "https://platform.xiaomimimo.com/console/plugin?userId=2933868983"


def validation_candidate_models(provider_code: str = "dashscope") -> list[str]:
    try:
        registry_models = registry_validation_candidate_models(provider_code)
        if registry_models:
            return registry_models
    except Exception:
        pass

    ordered: list[str] = [
        "qwen-plus",
        "qwen3.6-35b-a3b",
        "qwen-max",
        "qwen-flash",
        "qwen3.6-27b",
    ]

    try:
        from core.model_router import model_roles

        for profile in model_roles().values():
            ordered.append(profile.default_model)
            ordered.extend(profile.fallback_models)
    except Exception:
        pass

    for module in getattr(config, "USER_MODEL_OPTIONS", {}).values():
        for group in (module.get("tiers") or {}).values():
            for item in group:
                ordered.append(str((item or {}).get("model") or ""))
        for item in module.get("options") or []:
            ordered.append(str((item or {}).get("model") or ""))

    ordered.extend(getattr(config, "AI_MODEL_PRICING", {}).keys())

    seen: set[str] = set()
    models: list[str] = []
    for model in ordered:
        item = str(model or "").strip()
        lowered = item.lower()
        if lowered.startswith("text-embedding") or "embedding" in lowered or "rerank" in lowered:
            continue
        if not item or item in seen:
            continue
        seen.add(item)
        models.append(item)
    return models


def _client_for_api_key(api_key: str, provider_code: str = "dashscope") -> Any:
    from openai import OpenAI

    provider = provider_by_code(provider_code)
    base_url = config.DASHSCOPE_COMPAT_BASE
    if provider and str(provider.get("base_url") or "").strip():
        base_url = str(provider.get("base_url") or "").strip()
    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=min(float(config.OPENAI_TIMEOUT), 30.0),
        max_retries=0,
    )


def probe_api_key_model(api_key: str, model: str, provider_code: str = "dashscope") -> dict[str, Any]:
    client = _client_for_api_key(api_key, provider_code)
    response = direct_chat_completions_create(
        client,
        model=model,
        messages=[
            {"role": "system", "content": "Return OK."},
            {"role": "user", "content": "Reply with OK only."},
        ],
        max_tokens=8,
        temperature=0,
    )
    return {
        "ok": True,
        "model": model,
        "code": "ok",
        "message": "API Key validation succeeded.",
        "detail": str(getattr(response, "model", None) or model),
        "provider_code": provider_code,
    }


def probe_mimo_search_plugin(api_key: str) -> dict[str, Any]:
    client = _client_for_api_key(api_key, "mimo")
    response = direct_chat_completions_create(
        client,
        model="mimo-v2.5-pro",
        messages=[
            {"role": "system", "content": "Return OK."},
            {"role": "user", "content": "Reply with OK only."},
        ],
        max_tokens=8,
        temperature=0,
        tools=[{"type": "web_search", "max_keyword": 1, "force_search": False, "limit": 1}],
        tool_choice="auto",
    )
    return {
        "ok": True,
        "model": "mimo-v2.5-pro",
        "code": "ok",
        "message": "MiMo web search plugin validation succeeded.",
        "detail": str(getattr(response, "model", None) or "mimo-v2.5-pro"),
        "provider_code": "mimo",
        "search_enabled": True,
    }


def _summary_result(probes: list[dict[str, Any]]) -> dict[str, Any]:
    priority = [
        "invalid_api_key",
        "quota_exceeded",
        "permission_denied",
        "network_error",
        "provider_error",
        "model_unavailable",
        "unknown_error",
    ]
    by_code = {str(item.get("code") or "unknown_error"): item for item in probes}
    for code in priority:
        if code in by_code:
            item = by_code[code]
            return {
                "ok": False,
                "code": code,
                "message": item.get("message") or "API Key validation failed.",
                "retryable": bool(item.get("retryable", code in {"network_error", "provider_error", "model_unavailable", "unknown_error"})),
                "validated_model": None,
                "provider_code": item.get("provider_code") or "dashscope",
                "probes": probes,
            }
    return {
        "ok": False,
        "code": "unknown_error",
        "message": "API Key validation failed.",
        "retryable": True,
        "validated_model": None,
        "provider_code": "dashscope",
        "probes": probes,
    }


def validate_user_api_key(api_key: str, provider_code: str = "dashscope") -> dict[str, Any]:
    value = str(api_key or "").strip()
    if not value:
        return {
            "ok": False,
            "code": "invalid_api_key",
            "message": "API Key cannot be empty.",
            "retryable": False,
            "validated_model": None,
            "provider_code": provider_code,
            "probes": [],
        }

    probes: list[dict[str, Any]] = []
    try:
        candidate_models = validation_candidate_models(provider_code)
    except TypeError:
        candidate_models = validation_candidate_models()
    for model in candidate_models:
        try:
            result = probe_api_key_model(value, model, provider_code)
            probes.append(result)
            if result.get("ok"):
                if provider_code == "mimo":
                    try:
                        plugin_probe = probe_mimo_search_plugin(value)
                        probes.append(plugin_probe)
                    except Exception as exc:
                        classified = classify_provider_error(exc)
                        probes.append(
                            {
                                "ok": False,
                                "model": "mimo-v2.5-pro",
                                "provider_code": "mimo",
                                "code": "mimo_search_plugin_required",
                                "message": (
                                    "MiMo text validation passed, but web search is not enabled. "
                                    f"Please enable the MiMo plugin service at {MIMO_PLUGIN_URL}."
                                ),
                                "detail": classified.get("detail") or str(exc),
                                "retryable": False,
                                "search_enabled": False,
                            }
                        )
                        return {
                            "ok": False,
                            "code": "mimo_search_plugin_required",
                            "message": (
                                "MiMo text validation passed, but web search is not enabled. "
                                f"Please enable the MiMo plugin service at {MIMO_PLUGIN_URL}."
                            ),
                            "retryable": False,
                            "validated_model": model,
                            "provider_code": provider_code,
                            "probes": probes,
                            "search_enabled": False,
                        }
                return {
                    "ok": True,
                    "code": "ok",
                    "message": "API Key validation succeeded and is ready to use.",
                    "retryable": False,
                    "validated_model": model,
                    "provider_code": provider_code,
                    "probes": probes,
                    "search_enabled": provider_code != "mimo" or True,
                }
        except Exception as exc:
            classified = classify_provider_error(exc)
            probes.append(
                {
                    "ok": False,
                    "model": model,
                    "provider_code": provider_code,
                    **classified,
                }
            )
    return _summary_result(probes)
