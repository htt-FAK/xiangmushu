from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import config
from core.evidence_pack import WebFact
from core.fill_task import FillTask
from core.firecrawl_search import search_web_evidence


_LOG = logging.getLogger(__name__)


@dataclass
class WebEvidenceResult:
    facts: list[WebFact] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    profile: Any = None
    raw_text: str = ""
    error: str = ""
    cached: bool = False
    usage: Any = None
    model: str = ""

    def summary(self) -> dict[str, Any]:
        return {
            "fact_count": len(self.facts),
            "gap_count": len(self.gaps),
            "model": self.profile.model if self.profile else "",
            "role": self.profile.role if self.profile else "",
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

    query = (task.target_chapter + " " + task.description)[:200]

    try:
        results = search_web_evidence(
            query,
            limit=config.FIRECRAWL_SEARCH_LIMIT,
            timeout=config.FIRECRAWL_TIMEOUT,
        )
        facts = [
            WebFact(
                claim=result["content"] or result["title"],
                source=result["url"],
                confidence="unknown",
                use_for=[],
            )
            for result in results
        ]
        result = WebEvidenceResult(
            facts=facts,
            gaps=[],
            profile=None,
            raw_text="",
            error="",
            cached=False,
            usage=None,
            model="firecrawl-keyless",
        )
    except Exception as exc:
        _LOG.warning("web_evidence_error task_id=%s err=%s", task.task_id, exc)
        result = WebEvidenceResult(
            profile=None,
            error=str(exc),
            model="firecrawl-keyless",
        )

    if cache is not None:
        cache.set(key, result)
    return result
