from __future__ import annotations

from typing import Any

try:
    from openai import (
        APIConnectionError,
        APIStatusError,
        APITimeoutError,
        AuthenticationError,
        PermissionDeniedError,
        RateLimitError,
    )
except ImportError:  # pragma: no cover - compatibility fallback
    APIConnectionError = APITimeoutError = RateLimitError = Exception  # type: ignore
    APIStatusError = AuthenticationError = PermissionDeniedError = Exception  # type: ignore


def _status_code(exc: BaseException) -> int | None:
    code = getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code
    response = getattr(exc, "response", None)
    response_code = getattr(response, "status_code", None)
    return response_code if isinstance(response_code, int) else None


def classify_provider_error(exc: BaseException | str | None) -> dict[str, Any]:
    raw = str(exc or "")
    message = raw.strip() or "未知错误"
    lowered = message.lower()
    code = _status_code(exc) if isinstance(exc, BaseException) else None

    quota_markers = (
        "quota",
        "allocationquota",
        "allocationquota.freetieronly",
        "freetieronly",
        "exhausted",
        "free tier",
        "free tier only",
        "paid basis",
        "insufficient_quota",
        "insufficient quota",
        "余额",
        "用量",
        "配额",
    )
    model_markers = (
        "model_not_found",
        "model not found",
        "does not exist",
        "not exist",
        "unsupported model",
    )
    permission_markers = (
        "permission",
        "forbidden",
        "access denied",
        "无权",
    )
    invalid_key_markers = (
        "invalid api key",
        "incorrect api key",
        "authentication",
        "unauthorized",
        "invalid key",
    )
    network_markers = (
        "timeout",
        "timed out",
        "connection",
        "dns",
        "network",
        "temporarily unavailable",
    )

    if code == 402 or any(marker in lowered for marker in quota_markers):
        return {
            "code": "quota_exceeded",
            "message": "当前 API Key 的模型额度已用完，暂时无法继续调用。",
            "retryable": False,
            "detail": message,
        }
    if isinstance(exc, AuthenticationError) or code == 401 or any(marker in lowered for marker in invalid_key_markers):
        return {
            "code": "invalid_api_key",
            "message": "API Key 无效，请检查是否复制完整或输入错误。",
            "retryable": False,
            "detail": message,
        }
    if isinstance(exc, PermissionDeniedError) or code == 403 or any(marker in lowered for marker in permission_markers):
        return {
            "code": "permission_denied",
            "message": "当前 API Key 无权访问该模型或接口。",
            "retryable": False,
            "detail": message,
        }
    if any(marker in lowered for marker in model_markers) or code == 404:
        return {
            "code": "model_unavailable",
            "message": "当前测试模型不可用，系统需要尝试其他模型。",
            "retryable": True,
            "detail": message,
        }
    if isinstance(exc, (APIConnectionError, APITimeoutError)) or any(marker in lowered for marker in network_markers):
        return {
            "code": "network_error",
            "message": "当前无法连接模型服务，请检查网络后重试。",
            "retryable": True,
            "detail": message,
        }
    if isinstance(exc, RateLimitError):
        return {
            "code": "provider_error",
            "message": "模型服务暂时繁忙，请稍后再试。",
            "retryable": True,
            "detail": message,
        }
    if isinstance(exc, APIStatusError) or code in (408, 429, 500, 502, 503, 504):
        return {
            "code": "provider_error",
            "message": "模型服务暂时异常，请稍后重试。",
            "retryable": True,
            "detail": message,
        }
    return {
        "code": "unknown_error",
        "message": "模型调用失败，请稍后重试。",
        "retryable": True,
        "detail": message,
    }


def validation_http_status(result: dict[str, Any]) -> int:
    code = str(result.get("code") or "")
    if code in {"invalid_api_key", "permission_denied", "model_unavailable", "quota_exceeded"}:
        return 422
    if code in {"network_error", "provider_error"}:
        return 503
    return 500
