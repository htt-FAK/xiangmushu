from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from core.dashscope_chat import chat_completions_create
from core.evidence_pack import WebFact
from core.fill_task import FillTask
from core.model_router import WEB_SEARCH, ModelCallProfile, resolve_model_profile
from core.provider_clients import chat_client_for_model
from core.provider_registry import provider_code_for_model


_LOG = logging.getLogger(__name__)

_MIMO_WEB_SEARCH_TOOLS = [
    {
        "type": "web_search",
        "max_keyword": 3,
        "force_search": True,
        "limit": 1,
    }
]


WEB_SEARCH_SYSTEM = """You are a web evidence extraction agent. Search only for supporting public facts.
Return JSON only with keys:
- facts: array of objects with claim, source, confidence, use_for
- gaps: array of strings
Do not write final document prose."""


@dataclass
class WebEvidenceResult:
    facts: list[WebFact] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    profile: ModelCallProfile | None = None
    raw_text: str = ""
    error: str = ""
    cached: bool = False

    def summary(self) -> dict[str, Any]:
        return {
            "fact_count": len(self.facts),
            "gap_count": len(self.gaps),
            "model": self.profile.model if self.profile else "",
            "role": self.profile.role if self.profile else WEB_SEARCH,
            "cached": self.cached,
            "error": self.error,
        }


class SessionWebEvidenceCache:
    def __init__(self) -> None:
        self._items: dict[str, WebEvidenceResult] = {}

    def get(self, key: str) -> WebEvidenceResult | None:
        item = self._items.get(key)
        if item is None:
            return None
        return WebEvidenceResult(
            facts=list(item.facts),
            gaps=list(item.gaps),
            profile=item.profile,
            raw_text=item.raw_text,
            error=item.error,
            cached=True,
        )

    def set(self, key: str, value: WebEvidenceResult) -> None:
        self._items[key] = WebEvidenceResult(
            facts=list(value.facts),
            gaps=list(value.gaps),
            profile=value.profile,
            raw_text=value.raw_text,
            error=value.error,
            cached=False,
        )


def cache_key_for_task(task: FillTask) -> str:
    return "|".join(
        [
            str(task.task_type or ""),
            str(task.target_chapter or "").strip(),
            str(task.description or "").strip()[:240],
        ]
    )


def parse_web_evidence(raw: str) -> tuple[list[WebFact], list[str]]:
    text = (raw or "").strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1].strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
    data = json.loads(text)
    facts: list[WebFact] = []
    for item in data.get("facts") or []:
        if not isinstance(item, dict):
            continue
        claim = str(item.get("claim") or "").strip()
        if not claim:
            continue
        use_for_raw = item.get("use_for") or []
        use_for = [str(x) for x in use_for_raw] if isinstance(use_for_raw, list) else [str(use_for_raw)]
        facts.append(
            WebFact(
                claim=claim,
                source=str(item.get("source") or "").strip(),
                confidence=str(item.get("confidence") or "unknown").strip() or "unknown",
                use_for=[x for x in use_for if x.strip()],
            )
        )
    gaps_raw = data.get("gaps") or []
    gaps = [str(item).strip() for item in gaps_raw if str(item).strip()] if isinstance(gaps_raw, list) else []
    return facts, gaps


def fetch_web_evidence(
    client: Any,
    task: FillTask,
    *,
    user_id: int | None = None,
    cache: SessionWebEvidenceCache | None = None,
) -> WebEvidenceResult:
    key = cache_key_for_task(task)
    if cache is not None:
        cached = cache.get(key)
        if cached is not None:
            return cached

    profile = resolve_model_profile(
        WEB_SEARCH,
        user_id=user_id,
        routing_reason="web evidence extraction",
    )
    resolved_client = client
    if user_id is not None:
        try:
            resolved_client = chat_client_for_model(profile.model, user_id, purpose="chat")
        except Exception as exc:
            _LOG.warning(
                "web_evidence_client_resolve_failed task_id=%s model=%s err=%s",
                task.task_id,
                profile.model,
                exc,
            )
    prompt = (
        f"Task type: {task.task_type}\n"
        f"Target chapter: {task.target_chapter}\n"
        f"Requirement: {task.description}\n\n"
        "Search for concise facts that can support this project document section. "
        "Return claims with source metadata and gaps. Do not draft final prose."
    )
    request_kwargs: dict[str, Any] = {
        "model": profile.model,
        "messages": [
            {"role": "system", "content": WEB_SEARCH_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        "temperature": profile.temperature or 0.2,
        "stream": False,
        "allow_backup_fallback": False,
    }
    if provider_code_for_model(profile.model) == "mimo":
        request_kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        request_kwargs["tools"] = list(_MIMO_WEB_SEARCH_TOOLS)
        request_kwargs["tool_choice"] = "auto"
    else:
        request_kwargs["extra_body"] = dict(profile.extra_body)

    try:
        response = chat_completions_create(resolved_client, **request_kwargs)
        ch0 = response.choices[0] if response.choices else None
        raw = (ch0.message.content if ch0 and ch0.message else "") or ""
        facts, gaps = parse_web_evidence(raw)
        result = WebEvidenceResult(facts=facts, gaps=gaps, profile=profile, raw_text=raw)
    except Exception as exc:
        _LOG.warning("web_evidence_error task_id=%s err=%s", task.task_id, exc)
        result = WebEvidenceResult(profile=profile, error=str(exc))

    if cache is not None:
        cache.set(key, result)
    return result
