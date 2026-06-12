"""百炼/DeepSeek compatible-mode：chat 请求统一关闭深度思考。

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


def _is_dashscope_compatible_client(client: Any) -> bool:
    return _is_dashscope_compatible_base_url(_client_base_url(client))


def _is_deepseek_client(client: Any) -> bool:
    return _is_deepseek_base_url(_client_base_url(client))


def _apply_extra_body(client: Any, extra_in: dict | None) -> dict | None:
    """DeepSeek 用 thinking.type=disabled 关闭深度思考；百炼用 enable_thinking=False；
    复星网关不支持该字段，绝不发送。"""
    extra = dict(extra_in or {})
    extra.pop("enable_thinking", None)
    extra.pop("thinking", None)
    if _is_deepseek_client(client):
        extra["thinking"] = {"type": "disabled"}
    elif _is_dashscope_compatible_client(client):
        extra["enable_thinking"] = False
    return extra if extra else None


def prepare_chat_request(client: Any, **kwargs: Any) -> tuple[Any, dict[str, Any]]:
    """为直连 SDK 调用补齐关闭深度思考所需参数。"""
    kw = dict(kwargs)
    model_id = str(kw.get("model") or "")
    if config.is_deepseek_model(model_id):
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


def direct_chat_completions_create(client: Any, **kwargs: Any):
    """直连 SDK 调用：统一关闭深度思考，但不做跨通道回落。"""
    call_client, call_kwargs = prepare_chat_request(client, **kwargs)
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
    - 复星网关不传该字段（网关会 400 unknown_parameter）。

    当 client 指向非百炼 compatible-mode（如复星网关）且发生可恢复错误时，
    使用百炼 Key 重试同一请求（stream=True 时仅捕获 create 阶段异常；迭代期错误不包装）。
    """
    extra = dict(kwargs.pop("extra_body", None) or {})
    client, kwargs = prepare_chat_request(client, **kwargs, extra_body=extra)
    merged = dict(kwargs.get("extra_body", None) or {})
    if not merged:
        kwargs.pop("extra_body", None)
    enable_search = bool((merged or {}).get("enable_search"))

    backup = config.dashscope_backup_chat_client()

    try:
        resp = _create_on_client(client, kwargs, extra)
        # 检测错误内容
        if _is_error_response(resp):
            error_content = _error_response_content(resp)
            if error_content:
                raise RuntimeError(error_content)
            _LOG.error("主通道返回错误内容，尝试切换备用通道")
            if backup is not None and backup is not client:
                try:
                    backup_resp = _create_on_client(
                        backup,
                        _kwargs_for_dashscope_backup(
                            kwargs, for_enable_search=enable_search),
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
                _kwargs_for_dashscope_backup(
                    kwargs, for_enable_search=enable_search),
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
