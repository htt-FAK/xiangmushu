"""分组检索 + 证据压缩：为同组任务共享一次向量检索，减少重复 API 调用。

核心功能：
1. retrieve_for_group   —— 对 TaskGroup 做一次检索，返回 Evidence
2. compress_evidence    —— 从多份原文片段中截取与任务最相关的段落，减少输入 token
3. format_evidence      —— 将 Evidence 格式化为模型可用的字符串
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import config
from core.fill_task import FillTask
from core.query_expander import expand_query
from core.task_grouper import TaskGroup
from core.vector_store import VectorStore


@dataclass
class Evidence:
    """一个 TaskGroup 的检索结果与压缩后的证据文本。"""

    group_id: str
    raw_results: List[Dict[str, Any]] = field(default_factory=list)
    compressed_text: str = ""
    best_similarity: Optional[float] = None
    kb_hits: int = 0
    weak_kb: bool = True


def retrieve_for_group(
    vs: VectorStore,
    group: TaskGroup,
    top_k: int = 5,
    max_distance: Optional[float] = None,
) -> Evidence:
    """对整个 TaskGroup 做单次向量检索。"""
    max_d = max_distance if max_distance is not None else config.RETRIEVAL_MAX_DISTANCE
    if vs.get_collection_count() == 0:
        return Evidence(group_id=group.group_id)

    query = expand_query(
        group.shared_query,
        "",
        task_type=group.task_type,
    )
    results = vs.search(query, top_k=top_k, max_distance=max_d)
    kb_hits = len(results)
    weak_kb = kb_hits == 0

    best_sim: Optional[float] = None
    if results:
        dists = [float(r["distance"]) for r in results if r.get("distance") is not None]
        if dists:
            best_sim = max(0.0, min(1.0, 1.0 - min(dists)))

    return Evidence(
        group_id=group.group_id,
        raw_results=results,
        compressed_text="",
        best_similarity=best_sim,
        kb_hits=kb_hits,
        weak_kb=weak_kb,
    )


def compress_evidence(
    evidence: Evidence,
    task: FillTask,
    max_chars: int = 1000,
    *,
    all_tasks: Optional[List[FillTask]] = None,
) -> str:
    """
    从组级检索结果中，按 task 的 description 相关性截取最有用的段落，减少输入 token。

    all_tasks：若传入（如同行多个 table_cell），合并所有任务的描述/章节关键词用于打分，
    避免批量生成时证据只偏向第一格。
    """
    if not evidence.raw_results:
        return "（无有效知识库片段）"

    tasks_for_kw: List[FillTask] = list(all_tasks) if all_tasks else [task]
    task_keywords: set[str] = set()
    for t in tasks_for_kw:
        task_keywords |= set(re.findall(r"[\u4e00-\u9fff]{2,6}", t.description or ""))
        task_keywords |= set(re.findall(r"[\u4e00-\u9fff]{2,6}", t.target_chapter or ""))

    def _score(snippet: str) -> int:
        return sum(1 for kw in task_keywords if kw in snippet)

    scored: list[tuple[int, int, str]] = []
    for idx, r in enumerate(evidence.raw_results):
        text = (r.get("text") or r.get("document") or "").strip()
        if not text:
            continue
        sentences = re.split(r"(?<=[。！？.!?])\s*", text)
        for sent in sentences:
            s = sent.strip()
            if len(s) > 10:
                scored.append((_score(s), idx, s))

    scored.sort(key=lambda x: (-x[0], x[1]))

    selected: list[str] = []
    total = 0
    for _, _, s in scored:
        if total + len(s) > max_chars:
            break
        selected.append(s)
        total += len(s)

    if not selected:
        full = (evidence.raw_results[0].get("text") or "")[:max_chars]
        return full or "（无有效知识库片段）"

    return "\n".join(selected)


def format_evidence(evidence: Evidence, max_chars: int = 1400) -> str:
    """将 raw_results 格式化为模型输入字符串（不经过压缩，按原顺序截断）。"""
    if not evidence.raw_results:
        return "（无有效知识库片段）"
    parts: list[str] = []
    total = 0
    per_chunk = max(200, max_chars // max(1, len(evidence.raw_results)))
    for i, r in enumerate(evidence.raw_results, 1):
        text = (r.get("text") or r.get("document") or "").strip()
        if not text:
            continue
        chunk = text[:per_chunk]
        parts.append(f"[{i}] {chunk}")
        total += len(chunk)
        if total >= max_chars:
            break
    return "\n\n".join(parts) if parts else "（无有效知识库片段）"
