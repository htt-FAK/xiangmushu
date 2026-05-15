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
        if code in (408, 429, 500, 502, 503, 504):
            return True
    return False


def chat_completions_create(client: Any, **kwargs: Any):
    """
    包装 OpenAI SDK 的 chat.completions.create。
    始终写入 extra_body.enable_thinking=False（覆盖调用方传入的 True），
    避免部分大模型默认走深度思考导致耗时与用量偏高；其它 extra_body 字段保留。

    当 client 指向非百炼 compatible-mode（如复星网关）且发生可恢复错误时，
    使用百炼 Key 重试同一请求（stream=True 时仅捕获 create 阶段异常；迭代期错误不包装）。
    """
    extra = dict(kwargs.pop("extra_body", None) or {})
    extra["enable_thinking"] = False
    kwargs["extra_body"] = extra

    try:
        return client.chat.completions.create(**kwargs)
    except Exception as e:
        if not _is_retryable(e):
            raise
        if _is_dashscope_compatible_client(client):
            raise
        backup = config.dashscope_backup_chat_client()
        if backup is None or backup is client:
            raise
        _LOG.warning(
            "chat 主通道失败 (%s: %s)，切换百炼 compatible-mode 重试",
            type(e).__name__,
            e,
        )
        return backup.chat.completions.create(**kwargs)
