import json
import re

from eval_judge import judge_payload
from eval_paths import SCREENSHOT, UI_RESULT
from playwright.sync_api import expect, sync_playwright


PASS_THRESHOLD = 80
APP_URL = "http://127.0.0.1:8502"


def test_ui_ai_scenarios(auto_start_server):
    """UI scenario tests. The auto_start_server fixture ensures the server is up."""
    scenarios = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.goto(APP_URL, wait_until="networkidle", timeout=30000)

        expect(page.locator("#page-kb")).to_be_visible()
        expect(page.locator("#kbSelect")).to_be_visible()
        expect(page.locator(".nav-item[data-page='kb']")).to_have_class(re.compile(r"\bactive\b"))
        scenarios.append({"name": "home knowledge-base page render", "ok": True})

        page.locator(".nav-item[data-page='tpl']").click()
        expect(page.locator("#page-tpl")).to_be_visible()
        expect(page.locator("#tplUploadZone")).to_be_visible()
        expect(page.locator("#tplList")).to_be_visible()
        scenarios.append({"name": "switch to template page", "ok": True})

        page.locator(".nav-item[data-page='gen']").click()
        expect(page.locator("#page-gen")).to_be_visible()
        expect(page.locator("#genTemplate")).to_be_visible()
        expect(page.locator("#genWordLimit")).to_be_visible()
        scenarios.append({"name": "switch to generate page", "ok": True})

        page.screenshot(path=str(SCREENSHOT), full_page=True)
        browser.close()

    assert SCREENSHOT.exists()
    assert SCREENSHOT.stat().st_size > 0

    result = {
        "target": "ui",
        "app_url": APP_URL,
        "pass_threshold": PASS_THRESHOLD,
        "scenarios": scenarios,
        "functional_passed": True,
        "screenshot": str(SCREENSHOT.resolve()),
    }
    result["judge"] = judge_payload(result, target="ui", screenshot_path=SCREENSHOT)
    UI_RESULT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    assert UI_RESULT.exists()
