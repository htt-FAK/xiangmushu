from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from core.document_models import GenerationTrace, QualityReport, dataclass_to_dict
from core.fill_task import FillTask


def build_evidence_ref(metadata: Dict[str, Any]) -> str:
    source = str(metadata.get("source") or "unknown").strip() or "unknown"
    seq = metadata.get("seq")
    page = metadata.get("page")
    source_type = str(metadata.get("source_type") or metadata.get("kb_source") or "").strip()
    parts = [source]
    if seq is not None:
        parts.append(f"seq={seq}")
    if page is not None:
        parts.append(f"page={page}")
    if source_type:
        parts.append(source_type)
    return " | ".join(parts)


def evidence_refs_from_results(results: Iterable[Dict[str, Any]]) -> List[str]:
    refs: List[str] = []
    seen: set[str] = set()
    for item in results:
        meta = item.get("metadata") if isinstance(item, dict) else None
        if not isinstance(meta, dict):
            continue
        ref = build_evidence_ref(meta)
        if ref in seen:
            continue
        seen.add(ref)
        refs.append(ref)
    return refs


def build_generation_trace(
    task: FillTask,
    route_meta: Dict[str, Any],
    output_text: str,
    *,
    audit_verdict: str = "",
    audit_issues: Optional[List[str]] = None,
    revised: bool = False,
) -> GenerationTrace:
    return GenerationTrace(
        task_id=task.task_id,
        target_chapter=task.target_chapter,
        task_type=task.task_type,
        model=str(route_meta.get("model", "")),
        generation_tier=str(route_meta.get("generation_tier", "")),
        model_role=str(route_meta.get("model_role", "")),
        model_route=dict(route_meta.get("model_route") or {}),
        kb_hits=int(route_meta.get("kb_hits") or 0),
        weak_kb=bool(route_meta.get("weak_kb")),
        low_similarity=bool(route_meta.get("low_similarity")),
        native_web_search=bool(route_meta.get("native_web_search")),
        web_evidence_used=bool(route_meta.get("web_evidence_used")),
        web_evidence_summary=dict(route_meta.get("web_evidence_summary") or {}),
        evidence_pack=dict(route_meta.get("evidence_pack") or {}),
        evidence_refs=list(route_meta.get("evidence_refs") or []),
        audit_verdict=audit_verdict,
        audit_issues=list(audit_issues or []),
        revised=bool(revised),
        output_chars=len((output_text or "").strip()),
    )


def build_quality_report(
    *,
    template_name: str,
    output_path: str,
    traces: List[GenerationTrace],
    post_fill_checks: Dict[str, Any],
    visual_audit: Optional[Dict[str, Any]] = None,
) -> QualityReport:
    total_chars = sum(t.output_chars for t in traces)
    return QualityReport(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        template_name=template_name,
        output_name=os.path.basename(output_path),
        total_tasks=len(traces),
        total_chars=total_chars,
        traces=traces,
        post_fill_checks=post_fill_checks,
        visual_audit=dict(visual_audit or {}),
        final_output_path=output_path,
    )


def save_quality_report(output_path: str, report: QualityReport) -> str:
    report_path = os.path.splitext(output_path)[0] + ".report.json"
    payload = dataclass_to_dict(report)
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return report_path


def quality_report_summary(report: QualityReport) -> str:
    leftovers = len(report.post_fill_checks.get("leftover_placeholders") or [])
    missing = len(report.post_fill_checks.get("missing_chapters") or [])
    visual_score = report.visual_audit.get("score")
    parts = [
        f"任务 {report.total_tasks}",
        f"约 {report.total_chars} 字",
        f"残留占位 {leftovers}",
        f"缺失章节 {missing}",
    ]
    if visual_score is not None:
        parts.append(f"视觉分 {visual_score}")
    return " · ".join(parts)
