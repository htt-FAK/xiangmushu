from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.db import mysql_enabled, mysql_health_check, mysql_transaction  # noqa: E402
from core.provider_registry import catalog_seed_candidates, list_provider_rows  # noqa: E402


def _json_struct(value: Any) -> Any:
    if value in (None, "", b""):
        return None
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except Exception:
        return value


def _json_value(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return json.dumps(_json_struct(value), ensure_ascii=False, sort_keys=True)


def _raw_catalog_rows() -> list[dict[str, Any]]:
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT mc.id, mc.provider_id, mc.model_id, mc.display_name, mc.role_key, mc.enabled,
                       mc.capabilities_json, mc.input_price_per_1k, mc.output_price_per_1k,
                       mc.context_window, mc.config_json,
                       mp.code AS provider_code, mp.enabled AS provider_enabled
                FROM model_catalog mc
                JOIN model_providers mp ON mp.id = mc.provider_id
                ORDER BY mc.role_key ASC, mc.id ASC
                """
            )
            return list(cur.fetchall())


def _normalized_existing(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": str(row.get("display_name") or ""),
        "capabilities": _json_value(row.get("capabilities_json")),
        "input_price_per_1k": float(row["input_price_per_1k"]) if row.get("input_price_per_1k") is not None else None,
        "output_price_per_1k": float(row["output_price_per_1k"]) if row.get("output_price_per_1k") is not None else None,
        "context_window": int(row["context_window"]) if row.get("context_window") is not None else None,
        "config": _json_value(row.get("config_json") or {}),
    }


def _normalized_candidate(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "display_name": str(row.get("display_name") or ""),
        "capabilities": _json_value(row.get("capabilities") or []),
        "input_price_per_1k": float(row["input_price_per_1k"]) if row.get("input_price_per_1k") is not None else None,
        "output_price_per_1k": float(row["output_price_per_1k"]) if row.get("output_price_per_1k") is not None else None,
        "context_window": int(row["context_window"]) if row.get("context_window") is not None else None,
        "config": _json_value(row.get("config") or {}),
    }


def build_seed_plan() -> dict[str, Any]:
    if not mysql_enabled():
        raise RuntimeError("Set PERSISTENCE_MODE=mysql before seeding the model catalog.")
    health = mysql_health_check()
    if not health.get("ok"):
        raise RuntimeError(str(health.get("error") or "MySQL health check failed."))

    providers = {str(item["code"]): item for item in list_provider_rows(include_disabled=True)}
    existing_rows = _raw_catalog_rows()
    existing_by_key = {
        (int(row["provider_id"]), str(row["model_id"]), str(row["role_key"])): row
        for row in existing_rows
    }

    operations: list[dict[str, Any]] = []
    counts = {"insert": 0, "update": 0, "unchanged": 0, "skipped": 0}

    for candidate in catalog_seed_candidates():
        provider = providers.get(str(candidate["provider_code"]))
        if provider is None:
            counts["skipped"] += 1
            operations.append(
                {
                    "action": "skipped",
                    "reason": "missing_provider",
                    "role": candidate["role"],
                    "model": candidate["model"],
                    "provider_code": candidate["provider_code"],
                }
            )
            continue
        key = (int(provider["id"]), str(candidate["model"]), str(candidate["role"]))
        existing = existing_by_key.get(key)
        normalized_candidate = _normalized_candidate(candidate)
        if existing is None:
            counts["insert"] += 1
            operations.append(
                {
                    "action": "insert",
                    "role": candidate["role"],
                    "model": candidate["model"],
                    "provider_code": candidate["provider_code"],
                    "provider_id": int(provider["id"]),
                    "enabled": bool(provider.get("enabled")),
                    **normalized_candidate,
                }
            )
            continue
        normalized_existing = _normalized_existing(existing)
        diffs = {
            field: {"from": normalized_existing[field], "to": normalized_candidate[field]}
            for field in normalized_candidate
            if normalized_existing[field] != normalized_candidate[field]
        }
        if diffs:
            counts["update"] += 1
            operations.append(
                {
                    "action": "update",
                    "role": candidate["role"],
                    "model": candidate["model"],
                    "provider_code": candidate["provider_code"],
                    "provider_id": int(provider["id"]),
                    "enabled": bool(existing.get("enabled")),
                    "diff": diffs,
                    **normalized_candidate,
                }
            )
        else:
            counts["unchanged"] += 1
            operations.append(
                {
                    "action": "unchanged",
                    "role": candidate["role"],
                    "model": candidate["model"],
                    "provider_code": candidate["provider_code"],
                    "provider_id": int(provider["id"]),
                    "enabled": bool(existing.get("enabled")),
                    **normalized_candidate,
                }
            )

    return {
        "ok": True,
        "mode": "mysql",
        "health": health,
        "counts": counts,
        "operations": operations,
    }


def apply_seed_plan(plan: dict[str, Any]) -> dict[str, Any]:
    applied = {"inserted": 0, "updated": 0}
    with mysql_transaction() as conn:
        with conn.cursor() as cur:
            for op in plan.get("operations") or []:
                action = str(op.get("action") or "")
                if action == "insert":
                    cur.execute(
                        """
                        INSERT INTO model_catalog(
                            provider_id, model_id, display_name, role_key, capabilities_json,
                            input_price_per_1k, output_price_per_1k, context_window, enabled, config_json
                        )
                        VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            int(op["provider_id"]),
                            op["model"],
                            op["display_name"],
                            op["role"],
                            op["capabilities"],
                            op["input_price_per_1k"],
                            op["output_price_per_1k"],
                            op["context_window"],
                            1 if op.get("enabled") else 0,
                            op["config"],
                        ),
                    )
                    applied["inserted"] += 1
                elif action == "update":
                    cur.execute(
                        """
                        UPDATE model_catalog
                        SET display_name = %s,
                            capabilities_json = %s,
                            input_price_per_1k = %s,
                            output_price_per_1k = %s,
                            context_window = %s,
                            config_json = %s
                        WHERE provider_id = %s AND model_id = %s AND role_key = %s
                        """,
                        (
                            op["display_name"],
                            op["capabilities"],
                            op["input_price_per_1k"],
                            op["output_price_per_1k"],
                            op["context_window"],
                            op["config"],
                            int(op["provider_id"]),
                            op["model"],
                            op["role"],
                        ),
                    )
                    applied["updated"] += 1
    result = dict(plan)
    result["applied"] = applied
    return result


