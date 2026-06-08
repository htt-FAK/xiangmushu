from playwright.sync_api import sync_playwright
import os

out_dir = os.path.join(os.getcwd(), "artifacts", "page_screenshots")
os.makedirs(out_dir, exist_ok=True)

SET_AUTH_JS = """() => {
    localStorage.setItem("xiangmushu_token", "test-token");
    localStorage.setItem("xiangmushu_user", JSON.stringify({id: 1, email: "demo@example.com"}));
}"""

pages = [
    ("login", "/login"),
    ("home", "/"),
    ("generate", "/generate"),
    ("knowledge", "/knowledge"),
    ("settings", "/settings"),
    ("template", "/template"),
]

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)

    # Desktop view (1440x900)
    print("=== Desktop (1440x900) ===")
    d_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    d_page = d_ctx.new_page()
    d_page.goto("http://localhost:5173/login", wait_until="networkidle", timeout=15000)
    d_page.evaluate(SET_AUTH_JS)
    for name, path in pages:
        d_page.goto(f"http://localhost:5173{path}", wait_until="networkidle", timeout=15000)
        d_page.wait_for_timeout(1200)
        out = os.path.join(out_dir, f"desktop_{name}.png")
        d_page.screenshot(path=out, full_page=True)
        print(f"  desktop_{name} OK")
    d_ctx.close()

    # Mobile view (390x844 iPhone)
    print("=== Mobile (390x844) ===")
    m_ctx = browser.new_context(
        viewport={"width": 390, "height": 844},
        device_scale_factor=3,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)",
    )
    m_page = m_ctx.new_page()
    m_page.goto("http://localhost:5173/login", wait_until="networkidle", timeout=15000)
    m_page.evaluate(SET_AUTH_JS)
    for name, path in pages:
        m_page.goto(f"http://localhost:5173{path}", wait_until="networkidle", timeout=15000)
        m_page.wait_for_timeout(1200)
        out = os.path.join(out_dir, f"mobile_{name}.png")
        m_page.screenshot(path=out, full_page=True)
        print(f"  mobile_{name} OK")
    m_ctx.close()

    browser.close()

print("All screenshots done")
