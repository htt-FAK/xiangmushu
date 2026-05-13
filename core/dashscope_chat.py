"""百炼 compatible-mode：统一为 chat 请求关闭深度思考。"""
from __future__ import annotations

from typing import Any


def chat_completions_create(client: Any, **kwargs: Any):
    """
    包装 OpenAI SDK 的 chat.completions.create，合并 extra_body.enable_thinking=False。
    调用方仍可传入 extra_body 其它字段；enable_thinking 默认 False。
    """
    extra = dict(kwargs.pop("extra_body", None) or {})
    if "enable_thinking" not in extra:
        extra["enable_thinking"] = False
    kwargs["extra_body"] = extra
    return client.chat.completions.create(**kwargs)
