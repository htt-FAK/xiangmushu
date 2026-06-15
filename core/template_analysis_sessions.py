from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

LOG = logging.getLogger(__name__)


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class TemplateAnalysisSession:
    session_id: str
    user_id: int
    params: dict[str, Any]
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    status: str = "running"
    current_phase: str = "idle"
    status_message: str = ""
    template: str = ""
    mode: str = ""
    vision_status: str = ""
    tasks: list[dict[str, Any]] = field(default_factory=list)
    billing: dict[str, Any] | None = None
    logs: list[dict[str, Any]] = field(default_factory=list)
    last_error: dict[str, Any] | None = None
    events: list[dict[str, Any]] = field(default_factory=list)
    next_seq: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _condition: threading.Condition = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._condition = threading.Condition(self._lock)
        if not self.template:
            self.template = str(self.params.get("template") or "")

    def append_event(self, event: dict[str, Any]) -> dict[str, Any]:
        with self._condition:
            self.next_seq += 1
            payload = {**event, "seq": self.next_seq}
            self.events.append(payload)
            self.updated_at = _now_iso()
            self._apply_event(payload)
            self._condition.notify_all()
            return payload

    def _append_log(self, phase: str, message: str) -> None:
        self.logs.append(
            {
                "phase": phase,
                "message": message,
                "created_at": self.updated_at,
            }
        )

    def _apply_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("type") or "")
        if event_type == "status":
            self.status = "running"
            self.current_phase = str(event.get("phase") or self.current_phase or "running")
            self.status_message = str(event.get("message") or "")
            self._append_log(self.current_phase, self.status_message)
            return
        if event_type == "billing":
            billing = dict(event.get("billing") or {})
            if not self.billing:
                self.billing = {"records": [], "input_tokens": 0, "output_tokens": 0, "cost_cny": 0.0}
            self.billing["records"].append(billing)
            self.billing["input_tokens"] += int(billing.get("input_tokens") or 0)
            self.billing["output_tokens"] += int(billing.get("output_tokens") or 0)
            self.billing["cost_cny"] = round(float(self.billing["cost_cny"]) + float(billing.get("cost_cny") or 0), 8)
            return
        if event_type == "done":
            self.status = "done"
            self.current_phase = "done"
            self.status_message = str(event.get("message") or "Analysis complete")
            self.template = str(event.get("template") or self.template)
            self.mode = str(event.get("mode") or "")
            self.vision_status = str(event.get("vision_status") or "")
            self.tasks = list(event.get("tasks") or [])
            self.billing = event.get("billing") or self.billing
            self._append_log("done", self.status_message)
            return
        if event_type == "error":
            error = event.get("error")
            if isinstance(error, dict):
                self.last_error = error
                message = str(error.get("message") or "Template analysis failed")
            else:
                message = str(error or "Template analysis failed")
                self.last_error = {"code": "template_analysis_error", "message": message, "retryable": True}
            self.status = "error"
            self.current_phase = "error"
            self.status_message = message
            self._append_log("error", message)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "session_id": self.session_id,
                "user_id": self.user_id,
                "status": self.status,
                "currentPhase": self.current_phase,
                "statusMessage": self.status_message,
                "template": self.template,
                "vision_model": str(self.params.get("vision_model") or ""),
                "planner_model": str(self.params.get("planner_model") or ""),
                "mode": self.mode,
                "vision_status": self.vision_status,
                "tasks": list(self.tasks),
                "billing": self.billing,
                "logs": [dict(item) for item in self.logs],
                "last_error": self.last_error,
                "params": dict(self.params),
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "last_seq": self.next_seq,
            }

    def stream_events(self, after_seq: int = 0, heartbeat_seconds: float = 5.0):
        cursor = max(0, int(after_seq or 0))
        while True:
            heartbeat = False
            terminal = False
            batch: list[dict[str, Any]] = []
            with self._condition:
                if self.next_seq <= cursor and self.status not in {"done", "error"}:
                    notified = self._condition.wait(timeout=heartbeat_seconds)
                    if not notified and self.next_seq <= cursor and self.status not in {"done", "error"}:
                        heartbeat = True
                if self.next_seq > cursor:
                    batch = [dict(item) for item in self.events if int(item.get("seq") or 0) > cursor]
                elif self.status in {"done", "error"}:
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


