"""图片等非文本内容：调用多模态模型生成可入库的纯文本描述。"""
from __future__ import annotations

import base64

import config
from core.dashscope_chat import chat_completions_create

VISION_PROMPT = """请详细识别图片中的可见文字（按阅读顺序摘录）、图表数据、标题与要点。
输出一段连续的中文正文，便于后续语义检索；不要 Markdown，不要开场白。"""


def describe_image_bytes(image_bytes: bytes, mime_type: str) -> str:
    """对单张图片做视觉理解，返回纯文本（用于向量库）。"""
    if not config.chat_llm_configured():
        raise ValueError("未配置复星网关或 DASHSCOPE_API_KEY / OPENAI_API_KEY，无法调用视觉模型")

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    url = f"data:{mime_type};base64,{b64}"

    client = config.openai_client_for_chat()

    resp = chat_completions_create(
        client,
        model=getattr(config, "VISION_EXTRACT_MODEL", None) or config.VISION_WEB_MODEL,
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
    if not text:
        raise ValueError("视觉模型返回空内容")
    return text
