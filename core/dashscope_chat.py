"""百炼/DeepSeek compatible-mode：chat 请求统一关闭深度思考。

Native enable_search injection was removed — Firecrawl pre-injects web
evidence into the prompt; we no longer toggle enable_search on DashScope.

DeepSeek 模型（deepseek-v4-pro）：禁用 thinking（{"thinking": {"type": "disabled"}}）。
百炼模型（qwen 系列）：enable_thinking=False。
网关优先时：可恢复类错误自动回落到百炼 compatible-mode（须配置 DASHSCOPE_API_KEY）。"""
from __future__ import annotations

import logging
from typing import Any

import config

_LOG = logging.getLogger(__name__)

try:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        PermissionDeniedError,
        RateLimitError,
    )
except ImportError:  # 极端旧版 SDK
    APIConnectionError = APITimeoutError = RateLimitError = Exception  # type: ignore
    APIStatusError = AuthenticationError = PermissionDeniedError = Exception  # type: ignore


def _client_base_url(client: Any) -> str:
    raw = getattr(client, "base_url", None)
    if raw is None:
        return ""
    return str(raw).rstrip("/")


def _normalize_base_url(base_url: str | None) -> str:
    return str(base_url or "").rstrip("/").lower()


def _is_dashscope_compatible_base_url(base_url: str | None) -> bool:
    u = _normalize_base_url(base_url)
    return "dashscope.aliyuncs.com" in u or "compatible-mode" in u


def _is_deepseek_base_url(base_url: str | None) -> bool:
    return "api.deepseek.com" in _normalize_base_url(base_url)


def _is_mimo_base_url(base_url: str | None) -> bool:
    return "api.xiaomimimo.com" in _normalize_base_url(base_url)


def _is_dashscope_compatible_client(client: Any) -> bool:
    return _is_dashscope_compatible_base_url(_client_base_url(client))


def _is_deepseek_client(client: Any) -> bool:
    return _is_deepseek_base_url(_client_base_url(client))


def _is_mimo_client(client: Any) -> bool:
    return _is_mimo_base_url(_client_base_url(client))


def _apply_extra_body(client: Any, extra_in: dict | None) -> dict | None:
    """DeepSeek 用 thinking.type=disabled；百炼用 enable_thinking=False；MiMo 保留显式 thinking。"""
    extra = dict(extra_in or {})
    mimo_thinking = extra.get("thinking")
    extra.pop("enable_thinking", None)
    extra.pop("thinking", None)
    if _is_deepseek_client(client):
        extra["thinking"] = {"type": "disabled"}
    elif _is_mimo_client(client):
        if mimo_thinking is not None:
            extra["thinking"] = mimo_thinking
    elif _is_dashscope_compatible_client(client):
        extra["enable_thinking"] = False
    return extra if extra else None