class ActiveTemplateAnalysisExistsError(RuntimeError):
    def __init__(self, session_id: str):
        super().__init__(session_id)
        self.session_id = session_id


class TemplateAnalysisSessionManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, TemplateAnalysisSession] = {}
        self._active_by_user: dict[int, str] = {}
        self._latest_by_user: dict[int, str] = {}

    def create_session(self, user_id: int, params: dict[str, Any]) -> TemplateAnalysisSession:
        with self._lock:
            active_id = self._active_by_user.get(user_id)
            if active_id:
                active = self._sessions.get(active_id)
                if active and active.status == "running":
                    raise ActiveTemplateAnalysisExistsError(active.session_id)
            session_id = f"tmpl_{uuid.uuid4().hex}"
            session = TemplateAnalysisSession(session_id=session_id, user_id=user_id, params=params)
            self._sessions[session_id] = session
            self._active_by_user[user_id] = session_id
            self._latest_by_user[user_id] = session_id
            _persist_session_created(session)
            return session

    def get_session_for_user(self, user_id: int, session_id: str) -> TemplateAnalysisSession | None:
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

    def get_active_session(self, user_id: int) -> TemplateAnalysisSession | None:
        active_id = self._active_by_user.get(user_id)
        if not active_id:
            return None
        session = self._sessions.get(active_id)
        if session is None or session.status != "running":
            return None
        return session

    def get_latest_session(self, user_id: int) -> TemplateAnalysisSession | None:
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
        if session.status in {"done", "error"}:
            with self._lock:
                if self._active_by_user.get(session.user_id) == session_id:
                    self._active_by_user.pop(session.user_id, None)
        return payload


template_analysis_session_manager = TemplateAnalysisSessionManager()


def _persist_session_created(session: TemplateAnalysisSession) -> None:
    try:
        from core.template_analysis_store import persist_session_created

        persist_session_created(session)
    except Exception:
        LOG.exception("Failed to persist template-analysis session creation")


def _persist_session_snapshot(session: TemplateAnalysisSession) -> None:
    try:
        from core.template_analysis_store import persist_session_snapshot

        persist_session_snapshot(session)
    except Exception:
        LOG.exception("Failed to persist template-analysis session snapshot")


def _load_persisted_session(user_id: int, session_id: str) -> TemplateAnalysisSession | None:
    try:
        from core.template_analysis_store import load_session_snapshot

        snapshot = load_session_snapshot(user_id, session_id)
    except Exception:
        LOG.exception("Failed to load persisted template-analysis session")
        return None
    if not snapshot:
        return None
    session = TemplateAnalysisSession(
        session_id=str(snapshot.get("session_id") or session_id),
        user_id=int(snapshot.get("user_id") or user_id),
        params=dict(snapshot.get("params") or {}),
        created_at=str(snapshot.get("created_at") or _now_iso()),
        updated_at=str(snapshot.get("updated_at") or _now_iso()),
        status=str(snapshot.get("status") or "running"),
        current_phase=str(snapshot.get("currentPhase") or "idle"),
        status_message=str(snapshot.get("statusMessage") or ""),
        template=str(snapshot.get("template") or ""),
        mode=str(snapshot.get("mode") or ""),
        vision_status=str(snapshot.get("vision_status") or ""),
        tasks=list(snapshot.get("tasks") or []),
        billing=snapshot.get("billing"),
        logs=list(snapshot.get("logs") or []),
        last_error=snapshot.get("last_error"),
    )
    session.next_seq = int(snapshot.get("last_seq") or 0)
    return session


def _latest_persisted_session_key(user_id: int) -> str | None:
    try:
        from core.template_analysis_store import latest_session_key

        return latest_session_key(user_id)
    except Exception:
        LOG.exception("Failed to load latest persisted template-analysis session")
        return None
