#!/usr/bin/env python3
"""项目模型评分榜 V/A/C/G + 速度。

用法（项目根目录）:
  python scripts/run_leaderboard.py --dry-run
  python scripts/run_leaderboard.py --quick --channels fosun,dashscope
  python scripts/run_leaderboard.py --models qwen3.5-plus,gpt-5.4
  python scripts/run_leaderboard.py --offline-c-only
  python scripts/run_leaderboard.py --track probe
"""
from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
os.chdir(_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

from core.leaderboard.runner import run_leaderboard  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="项目模型评分榜 V/A/C/G + 速度")
    ap.add_argument("--config", default=None, help="leaderboard YAML 路径")
    ap.add_argument(
        "--channels",
        default="fosun,dashscope",
        help="逗号分隔：fosun,dashscope",
    )
    ap.add_argument("--models", default="", help="逗号分隔模型 ID，空=全池")
    ap.add_argument("--quick", action="store_true", help="仅 quick_models 子集")
    ap.add_argument("--dry-run", action="store_true", help="不调 API，占位分")
    ap.add_argument(
        "--offline-c-only",
        action="store_true",
        help="仅跑 C 榜离线 repo 子项",
    )
    ap.add_argument("--skip-vision-suite", action="store_true")
    ap.add_argument("--skip-agent-suite", action="store_true")
    ap.add_argument(
        "--track",
        default="",
        help="逗号分隔：probe,v,a,c,e；空=全部",
    )
    args = ap.parse_args()

    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    model_ids = [m.strip() for m in args.models.split(",") if m.strip()] or None
    tracks = [t.strip() for t in args.track.split(",") if t.strip()] or None

    out = run_leaderboard(
        config_path=args.config,
        channels=channels,
        model_ids=model_ids,
        quick=args.quick,
        dry_run=args.dry_run,
        offline_c_only=args.offline_c_only,
        skip_vision_suite=args.skip_vision_suite,
        skip_agent_suite=args.skip_agent_suite,
        tracks=tracks,
    )
    print(f"[OK] 结果 JSON: {out}")
    print(f"[OK] 榜单 Markdown: docs/模型评分榜.md")
    if not args.dry_run:
        print("[OK] 选型: data/leaderboard/model_selection.yaml")
        print("[OK] 说明: docs/模型选型建议.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
