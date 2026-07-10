#!/usr/bin/env python3
"""Probe Firecrawl hosted MCP /v2/mcp — wire-protocol investigation.

Answers three questions:
  A) Does a stateless POST (no initialize handshake, no session header) work?
  B) If not, what does the server require?
  C) For success, JSON body or SSE stream?

Usage:
    python scripts/probe_firecrawl_mcp.py 2>&1 | tee .omo/evidence/task-1-firecrawl-web-search.txt
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

import httpx

ENDPOINT = "https://mcp.firecrawl.dev/v2/mcp"
TIMEOUT_S = 60
MAX_RETRIES = 3

TOOL_SEARCH_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
        "name": "firecrawl_search",
        "arguments": {"query": "python httpx streaming", "limit": 3},
    },
}

INITIALIZE_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {"name": "mprobe", "version": "0.1.0"},
    },
}


def sep(title):
    w = 72
    print(f"\n{'=' * w}")
    print(f" {title}")
    print(f"{'=' * w}\n")


def dump_hdrs(label, headers):
    print(f"\n--- {label} headers ---")
    for k, v in headers.items():
        print(f"  {k}: {v}")
    print()


def _maybe_add(results, item):
    if isinstance(item, dict):
        url = item.get("url") or item.get("link") or item.get("href")
        title = item.get("title") or item.get("name")
        if url:
            results.append((url, title))


def extract_real_url_title(obj):
    """Walk firecrawl tools/call result structure to find (url, title)."""
    if not isinstance(obj, dict) or "result" not in obj:
        return None, None
    found = []
    root = obj["result"]
    content = root.get("content", [])
    if not isinstance(content, list):
        return None, None
    for item in content:
        if not isinstance(item, dict):
            continue
        # Direct data.results[] / data[] nesting
        data = item.get("data") or {}
        if isinstance(data, list):
            for entry in data:
                _maybe_add(found, entry)
        elif isinstance(data, dict):
            sub = data.get("results", [])
            if isinstance(sub, list):
                for entry in sub:
                    _maybe_add(found, entry)
            else:
                _maybe_add(found, data)
        # Raw JSON string in .content[]._raw field
        raw_str = item.get("_raw", "")
        if isinstance(raw_str, str) and raw_str.startswith("{"):
            try:
                for key in ("results", "data", "links"):
                    val = json.loads(raw_str).get(key)
                    if isinstance(val, list):
                        for entry in val:
                            _maybe_add(found, entry)
            except json.JSONDecodeError:
                pass
        # Common MCP wrapping: content.type="text" containing JSON string of results
        text_val = item.get("text", "")
        if isinstance(text_val, str) and text_val.strip().startswith("{"):
            try:
                inner = json.loads(text_val)
                if isinstance(inner, dict):
                    for key in ("results", "data", "web"):
                        payload = inner.get(key)
                        if isinstance(payload, list):
                            for entry in payload:
                                _maybe_add(found, entry)
                        elif isinstance(payload, dict):
                            _maybe_add(found, payload)
            except json.JSONDecodeError:
                pass
    if found:
        return found[0]
    return None, None


def parse_sse(raw_bytes):
    evts = []
    text = raw_bytes.decode("utf-8", errors="replace")
    for line in text.split("\n"):
        s = line.strip()
        if s.startswith("data:"):
            payload = s[5:].strip()
            if payload:
                try:
                    evts.append(json.loads(payload))
                except json.JSONDecodeError:
                    evts.append({"_raw_unparsed": payload})
    return evts


def is_error_resp(p, status):
    """Return (bool_is_err, code, msg, extra). Extra captures auth/wwwauth details."""
    extra = {}
    # Always flag HTTP errors
    if status >= 400:
        http_msg = f"HTTP_{status}"
        if p and isinstance(p, dict):
            desc = p.get("error_description", "") or p.get("error", "")
            if desc:
                extra["error_description"] = desc
        return True, http_msg, desc or http_msg, extra
    # JSON-RPC error within 2xx (some servers wrap errors in result envelope)
    if p and isinstance(p, dict) and "error" in p:
        e = p["error"]
        c = e.get("code", "?") if isinstance(e, dict) else "?"
        m = e.get("message", "") if isinstance(e, dict) else ""
        return True, c, m, extra
    return False, None, None, extra


def collect_text(raw_bytes):
    t = raw_bytes.decode("utf-8", errors="replace")
    return (t[:4000] + "\n ...truncated...\n") if len(t) > 4000 else t + "\n"


def make_base_headers(extra=None):
    hdrs = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if extra:
        hdrs.update(extra)
    return hdrs


# ===========================================================================
# Probe phases
# ===========================================================================
async def phase_stateless(client):
    sep("PHASE 1 — STATELESS POST (no handshake)")
    print(f"Endpoint : {ENDPOINT}")
    print(f"Payload  : {json.dumps(TOOL_SEARCH_PAYLOAD, indent=2)}\n")

    last_raw = b""
    for attempt in range(1, MAX_RETRIES + 1):
        if attempt > 1:
            delay = 2 ** (attempt - 1)
            print(f"Retry {attempt}/{MAX_RETRIES}, waiting {delay}s\n")
            time.sleep(delay)
        print(f"--- attempt {attempt} ---")
        try:
            async with client.stream(
                "POST", ENDPOINT, headers=make_base_headers(), json=TOOL_SEARCH_PAYLOAD, timeout=TIMEOUT_S
            ) as resp:
                st = resp.status_code
                rh = dict(resp.headers)
                print(f"HTTP {st}")
                dump_hdrs("Response", rh)

                raw = await resp.aread()
                last_raw = raw
                ct = rh.get("content-type", "").lower()
                is_sse = "text/event-stream" in ct

                print("--- raw response body ---")
                print(collect_text(raw))
                print("---- end ----\n")

                parsed = None
                evts = []
                if raw.strip():
                    # Try plain-JSON first (succeeds when server bypasses SSE or returns single blob)
                    try:
                        parsed = json.loads(raw)
                    except json.JSONDecodeError:
                        # Fall back to SSE parsing
                        evts = parse_sse(raw)
                        # Combine result from first event that has one
                        for ev in evts:
                            if isinstance(ev, dict) and "result" in ev:
                                parsed = ev
                                break

                err_found, err_code, err_msg, extra = is_error_resp(parsed, st)
                if err_found:
                    print(f"ERROR — code={err_code}, msg={err_msg}")
                    for ek, ev in extra.items():
                        print(f"  extra[{ek}] = {ev}")

                sid = rh.get("mcp-session-id", "")
                fmt = "sse" if is_sse else ("json" if parsed else "unknown")
                if evts:
                    print(f"[SSE events extracted: {len(evts)}]\n")
                    for i, ev in enumerate(evts):
                        print(f"  [{i}] keys={list(ev.keys()) if isinstance(ev, dict) else type(ev).__name__}")

                live_url, live_title = extract_real_url_title(parsed) if parsed else (None, None)
                if live_url:
                    print(f"REAL RESULT FOUND  URL={live_url}  TITLE={live_title}")
                elif parsed:
                    rk = parsed.get("result", {})
                    print("[!] No URL/title extracted; dumping keys:\n")
                    items = rk.items() if isinstance(rk, dict) else [["???", rk]]
                    for k, v in items:
                        print(f"  {k} = {str(v)[:300]}")

                return {
                    "phase": "stateless", "status": st,
                    "session_required": err_found or st >= 500,
                    "format": fmt, "sid_header": sid,
                    "live_url": live_url, "live_title": live_title,
                    "raw": last_raw,
                }
        except Exception as exc:
            print(f"[{type(exc).__name__}] {exc}\n")

    return {
        "phase": "stateless", "status": 0,
        "session_required": True, "format": "unknown",
        "sid_header": "", "live_url": None, "live_title": None,
        "raw": last_raw,
    }


async def phase_init_and_search(client):
    """Do full init->session-handshake then retry search."""
    sep("PHASE 1b — INITIALIZE HANDSHAKE")
    raw_parts = []
    init_sid = ""
    try:
        async with client.stream(
            "POST", ENDPOINT, headers=make_base_headers(), json=INITIALIZE_PAYLOAD, timeout=TIMEOUT_S
        ) as inp:
            ist = inp.status_code
            irh = dict(inp.headers)
            print(f"\nInit HTTP {ist}")
            dump_hdrs("Initialize Response", irh)
            ib_raw = await inp.aread()
            ib_text = collect_text(ib_raw)
            print("--- initialize raw body ---")
            print(ib_text)
            print("---- end ----\n")
            raw_parts.append(ib_text)

            ip = None
            if ib_raw.strip():
                try:
                    ip = json.loads(ib_raw)
                except json.JSONDecodeError:
                    pass

            init_sid = irh.get("mcp-session-id", "")
            findings_b = f"Init => HTTP {ist}"
            if ip and isinstance(ip, dict) and "error" in ip:
                e = ip["error"]
                ec = e.get("code", "?") if isinstance(e, dict) else "?"
                em = e.get("message", "") if isinstance(e, dict) else ""
                findings_b += f" RPC code={ec} msg={em}"
            if init_sid:
                findings_b += f" Mcp-Session-Id={init_sid!r}"

        # ----- Search WITH session -----
        sep("PHASE 2 — SEARCH WITH SESSION-ID")
        extras = {"Mcp-Session-Id": init_sid}
        live_url, live_title = None, None

        for att in range(1, MAX_RETRIES + 1):
            if att > 1:
                time.sleep(2 ** (att - 1))
            print(f"--- attempt {att} ---")
            try:
                async with client.stream(
                    "POST", ENDPOINT, headers=make_base_headers(extras),
                    json=TOOL_SEARCH_PAYLOAD, timeout=TIMEOUT_S
                ) as resp:
                    st = resp.status_code
                    rh = dict(resp.headers)
                    print(f"HTTP {st}")
                    dump_hdrs("Response-with-session", rh)

                    raw = await resp.aread()
                    ct = rh.get("content-type", "").lower()
                    is_sse = "text/event-stream" in ct
                    fmt = "sse" if is_sse else "json"

                    print("--- raw response body ---")
                    print(collect_text(raw))
                    print("---- end ----\n")
                    raw_parts.append(collect_text(raw))

                    parsed = None
                    if raw.strip():
                        try:
                            parsed = json.loads(raw)
                        except json.JSONDecodeError:
                            evts = parse_sse(raw)
                            print(f"SSE events ({len(evts)}):\n")
                            combined = None
                            for i, ev in enumerate(evts):
                                print(f"  [{i}] {json.dumps(ev)[:500]}")
                                if isinstance(ev, dict) and "result" in ev:
                                    combined = ev
                            if combined:
                                ur2, ti2 = extract_real_url_title(combined)
                                if ur2:
                                    live_url, live_title = ur2, ti2
                                    print(f"LIVE SUCCESS via SSE  URL={ur2}  TITLE={ti2}")
                        if parsed:
                            ef, _, _, _ex = is_error_resp(parsed, st)
                            if ef:
                                desc = _ex.get("error_description", "") or ""
                                print(f"Still failed — {parsed.get('error', desc)}")
                            else:
                                ur, ti = extract_real_url_title(parsed)
                                if ur:
                                    live_url, live_title = ur, ti
                                    print(f"LIVE SUCCESS via JSON  URL={ur}  TITLE={ti}")
                                else:
                                    print("[!] No URL from search-with-session JSON")
                                    rk = parsed.get("result", {})
                                    items = rk.items() if isinstance(rk, dict) else [["??", rk]]
                                    for k, v in items:
                                        print(f"  {k} = {str(v)[:300]}")
                        break

            except Exception as exc:
                print(f"[{type(exc).__name__}] {exc}\n")

        return {
            "findings_a": "session-required",
            "findings_b": findings_b,
            "findings_c": fmt,
            "live_url": live_url,
            "live_title": live_title,
            "raw": raw_parts,
        }

    except Exception as exc:
        print(f"[init flow failed]: {exc}", file=sys.stderr)
        return {
            "findings_a": "session-rejected",
            "findings_b": f"Init flow failed: {exc}",
            "findings_c": "unknown",
            "live_url": None,
            "live_title": None,
            "raw": raw_parts,
        }


# ===========================================================================
# Main
# ===========================================================================
async def main_probe():
    all_raw_parts = []
    live_url = None
    live_title = None

    async with httpx.AsyncClient(timeout=TIMEOUT_S, follow_redirects=True) as client:

        # Phase 1: stateless
        r1 = await phase_stateless(client)
        all_raw_parts.append(collect_text(r1["raw"]))

        if r1["live_url"]:
            live_url, live_title = r1["live_url"], r1["live_title"]

        if not r1["session_required"]:
            fa = "stateless"
            fb = "N/A (no session required)"
            fc = r1["format"]
        else:
            session_result = await phase_init_and_search(client)
            fa = session_result["findings_a"]
            fb = session_result["findings_b"]
            fc = session_result["findings_c"]
            if session_result["live_url"]:
                live_url, live_title = session_result["live_url"], session_result["live_title"]
            all_raw_parts.extend(session_result["raw"])

    sep("FINAL FINDINGS")
    print(f"FINDING_A (stateless vs session): {fa}")
    print(f"FINDING_B (session protocol):     {fb}")
    print(f"FINDING_C (response format):      {fc}")

    if live_url:
        print(f"\nVERIFIED LIVE RESULT:")
        print(f"  URL   : {live_url}")
        print(f"  Title : {live_title}")
        print("\n** PROBE SUCCESS — live results confirmed. **")
    else:
        print("\n! WARNING — no live URL+title captured.\n", file=sys.stderr)

    # Write evidence file
    ev_dir = Path(".omo/evidence")
    ev_dir.mkdir(parents=True, exist_ok=True)
    ev_path = ev_dir / "task-1-firecrawl-web-search.txt"
    ev_content = (
        f"FIRECRAWL MCP PROBE EVIDENCE\n{'=' * 60}\n\n"
        f"FINDING_A: {fa}\n"
        f"FINDING_B: {fb}\n"
        f"FINDING_C: {fc}\n"
        f"Live URL: {live_url or 'NONE'}\n"
        f"Live Title: {live_title or 'NONE'}\n\n"
        + "".join(all_raw_parts)
    )
    ev_path.write_text(ev_content, encoding="utf-8")
    print(f"\nEvidence written: {ev_path}")
    return 0


if __name__ == "__main__":
    rc = asyncio.run(main_probe())
    print(f"\nExit code: {rc}")
    sys.exit(rc)
