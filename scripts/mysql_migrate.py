from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import (  # noqa: E402
    DatabaseConfigurationError,
    ensure_configured_database,
    migration_files,
    mysql_database_url,
    mysql_enabled,
    mysql_health_check,
    run_mysql_migrations,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or apply Xiangmushu MySQL migrations.")
    parser.add_argument("--check", action="store_true", help="Check configuration and health without applying migrations.")
    parser.add_argument("--migrate", action="store_true", help="Apply pending migrations immediately.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    args = parser.parse_args()

    try:
        if not mysql_enabled():
            result = {
                "ok": True,
                "mode": "sqlite",
                "message": "PERSISTENCE_MODE is not mysql; no MySQL migration needed.",
                "migration_files": [path.name for path in migration_files()],
            }
        elif args.check:
            result = {
                "ok": True,
                "mode": "mysql",
                "database_url": mysql_database_url(mask_password=True),
                "health": mysql_health_check(),
                "migration_files": [path.name for path in migration_files()],
            }
        elif args.migrate:
            result = {
                "ok": True,
                "mode": "mysql",
                "database_url": mysql_database_url(mask_password=True),
                "applied": run_mysql_migrations(),
                "health": mysql_health_check(),
            }
        else:
            result = ensure_configured_database()
            result["database_url"] = mysql_database_url(mask_password=True) if mysql_enabled() else ""

    except DatabaseConfigurationError as exc:
        result = {"ok": False, "error": str(exc)}
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("MySQL migration check")
        print(f"ok: {result.get('ok')}")
        print(f"mode: {result.get('mode', '')}")
        if result.get("database_url"):
            print(f"database: {result['database_url']}")
        if result.get("migration_files"):
            print("migration files:")
            for name in result["migration_files"]:
                print(f"  - {name}")
        if result.get("applied"):
            print("applied:")
            for name in result["applied"]:
                print(f"  - {name}")
        if result.get("health"):
            print(f"health: {result['health']}")
        if result.get("error"):
            print(f"error: {result['error']}", file=sys.stderr)
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
