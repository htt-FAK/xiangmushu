from playwright.sync_api import sync_playwright
import os

out_dir = os.path.join(os.getcwd(), "artifacts", "mobile_screenshots")
os.makedirs(out_dir, exist_ok=True)

SET_AUTH_JS = """() => {
    localStorage.setItem("xiangmushu.auth.token", "test-token-for-screenshot");
}"""

pages = [
    ("02_home", "/"),
    ("03_generate", "/generate"),
    ("04_knowledge", "/knowledge"),
    ("05_settings", "/settings"),
    ("06_template", "/template"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=3,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
    )
    page = ctx.new_page()

    # Set auth token
    page.goto("http://localhost:5173/auth", wait_until="networkidle", timeout=15000)
    page.evaluate(SET_AUTH_JS)

    for name, path in pages:
        page.goto(f"http://localhost:5173{path}", wait_until="networkidle", timeout=15000)
        page.wait_for_timeout(1500)
        out_path = os.path.join(out_dir, f"{name}.png")
        page.screenshot(path=out_path, full_page=True)
        print(f"{name} captured -> {out_path}")

    browser.close()

print("All screenshots done")
