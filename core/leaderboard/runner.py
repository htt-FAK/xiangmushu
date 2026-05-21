"""评测编排入口。"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.leaderboard.config_loader import load_leaderboard_config
from core.leaderboard.harness import run_probes_for_entry
from core.leaderboard.models_registry import build_model_registry
from core.leaderboard.report import (
    build_model_selection,
    render_markdown,
    render_selection_md,
    rows_to_dict,
    write_model_selection,
    write_results_json,
)
from core.leaderboard.scoring import (
    ModelScoreRow,
    aggregate_row,
    mark_parallel,
    tier_for,
    weighted_score,
)
from core.leaderboard.config_loader import track_weights
from core.leaderboard.suites import run_agent_suite, run_coding_suite, run_vision_suite
from core.leaderboard.suites.project_c import (
    reset_offline_repo_cache,
    run_offline_repo_score_once,
)
from core.leaderboard.harness import probe_embed, client_for_channel


def run_leaderboard(
    *,
    config_path: Optional[str] = None,
    channels: Optional[List[str]] = None,
    model_ids: Optional[List[str]] = None,
    quick: bool = False,
    dry_run: bool = False,
    offline_c_only: bool = False,
    skip_vision_suite: bool = False,
    skip_agent_suite: bool = False,
    tracks: Optional[List[str]] = None,
) -> str:
    cfg = load_leaderboard_config(config_path)
    chs = channels or list(cfg.get("channels") or ["fosun", "dashscope"])
    entries = build_model_registry(model_ids)
    if quick:
        qm = set(cfg.get("quick_models") or [])
        entries = [e for e in entries if e.model_id in qm]
    elif model_ids:
        wanted = set(model_ids)
        entries = [e for e in entries if e.model_id in wanted]

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    out_dir = os.path.join(root, "data", "leaderboard")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(out_dir, f"results_{ts}.json")
    md_path = os.path.join(root, "docs", "模型评分榜.md")
    sel_path = os.path.join(out_dir, "model_selection.yaml")
    sel_md_path = os.path.join(root, "docs", "模型选型建议.md")

    rows: List[ModelScoreRow] = []
    run_tracks = set(tracks or ["v", "a", "c", "e", "probe"])

    reset_offline_repo_cache()
    cached_repo_level: Optional[float] = None
    if "c" in run_tracks and not dry_run:
        print("[leaderboard] C 榜离线套件（全榜仅一次）…", flush=True)
        cached_repo_level = run_offline_repo_score_once(verbose=False)
        print(
            f"[leaderboard] repo_level={'通过' if cached_repo_level >= 1.0 else '未通过'}",
            flush=True,
        )

    work: List[tuple] = []
    for entry in entries:
        for ch in chs:
            if ch == "fosun":
                import config as app_config
                if not (app_config.FOSUN_AIGW_API_KEY or "").strip():
                    continue
            elif ch == "dashscope":
                import config as app_config
                if not app_config.dashscope_backup_chat_client():
                    continue
            work.append((entry, ch))
    total_work = len(work)
    done = 0

    for entry, ch in work:
        done += 1
        print(
            f"[leaderboard] ({done}/{total_work}) {entry.model_id} @ {ch} …",
            flush=True,
        )
        pr = None
        if (
            "probe" in run_tracks
            and entry.supports_vac()
            and not dry_run
            and not offline_c_only
        ):
            pr = run_probes_for_entry(entry, ch)

        sub_v: Dict[str, float] = {}
        sub_a: Dict[str, float] = {}
        sub_c: Dict[str, float] = {}
        sub_e: Dict[str, float] = {}

        if entry.status == "embed_only":
            if "e" in run_tracks and not dry_run:
                client = client_for_channel(ch)
                if client:
                    em = probe_embed(client, entry.resolve_id(ch))
                    sub_e = {"embed_ping": 1.0 if em.ok else 0.0}
            row = ModelScoreRow(
                model_id=entry.model_id,
                channel=ch,
                provider=entry.provider,
                status=entry.status,
            )
            row.e = weighted_score(sub_e, track_weights(cfg, "embed"))
            rows.append(row)
            continue

        if entry.status == "asr_only":
            continue

        if (
            not offline_c_only
            and "v" in run_tracks
            and not skip_vision_suite
        ):
            sub_v = run_vision_suite(entry, ch, dry_run=dry_run)

        if (
            not offline_c_only
            and "a" in run_tracks
            and not skip_agent_suite
        ):
            sub_a = run_agent_suite(entry, ch, probe=pr, dry_run=dry_run)

        if "c" in run_tracks:
            sub_c = run_coding_suite(
                entry,
                ch,
                dry_run=dry_run,
                offline_only=offline_c_only,
                cached_repo_level=cached_repo_level,
            )

        vision_capable = bool(pr and pr.vision_capable) or (
            dry_run and entry.supports_vision()
        )
        if pr and pr.vision.ok:
            vision_capable = True

        latencies = []
        if pr:
            for m in (pr.chat, pr.vision, pr.search_wrap, pr.search_gw):
                if m.ok:
                    latencies.append(m.t_total_ms)
        p50 = sorted(latencies)[len(latencies) // 2] if latencies else None

        v, a, c, g, g_doc = aggregate_row(
            cfg,
            sub_v=sub_v,
            sub_a=sub_a,
            sub_c=sub_c,
            vision_capable=vision_capable,
            p50_ms=p50,
        )

        row = ModelScoreRow(
            model_id=entry.model_id,
            channel=ch,
            provider=entry.provider,
            v=v,
            a=a,
            c=c,
            g=g,
            g_doc=g_doc,
            tier=tier_for(g),
            tier_doc=tier_for(g_doc),
            p50_ms=p50,
            vision_capable=vision_capable,
            probe_chat_ok=bool(pr and pr.chat.ok),
            probe_search_gw=bool(pr and pr.search_gw_ok),
            probe_search_wrap=bool(pr and pr.search_wrap_ok),
            subscores_v=sub_v,
            subscores_a=sub_a,
            subscores_c=sub_c,
            status=entry.status,
        )
        if pr and not pr.chat.ok:
            row.notes = (pr.chat.error or "")[:60]
        rows.append(row)

    parallel_band = float(cfg.get("parallel_band") or 15)
    mark_parallel(rows, parallel_band)

    payload = {
        "leaderboard_version": cfg.get("leaderboard_version"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "channels": chs,
        "quick": quick,
        "dry_run": dry_run,
        "rows": rows_to_dict(rows),
    }
    write_results_json(json_path, payload)

    md = render_markdown(
        cfg, rows, run_meta=payload,
    )
    os.makedirs(os.path.dirname(md_path), exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md)

    if not dry_run:
        sel = build_model_selection(rows, cfg)
        write_model_selection(sel_path, sel)
        with open(sel_md_path, "w", encoding="utf-8") as f:
            f.write(render_selection_md(sel))

    return json_path
