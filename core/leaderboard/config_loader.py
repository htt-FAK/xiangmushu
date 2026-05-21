"""加载 leaderboard YAML 配置。"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List

import yaml

_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = _ROOT / "data" / "leaderboard" / "leaderboard_v2026.05.21.yaml"


def load_leaderboard_config(path: str | Path | None = None) -> Dict[str, Any]:
    p = Path(path) if path else DEFAULT_CONFIG
    if not p.is_file():
        raise FileNotFoundError(f"leaderboard config not found: {p}")
    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def track_weights(cfg: Dict[str, Any], track: str) -> Dict[str, float]:
    tracks = cfg.get("tracks") or {}
    t = tracks.get(track) or {}
    return dict((t.get("weights") or {}))


def project_profile_weights(cfg: Dict[str, Any], profile: str = "doc_fill") -> Dict[str, float]:
    profiles = cfg.get("project_profiles") or {}
    p = profiles.get(profile) or {}
    return dict((p.get("formula") or {}))
