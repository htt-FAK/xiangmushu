"""Verify T1 (API key preview) and T3 (bottom nav spacing) via screenshots."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from core.auth import get_or_create_user, create_access_token
import requests

BASE = "http://localhost:8502"
OUT_DIR = os.path.join("artifacts", "ui_verify")
os.makedirs(OUT_DIR, exist_ok=True)

# Create user with API key for preview verification
user = get_or_create_user("ui_verify@test.com")
token = create_access_token(user)

# Save a test API key
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
requests.post(f"{BASE}/api/user/apikey", json={"api_key": "sk-test-abcdefghij-9876wxyz"}, headers=headers)
print("API key saved for preview test")

# Storage state
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

    # T1: Settings page - API key preview visible
    page = ctx.new_page()
    page.goto(f"{BASE}/settings", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    page.screenshot(path=os.path.join(OUT_DIR, "t1_settings_preview.png"), full_page=True)
    print("T1 screenshot saved")
    page.close()

    # T3: Generate page - check bottom content not obscured by nav
    page = ctx.new_page()
    page.goto(f"{BASE}/generate", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    page.screenshot(path=os.path.join(OUT_DIR, "t3_generate_bottom.png"), full_page=True)
    print("T3 generate screenshot saved")
    page.close()

    # T3: Knowledge page - scroll to bottom
    page = ctx.new_page()
    page.goto(f"{BASE}/knowledge", wait_until="networkidle", timeout=15000)
    page.wait_for_timeout(2000)
    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    page.wait_for_timeout(500)
    page.screenshot(path=os.path.join(OUT_DIR, "t3_knowledge_bottom.png"), full_page=False)
    print("T3 knowledge bottom screenshot saved")
    page.close()

    # T2: Verify empty state link (create temp user without templates/kbs)
    # Skip - would need isolated DB state

    browser.close()

if os.path.exists(state_file):
    os.remove(state_file)

# Cleanup test API key
requests.delete(f"{BASE}/api/user/apikey", headers=headers)
print("Done.")
