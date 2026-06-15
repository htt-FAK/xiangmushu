"""Screenshot all mobile pages using storageState for auth persistence."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from playwright.sync_api import sync_playwright
from core.auth import get_or_create_user, create_access_token

BASE = "http://localhost:8502"
OUT_DIR = os.path.join("artifacts", "mobile_all")
os.makedirs(OUT_DIR, exist_ok=True)

# Get a valid token
user = get_or_create_user("screenshot_temp3@test.com")
token = create_access_token(user)
print(f"Token OK for user {user.email}")

# Create a storage state file with the token pre-set
storage_state = {
    "cookies": [],
    "origins": [
        {
            "origin": BASE,
            "localStorage": [
                {"name": "xiangmushu.auth.token", "value": token}
            ]
        }
    ]
}
state_file = os.path.join(OUT_DIR, "_auth_state.json")
with open(state_file, "w") as f:
    json.dump(storage_state, f)
print(f"Storage state written to {state_file}")

pages = [
    ("auth", "/auth"),
    ("home", "/"),
    ("generate_simple", "/generate"),
    ("knowledge", "/knowledge"),
    ("settings", "/settings"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    # Load storage state so all pages start authenticated
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        storage_state=state_file,
    )
    print("Context created with storage state")

    for name, path in pages:
        page = ctx.new_page()
        url = f"{BASE}{path}"
        try:
            page.goto(url, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)
            out_path = os.path.join(OUT_DIR, f"{name}.png")
            page.screenshot(path=out_path, full_page=True)
            final_url = page.url
            print(f"OK: {name} -> {final_url}")
        except Exception as e:
            print(f"FAIL: {name} - {e}")
        finally:
            page.close()

    # Advanced mode screenshot
    page = ctx.new_page()
    try:
        page.goto(f"{BASE}/generate", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(2000)
        adv_btn = page.locator('button:has-text("Advanced")')
        if adv_btn.count() > 0:
            adv_btn.first.click()
            page.wait_for_timeout(1000)
        out_path = os.path.join(OUT_DIR, "generate_advanced.png")
        page.screenshot(path=out_path, full_page=True)
        print(f"OK: generate_advanced -> {page.url}")
    except Exception as e:
        print(f"FAIL: generate_advanced - {e}")
    finally:
        page.close()

    browser.close()

# Cleanup
os.remove(state_file)
print("All done.")