def prepare_chat_request(client: Any, force_client: bool = False, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
    """为直连 SDK 调用补齐关闭深度思考所需参数。

    force_client=True 时不做跨通道客户端切换（用于 BYOK 校验：必须用
    传入的、携带用户自己 Key 的客户端，而不是全局 deepseek_client）。"""
    kw = dict(kwargs)
    model_id = str(kw.get("model") or "")
    if not force_client and config.is_deepseek_model(model_id):
        deepseek_client = config.deepseek_client()
        if deepseek_client is not None:
            client = deepseek_client
    extra = dict(kw.pop("extra_body", None) or {})
    merged = _apply_extra_body(client, extra)
    if merged is not None:
        kw["extra_body"] = merged
    else:
        kw.pop("extra_body", None)
    return client, kw


def prepare_raw_chat_body(base_url: str | None, body_in: dict[str, Any]) -> dict[str, Any]:
    """为裸 HTTP chat/completions 请求补齐关闭深度思考所需字段。"""
    body = dict(body_in)
    body.pop("enable_thinking", None)
    body.pop("thinking", None)
    if _is_deepseek_base_url(base_url):
        body["thinking"] = {"type": "disabled"}
    elif _is_dashscope_compatible_base_url(base_url):
        body["enable_thinking"] = False
    return body


def direct_chat_completions_create(client: Any, force_client: bool = False, **kwargs: Any):
    """直连 SDK 调用：统一关闭深度思考，但不做跨通道回落。

    force_client=True 时强制使用传入的客户端（BYOK 校验用），避免被全局
    deepseek_client 覆盖。"""
    call_client, call_kwargs = prepare_chat_request(client, force_client=force_client, **kwargs)
    try:
        return call_client.chat.completions.create(**call_kwargs)
    except Exception as exc:
        merged = dict(call_kwargs.get("extra_body", None) or {})
        if merged and "enable_thinking" in merged and _is_enable_thinking_rejected(exc):
            retry_kwargs = dict(call_kwargs)
            retry_extra = dict(merged)
            retry_extra.pop("enable_thinking", None)
            if retry_extra:
                retry_kwargs["extra_body"] = retry_extra
            else:
                retry_kwargs.pop("extra_body", None)
            _LOG.warning("网关不支持 enable_thinking，已去掉该参数后重试")
            return call_client.chat.completions.create(**retry_kwargs)
        raise


def _is_enable_thinking_rejected(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "enable_thinking" in msg and (
        "unknown parameter" in msg
        or "unknown_parameter" in msg
        or "invalid_request" in msg
    )


def _kwargs_for_dashscope_backup(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Fallback to DashScope backup: strip enable_thinking; preserve existing extra_body."""
    bk = dict(kwargs)
    extra = dict(bk.pop("extra_body", None) or {})
    extra.pop("enable_thinking", None)
    if extra:
        bk["extra_body"] = extra
    else:
        bk.pop("extra_body", None)
    return bk


def _is_cross_provider_model(model: str) -> bool:
    mid = str(model or "").strip().lower()
    return mid.startswith("deepseek") or mid.startswith("mimo-")


def _dashscope_fallback_model(model: str) -> str:
    if _is_cross_provider_model(model):
        return str(getattr(config, "MAIN_WRITER_MODEL", "") or "qwen3.7-plus")
    return model


def _chat_content_empty(response: Any) -> bool:
    try:
        return not (response.choices[0].message.content or "").strip()
    except (AttributeError, IndexError, TypeError, KeyError):
        return True


def _error_response_content(response: Any) -> str:
    try:
        return (response.choices[0].message.content or "").strip()
    except (AttributeError, IndexError, TypeError, KeyError):
        return ""


def _is_error_response(response: Any) -> bool:
    """检测响应内容是否为 API 错误信息。"""
    content = _error_response_content(response)
    if not content:
        return False
    error_markers = [
        "Error code:",
        "error:",
        "'error':",
        "AllocationQuota",
        "FreeTierOnly",
        "exhausted",
        "chatcmpl-",
        "request_id",
        "The free tier",
        "paid basis",
    ]
    return any(marker in content for marker in error_markers)


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (APIConnectionError, APITimeoutError, RateLimitError)):
        return True
    if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
        return True
    if isinstance(exc, APIStatusError):
        code = getattr(exc, "status_code", None)
        if code is None:
            resp = getattr(exc, "response", None)
            if resp is not None:
                code = getattr(resp, "status_code", None)
        if code in (402, 408, 429, 500, 502, 503, 504):
            return True
    return False


def _create_on_client(client: Any, kwargs: dict[str, Any], extra_in: dict) -> Any:
    kw = dict(kwargs)
    if extra_in:
        kw["extra_body"] = dict(extra_in)
    call_client, call_kwargs = prepare_chat_request(client, **kw)
    return call_client.chat.completions.create(**call_kwargs)


def chat_completions_create(client: Any, **kwargs: Any):
    """
    包装 OpenAI SDK 的 chat.completions.create。

    - DeepSeek 模型（deepseek-*）：自动切换到 DeepSeek client，extra_body 写入
      thinking.type=disabled 关闭深度思考。
    - 百炼模型（qwen* 等）：extra_body 写入 enable_thinking=False。

    当发生可恢复错误时，使用百炼 Key 重试同一请求
    （stream=True 时仅捕获 create 阶段异常；迭代期错误不包装）。
    """
    backup_client = kwargs.pop("backup_client", None)
    allow_cross_provider_fallback = bool(kwargs.pop("allow_cross_provider_fallback", False))
    allow_backup_fallback = bool(kwargs.pop("allow_backup_fallback", True))
    extra = dict(kwargs.pop("extra_body", None) or {})
    client, kwargs = prepare_chat_request(client, **kwargs, extra_body=extra)
    merged = dict(kwargs.get("extra_body", None) or {})
    if not merged:
        kwargs.pop("extra_body", None)
    enable_search = bool((merged or {}).get("enable_search"))
    original_model = str(kwargs.get("model") or "")

    backup = backup_client or config.dashscope_backup_chat_client()
    allow_backup = allow_backup_fallback and (
        allow_cross_provider_fallback or not _is_cross_provider_model(original_model)
    )
    fallback_model = _dashscope_fallback_model(original_model)

    try:
        resp = _create_on_client(client, kwargs, extra)
        # 检测错误内容
        if _is_error_response(resp):
            error_content = _error_response_content(resp)
            if error_content:
                raise RuntimeError(error_content)
            _LOG.error("主通道返回错误内容，尝试切换备用通道")
            if allow_backup and backup is not None and backup is not client:
                try:
                    backup_kwargs = _kwargs_for_dashscope_backup(kwargs)
                    backup_kwargs["model"] = fallback_model
                    backup_resp = _create_on_client(
                        backup,
                        backup_kwargs,
                        extra,
                    )
                    if not _is_error_response(backup_resp):
                        return backup_resp
                except Exception as backup_e:
                    _LOG.warning("备用通道也失败: %s", backup_e)
            # 返回空响应，让上层处理
            raise APIStatusError(
                "模型返回错误内容，请检查 API 配置或配额",
                response=getattr(resp, "response", None),
                body=None,
            )
        if (
            _chat_content_empty(resp)
            and allow_backup
            and backup is not None
            and backup is not client
            and not _is_dashscope_compatible_client(client)
        ):
            _LOG.warning(
                "chat 主通道空回复 (model=%s)，切换百炼 compatible-mode 重试",
                kwargs.get("model"),
            )
            backup_kwargs = _kwargs_for_dashscope_backup(kwargs)
            backup_kwargs["model"] = fallback_model
            return _create_on_client(backup, backup_kwargs, extra)
        return resp
    except Exception as e:
        if merged and "enable_thinking" in merged and _is_enable_thinking_rejected(e):
            kwargs_retry = dict(kwargs)
            ex_retry = dict(merged)
            ex_retry.pop("enable_thinking", None)
            if ex_retry:
                kwargs_retry["extra_body"] = ex_retry
            else:
                kwargs_retry.pop("extra_body", None)
            _LOG.warning("网关不支持 enable_thinking，已去掉该参数后重试")
            return client.chat.completions.create(**kwargs_retry)
        if (
            allow_backup
            and enable_search
            and backup is not None
            and backup is not client
            and not _is_dashscope_compatible_client(client)
        ):
            _LOG.warning(
                "enable_search 主通道失败 (%s: %s)，切换百炼 compatible-mode（%s）重试",
                type(e).__name__,
                e,
                config.VISION_WEB_MODEL,
            )
            backup_kwargs = _kwargs_for_dashscope_backup(kwargs)
            backup_kwargs["model"] = fallback_model
            return _create_on_client(backup, backup_kwargs, extra)
        if not _is_retryable(e):
            raise
        if _is_dashscope_compatible_client(client):
            raise
        if not allow_backup:
            raise
        if backup is None or backup is client:
            raise
        _LOG.warning(
            "chat 主通道失败 (%s: %s)，切换百炼 compatible-mode 重试",
            type(e).__name__,
            e,
        )
        backup_kwargs = _kwargs_for_dashscope_backup(kwargs)
        backup_kwargs["model"] = fallback_model
        return _create_on_client(backup, backup_kwargs, extra)
