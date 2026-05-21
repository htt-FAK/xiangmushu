"""生成 JSON / Markdown 榜单与 model_selection.yaml。"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import yaml

from core.leaderboard.scoring import ModelScoreRow, rank_rows


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "—"
    return str(int(round(v)))


def rows_to_dict(rows: List[ModelScoreRow]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        out.append({
            "model_id": r.model_id,
            "channel": r.channel,
            "provider": r.provider,
            "V": r.v,
            "A": r.a,
            "C": r.c,
            "E": r.e,
            "G": r.g,
            "G_doc": r.g_doc,
            "tier": r.tier,
            "tier_doc": r.tier_doc,
            "p50_ms": r.p50_ms,
            "vision_capable": r.vision_capable,
            "probe_chat_ok": r.probe_chat_ok,
            "notes": r.notes,
            "subscores_v": r.subscores_v,
            "subscores_a": r.subscores_a,
            "subscores_c": r.subscores_c,
        })
    return out


def write_results_json(path: str, payload: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def render_markdown(
    cfg: Dict[str, Any],
    rows: List[ModelScoreRow],
    *,
    run_meta: Dict[str, Any],
) -> str:
    ver = cfg.get("leaderboard_version", "")
    lines = [
        f"# 项目模型评分榜 ({ver})",
        "",
        f"生成时间：{run_meta.get('timestamp', '')}",
        "",
        f"通道：{', '.join(run_meta.get('channels', []))} · "
        f"模型条目：{len(rows)}",
        "",
        "## 质量主榜（G_doc 多模态办公 / 申报填表）",
        "",
        "公式：`G_doc = 0.50×V + 0.30×A + 0.20×C`；无视觉能力者不计算 G/G_doc。",
        "",
        "| Rank | Model | Channel | V | A | C | G | G_doc | Tier | p50(s) | 备注 |",
        "|------|-------|---------|--:|--:|--:|--:|------:|------|-------:|------|",
    ]
    ranked = rank_rows(rows, "g_doc")
    for i, r in enumerate(ranked, 1):
        if r.g_doc is None and r.status == "embed_only":
            continue
        p50s = f"{(r.p50_ms or 0)/1000:.1f}" if r.p50_ms else "—"
        lines.append(
            f"| {i} | {r.model_id} | {r.channel} | {_fmt(r.v)} | {_fmt(r.a)} | "
            f"{_fmt(r.c)} | {_fmt(r.g)} | {_fmt(r.g_doc)} | {r.tier_doc} | {p50s} | {r.notes} |"
        )
    lines.extend([
        "",
        "## 通用 G 榜（0.30V + 0.35A + 0.35C）",
        "",
        "| Rank | Model | Channel | G | Tier |",
        "|------|-------|---------|--:|------|",
    ])
    ranked_g = rank_rows(rows, "g")
    for i, r in enumerate(ranked_g, 1):
        if r.g is None:
            continue
        lines.append(f"| {i} | {r.model_id} | {r.channel} | {_fmt(r.g)} | {r.tier} |")

    lines.extend(["", "## 低延迟副榜（G_doc / p50）", ""])
    lat = sorted(
        [r for r in rows if r.latency_score() is not None],
        key=lambda x: x.latency_score() or 0,
        reverse=True,
    )[:15]
    for i, r in enumerate(lat, 1):
        lines.append(
            f"{i}. **{r.model_id}** ({r.channel}) — "
            f"latency_score≈{r.latency_score():.0f}"
        )

    lines.extend(["", "## 仅 A/C 榜（无视觉）", ""])
    for r in rows:
        if r.vision_capable:
            continue
        if r.a is None and r.c is None:
            continue
        lines.append(
            f"- {r.model_id} / {r.channel}: A={_fmt(r.a)} C={_fmt(r.c)}"
        )

    lines.extend(["", "## E 榜（嵌入）", ""])
    for r in rows:
        if r.e is not None:
            lines.append(f"- {r.model_id} / {r.channel}: E={_fmt(r.e)}")

    return "\n".join(lines) + "\n"


def build_model_selection(
    rows: List[ModelScoreRow],
    cfg: Dict[str, Any],
) -> Dict[str, Any]:
    """按 G_doc 与通道优选 config 角色。"""
    import config as app_config

    ranked = rank_rows(rows, "g_doc")
    vac = [r for r in ranked if r.g_doc is not None]

    def _pick(
        pred,
        prefer_channel: str = "fosun",
    ) -> Optional[ModelScoreRow]:
        for ch in (prefer_channel, "dashscope"):
            for r in vac:
                if r.channel == ch and pred(r):
                    return r
        for r in vac:
            if pred(r):
                return r
        return None

    picks: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "profile": "doc_fill",
        "recommendations": {},
        "current_config": {
            "LARGE_LLM_MODEL": app_config.LARGE_LLM_MODEL,
            "SMALL_LLM_MODEL": app_config.SMALL_LLM_MODEL,
            "TEMPLATE_VISION_MODEL": app_config.TEMPLATE_VISION_MODEL,
            "TABLE_CELL_VISION_MODEL": app_config.TABLE_CELL_VISION_MODEL,
            "VISION_WEB_MODEL": app_config.VISION_WEB_MODEL,
            "AUDIT_LLM_MODEL": app_config.AUDIT_LLM_MODEL,
            "BATCH_TABLE_FAST_MODEL": getattr(
                app_config, "BATCH_TABLE_FAST_MODEL", "qwen3.5-plus"
            ),
            "EMBEDDING_MODEL": app_config.EMBEDDING_MODEL,
        },
    }

    large = _pick(lambda r: (r.subscores_a.get("execution") or 0) >= 0.5)
    small = _pick(
        lambda r: (r.subscores_a.get("schema") or 0) >= 0.6
        and (r.p50_ms or 99999) < 8000
    )
    vision = _pick(
        lambda r: (r.subscores_v.get("doc_ocr_table") or 0) >= 0.4
        and r.vision_capable
    )
    web = _pick(
        lambda r: r.probe_search_gw or r.probe_search_wrap,
    )
    audit = _pick(lambda r: (r.subscores_a.get("verification") or 0) >= 0.5)
    batch = _pick(
        lambda r: (r.subscores_a.get("schema") or 0) >= 0.7
        and (r.p50_ms or 1e9) < 60000,
    )

    def _rec(row: Optional[ModelScoreRow], role: str) -> None:
        if not row:
            picks["recommendations"][role] = {"status": "no_candidate"}
            return
        picks["recommendations"][role] = {
            "model_id": row.model_id,
            "channel": row.channel,
            "G_doc": row.g_doc,
            "p50_ms": row.p50_ms,
        }

    _rec(large, "LARGE_LLM_MODEL")
    _rec(small, "SMALL_LLM_MODEL")
    _rec(vision, "TEMPLATE_VISION_MODEL")
    _rec(vision, "TABLE_CELL_VISION_MODEL")
    _rec(web, "VISION_WEB_MODEL")
    _rec(audit, "AUDIT_LLM_MODEL")
    _rec(batch, "BATCH_TABLE_FAST_MODEL")

    return picks


def write_model_selection(path: str, data: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def render_selection_md(data: Dict[str, Any]) -> str:
    lines = [
        "# 模型选型建议（自动生成）",
        "",
        f"生成时间：{data.get('generated_at', '')}",
        "",
        "## 当前 config.py 默认值",
        "",
        "```yaml",
        yaml.safe_dump(data.get("current_config") or {}, allow_unicode=True, sort_keys=False).strip(),
        "```",
        "",
        "## 评测推荐",
        "",
    ]
    for role, rec in (data.get("recommendations") or {}).items():
        if rec.get("status") == "no_candidate":
            lines.append(f"- **{role}**：暂无合格候选")
        else:
            lines.append(
                f"- **{role}**：`{rec.get('model_id')}` @ `{rec.get('channel')}` "
                f"(G_doc={rec.get('G_doc')}, p50={rec.get('p50_ms')}ms)"
            )
    lines.append("")
    lines.append(
        "将推荐写入 `.env` 或 `config.py` 前请再跑一轮 `streamlit` 端到端验证。"
    )
    return "\n".join(lines)
