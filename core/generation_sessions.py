from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
import logging
from typing import Any


LOG = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class GenerationSession:
    session_id: str
    user_id: int
    params: dict[str, Any]
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    status: str = "running"
    current_step: str = "idle"
    current_task: str = ""
    progress: dict[str, int] = field(default_factory=lambda: {"done": 0, "total": 0})
    outputs: list[dict[str, Any]] = field(default_factory=list)
    download: str = ""
    report_download: str = ""
    artifact_id: str = ""
    report_artifact_id: str = ""
    report_summary: str = ""
    post_fill_checks: dict[str, Any] | None = None
    visual_score: int | float | None = None
    billing: dict[str, Any] | None = None
    billing_summary: dict[str, Any] | None = None
    last_error: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    next_seq: int = 0
    terminate_requested: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _condition: threading.Condition = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._condition = threading.Condition(self._lock)

    def _ensure_output(self, index: int, chapter: str | None = None) -> dict[str, Any]:
        while len(self.outputs) <= index:
            self.outputs.append(
                {
                    "chapter": chapter or f"任务 {len(self.outputs) + 1}",
                    "text": "",
                    "evidenceRefs": [],
                    "auditIssues": [],
                }
            )
        if chapter:
            self.outputs[index]["chapter"] = chapter
        return self.outputs[index]

    def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._condition:
            self.next_seq += 1
            payload = {**event, "seq": self.next_seq}
            self.events.append(payload)
            self.updated_at = _now_iso()
            self._apply_event(payload)
            self._condition.notify_all()
            return payload

    def _apply_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type == "task":
            self.status = "running"
            self.current_step = "generation"
            self.current_task = str(event.get("chapter") or "")
            self.progress["total"] = int(event.get("total") or 0)
            block = self._ensure_output(int(event.get("index") or 0), self.current_task)
            block.update(
                {
                    "chapter": self.current_task,
                    "text": "",
                    "model": None,
                    "tier": None,
                    "kbHits": None,
                    "evidenceRefs": [],
                    "auditVerdict": None,
                    "auditIssues": [],
                    "revised": False,
                }
            )
            return
        if event_type == "route":
            self.current_step = "retrieval"
            block = self._ensure_output(int(event.get("index") or 0))
            block.update(
                {
                    "model": event.get("model"),
                    "tier": event.get("tier"),
                    "role": event.get("role"),
                    "kbHits": event.get("kb_hits"),
                    "evidenceRefs": event.get("evidence_refs") or [],
                }
            )
            return
        if event_type == "chunk":
            block = self._ensure_output(int(event.get("index") or 0))
            block["text"] = f"{block.get('text', '')}{event.get('text') or ''}"
            return
        if event_type == "audit":
            if event.get("is_model_audit") is not False:
                self.current_step = "audit"
            block = self._ensure_output(int(event.get("index") or 0))
            block.update(
                {
                    "auditVerdict": event.get("verdict"),
                    "auditIssues": event.get("issues") or [],
                    "revised": bool(event.get("revised")),
                }
            )
            return
        if event_type == "billing":
            billing = event.get("billing") or {}
            if not self.billing:
                self.billing = {"records": [], "input_tokens": 0, "output_tokens": 0, "cost_cny": 0}
            self.billing["records"].append(billing)
            self.billing["input_tokens"] += int(billing.get("input_tokens") or 0)
            self.billing["output_tokens"] += int(billing.get("output_tokens") or 0)
            self.billing["cost_cny"] = round(float(self.billing["cost_cny"]) + float(billing.get("cost_cny") or 0), 8)
            return
        if event_type == "progress":
            self.progress = {"done": int(event.get("index") or 0) + 1, "total": int(event.get("total") or 0)}
            return
        if event_type == "done":
            self.status = "done"
            self.current_step = "done"
            self.download = str(event.get("download") or "")
            self.report_download = str(event.get("report_download") or "")
            self.artifact_id = str(event.get("artifact_id") or "")
            self.report_artifact_id = str(event.get("report_artifact_id") or "")
            self.report_summary = str(event.get("report_summary") or "")
            self.post_fill_checks = event.get("post_fill_checks")
            self.visual_score = event.get("visual_score")
            self.billing = event.get("billing") or self.billing
            self.billing_summary = event.get("billing_summary")
            return
        if event_type == "terminated":
            self.status = "terminated"
            self.current_step = "terminated"
            self.current_task = str(event.get("message") or "已终止")
            self.last_error = {
                "code": "terminated",
                "message": str(event.get("message") or "生成任务已终止"),
                "retryable": False,
            }
            return
        if event_type == "quota_alert":
            message = str(event.get("message") or event.get("detail") or "Quota exceeded")
            self.last_error = {
                "code": "quota_exceeded",
                "message": message,
                "retryable": False,
                "detail": message,
            }
            self.status = "error"
            self.current_step = "error"
            return
        if event_type == "error":
            self.last_error = event.get("error") if isinstance(event.get("error"), dict) else {"code": "unknown_error", "message": str(event.get("error") or ""), "retryable": True}
            if event.get("terminal"):
                self.status = "error"
                self.current_step = "error"

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "status": self.status,
                "currentStep": self.current_step,
                "currentTask": self.current_task,
                "progress": dict(self.progress),
                "outputs": [dict(item) for item in self.outputs],
                "download": self.download,
                "report_download": self.report_download,
                "artifact_id": self.artifact_id,
                "report_artifact_id": self.report_artifact_id,
                "report_summary": self.report_summary,
                "post_fill_checks": self.post_fill_checks,
                "visual_score": self.visual_score,
                "billing": self.billing,
                "billing_summary": self.billing_summary,
                "last_error": self.last_error,
                "params": dict(self.params),
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "last_seq": self.next_seq,
                "terminate_requested": self.terminate_requested,
            }

    def request_terminate(self) -> None:
        with self._condition:
            self.terminate_requested = True
            self.updated_at = _now_iso()
            self._condition.notify_all()

    def stream_events(self, after_seq: int = 0, heartbeat_seconds: float = 5.0):
        cursor = max(0, int(after_seq or 0))
        while True:
            heartbeat = False
            terminal = False
            batch: list[dict[str, Any]] = []
            with self._condition:
                if self.next_seq <= cursor and self.status not in {"done", "error", "terminated"}:
                    notified = self._condition.wait(timeout=heartbeat_seconds)
                    if not notified and self.next_seq <= cursor and self.status not in {"done", "error", "terminated"}:
                        heartbeat = True
                if self.next_seq > cursor:
                    batch = [dict(item) for item in self.events if int(item.get("seq") or 0) > cursor]
                elif self.status in {"done", "error", "terminated"}:
                    terminal = True
            if batch:
                for event in batch:
                    cursor = int(event.get("seq") or cursor)
                    yield event
                continue
            if heartbeat:
                yield {"type": "heartbeat", "seq": cursor}
                continue
            if terminal:
                break


