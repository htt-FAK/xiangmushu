"""Benchmark: serial (workers=1) vs concurrent (workers=3) generation."""
import sys, os, time, json, hashlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from core.auth import get_or_create_user, create_access_token

BASE = "http://localhost:8502"
TEMPLATE = "2024级广东理工学院创新计划书参考模板.docx"
SLUG = "default"

user = get_or_create_user("bench@test.com")
token = create_access_token(user)
headers = {"Authorization": f"Bearer {token}"}

def run_generate(label: str) -> dict:
    """Run a full generation and return timing + output hash."""
    print(f"\n[{label}] Starting generation...")
    t0 = time.time()

    resp = requests.post(
        f"{BASE}/api/generate",
        data={
            "slug": SLUG,
            "template": TEMPLATE,
            "word_limit": 300,
            "top_k": 4,
            "max_distance": 1.25,
            "enable_web": False,
            "use_stream": False,  # non-stream for fair timing comparison
            "enable_audit": False,
            "enable_visual_audit": False,
            "custom_instructions": "",
        },
        headers=headers,
        stream=True,
        timeout=600,
    )

    chunks_received = 0
    tasks_total = 0
    done_data = None
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        event = json.loads(line[6:])
        etype = event.get("type")
        if etype == "task":
            tasks_total = event.get("total", 0)
        elif etype == "chunk":
            chunks_received += 1
        elif etype == "progress":
            idx = event.get("index", 0)
            total = event.get("total", 0)
            elapsed = time.time() - t0
            print(f"  [{label}] progress {idx+1}/{total} ({elapsed:.1f}s)")
        elif etype == "done":
            done_data = event
        elif etype == "error":
            print(f"  [{label}] ERROR: {event}")

    elapsed = time.time() - t0

    # Download the output file to hash it
    output_hash = ""
    output_size = 0
    if done_data and done_data.get("download"):
        dl_url = f"{BASE}{done_data['download']}"
        dl_resp = requests.get(dl_url, headers=headers, timeout=30)
        if dl_resp.status_code == 200:
            output_hash = hashlib.md5(dl_resp.content).hexdigest()[:12]
            output_size = len(dl_resp.content)

    billing = done_data.get("billing", {}) if done_data else {}
    result = {
        "label": label,
        "elapsed_seconds": round(elapsed, 2),
        "tasks_total": tasks_total,
        "chunks_received": chunks_received,
        "output_hash": output_hash,
        "output_size_kb": round(output_size / 1024, 1),
        "input_tokens": billing.get("input_tokens", 0),
        "output_tokens": billing.get("output_tokens", 0),
        "cost_cny": billing.get("cost_cny", 0),
    }
    print(f"[{label}] Done: {elapsed:.1f}s, {tasks_total} tasks, hash={output_hash}, size={result['output_size_kb']}KB")
    return result


if __name__ == "__main__":
    # Check server health
    try:
        r = requests.get(f"{BASE}/api/health", timeout=5)
        if r.status_code != 200:
            print(f"Server not ready: {r.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"Server not reachable: {e}")
        sys.exit(1)

    print("=" * 60)
    print("Benchmark: Serial (workers=1) vs Concurrent (workers=3)")
    print(f"Template: {TEMPLATE}")
    print("=" * 60)

    import importlib
    import config

    # Final comparison: w=5 with H3 optimizations
    os.environ["GENERATION_MAX_WORKERS"] = "5"
    importlib.reload(config)
    r1 = run_generate("w=5-optimized")

    # Also run w=5 stream mode for comparison
    os.environ["GENERATION_MAX_WORKERS"] = "5"
    importlib.reload(config)
    # Note: run_generate uses use_stream=False; we just verify the optimized path

    print("\n" + "=" * 60)
    print("FINAL BENCHMARK (w=5 with H3 optimizations)")
    print("=" * 60)
    print(f"  Time:       {r1['elapsed_seconds']}s")
    print(f"  Tasks:      {r1['tasks_total']}")
    print(f"  Size:       {r1['output_size_kb']}KB")
    print(f"  Tokens:     in={r1['input_tokens']} out={r1['output_tokens']}")
    print(f"  Cost:       {r1['cost_cny']} CNY")
    print("=" * 60)