def _print_text(plan: dict[str, Any], *, applied: bool) -> None:
    counts = plan.get("counts") or {}
    print("Model catalog seed")
    print(f"mode: {plan.get('mode')}")
    print(f"dry_run: {not applied}")
    print(
        "counts: "
        f"insert={counts.get('insert', 0)} "
        f"update={counts.get('update', 0)} "
        f"unchanged={counts.get('unchanged', 0)} "
        f"skipped={counts.get('skipped', 0)}"
    )
    if applied:
        print(f"applied: inserted={plan.get('applied', {}).get('inserted', 0)} updated={plan.get('applied', {}).get('updated', 0)}")
    print("operations:")
    for op in plan.get("operations") or []:
        print(f"  - {op['action']}: {op['provider_code']} / {op['role']} / {op['model']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill supported model catalog rows into MySQL.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply the seed plan to MySQL.")
    mode.add_argument("--dry-run", action="store_true", help="Preview the seed plan without modifying MySQL.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON output.")
    args = parser.parse_args()

    try:
        plan = build_seed_plan()
        if args.apply:
            plan = apply_seed_plan(plan)
        ok = True
    except Exception as exc:
        plan = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        ok = False

    if args.json:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
    else:
        _print_text(plan, applied=bool(args.apply) and ok) if ok else print(plan["error"], file=sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
