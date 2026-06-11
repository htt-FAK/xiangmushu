from __future__ import annotations

from typing import Any

import config
from core.dashscope_chat import direct_chat_completions_create
from core.provider_errors import classify_provider_error


def validation_candidate_models() -> list[str]:
    ordered = [
        config.SMALL_LLM_MODEL,
        "qwen3.6-flash",
        "qwen3.5-flash",
        config.VISION_WEB_MODEL,
    ]
    seen: set[str] = set()
    models: list[str] = []
    for model in ordered:
        item = (model or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        models.append(item)
    return models


def _client_for_api_key(api_key: str) -> Any:
    from openai import OpenAI

    return OpenAI(
        api_key=api_key,
        base_url=config.DASHSCOPE_COMPAT_BASE,
        timeout=min(float(config.OPENAI_TIMEOUT), 30.0),
        max_retries=0,
    )


def probe_api_key_model(api_key: str, model: str) -> dict[str, Any]:
    client = _client_for_api_key(api_key)
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
        "message": "API Key 验证成功。",
        "detail": str(getattr(response, "model", None) or model),
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
                "message": item.get("message") or "API Key 验证失败。",
                "retryable": bool(item.get("retryable", code in {"network_error", "provider_error", "model_unavailable", "unknown_error"})),
                "validated_model": None,
                "probes": probes,
            }
    return {
        "ok": False,
        "code": "unknown_error",
        "message": "API Key 验证失败。",
        "retryable": True,
        "validated_model": None,
        "probes": probes,
    }


def validate_user_api_key(api_key: str) -> dict[str, Any]:
    value = (api_key or "").strip()
    if not value:
        return {
            "ok": False,
            "code": "invalid_api_key",
            "message": "API Key 不能为空。",
            "retryable": False,
            "validated_model": None,
            "probes": [],
        }

    probes: list[dict[str, Any]] = []
    for model in validation_candidate_models():
        try:
            result = probe_api_key_model(value, model)
            probes.append(result)
            if result.get("ok"):
                return {
                    "ok": True,
                    "code": "ok",
                    "message": "API Key 验证成功，可用于后续生成。",
                    "retryable": False,
                    "validated_model": model,
                    "probes": probes,
                }
        except Exception as exc:
            classified = classify_provider_error(exc)
            probes.append({
                "ok": False,
                "model": model,
                **classified,
            })
    return _summary_result(probes)
