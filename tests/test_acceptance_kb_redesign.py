"""End-to-end acceptance tests for kb-formats-and-generate-redesign.

Covers the manual-acceptance tasks:
  10.3 — KB upload with .txt / .html / .xlsx happy paths + .zip rejection
  10.4 — Generate session honors the three new control switches
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

import config
import server
from core.auth import create_access_token, get_or_create_user
from core.kb_registry import remove_kb


@pytest.fixture
def acceptance_user():
    user = get_or_create_user("acceptance_redesign@example.com")
    return user, create_access_token(user)


@pytest.fixture
def acceptance_client():
    with TestClient(server.app) as client:
        yield client


@pytest.fixture
def acceptance_kb(tmp_path, monkeypatch, acceptance_user):
    """Isolated HISTORICAL_DIR so each upload test has its own disk state."""
    monkeypatch.setattr(config, "HISTORICAL_DIR", str(tmp_path))
    # ensure the dir exists
    os.makedirs(tmp_path, exist_ok=True)
    yield tmp_path


def _upload(client: TestClient, token: str, slug: str, filename: str, payload: bytes, content_type: str = "application/octet-stream"):
    return client.post(
        "/api/kb/upload",
        headers={"Authorization": f"Bearer {token}"},
        data={"slug": slug},
        files=[("files", (filename, payload, content_type))],
    )


def test_10_3_happy_txt_ingestion(acceptance_client, acceptance_user, acceptance_kb):
    user, token = acceptance_user
    resp = _upload(acceptance_client, token, "kb1", "sample.txt", b"# Title\n\nHello world content.", "text/plain")
    assert resp.status_code == 200
    body = resp.json()
    result = body["results"][0]
    assert result["ok"] is True
    assert result["chunks"] >= 1
    # file must actually live on disk
    assert (acceptance_kb / "sample.txt").exists()


def test_10_3_happy_html_ingestion(acceptance_client, acceptance_user, acceptance_kb):
    user, token = acceptance_user
    resp = _upload(
        acceptance_client,
        token,
        "kb1",
        "sample.html",
        b"<html><body><h1>Page</h1><p>Some text body</p></body></html>",
        "text/html",
    )
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["ok"] is True
    assert result["chunks"] >= 1


def test_10_3_happy_xlsx_ingestion(acceptance_client, acceptance_user, acceptance_kb):
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Metric", "Value"])
    ws.append(["Revenue", "2000"])
    ws.append(["Cost", "600"])
    path = acceptance_kb / "sample.xlsx"
    wb.save(path)
    payload = path.read_bytes()
    user, token = acceptance_user
    resp = _upload(
        acceptance_client,
        token,
        "kb1",
        "sample.xlsx",
        payload,
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert result["ok"] is True
    assert result["chunks"] >= 1


def test_10_3_rejected_zip_no_persist(acceptance_client, acceptance_user, acceptance_kb):
    user, token = acceptance_user
    resp = _upload(acceptance_client, token, "kb1", "evil.zip", b"\x50\x4b\x03\x04fakezip", "application/zip")
    assert resp.status_code == 200
    body = resp.json()
    result = body["results"][0]
    assert result["ok"] is False
    assert result.get("unsupported_format") is True
    assert "不支持" in result["error"]
    # Must NOT have been written to disk
    assert not (acceptance_kb / "evil.zip").exists()
    # Source list must not include the zip
    sources = acceptance_client.get(
        "/api/kb/sources?slug=kb1",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert "evil.zip" not in (sources.get("sources") or [])


def test_10_4_generate_session_sends_switch_state(acceptance_client, acceptance_user, acceptance_kb, monkeypatch):
    """Verify that /api/generate/sessions forwards enable_web / enable_audit / enable_visual_audit exactly as supplied."""
    user, token = acceptance_user

    # Stub the session runner so we don't actually call any LLM.
    from core.generation_sessions import session_manager

    session_manager._sessions.clear()
    session_manager._active_by_user.clear()
    session_manager._latest_by_user.clear()

    captured_params: dict = {}

    def fake_run(session_id, current_user, params, resolved):
        captured_params.update(params)
        session_manager.append_event(session_id, {
            "type": "done",
            "download": "/api/download/test.docx",
            "billing": {"records": [], "input_tokens": 0, "output_tokens": 0, "cost_cny": 0},
            "billing_summary": {"input_tokens": 0, "output_tokens": 0, "cost_cny": 0, "generation_count": 0},
        })

    monkeypatch.setattr(server, "_resolve_generation_request", lambda *a, **kw: {"resolved": True})
    monkeypatch.setattr(server, "_run_generation_session", fake_run)

    class ImmediateThread:
        def __init__(self, target=None, args=(), daemon=None):
            self._t = target
            self._a = args

        def start(self):
            if self._t:
                self._t(*self._a)

    monkeypatch.setattr(server.threading, "Thread", ImmediateThread)

    # Need at least one template on disk for the form to pass the route-level checks.
    monkeypatch.setattr(config, "TEMPLATE_DIR", str(acceptance_kb))
    tpl_path = acceptance_kb / "demo.docx"
    # Minimal valid-ish docx is nontrivial to produce here; skip the full parse path
    # by stubbing the analysis step. We just need the route to succeed.
    from core.fill_task import FillTask
    import uuid

    fake_tasks = [
        FillTask(
            task_id=str(uuid.uuid4()),
            target_chapter="摘要",
            task_type="paragraph",
            description="Write summary",
            location_hint={},
            word_limit=100,
        )
    ]
    monkeypatch.setattr(server, "_cached_analyze", lambda p: fake_tasks)
    tpl_path.write_bytes(b"\x00")  # placeholder; analysis is stubbed

    # --- Case 1: all three switches ON
    resp_on = acceptance_client.post(
        "/api/generate/sessions",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "slug": "kb1",
            "template": "demo.docx",
            "word_limit": "300",
            "top_k": "4",
            "max_distance": "1.25",
            "enable_web": "true",
            "use_stream": "true",
            "enable_audit": "true",
            "enable_visual_audit": "true",
            "custom_instructions": "",
        },
    )
    assert resp_on.status_code == 200
    assert resp_on.json()["ok"] is True
    assert captured_params.get("enable_web") is True
    assert captured_params.get("enable_audit") is True
    assert captured_params.get("enable_visual_audit") is True
    assert captured_params.get("use_stream") is True

    # Reset for case 2: all three switches OFF (web/audit/visual off)
    captured_params.clear()
    session_manager._sessions.clear()
    session_manager._active_by_user.clear()
    session_manager._latest_by_user.clear()

    resp_off = acceptance_client.post(
        "/api/generate/sessions",
        headers={"Authorization": f"Bearer {token}"},
        data={
            "slug": "kb1",
            "template": "demo.docx",
            "word_limit": "300",
            "top_k": "4",
            "max_distance": "1.25",
            "enable_web": "false",
            "use_stream": "true",
            "enable_audit": "false",
            "enable_visual_audit": "false",
            "custom_instructions": "",
        },
    )
    assert resp_off.status_code == 200
    assert resp_off.json()["ok"] is True
    assert captured_params.get("enable_web") is False
    assert captured_params.get("enable_audit") is False
    assert captured_params.get("enable_visual_audit") is False
    assert captured_params.get("use_stream") is True
