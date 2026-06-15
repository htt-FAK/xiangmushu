"""Full mobile API integration test - correct endpoints, comprehensive coverage."""
import sys, os, json, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from core.auth import get_or_create_user, create_access_token

BASE = "http://localhost:8502"
OUT_DIR = os.path.join("artifacts", "mobile_full_test")
os.makedirs(OUT_DIR, exist_ok=True)

user = get_or_create_user("mobile_full@test.com")
token = create_access_token(user)
print(f"[AUTH] Token OK for {user.email}")

results = []

def record(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    results.append({"name": name, "passed": passed, "detail": detail})
    print(f"[{status}] {name}" + (f" - {detail}" if detail else ""))

# Prepare storage state
state_file = os.path.join(OUT_DIR, "_auth.json")
storage_state = {
    "cookies": [],
    "origins": [{"origin": BASE, "localStorage": [{"name": "xiangmushu.auth.token", "value": token}]}]
}
with open(state_file, "w") as f:
    json.dump(storage_state, f)

UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        user_agent=UA, is_mobile=True, has_touch=True,
        storage_state=state_file,
    )

    # T01: Auth entry page renders
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/auth", wait_until="networkidle", timeout=15000)
        has_form = page.locator('input[type="email"], input[placeholder*="mail"]').count() > 0
        record("T01 auth page renders", has_form, f"url={page.url}")
        page.screenshot(path=os.path.join(OUT_DIR, "t01.png"), full_page=True)
    except Exception as e:
        record("T01 auth page renders", False, str(e)[:120])
    finally:
        page.close()

    # T02: Home page (authenticated)
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        on_home = "/auth" not in page.url
        record("T02 home auth pass", on_home, f"url={page.url}")
        page.screenshot(path=os.path.join(OUT_DIR, "t02.png"), full_page=True)
    except Exception as e:
        record("T02 home auth pass", False, str(e)[:120])
    finally:
        page.close()

    # T03: API /api/template/list
    page = ctx.new_page()
    try:
        resp = page.request.get(f"{BASE}/api/template/list", headers={"Authorization": f"Bearer {token}"})
        ok = resp.status == 200
        body = resp.json() if ok else {}
        count = len(body.get("templates", []))
        record("T03 template list API", ok and count > 0, f"status={resp.status}, count={count}")
    except Exception as e:
        record("T03 template list API", False, str(e)[:120])
    finally:
        page.close()

    # T04: API /api/kb/list
    page = ctx.new_page()
    try:
        resp = page.request.get(f"{BASE}/api/kb/list", headers={"Authorization": f"Bearer {token}"})
        ok = resp.status == 200
        body = resp.json() if ok else []
        count = len(body) if isinstance(body, list) else 0
        record("T04 kb list API", ok, f"status={resp.status}, count={count}")
    except Exception as e:
        record("T04 kb list API", False, str(e)[:120])
    finally:
        page.close()

    # T05: API /api/billing/summary
    page = ctx.new_page()
    try:
        resp = page.request.get(f"{BASE}/api/billing/summary", headers={"Authorization": f"Bearer {token}"})
        ok = resp.status == 200
        record("T05 billing summary API", ok, f"status={resp.status}")
    except Exception as e:
        record("T05 billing summary API", False, str(e)[:120])
    finally:
        page.close()

    # T06: API /api/user/apikey with key_preview field
    page = ctx.new_page()
    try:
        resp = page.request.get(f"{BASE}/api/user/apikey", headers={"Authorization": f"Bearer {token}"})
        ok = resp.status == 200
        body = resp.json() if ok else {}
        has_field = "key_preview" in body
        record("T06 apikey status+preview", ok and has_field, f"status={resp.status}, preview={body.get('key_preview')}")
    except Exception as e:
        record("T06 apikey status+preview", False, str(e)[:120])
    finally:
        page.close()

    # T07: Generate page - simple mode only, no Advanced toggle
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/generate", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        on_gen = "/generate" in page.url
        no_adv = page.locator('button:has-text("Advanced")').count() == 0
        has_start = page.locator('button:has-text("开始生成"), button:has-text("Start")').count() > 0
        record("T07 generate simple-only", on_gen and no_adv and has_start,
               f"url={page.url}, no_adv={no_adv}, has_start={has_start}")
        page.screenshot(path=os.path.join(OUT_DIR, "t07.png"), full_page=True)
    except Exception as e:
        record("T07 generate simple-only", False, str(e)[:120])
    finally:
        page.close()

    # T08: Knowledge base page
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/knowledge", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        on_kb = "/knowledge" in page.url
        record("T08 knowledge page", on_kb, f"url={page.url}")
        page.screenshot(path=os.path.join(OUT_DIR, "t08.png"), full_page=True)
    except Exception as e:
        record("T08 knowledge page", False, str(e)[:120])
    finally:
        page.close()

    # T09: Settings page
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/settings", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        on_set = "/settings" in page.url
        record("T09 settings page", on_set, f"url={page.url}")
        page.screenshot(path=os.path.join(OUT_DIR, "t09.png"), full_page=True)
    except Exception as e:
        record("T09 settings page", False, str(e)[:120])
    finally:
        page.close()

    # T10: Touch tap on generate start button
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/generate", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        btn = page.locator('button:has-text("开始生成"), button:has-text("Start")')
        if btn.count() > 0:
            btn.first.tap()
            page.wait_for_timeout(1000)
            record("T10 touch tap generate", True, "tap ok")
        else:
            record("T10 touch tap generate", False, "btn not found")
        page.screenshot(path=os.path.join(OUT_DIR, "t10.png"), full_page=True)
    except Exception as e:
        record("T10 touch tap generate", False, str(e)[:120])
    finally:
        page.close()

    # T11: Slow 3G network simulation
    page = ctx.new_page()
    try:
        cdp = page.context.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.send("Network.emulateNetworkConditions", {
            "offline": False,
            "downloadThroughput": int(1.5 * 1024 * 1024 / 8),
            "uploadThroughput": int(750 * 1024 / 8),
            "latency": 300,
        })
        t0 = time.time()
        page.goto(f"{BASE}/", wait_until="networkidle", timeout=30000)
        elapsed = time.time() - t0
        on_home = "/auth" not in page.url
        record("T11 slow-3g load", on_home, f"elapsed={elapsed:.1f}s")
        page.screenshot(path=os.path.join(OUT_DIR, "t11.png"), full_page=True)
    except Exception as e:
        record("T11 slow-3g load", False, str(e)[:120])
    finally:
        page.close()

    # T12: API key save flow (save -> verify preview -> delete)
    page = ctx.new_page()
    try:
        test_key = "sk-test-abcdef1234567890xyzw"
        # Save
        r1 = page.request.post(f"{BASE}/api/user/apikey",
                               data=json.dumps({"api_key": test_key}),
                               headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
        save_ok = r1.status == 200
        # Check preview
        r2 = page.request.get(f"{BASE}/api/user/apikey", headers={"Authorization": f"Bearer {token}"})
        body = r2.json() if r2.status == 200 else {}
        preview = body.get("key_preview", "")
        # Verify masking: first 4 + stars + last 4
        mask_ok = preview is not None and "****" in preview and preview[:4] == test_key[:4] and preview[-4:] == test_key[-4:]
        # Delete
        r3 = page.request.delete(f"{BASE}/api/user/apikey", headers={"Authorization": f"Bearer {token}"})
        del_ok = r3.status == 200
        record("T12 apikey save+mask+delete", save_ok and mask_ok and del_ok,
               f"save={r1.status}, preview={preview}, del={r3.status}")
    except Exception as e:
        record("T12 apikey save+mask+delete", False, str(e)[:120])
    finally:
        page.close()

    # T13: Admin page loads
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/admin", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        on_admin = "/admin" in page.url
        record("T13 admin page", on_admin, f"url={page.url}")
        page.screenshot(path=os.path.join(OUT_DIR, "t13.png"), full_page=True)
    except Exception as e:
        record("T13 admin page", False, str(e)[:120])
    finally:
        page.close()

    # T14: Template analysis page loads
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/template-analysis", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        on_ta = "/template-analysis" in page.url or "/template" in page.url
        record("T14 template-analysis page", on_ta, f"url={page.url}")
        page.screenshot(path=os.path.join(OUT_DIR, "t14.png"), full_page=True)
    except Exception as e:
        record("T14 template-analysis page", False, str(e)[:120])
    finally:
        page.close()

    # T15: Health endpoint
    page = ctx.new_page()
    try:
        resp = page.request.get(f"{BASE}/api/health")
        ok = resp.status == 200
        record("T15 health endpoint", ok, f"status={resp.status}")
    except Exception as e:
        record("T15 health endpoint", False, str(e)[:120])
    finally:
        page.close()

    browser.close()

if os.path.exists(state_file):
    os.remove(state_file)

# Summary
passed = sum(1 for r in results if r["passed"])
total = len(results)
print(f"\nRESULT: {passed}/{total} passed")
for r in results:
    mark = "[OK]" if r["passed"] else "[XX]"
    print(f"  {mark} {r['name']}: {r['detail']}")
