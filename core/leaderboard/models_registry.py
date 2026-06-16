"""入榜模型池：阿里云可调用模型 ID、能力标签、百炼 alias。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

# 阿里云百炼兼容通道下可测的模型列表
ALIYUN_MODEL_IDS: List[str] = [
    "claude-opus-4.6",
    "claude-opus-4.7",
    "claude-sonnet-4.6",
    "text-embedding-3-small",
    "text-embedding-v3",
    "gemini-2.5-pro",
    "gemini-3-flash",
    "gemini-3-pro",
    "minimax-m2.7",
    "gpt-5.2",
    "gpt-5.4",
    "gte-rerank-v2",
    "grok-4.20",
    "deepseek-r1",
    "deepseek-v3.2",
    "deepseek-v4-flash",
    "deepseek-v4-pro",
    "glm-5",
    "glm-5.1",
    "kimi-k2",
    "kimi-k2.5",
    "kimi-k2.6",
    "mimo-v2-pro",
    "qwen3-asr-flash",
    "qwen3-max",
    "qwen3.5-plus",
    "qwen3.6-plus",
    "gemma4",
    "qwen3.7max",
]

EMBED_ONLY: Set[str] = {
    "text-embedding-3-small",
    "text-embedding-v3",
    "gte-rerank-v2",
}

ASR_ONLY: Set[str] = {"qwen3-asr-flash"}

# 百炼侧 model_id 可能与网关不同
DASHSCOPE_ALIASES: Dict[str, str] = {
    "qwen3.5-plus": "qwen3.5-plus",
    "qwen3.5-plus-2026-04-20": "qwen3.5-plus",
    "qwen3.6-plus": "qwen3.6-plus",
    "qwen3-max": "qwen3-max",
    "qwen3.6-max-preview": "qwen3-max",
    "qwen3.6-27b": "qwen3.5-plus",
    "qwen3.5-flash-2026-02-23": "qwen3.5-flash",
    "gpt-5.4": "gpt-5.4",
    "gpt-5.2": "gpt-5.2",
    "glm-5.1": "glm-5.1",
    "glm-5": "glm-5",
    "deepseek-v4-pro": "deepseek-v4-pro",
    "deepseek-v4-flash": "deepseek-v4-flash",
    "deepseek-v3.2": "deepseek-v3.2",
    "deepseek-r1": "deepseek-r1",
    "claude-sonnet-4.6": "claude-sonnet-4.6",
    "gemini-3-pro": "gemini-3-pro",
    "gemini-3-flash": "gemini-3-flash",
    "gemini-2.5-pro": "gemini-2.5-pro",
    "kimi-k2.6": "kimi-k2.6",
    "kimi-k2.5": "kimi-k2.5",
    "kimi-k2": "kimi-k2",
}


@dataclass
class ModelEntry:
    model_id: str
    provider: str = "unknown"
    capabilities: List[str] = field(default_factory=lambda: ["chat"])
    dashscope_alias: Optional[str] = None
    status: str = "active"  # active | pending_eval | embed_only | asr_only

    def supports_vac(self) -> bool:
        return self.status == "active" and "embed_only" not in self.capabilities

    def supports_vision(self) -> bool:
        return "vision" in self.capabilities or "chat" in self.capabilities

    def resolve_id(self, channel: str) -> str:
        if channel == "dashscope":
            return self.dashscope_alias or DASHSCOPE_ALIASES.get(self.model_id, self.model_id)
        return self.model_id


def _capabilities_for(model_id: str) -> List[str]:
    if model_id in EMBED_ONLY:
        return ["embed_only"]
    if model_id in ASR_ONLY:
        return ["asr_only"]
    caps = ["chat", "vision", "search"]
    # 推理/超大模型仍测 chat，vision 探针决定是否进 G 榜
    return caps


def _provider_for(model_id: str) -> str:
    low = model_id.lower()
    if low.startswith("qwen") or low == "qwen3.7max":
        return "Alibaba/Qwen"
    if low.startswith("gpt") or low.startswith("claude"):
        return "OpenAI/Anthropic-via-gateway"
    if low.startswith("gemini") or low == "gemma4":
        return "Google"
    if low.startswith("deepseek"):
        return "DeepSeek"
    if low.startswith("glm"):
        return "Zhipu"
    if low.startswith("kimi"):
        return "Moonshot"
    if low.startswith("grok"):
        return "xAI"
    if low.startswith("minimax") or low.startswith("mimo"):
        return "MiniMax"
    if "embedding" in low or low.startswith("gte-"):
        return "Embedding"
    return "gateway"


def build_model_registry(extra_ids: Optional[List[str]] = None) -> List[ModelEntry]:
    ids = list(ALIYUN_MODEL_IDS)
    if extra_ids:
        for m in extra_ids:
            if m not in ids:
                ids.append(m)
    entries: List[ModelEntry] = []
    for mid in ids:
        caps = _capabilities_for(mid)
        status = "active"
        if mid in EMBED_ONLY:
            status = "embed_only"
        elif mid in ASR_ONLY:
            status = "asr_only"
        elif mid == "qwen3.7max":
            status = "pending_eval"
        entries.append(
            ModelEntry(
                model_id=mid,
                provider=_provider_for(mid),
                capabilities=caps,
                dashscope_alias=DASHSCOPE_ALIASES.get(mid, mid if mid not in EMBED_ONLY else None),
                status=status,
            )
        )
    return entries


def vac_models(entries: List[ModelEntry]) -> List[ModelEntry]:
    return [e for e in entries if e.supports_vac()]


def embed_models(entries: List[ModelEntry]) -> List[ModelEntry]:
    return [e for e in entries if e.status == "embed_only"]
