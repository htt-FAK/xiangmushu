"""合并 LLM 结构分析任务与确定性扫槽任务。"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from core.fill_task import FillTask
from core.template_slots import (
    default_word_limit_for_paragraph,
    is_bracket_fill_slot,
    normalize_visible_text,
)

_LOG = logging.getLogger(__name__)


def _para_key(chapter: str, hint: Dict[str, Any]) -> str:
    pt = (hint.get("paragraph_text") or "").strip()
    anchor = (hint.get("anchor") or "").strip()
    return f"p|{normalize_visible_text(chapter)}|{normalize_visible_text(pt)}|{anchor}"


def _table_key(chapter: str, hint: Dict[str, Any]) -> str:
    return (
        f"t|{normalize_visible_text(chapter)}|"
        f"{int(hint.get('table_index', -1))}|"
        f"{int(hint.get('row', -1))}|"
        f"{int(hint.get('col', -1))}"
    )


def _task_key(task: FillTask) -> str:
    h = task.location_hint or {}
    if task.task_type == "table_cell":
        return _table_key(task.target_chapter or "", h)
    return _para_key(task.target_chapter or "", h)


def _merge_hint(
    analyzer_hint: Dict[str, Any],
    scanner_hint: Dict[str, Any],
    task_type: str,
) -> Dict[str, Any]:
    out = dict(analyzer_hint or {})
    for k, v in (scanner_hint or {}).items():
        if k not in out or out[k] in (None, "", -1):
            out[k] = v
    if task_type == "table_cell":
        for field in ("table_index", "row", "col"):
            si = scanner_hint.get(field)
            ai = analyzer_hint.get(field)
            if si is not None and ai is not None and int(si) != int(ai):
                _LOG.warning(
                    "reconcile table_index mismatch analyzer=%s scanner=%s field=%s",
                    ai,
                    si,
                    field,
                )
                out[field] = int(si)
    return out


def reconcile_fill_tasks(
    analyzer_tasks: List[FillTask],
    scanner_tasks: List[FillTask],
) -> List[FillTask]:
    """
    analyzer ∪ scanner；scanner 补缺失槽；table_index 以 scanner 为准。
    """
    by_key: Dict[str, FillTask] = {}
    order: List[str] = []

    for t in analyzer_tasks:
        k = _task_key(t)
        if k not in by_key:
            order.append(k)
        by_key[k] = t

    added = 0
    for st in scanner_tasks:
        k = _task_key(st)
        if k in by_key:
            at = by_key[k]
            merged = _merge_hint(
                at.location_hint or {},
                st.location_hint or {},
                at.task_type,
            )
            at.location_hint = merged
            if is_bracket_fill_slot(
                (merged.get("paragraph_text") or "")
            ) and not (merged.get("replace_mode") or "").strip():
                merged["replace_mode"] = "full"
            continue
        by_key[k] = st
        order.append(k)
        added += 1

    if added:
        _LOG.info("reconcile_fill_tasks: added %d scanner-only tasks", added)

    return [by_key[k] for k in order if k in by_key]
