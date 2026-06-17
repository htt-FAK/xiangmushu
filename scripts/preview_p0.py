"""Preview P0 mobile UI changes - mocks all API routes, no backend needed."""
import json
import os
import re
import time
from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(__file__), "..", "artifacts", "p0_preview")
os.makedirs(OUT, exist_ok=True)

def sse_resp(events):
    body = "".join(f"data: {json.dumps(e)}\n\n" for e in events)
    return {"status": 200, "headers": {"content-type": "text/event-stream", "cache-control": "no-cache"}, "body": body}

def json_resp(value, status=200):
    return {"status": status, "headers": {"content-type": "application/json"}, "body": json.dumps(value)}

def route_handler(route):
    req = route.request
    url = req.url
    path = url.split("?")[0].split("#")[0]
    method = req.method.upper()

    # Only mock /api/** — let Vite /assets and the SPA HTML pass through.
    if "/api/" not in path and not path.endswith("/api"):
        return route.continue_()

    api_pos = path.find("/api/")
    if api_pos < 0:
        return route.continue_()
    tail = path[api_pos:]
    if tail.endswith("/health"):
        return route.fulfill(**json_resp({"ok": True}))

    # ---- Auth
    if tail.endswith("/auth/me"):
        return route.fulfill(**json_resp({"email": "test@demo.com", "is_admin": False}))
    if tail.endswith("/auth/identify"):
        return route.fulfill(**json_resp({"email": "test@demo.com", "account_state": "existing_verified"}))
    if tail.endswith("/auth/login") or tail.endswith("/auth/verify-code"):
        return route.fulfill(**json_resp({"access_token": "mock-token", "token_type": "bearer", "user": {"id": 1, "email": "test@demo.com"}}))

    # ---- User preferences / API key
    if tail.endswith("/user/preferences"):
        if method == "PUT":
            return route.fulfill(**json_resp({"language": "zh", "model_choices": {}}))
        return route.fulfill(**json_resp({"language": "zh", "model_choices": {}, "warnings": {}}))
    if tail.endswith("/user/apikey"):
        if method == "DELETE":
            return route.fulfill(**json_resp({"ok": True, "providers": {}}))
        return route.fulfill(**json_resp({"providers": {
            "dashscope": {"provider_code": "dashscope", "has_key": True, "validated": True, "key_preview": "sk-...demo"},
            "deepseek": {"provider_code": "deepseek", "has_key": False, "validated": False},
            "mimo": {"provider_code": "mimo", "has_key": False, "validated": False},
        }}))
    if tail.endswith("/user/apikey/validate") or tail.endswith("/user/apikey/test"):
        return route.fulfill(**json_resp({"ok": True, "code": "ok", "message": "", "retryable": False, "validated_model": "qwen3.7-plus", "probes": []}))
    if tail.endswith("/user/model-options"):
        return route.fulfill(**json_resp({}))

    # ---- Billing
    if tail.endswith("/billing/summary"):
        return route.fulfill(**json_resp({"input_tokens": 0, "output_tokens": 0, "cost_cny": 0, "generation_count": 0}))

    # ---- Templates
    if tail.endswith("/template/list"):
        return route.fulfill(**json_resp({"templates": [{"name": "科技项目申报书.docx"}, {"name": "基金说明书模板.docx"}]}))

    # ---- Knowledge bases
    if tail.endswith("/kb/list"):
        return route.fulfill(**json_resp([
            {"slug": "project-a", "label": "项目 A 资料", "name": "project-a"},
            {"slug": "ref-docs", "label": "政策参考资料", "name": "ref-docs"},
        ]))
    if "/kb/sources" in tail:
        return route.fulfill(**json_resp({
            "sources": ["技术方案.pdf", "团队简介.docx", "财务摘要.xlsx"],
            "chunk_count": 128,
            "source_count": 3,
            "integrity": {"collection_exists": True, "vector_count": 128},
        }))
    if tail.endswith("/kb/create"):
        return route.fulfill(**json_resp({"ok": True, "slug": "new-kb"}))

    # ---- Generation sessions
    if tail.endswith("/generate/sessions/active"):
        return route.fulfill(**json_resp({"session": None}))
    if tail.endswith("/template/analyze/sessions/active"):
        return route.fulfill(**json_resp({"session": None}))
    if tail.endswith("/generate/sessions") and method == "POST":
        snap = {
            "session_id": "mock-session-1",
            "user_id": 1,
            "status": "running",
            "currentStep": "generation",
            "currentTask": "第一章：项目概述与背景",
            "progress": {"done": 2, "total": 6},
            "outputs": [
                {"chapter": "封面", "text": "智能计划书智能体 — 2025年度科技项目申报书", "model": "qwen3.7-plus", "tier": "high", "role": "main_writer", "kbHits": 4, "evidenceRefs": ["技术方案.pdf:p3"], "auditVerdict": "pass", "auditIssues": [], "revised": False},
                {"chapter": "第一章：项目概述与背景", "text": "本项目旨在构建一套面向政企客户的本地化辅助写作系统，通过大语言模型与检索增强生成（RAG）技术，实现从知识库资料到 Word 模板空位的自动化内容填充。系统支持多种文档格式的解析入库，并通过多模态视觉分析识别模板结构。", "model": "qwen3.7-plus", "tier": "high", "role": "main_writer", "kbHits": 8, "evidenceRefs": ["技术方案.pdf:p1"], "auditVerdict": None, "auditIssues": [], "revised": False},
            ],
            "download": "",
            "report_download": "",
            "report_summary": "",
            "post_fill_checks": None,
            "visual_score": None,
            "billing": {"records": [], "input_tokens": 3420, "output_tokens": 1850, "cost_cny": 0.0064},
            "billing_summary": {"input_tokens": 3420, "output_tokens": 1850, "cost_cny": 0.0064, "generation_count": 1},
            "last_error": None,
            "params": {
                "slug": "project-a", "template": "科技项目申报书.docx",
                "custom_instructions": "", "word_limit": 300,
                "top_k": 4, "max_distance": 1.25,
                "enable_web": False, "use_stream": True,
                "enable_audit": False, "enable_visual_audit": True,
            },
            "created_at": "2025-06-17T10:00:00",
            "updated_at": "2025-06-17T10:01:00",
            "last_seq": 14,
        }
        return route.fulfill(**json_resp({"ok": True, "session_id": "mock-session-1", "session": snap}))
    if "/generate/sessions/" in tail and tail.endswith("/stream"):
        events = [
            {"type": "heartbeat", "seq": 15},
            {"type": "route", "index": 2, "model": "qwen3.7-plus", "tier": "high", "role": "main_writer", "kb_hits": 6, "evidence_refs": ["团队简介.docx:p2"]},
            {"type": "task", "index": 2, "total": 6, "chapter": "第二章：技术方案与创新点"},
            {"type": "chunk", "index": 2, "text": "本项目采用 FastAPI + React + Tailwind 前后端分离架构"},
        ]
        return route.fulfill(**sse_resp(events))
    if "/generate/sessions/mock-session-1/terminate" in tail:
        return route.fulfill(**json_resp({"ok": True}))

    # ---- Template analysis sessions
    if "/template/analyze/sessions" in tail:
        if method == "POST":
            return route.fulfill(**json_resp({"ok": True, "session_id": "mock-ta", "session": None}))
        return route.fulfill(**json_resp({"session": None}))

    # ---- SSE: generation stream
    if "/generate/sessions" in tail and "stream" in tail:
        return route.fulfill(**json_resp({"session": None}))

    # ---- Admin
    if tail.endswith("/admin/stats"):
        return route.fulfill(**json_resp({"forbidden": True}, status=403))

    # ---- History
    if tail.endswith("/history/articles"):
        return route.fulfill(**json_resp({"articles": [], "summary": {"count": 0, "inputTokens": 0, "outputTokens": 0, "totalTokens": 0, "costCny": 0, "modelUsage": []}, "availability": {"available": True, "source": "backend"}}))

    # Default: 200 empty
    print(f"  [unmocked {method}] {tail}")
    return route.fulfill(**json_resp({"ok": True}))


