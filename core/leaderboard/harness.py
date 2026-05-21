"""双通道 API 调用与延迟/token 采集。"""
from __future__ import annotations

import base64
import struct
import time
import zlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from openai import OpenAI

import config
from core.dashscope_chat import chat_completions_create
from core.leaderboard.models_registry import ModelEntry


@dataclass
class CallMetrics:
    ok: bool
    text: str = ""
    error: str = ""
    t_total_ms: float = 0.0
    t_first_token_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    kind: str = "chat"


def rgba_png_bytes(width: int = 16, height: int = 16) -> bytes:
    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def vision_data_url() -> str:
    png = rgba_png_bytes(16, 16)
    return "data:image/png;base64," + base64.standard_b64encode(png).decode("ascii")


def client_for_channel(channel: str) -> Optional[OpenAI]:
    if channel == "fosun":
        if not (config.FOSUN_AIGW_API_KEY or "").strip():
            return None
        return config.openai_client_for_chat()
    if channel == "dashscope":
        return config.dashscope_backup_chat_client()
    return None


def _usage_from_response(resp: Any) -> Tuple[int, int]:
    u = getattr(resp, "usage", None)
    if u is None:
        return 0, 0
    return int(getattr(u, "prompt_tokens", 0) or 0), int(
        getattr(u, "completion_tokens", 0) or 0
    )


def probe_chat(
    client: OpenAI,
    model: str,
    *,
    use_wrapper: bool = True,
    temperature: float = 0.0,
) -> CallMetrics:
    t0 = time.perf_counter()
    try:
        kwargs = {
            "model": model,
            "messages": [{"role": "user", "content": "只回复一个字：好"}],
            "temperature": temperature,
            "max_tokens": 16,
        }
        if use_wrapper:
            resp = chat_completions_create(client, **kwargs)
        else:
            resp = client.chat.completions.create(**kwargs)
        text = (resp.choices[0].message.content if resp.choices else "") or ""
        text = text.strip()
        pt, ct = _usage_from_response(resp)
        dt = (time.perf_counter() - t0) * 1000
        if not text:
            return CallMetrics(False, error="空回复", t_total_ms=dt, kind="chat")
        return CallMetrics(
            True, text=text[:80], t_total_ms=dt, t_first_token_ms=dt,
            prompt_tokens=pt, completion_tokens=ct, kind="chat",
        )
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return CallMetrics(False, error=str(e)[:200], t_total_ms=dt, kind="chat")


def probe_vision(
    client: OpenAI,
    model: str,
    *,
    use_wrapper: bool = True,
    temperature: float = 0.0,
) -> CallMetrics:
    t0 = time.perf_counter()
    try:
        kwargs = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请用一句话描述这张图（若空白则说明空白）。"},
                        {"type": "image_url", "image_url": {"url": vision_data_url()}},
                    ],
                }
            ],
            "temperature": temperature,
            "max_tokens": 64,
        }
        if use_wrapper:
            resp = chat_completions_create(client, **kwargs)
        else:
            resp = client.chat.completions.create(**kwargs)
        text = (resp.choices[0].message.content if resp.choices else "") or ""
        text = text.strip()
        pt, ct = _usage_from_response(resp)
        dt = (time.perf_counter() - t0) * 1000
        if not text:
            return CallMetrics(False, error="空回复", t_total_ms=dt, kind="vision")
        return CallMetrics(
            True, text=text[:120], t_total_ms=dt, t_first_token_ms=dt,
            prompt_tokens=pt, completion_tokens=ct, kind="vision",
        )
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return CallMetrics(False, error=str(e)[:200], t_total_ms=dt, kind="vision")


def probe_search(
    client: OpenAI,
    model: str,
    *,
    use_wrapper: bool = True,
    gateway_raw: bool = False,
    temperature: float = 0.0,
) -> CallMetrics:
    t0 = time.perf_counter()
    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "user", "content": "今天是星期几？只回答星期几，不要解释。"}
            ],
            "temperature": temperature,
            "max_tokens": 32,
        }
        if gateway_raw:
            kwargs["extra_body"] = {"enable_search": True}
        elif use_wrapper:
            kwargs["extra_body"] = {"enable_search": True}
        if use_wrapper and not gateway_raw:
            resp = chat_completions_create(client, **kwargs)
        else:
            resp = client.chat.completions.create(**kwargs)
        text = (resp.choices[0].message.content if resp.choices else "") or ""
        text = text.strip()
        pt, ct = _usage_from_response(resp)
        dt = (time.perf_counter() - t0) * 1000
        if not text:
            return CallMetrics(False, error="空回复", t_total_ms=dt, kind="search")
        return CallMetrics(
            True, text=text[:80], t_total_ms=dt, t_first_token_ms=dt,
            prompt_tokens=pt, completion_tokens=ct, kind="search",
        )
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return CallMetrics(False, error=str(e)[:200], t_total_ms=dt, kind="search")


