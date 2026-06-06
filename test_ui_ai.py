import json
import uuid

from core.auth import create_access_token, get_or_create_user
from eval_judge import judge_payload
from eval_paths import SCREENSHOT, UI_RESULT
from playwright.sync_api import expect, sync_playwright


PASS_THRESHOLD = 80
APP_URL = "http://127.0.0.1:8502"


def test_ui_ai_scenarios(auto_start_server):
    """UI scenario tests. The auto_start_server fixture ensures the server is up."""
    user = get_or_create_user(f"ui-{uuid.uuid4().hex}@example.com")
    token = create_access_token(user)
    scenarios = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        page.add_init_script(
            f"window.localStorage.setItem('xiangmushu.auth.token', {json.dumps(token)});"
        )
        page.goto(APP_URL, wait_until="networkidle", timeout=30000)

        expect(page.get_by_role("heading", name="AI 驱动的项目书自动生成工作台")).to_be_visible()
        expect(page.get_by_role("link", name="知识库")).to_be_visible()
        scenarios.append({"name": "authenticated home page render", "ok": True})

        page.get_by_role("link", name="模板分析").click()
        expect(page.get_by_role("heading", name="上传 Word 模板，识别可填写任务")).to_be_visible()
        expect(page.get_by_text("模板上传")).to_be_visible()
        scenarios.append({"name": "switch to template page", "ok": True})

        page.get_by_role("link", name="生成舱").click()
        expect(page.get_by_role("heading", name="选择知识库和模板，启动文档生成")).to_be_visible()
        expect(page.get_by_text("视觉评分")).to_be_visible()
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
