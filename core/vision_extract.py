"""Image-to-text extraction for KB ingestion."""
from __future__ import annotations

import base64

import config
from core.dashscope_chat import chat_completions_create

VISION_PROMPT = """请详细识别图片中的可见文字、图表数据、标题与要点。
输出一段连续的中文正文，便于后续语义检索；不要 Markdown，不要开场白。"""


def describe_image_bytes(image_bytes: bytes, mime_type: str) -> str:
    """Return plain text extracted from an image using the configured vision chain."""
    if not config.chat_llm_configured():
        raise ValueError("未配置聊天模型 Key，无法调用视觉模型")

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    url = f"data:{mime_type};base64,{b64}"
    client = config.openai_client_for_chat()
    models = [
        getattr(config, "VISION_EXTRACT_MODEL", None) or config.VISION_WEB_MODEL,
        getattr(config, "VISION_EXTRACT_FALLBACK_MODEL", None) or "",
    ]

    last_error = None
    for model in models:
        model = (model or "").strip()
        if not model:
            continue
        try:
            resp = chat_completions_create(
                client,
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": VISION_PROMPT},
                            {"type": "image_url", "image_url": {"url": url}},
                        ],
                    }
                ],
                temperature=config.TEMP_VISION,
                max_tokens=4096,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception as e:
            last_error = e

    if last_error is not None:
        raise ValueError(f"视觉模型调用失败: {last_error}")
    raise ValueError("视觉模型返回空内容")
