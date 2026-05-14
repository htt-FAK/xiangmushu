"""百炼 compatible-mode：chat 请求统一关闭深度思考（enable_thinking=False）。"""
from __future__ import annotations

from typing import Any


def chat_completions_create(client: Any, **kwargs: Any):
    """
    包装 OpenAI SDK 的 chat.completions.create。
    始终写入 extra_body.enable_thinking=False（覆盖调用方传入的 True），
    避免部分大模型默认走深度思考导致耗时与用量偏高；其它 extra_body 字段保留。
    """
    extra = dict(kwargs.pop("extra_body", None) or {})
    extra["enable_thinking"] = False
    kwargs["extra_body"] = extra
    return client.chat.completions.create(**kwargs)
