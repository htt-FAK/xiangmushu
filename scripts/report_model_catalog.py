from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.provider_registry import list_catalog_rows, list_provider_rows  # noqa: E402


def build_report(include_disabled: bool = True) -> dict[str, object]:
    providers = list_provider_rows(include_disabled=True)
    rows = list_catalog_rows(include_disabled=include_disabled)
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["role"])].append(
            {
                "provider_code": row["provider_code"],
                "model": row["model"],
                "enabled": row["enabled"],
                "display_name": row["display_name"],
            }
        )
    return {
        "providers": providers,
        "roles": grouped,
    }


def _print_text(report: dict[str, object]) -> None:
    print("Providers:")
    for provider in report.get("providers", []):
        print(
            f" - {provider['code']} | enabled={provider['enabled']} | "
            f"search={provider['supports_search']} | vision={provider['supports_vision']}"
        )
    for role, rows in report.get("roles", {}).items():
        print(f"\n[{role}]")
        for row in rows:
            print(f" - {row['provider_code']} | {row['model']} | enabled={row['enabled']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only model provider/catalog report.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    parser.add_argument(
        "--enabled-only",
        action="store_true",
        help="Only include enabled model_catalog rows.",
    )
    args = parser.parse_args()

    report = build_report(include_disabled=not args.enabled_only)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        _print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
