"""百炼 compatible-mode：chat 请求统一关闭深度思考（enable_thinking=False）。

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


def _is_dashscope_compatible_client(client: Any) -> bool:
    u = _client_base_url(client).lower()
    return "dashscope.aliyuncs.com" in u or "compatible-mode" in u


def _apply_extra_body(client: Any, extra_in: dict | None) -> dict | None:
    """仅百炼 compatible-mode 附带 enable_thinking=False；复星网关不支持该字段，绝不发送。"""
    extra = dict(extra_in or {})
    extra.pop("enable_thinking", None)
    if _is_dashscope_compatible_client(client):
        extra["enable_thinking"] = False
    return extra if extra else None


def _is_enable_thinking_rejected(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "enable_thinking" in msg and (
        "unknown parameter" in msg
        or "unknown_parameter" in msg
        or "invalid_request" in msg
    )


def _kwargs_for_dashscope_backup(kwargs: dict[str, Any], *, for_enable_search: bool) -> dict[str, Any]:
    """回落百炼：去掉 enable_thinking；联网档强制 VISION_WEB_MODEL（Qwen + enable_search）。"""
    bk = dict(kwargs)
    extra = dict(bk.pop("extra_body", None) or {})
    extra.pop("enable_thinking", None)
    if for_enable_search:
        extra["enable_search"] = True
        bk["model"] = config.VISION_WEB_MODEL
    if extra:
        bk["extra_body"] = extra
    else:
        bk.pop("extra_body", None)
    return bk


def _chat_content_empty(response: Any) -> bool:
    try:
        return not (response.choices[0].message.content or "").strip()
    except (AttributeError, IndexError, TypeError, KeyError):
        return True


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
    merged = _apply_extra_body(client, dict(extra_in))
    if merged is not None:
        kw["extra_body"] = merged
    else:
        kw.pop("extra_body", None)
    return client.chat.completions.create(**kw)


def chat_completions_create(client: Any, **kwargs: Any):
    """
    包装 OpenAI SDK 的 chat.completions.create。
    百炼 compatible-mode 写入 extra_body.enable_thinking=False；
    复星网关不传该字段（网关会 400 unknown_parameter）。

    当 client 指向非百炼 compatible-mode（如复星网关）且发生可恢复错误时，
    使用百炼 Key 重试同一请求（stream=True 时仅捕获 create 阶段异常；迭代期错误不包装）。
    """
    extra = dict(kwargs.pop("extra_body", None) or {})
    merged = _apply_extra_body(client, extra)
    if merged is not None:
        kwargs["extra_body"] = merged
    enable_search = bool((merged or {}).get("enable_search"))

    backup = config.dashscope_backup_chat_client()
    model_id = str(kwargs.get("model") or "")

    if (
        backup is not None
        and backup is not client
        and not _is_dashscope_compatible_client(client)
        and config.chat_prefers_dashscope_first(model_id)
    ):
        _LOG.info(
            "chat 模型 %s 直连百炼 compatible-mode（跳过复星网关）",
            model_id,
        )
        return _create_on_client(
            backup,
            _kwargs_for_dashscope_backup(kwargs, for_enable_search=enable_search),
            extra,
        )

    try:
        resp = _create_on_client(client, kwargs, extra)
        if (
            _chat_content_empty(resp)
            and backup is not None
            and backup is not client
            and not _is_dashscope_compatible_client(client)
        ):
            _LOG.warning(
                "chat 主通道空回复 (model=%s)，切换百炼 compatible-mode 重试",
                kwargs.get("model"),
            )
            return _create_on_client(
                backup,
                _kwargs_for_dashscope_backup(kwargs, for_enable_search=enable_search),
                extra,
            )
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
            enable_search
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
            return _create_on_client(
                backup,
                _kwargs_for_dashscope_backup(kwargs, for_enable_search=True),
                extra,
            )
        if not _is_retryable(e):
            raise
        if _is_dashscope_compatible_client(client):
            raise
        if backup is None or backup is client:
            raise
        _LOG.warning(
            "chat 主通道失败 (%s: %s)，切换百炼 compatible-mode 重试",
            type(e).__name__,
            e,
        )
        return _create_on_client(
            backup,
            _kwargs_for_dashscope_backup(kwargs, for_enable_search=False),
            extra,
        )
