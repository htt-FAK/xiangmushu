from __future__ import annotations

from typing import Any

import config
from core.dashscope_chat import direct_chat_completions_create
from core.provider_errors import classify_provider_error
from core.provider_registry import (
    provider_by_code,
    provider_code_for_model,
    validation_candidate_models as registry_validation_candidate_models,
)

MIMO_PLUGIN_URL = "https://platform.xiaomimimo.com/console/plugin?userId=2933868983"

# 每个 provider 的内置探测模型（按其自身的模型命名），用于在没有 MySQL
# provider registry 时正确校验：deepseek 只探测 deepseek 模型、mimo 只探测
# mimo 模型，避免拿 qwen 的模型名去 deepseek/mimo 端点探测而误判。
PROVIDER_FALLBACK_MODELS: dict[str, list[str]] = {
    "dashscope": [
        "qwen-plus",
        "qwen3.6-35b-a3b",
        "qwen-max",
        "qwen-flash",
        "qwen3.6-27b",
    ],
    "deepseek": [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
        "deepseek-chat",
    ],
    "mimo": [
        "mimo-v2.5-pro",
        "mimo-v2.5-pro-ultraspeed",
        "mimo-v2.5",
    ],
}


def validation_candidate_models(provider_code: str = "dashscope") -> list[str]:
    provider = str(provider_code or "dashscope").strip().lower()

    try:
        registry_models = registry_validation_candidate_models(provider)
        if registry_models:
            return registry_models
    except Exception:
        pass

    ordered: list[str] = list(PROVIDER_FALLBACK_MODELS.get(provider, []))

    # 仅 dashscope（百炼）才从 model_router / USER_MODEL_OPTIONS 补充候选模型，
    # 这些列表是混合 provider 的，直接用于 deepseek/mimo 会探测到错误的模型。
    if provider == "dashscope":
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
        # dashscope 端点只能识别 qwen 等百炼模型，过滤掉混进来的
        # deepseek-/mimo- 等其它 provider 的模型名。
        if provider == "dashscope" and (lowered.startswith("deepseek") or lowered.startswith("mimo")):
            continue
        seen.add(item)
        models.append(item)
    return models


def _base_url_for_provider(provider_code: str) -> str:
    """按 provider 解析 base_url：优先 MySQL registry，其次代码内置映射。

    这样即便没有启用 MySQL provider registry（默认 sqlite 模式），
    deepseek / mimo 也能走各自的调用端点，而不是统统退化成百炼端点。
    """
    try:
        provider = provider_by_code(provider_code)
    except Exception:
        provider = None
    if provider and str(provider.get("base_url") or "").strip():
        return str(provider.get("base_url") or "").strip()
    return config.provider_base_url(provider_code)


def _client_for_api_key(api_key: str, provider_code: str = "dashscope") -> Any:
    from openai import OpenAI

    base_url = _base_url_for_provider(provider_code)
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
        force_client=True,
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
        force_client=True,
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


def _selected_models_for_provider(user_id: int | None, provider_code: str) -> list[str]:
    if user_id is None:
        return []
    try:
        from core.provider_registry import load_user_model_choices
    except Exception:
        return []
    try:
        choices = load_user_model_choices(user_id)
    except Exception:
        return []
    selected: list[str] = []
    seen: set[str] = set()
    for model in (choices or {}).values():
        mid = str(model or "").strip()
        if not mid or mid in seen:
            continue
        try:
            model_provider = provider_code_for_model(mid)
        except Exception:
            model_provider = "dashscope"
        if model_provider == provider_code:
            selected.append(mid)
            seen.add(mid)
    return selected


def validate_user_api_key(api_key: str, provider_code: str = "dashscope", user_id: int | None = None) -> dict[str, Any]:
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
    selected_models = _selected_models_for_provider(user_id, provider_code)
    ordered = selected_models + [model for model in candidate_models if model not in selected_models]
    for model in ordered:
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
    result = _summary_result(probes)
    if selected_models:
        result["selected_models"] = selected_models
    if selected_models and not result.get("ok"):
        result["message"] = (
            f"该 API Key 无法调用当前已选模型（{selected_models[0]}）。"
            "请检查对应 Provider 的 Key、模型权限或切换已选模型。"
        )
    return result