def probe_embed(client: OpenAI, model: str) -> CallMetrics:
    t0 = time.perf_counter()
    try:
        resp = client.embeddings.create(model=model, input=["测试嵌入"])
        dt = (time.perf_counter() - t0) * 1000
        vec = resp.data[0].embedding if resp.data else []
        if not vec:
            return CallMetrics(False, error="空向量", t_total_ms=dt, kind="embed")
        return CallMetrics(True, text=f"dim={len(vec)}", t_total_ms=dt, kind="embed")
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return CallMetrics(False, error=str(e)[:200], t_total_ms=dt, kind="embed")


@dataclass
class ProbeResult:
    model_id: str
    channel: str
    chat: CallMetrics = field(default_factory=lambda: CallMetrics(False))
    vision: CallMetrics = field(default_factory=lambda: CallMetrics(False))
    search_gw: CallMetrics = field(default_factory=lambda: CallMetrics(False))
    search_wrap: CallMetrics = field(default_factory=lambda: CallMetrics(False))
    embed: Optional[CallMetrics] = None
    vision_capable: bool = False
    search_gw_ok: bool = False
    search_wrap_ok: bool = False


def run_probes_for_entry(
    entry: ModelEntry,
    channel: str,
    *,
    skip_vision: bool = False,
    skip_search: bool = False,
) -> Optional[ProbeResult]:
    if entry.status in ("embed_only", "asr_only"):
        client = client_for_channel(channel)
        if client is None:
            return None
        mid = entry.resolve_id(channel)
        if entry.status == "embed_only":
            return ProbeResult(
                model_id=entry.model_id,
                channel=channel,
                embed=probe_embed(client, mid),
            )
        return None

    client = client_for_channel(channel)
    if client is None:
        return None
    mid = entry.resolve_id(channel)
    use_gw_raw = channel == "fosun"
    pr = ProbeResult(model_id=entry.model_id, channel=channel)
    pr.chat = probe_chat(client, mid, use_wrapper=not use_gw_raw or True)
    if not skip_vision:
        pr.vision = probe_vision(client, mid, use_wrapper=True)
        pr.vision_capable = pr.vision.ok
    if not skip_search:
        if channel == "fosun":
            pr.search_gw = probe_search(
                client, mid, use_wrapper=False, gateway_raw=True, temperature=0.0
            )
            pr.search_wrap = probe_search(client, mid, use_wrapper=True)
            pr.search_gw_ok = pr.search_gw.ok
            pr.search_wrap_ok = pr.search_wrap.ok
        else:
            pr.search_wrap = probe_search(client, mid, use_wrapper=True)
            pr.search_wrap_ok = pr.search_wrap.ok
    return pr


def chat_completion_text(
    client: OpenAI,
    model: str,
    messages: List[Dict[str, Any]],
    *,
    max_tokens: int = 512,
    extra_body: Optional[Dict[str, Any]] = None,
    use_wrapper: bool = True,
) -> Tuple[bool, str, CallMetrics]:
    t0 = time.perf_counter()
    try:
        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": max_tokens,
        }
        if extra_body:
            kwargs["extra_body"] = extra_body
        if use_wrapper:
            resp = chat_completions_create(client, **kwargs)
        else:
            resp = client.chat.completions.create(**kwargs)
        text = (resp.choices[0].message.content if resp.choices else "") or ""
        pt, ct = _usage_from_response(resp)
        dt = (time.perf_counter() - t0) * 1000
        return True, text.strip(), CallMetrics(
            True, text=text[:200], t_total_ms=dt, t_first_token_ms=dt,
            prompt_tokens=pt, completion_tokens=ct,
        )
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return False, "", CallMetrics(False, error=str(e)[:200], t_total_ms=dt)
