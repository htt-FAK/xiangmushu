from __future__ import annotations

from typing import Any

import config
from core.billing import load_provider_api_key, load_provider_api_key_validation
from core.provider_registry import provider_by_code, provider_code_for_model


def env_api_key_for_provider(provider_code: str) -> str:
    code = str(provider_code or "").strip().lower()
    if code == "dashscope":
        return (config.DASHSCOPE_API_KEY or config.OPENAI_API_KEY or "").strip()
    if code == "deepseek":
        return (getattr(config, "DEEPSEEK_API_KEY", "") or "").strip()
    if code == "mimo":
        return (getattr(config, "MIMO_API_KEY", "") or "").strip()
    return ""


def provider_base_url(provider_code: str) -> str:
    provider = provider_by_code(provider_code) or {}
    base_url = str(provider.get("base_url") or "").strip()
    if base_url:
        return base_url
    code = str(provider_code or "").strip().lower()
    if code == "dashscope":
        return config.DASHSCOPE_COMPAT_BASE
    if code == "deepseek":
        return str(getattr(config, "DEEPSEEK_BASE_URL", "") or "").strip() or "https://api.deepseek.com"
    if code == "mimo":
        return "https://api.xiaomimimo.com/v1"
    return config.OPENAI_BASE_URL


def provider_key_status_for_user(user_id: int, provider_code: str) -> dict[str, Any]:
    validation = load_provider_api_key_validation(user_id, provider_code)
    return {
        "provider_code": provider_code,
        "has_user_key": bool(load_provider_api_key(user_id, provider_code)),
        "validation": validation,
    }


def api_key_for_provider(provider_code: str, user_id: int | None = None) -> str:
    if user_id is not None:
        user_key = load_provider_api_key(user_id, provider_code)
        if user_key:
            return user_key
    return env_api_key_for_provider(provider_code)


def client_for_provider(
    provider_code: str,
    user_id: int | None = None,
    *,
    purpose: str = "chat",
    timeout: float | None = None,
    max_retries: int | None = None,
) -> Any:
    from openai import OpenAI

    code = str(provider_code or "").strip().lower() or "dashscope"
    api_key = api_key_for_provider(code, user_id)
    if not api_key:
        raise ValueError(f"No API key available for provider '{code}'")
    resolved_timeout = config.OPENAI_TIMEOUT if timeout is None else timeout
    if purpose == "template_analysis":
        resolved_timeout = timeout if timeout is not None else config.TEMPLATE_ANALYZE_TIMEOUT
    return OpenAI(
        api_key=api_key,
        base_url=provider_base_url(code),
        timeout=resolved_timeout,
        max_retries=config.OPENAI_MAX_RETRIES if max_retries is None else max_retries,
    )


def chat_client_for_model(
    model_id: str,
    user_id: int | None = None,
    *,
    purpose: str = "chat",
    timeout: float | None = None,
    max_retries: int | None = None,
) -> Any:
    provider_code = provider_code_for_model(model_id)
    return client_for_provider(
        provider_code,
        user_id,
        purpose=purpose,
        timeout=timeout,
        max_retries=max_retries,
    )
