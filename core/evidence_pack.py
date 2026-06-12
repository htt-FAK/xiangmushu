from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

import config
from core.fill_task import FillTask
from core.query_expander import expand_query
from core.reporting import evidence_refs_from_results
from core.vector_store import VectorStore


NO_KB_TEXT = "（无有效知识库片段）"


@dataclass
class WebFact:
    claim: str
    source: str = ""
    confidence: str = "unknown"
    use_for: list[str] = field(default_factory=list)


@dataclass
class EvidencePack:
    task_id: str = ""
    target_chapter: str = ""
    kb_facts: list[str] = field(default_factory=list)
    web_facts: list[WebFact] = field(default_factory=list)
    visual_notes: list[str] = field(default_factory=list)
    table_context: str = ""
    user_instructions: str = ""
    gaps: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    raw_results: list[dict[str, Any]] = field(default_factory=list)
    kb_hits: int = 0
    weak_kb: bool = True
    best_similarity: float | None = None
    budget_chars: int = 0
    source_mode: str = "search"

    def facts_text(self) -> str:
        parts: list[str] = []
        if self.kb_facts:
            parts.append("【知识库证据】\n" + "\n".join(f"- {item}" for item in self.kb_facts))
        else:
            parts.append("【知识库证据】\n" + NO_KB_TEXT)
        if self.web_facts:
            lines = []
            for fact in self.web_facts:
                src = f" 来源：{fact.source}" if fact.source else ""
                confidence = f" 可信度：{fact.confidence}" if fact.confidence else ""
                lines.append(f"- {fact.claim}{src}{confidence}")
            parts.append("【联网证据】\n" + "\n".join(lines))
        if self.visual_notes:
            parts.append("【模板/视觉提示】\n" + "\n".join(f"- {item}" for item in self.visual_notes))
        if self.table_context:
            parts.append("【表格上下文】\n" + self.table_context.strip())
        if self.user_instructions:
            parts.append("【用户补充要求】\n" + self.user_instructions.strip())
        if self.conflicts:
            parts.append("【证据冲突】\n" + "\n".join(f"- {item}" for item in self.conflicts))
        if self.gaps:
            parts.append("【缺口】\n" + "\n".join(f"- {item}" for item in self.gaps))
        return "\n\n".join(parts)

    def summary(self, *, max_items: int = 5) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "target_chapter": self.target_chapter,
            "kb_hits": self.kb_hits,
            "weak_kb": self.weak_kb,
            "best_similarity": self.best_similarity,
            "source_mode": self.source_mode,
            "budget_chars": self.budget_chars,
            "kb_fact_count": len(self.kb_facts),
            "web_fact_count": len(self.web_facts),
            "visual_note_count": len(self.visual_notes),
            "gap_count": len(self.gaps),
            "conflict_count": len(self.conflicts),
            "evidence_refs": self.evidence_refs[:max_items],
        }

    def to_trace_dict(self) -> dict[str, Any]:
        data = self.summary()
        data["web_facts"] = [asdict(fact) for fact in self.web_facts[:5]]
        data["gaps"] = self.gaps[:5]
        data["conflicts"] = self.conflicts[:5]
        return data


@dataclass
class SessionEvidencePack:
    common_facts: list[str] = field(default_factory=list)
    web_facts: list[WebFact] = field(default_factory=list)
    visual_notes: list[str] = field(default_factory=list)
    user_instructions: str = ""
    budget_chars: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "common_fact_count": len(self.common_facts),
            "web_fact_count": len(self.web_facts),
            "visual_note_count": len(self.visual_notes),
            "has_user_instructions": bool(self.user_instructions.strip()),
            "budget_chars": self.budget_chars,
        }


def _best_similarity(results: Iterable[dict[str, Any]]) -> float | None:
    distances: list[float] = []
    for result in results:
        if result.get("distance") is None:
            continue
        try:
            distances.append(float(result["distance"]))
        except (TypeError, ValueError):
            continue
    if not distances:
        return None
    return max(0.0, min(1.0, 1.0 - min(distances)))


def _sentences(text: str) -> list[str]:
    return [item.strip() for item in re.split(r"(?<=[。！？!?])\s*", text or "") if item.strip()]


def _keywords_for_task(task: FillTask) -> set[str]:
    text = f"{task.target_chapter}\n{task.description}"
    keywords = set(re.findall(r"[\u4e00-\u9fff]{2,8}|[A-Za-z][A-Za-z0-9_-]{2,}", text))
    for segment in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        for size in (2, 3, 4):
            for i in range(0, max(0, len(segment) - size + 1)):
                keywords.add(segment[i : i + size])
    return keywords


def _compress_results(results: list[dict[str, Any]], task: FillTask, max_chars: int) -> list[str]:
    if not results:
        return []
    keywords = _keywords_for_task(task)
    scored: list[tuple[int, int, str]] = []
    for idx, result in enumerate(results):
        text = str(result.get("text") or result.get("document") or "").strip()
        for sentence in _sentences(text):
            if len(sentence) < 8:
                continue
            score = sum(1 for keyword in keywords if keyword and keyword in sentence)
            scored.append((score, idx, sentence))
    if not scored:
        first = str(results[0].get("text") or "")[:max_chars].strip()
        return [first] if first else []
    scored.sort(key=lambda item: (-item[0], item[1], len(item[2])))
    if scored and scored[0][0] > 0:
        scored = [item for item in scored if item[0] > 0]
    selected: list[str] = []
    seen: set[str] = set()
    total = 0
    for _, _, sentence in scored:
        normalized = sentence[:120]
        if normalized in seen:
            continue
        if total + len(sentence) > max_chars:
            continue
        seen.add(normalized)
        selected.append(sentence)
        total += len(sentence)
        if total >= max_chars:
            break
    return selected


def build_task_evidence_pack(
    vs: VectorStore,
    task: FillTask,
    *,
    top_k: int = 3,
    max_distance: float | None = None,
    table_context: str | None = None,
    visual_notes: list[str] | None = None,
    user_instructions: str = "",
    web_facts: list[WebFact] | None = None,
    budget_chars: int | None = None,
    use_full_recall: bool | None = None,
) -> EvidencePack:
    budget = int(budget_chars or config.RAG_SNIPPET_MAX_CHARS)
    max_d = max_distance if max_distance is not None else config.RETRIEVAL_MAX_DISTANCE
    collection_empty = vs.get_collection_count() == 0
    source_mode = "empty"
    results: list[dict[str, Any]] = []
    if not collection_empty:
        if bool(config.FULL_RECALL_MODE if use_full_recall is None else use_full_recall):
            results = vs.get_all_documents(max_chars=budget)
            source_mode = "full_recall_compact"
        else:
            query = expand_query(task.target_chapter, task.description, task.task_type)
            results = vs.search(query, top_k=top_k, max_distance=max_d)
            source_mode = "search"

    best_similarity = _best_similarity(results)
    kb_facts = _compress_results(results, task, max_chars=budget)
    gaps: list[str] = []
    if not kb_facts:
        gaps.append("知识库未提供足够证据")

    return EvidencePack(
        task_id=task.task_id,
        target_chapter=task.target_chapter,
        kb_facts=kb_facts,
        web_facts=list(web_facts or []),
        visual_notes=list(visual_notes or []),
        table_context=(table_context or "").strip(),
        user_instructions=user_instructions.strip(),
        gaps=gaps,
        evidence_refs=evidence_refs_from_results(results),
        raw_results=results,
        kb_hits=len(results),
        weak_kb=len(results) == 0,
        best_similarity=best_similarity,
        budget_chars=budget,
        source_mode=source_mode,
    )
