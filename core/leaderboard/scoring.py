"""V/A/C 加权、G/G_doc、Tier、并列判定。"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from core.leaderboard.config_loader import project_profile_weights, track_weights


TIERS = [
    ("T0", 900, 1000),
    ("T1", 850, 899),
    ("T2", 800, 849),
    ("T3", 730, 799),
    ("T4", 650, 729),
    ("T5", 550, 649),
    ("T6", 0, 549),
]


def weighted_score(subscores: Dict[str, float], weights: Dict[str, float]) -> Optional[float]:
    if not weights:
        return None
    total_w = 0.0
    acc = 0.0
    for key, w in weights.items():
        if key not in subscores:
            continue
        v = subscores[key]
        if v is None or (isinstance(v, float) and math.isnan(v)):
            continue
        acc += float(v) * w
        total_w += w
    if total_w < 1e-9:
        return None
    return 1000.0 * (acc / total_w)


def tier_for(score: Optional[float]) -> str:
    if score is None:
        return "待测"
    s = int(round(score))
    for name, lo, hi in TIERS:
        if lo <= s <= hi:
            return name
    return "T6"


def compute_g(
    v: Optional[float],
    a: Optional[float],
    c: Optional[float],
    formula: Dict[str, float],
    *,
    require_vision: bool = True,
    vision_capable: bool = True,
) -> Optional[float]:
    if require_vision and not vision_capable:
        return None
    parts: List[Tuple[float, float]] = []
    if v is not None and "vision" in formula:
        parts.append((v, formula["vision"]))
    if a is not None and "agent" in formula:
        parts.append((a, formula["agent"]))
    if c is not None and "coding" in formula:
        parts.append((c, formula["coding"]))
    if not parts:
        return None
    tw = sum(w for _, w in parts)
    if tw < 1e-9:
        return None
    return sum(s * w for s, w in parts) / tw


def speed_score_from_p50(p50_ms: float, baseline_ms: float = 3000.0) -> float:
    if p50_ms <= 0:
        return 0.0
    return 1000.0 * min(1.0, baseline_ms / p50_ms)


@dataclass
class ModelScoreRow:
    model_id: str
    channel: str
    provider: str = ""
    v: Optional[float] = None
    a: Optional[float] = None
    c: Optional[float] = None
    e: Optional[float] = None
    g: Optional[float] = None
    g_doc: Optional[float] = None
    tier: str = "待测"
    tier_doc: str = "待测"
    ci_margin: float = 12.0
    p50_ms: Optional[float] = None
    cost_per_1k: float = 0.002
    vision_capable: bool = False
    probe_chat_ok: bool = False
    probe_search_gw: bool = False
    probe_search_wrap: bool = False
    subscores_v: Dict[str, float] = field(default_factory=dict)
    subscores_a: Dict[str, float] = field(default_factory=dict)
    subscores_c: Dict[str, float] = field(default_factory=dict)
    status: str = "active"
    notes: str = ""

    def value_score(self) -> Optional[float]:
        if self.g_doc is None:
            return None
        tok = max((self.p50_ms or 3000) / 1000.0, 0.1)
        return self.g_doc / (self.cost_per_1k * 10 + tok * 0.5)

    def latency_score(self) -> Optional[float]:
        if self.g_doc is None or not self.p50_ms:
            return None
        return self.g_doc / max(self.p50_ms / 1000.0, 0.1)


def aggregate_row(
    cfg: Dict[str, Any],
    *,
    sub_v: Dict[str, float],
    sub_a: Dict[str, float],
    sub_c: Dict[str, float],
    sub_e: Optional[Dict[str, float]] = None,
    vision_capable: bool = False,
    p50_ms: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    w_v = track_weights(cfg, "vision")
    w_a = track_weights(cfg, "agent")
    w_c = track_weights(cfg, "coding")
    v = weighted_score(sub_v, w_v) if sub_v else None
    a = weighted_score(sub_a, w_a) if sub_a else None
    c = weighted_score(sub_c, w_c) if sub_c else None
    e = weighted_score(sub_e or {}, track_weights(cfg, "embed")) if sub_e else None
    overall = (cfg.get("overall") or {}).get("formula") or {}
    g = compute_g(v, a, c, overall, vision_capable=vision_capable)
    g_doc = compute_g(
        v, a, c,
        project_profile_weights(cfg, "doc_fill"),
        vision_capable=vision_capable,
    )
    return v, a, c, g, g_doc


def rank_rows(rows: List[ModelScoreRow], key: str = "g_doc") -> List[ModelScoreRow]:
    def _key(r: ModelScoreRow) -> float:
        val = getattr(r, key, None)
        return val if val is not None else -1.0

    return sorted(rows, key=_key, reverse=True)


def mark_parallel(rows: List[ModelScoreRow], band: float = 15.0) -> None:
    """分差小于 band 的相邻行标记并列（写入 notes）。"""
    ranked = rank_rows(rows)
    i = 0
    while i < len(ranked):
        cluster = [ranked[i]]
        j = i + 1
        while j < len(ranked):
            a = ranked[i].g_doc
            b = ranked[j].g_doc
            if a is None or b is None:
                break
            if abs(a - b) < band:
                cluster.append(ranked[j])
                j += 1
            else:
                break
        if len(cluster) > 1:
            tag = f"并列({len(cluster)})"
            for r in cluster:
                r.notes = (r.notes + " " + tag).strip()
        i = j if j > i + 1 else i + 1