def wait_for_render(page, selector=None, timeout_ms=8000):
    try:
        if selector:
            page.wait_for_selector(selector, timeout=timeout_ms)
    except Exception:
        pass
    page.wait_for_timeout(1200)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(
            channel="chrome",
            headless=True,
            args=["--disable-features=ChromeWhatsNewUI", "--no-sandbox"],
        )
        ctx = browser.new_context(
            viewport={"width": 390, "height": 844},
            device_scale_factor=2,
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
        )
        page = ctx.new_page()
        page.route("**/*", route_handler)

        # ---------- Login ----------
        print("1. Setting up auth...")
        page.goto("http://localhost:5173/", wait_until="domcontentloaded")
        page.wait_for_timeout(600)
        page.evaluate("""() => { localStorage.setItem("xiangmushu.auth.token", "mock-token"); }""")
        page.goto("http://localhost:5173/", wait_until="domcontentloaded")
        wait_for_render(page, "nav")

        # ---------- Screenshot 1: Home — 4-item bottom bar ----------
        print("2. Capturing: P0#1 home (4-item bottom bar)...")
        page.screenshot(path=os.path.join(OUT, "01_home_bottombar.png"), full_page=False)

        # ---------- Screenshot 2: Generate idle state ----------
        print("3. Capturing: P0#2 generate idle...")
        page.goto("http://localhost:5173/generate", wait_until="domcontentloaded")
        wait_for_render(page, "button")
        page.screenshot(path=os.path.join(OUT, "02_generate_idle.png"), full_page=False)

        # ---------- Screenshot 3: More sheet open ----------
        print("4. Capturing: P0#1 more sheet open...")
        page.goto("http://localhost:5173/", wait_until="domcontentloaded", timeout=15000)
        wait_for_render(page, "nav")
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(600)
        # Click the "更多"/"More" button - works via i18n key nav.more
        more_btn = page.get_by_role("button").filter(has_text=re.compile(r"^(?:更多|More)$"))
        more_btn.wait_for(timeout=5000)
        more_btn.click()
        page.wait_for_timeout(700)
        page.screenshot(path=os.path.join(OUT, "03_more_sheet.png"), full_page=False)

        # ---------- Screenshot 4: Generate running (mobile) ----------
        print("5. Capturing: P0#2 + P0#3 generate running (mobile)...")
        page.goto("http://localhost:5173/generate", wait_until="domcontentloaded")
        wait_for_render(page, "button")
        page.wait_for_timeout(1000)

        # Click start → confirm → wait for mock SSE → capture running layout
        start_btns = page.locator("button").filter(has_text="开始生成")
        if start_btns.count() > 0:
            start_btns.first.click()
            page.wait_for_timeout(800)
            # Click confirm button
            confirm_btns = page.locator("button").filter(has_text="确认生成")
            if confirm_btns.count() > 0:
                confirm_btns.first.click()
            page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(OUT, "04_generate_running_mobile.png"), full_page=False)

        # Also get a full-page version showing scroll content
        page.screenshot(path=os.path.join(OUT, "05_generate_running_mobile_full.png"), full_page=True)

        # ---------- Screenshot 5: Steps scrolling verification ----------
        print("6. Capturing: P0#3 step row detail...")
        # The steps are already visible in screenshot 04/05

        # ---------- Screenshot 6: Desktop verification (no changes) ----------
        print("7. Capturing: desktop viewport (should be unchanged)...")
        page.set_viewport_size({"width": 1440, "height": 900})
        page.goto("http://localhost:5173/generate", wait_until="domcontentloaded")
        wait_for_render(page, "aside")
        page.screenshot(path=os.path.join(OUT, "06_desktop_generate.png"), full_page=False)

        browser.close()

    print(f"\nAll done! Screenshots in: {os.path.abspath(OUT)}")


if __name__ == "__main__":
    main()