class ActiveGenerationExistsError(RuntimeError):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.session_id = session_id


class GenerationSessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, GenerationSession] = {}
        self._active_by_user: dict[int, str] = {}
        self._latest_by_user: dict[int, str] = {}

    def create_session(self, user_id: int, params: dict[str, Any]) -> GenerationSession:
        with self._lock:
            active_id = self._active_by_user.get(user_id)
            if active_id:
                active = self._sessions.get(active_id)
                if active and active.status == "running":
                    raise ActiveGenerationExistsError(active.session_id)
            session_id = f"gen_{uuid.uuid4().hex}"
            session = GenerationSession(session_id=session_id, user_id=user_id, params=params)
            self._sessions[session_id] = session
            self._active_by_user[user_id] = session_id
            self._latest_by_user[user_id] = session_id
            _persist_session_created(session)
            return session

    def get_session_for_user(self, user_id: int, session_id: str) -> GenerationSession | None:
        session = self._sessions.get(session_id)
        if session is None:
            session = _load_persisted_session(user_id, session_id)
            if session is not None:
                with self._lock:
                    self._sessions[session_id] = session
                    self._latest_by_user[user_id] = session_id
                    if session.status == "running":
                        self._active_by_user[user_id] = session_id
        if session is None or session.user_id != user_id:
            return None
        return session

    def get_active_session(self, user_id: int) -> GenerationSession | None:
        active_id = self._active_by_user.get(user_id)
        if not active_id:
            return None
        session = self._sessions.get(active_id)
        if session is None or session.status != "running":
            return None
        return session

    def get_latest_session(self, user_id: int) -> GenerationSession | None:
        latest_id = self._latest_by_user.get(user_id)
        if not latest_id:
            latest_id = _latest_persisted_session_key(user_id)
        if not latest_id:
            return None
        return self.get_session_for_user(user_id, latest_id)

    def append_event(self, session_id: str, event: dict[str, Any]) -> dict[str, Any]:
        session = self._sessions[session_id]
        payload = session.append_event(event)
        _persist_session_snapshot(session)
        if session.status in {"done", "error", "terminated"}:
            with self._lock:
                if self._active_by_user.get(session.user_id) == session_id:
                    self._active_by_user.pop(session.user_id, None)
        return payload

    def is_terminate_requested(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        return bool(session and session.terminate_requested)

    def terminate_session_for_user(self, user_id: int, session_id: str) -> GenerationSession | None:
        session = self.get_session_for_user(user_id, session_id)
        if session is None:
            return None
        session.request_terminate()
        if session.status == "running":
            self.append_event(
                session_id,
                {
                    "type": "terminated",
                    "message": "生成任务已终止",
                },
            )
        return session


session_manager = GenerationSessionManager()


def _persist_session_created(session: GenerationSession) -> None:
    try:
        from core.history import persist_session_created

        persist_session_created(session)
    except Exception:
        LOG.exception("Failed to persist generation session creation")


def _persist_session_snapshot(session: GenerationSession) -> None:
    try:
        from core.history import persist_session_snapshot

        persist_session_snapshot(session)
    except Exception:
        LOG.exception("Failed to persist generation session snapshot")


def _load_persisted_session(user_id: int, session_id: str) -> GenerationSession | None:
    try:
        from core.history import load_session_snapshot

        snapshot = load_session_snapshot(user_id, session_id)
    except Exception:
        LOG.exception("Failed to load persisted generation session")
        return None
    if not snapshot:
        return None
    status = str(snapshot.get("status") or "running")
    last_error = snapshot.get("last_error")
    current_step = str(snapshot.get("currentStep") or "idle")
    current_task = str(snapshot.get("currentTask") or "")
    if status == "running":
        status = "terminated"
        current_step = "terminated"
        current_task = "生成任务在服务器重启后已终止"
        last_error = {
            "code": "terminated",
            "message": "生成任务在服务器重启后已终止",
            "retryable": False,
        }

    session = GenerationSession(
        session_id=str(snapshot.get("session_id") or session_id),
        user_id=int(snapshot.get("user_id") or user_id),
        params=dict(snapshot.get("params") or {}),
        created_at=str(snapshot.get("created_at") or _now_iso()),
        updated_at=str(snapshot.get("updated_at") or _now_iso()),
        status=status,
        current_step=current_step,
        current_task=current_task,
        progress=dict(snapshot.get("progress") or {"done": 0, "total": 0}),
        outputs=list(snapshot.get("outputs") or []),
        download=str(snapshot.get("download") or ""),
        report_download=str(snapshot.get("report_download") or ""),
        artifact_id=str(snapshot.get("artifact_id") or ""),
        report_artifact_id=str(snapshot.get("report_artifact_id") or ""),
        report_summary=str(snapshot.get("report_summary") or ""),
        post_fill_checks=snapshot.get("post_fill_checks"),
        visual_score=snapshot.get("visual_score"),
        billing=snapshot.get("billing"),
        billing_summary=snapshot.get("billing_summary"),
        last_error=last_error,
    )
    session.next_seq = int(snapshot.get("last_seq") or 0)
    return session


def _latest_persisted_session_key(user_id: int) -> str | None:
    try:
        from core.history import latest_session_key

        return latest_session_key(user_id)
    except Exception:
        LOG.exception("Failed to load latest persisted generation session")
        return None
