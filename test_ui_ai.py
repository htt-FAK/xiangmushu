import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from eval_judge import judge_payload
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parent
RESULT_PATH = ROOT / "ui_eval_result.json"
SCREENSHOT_PATH = ROOT / "debug.png"
PASS_THRESHOLD = 80
APP_URL = "http://127.0.0.1:8502"


def _port_open(port: int = 8502) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def _start_server():
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", "8502"],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    for _ in range(45):
        if proc.poll() is not None:
            raise RuntimeError("server exited before becoming ready")
        if _port_open():
            return proc
        time.sleep(1)
    proc.terminate()
    raise RuntimeError("server did not start on port 8502")


def test_ui_ai_scenarios():
    server_proc = None
    if not _port_open():
        server_proc = _start_server()
    scenarios = []
    try:
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

            page.screenshot(path=str(SCREENSHOT_PATH), full_page=True)
            browser.close()

        assert SCREENSHOT_PATH.exists()
        assert SCREENSHOT_PATH.stat().st_size > 0

        result = {
            "target": "ui",
            "app_url": APP_URL,
            "pass_threshold": PASS_THRESHOLD,
            "scenarios": scenarios,
            "functional_passed": True,
            "screenshot": str(SCREENSHOT_PATH.resolve()),
        }
        result["judge"] = judge_payload(result, target="ui", screenshot_path=SCREENSHOT_PATH)
        RESULT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        assert RESULT_PATH.exists()
    finally:
        if server_proc is not None and server_proc.poll() is None:
            server_proc.terminate()
            try:
                server_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server_proc.kill()
