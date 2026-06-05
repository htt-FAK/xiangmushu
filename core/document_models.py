from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any, Dict, List, Optional


@dataclass
class DocumentBlock:
    """A light-weight, cross-format block used by parsing and chunking."""

    text: str
    page: int = 1
    block_type: str = "text"
    source_type: str = "docx"
    chapter: str = ""
    bbox: Optional[List[float]] = None
    table_index: Optional[int] = None
    content_format: str = "text"
    table_header: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationTrace:
    task_id: str
    target_chapter: str
    task_type: str
    model: str
    generation_tier: str
    kb_hits: int = 0
    weak_kb: bool = False
    low_similarity: bool = False
    native_web_search: bool = False
    evidence_refs: List[str] = field(default_factory=list)
    audit_verdict: str = ""
    audit_issues: List[str] = field(default_factory=list)
    revised: bool = False
    output_chars: int = 0


@dataclass
class QualityReport:
    generated_at: str
    template_name: str
    output_name: str
    total_tasks: int
    total_chars: int
    traces: List[GenerationTrace] = field(default_factory=list)
    post_fill_checks: Dict[str, Any] = field(default_factory=dict)
    visual_audit: Dict[str, Any] = field(default_factory=dict)
    final_output_path: str = ""


def dataclass_to_dict(obj: Any) -> Any:
    """Serialize nested dataclasses into plain dict/list values."""

    if is_dataclass(obj):
        return {k: dataclass_to_dict(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {k: dataclass_to_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [dataclass_to_dict(v) for v in obj]
    return obj
