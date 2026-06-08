"""
FastAPI 后端 — 为 HTML 前端提供 REST + SSE 接口
运行: python server.py  →  http://localhost:8502
"""
from __future__ import annotations

import concurrent.futures
import json
import logging
import mimetypes
import os
import threading
import time
from dataclasses import asdict

from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from core.auth import (
    AuthError,
    InvalidCodeError,
    InvalidEmailError,
    InvalidLanguageError,
    InvalidPasswordError,
    InvalidTokenError,
    User,
    consume_verification_code,
    create_access_token,
    create_verification_code,
    get_user_preferences,
    get_or_create_user,
    init_db,
    reset_password_with_code,
    send_verification_email,
    update_user_preferences,
    user_from_token,
    verify_password,
)
from core.billing import (
    billing_summary,
    delete_user_api_key,
    get_user_api_key_status,
    load_user_api_key,
    normalize_usage,
    record_billing,
    save_user_api_key,
)
from core.audit_log import (
    ADMIN_ACCESS,
    API_KEY_DELETED,
    API_KEY_SAVED,
    CODE_REQUESTED,
    FILE_UPLOADED,
    LOGIN_FAILED,
    LOGIN_SUCCESS,
    PASSWORD_RESET_FAILED,
    PASSWORD_RESET_SUCCESS,
    REGISTER_SUCCESS,
    log_audit,
)


def _get_password_hash(email: str) -> str:
    """Look up password hash from DB for login verification."""
    import sqlite3
    db_path = config.AUTH_DB_PATH
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE email = ?",
            (email.lower().strip(),),
        ).fetchone()
    if not row or not row[0]:
        return ""
    return row[0]
from core.chunker import Chunker
from core.content_auditor import (
    ContentAuditor,
    need_model_audit,
    rule_audit,
    should_apply_revision,
)
from core.filler import WordFiller
from core.generator import ContentGenerator
from core.kb_extract import path_to_parsed_document
from core.kb_registry import add_kb, load_registry, remove_kb
from core.post_fill_verifier import verify_filled_document
from core.reporting import (
    build_generation_trace,
    build_quality_report,
    quality_report_summary,
    save_quality_report,
)
from core.template_analyzer import TemplateAnalyzer
from core.vector_store import VectorStore
from core.visual_auditor import audit_document_visual


class SimpleRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, list[float]] = {}

    def allow(self, key: str, limits: list[tuple[int, int]]) -> bool:
        now = time.monotonic()
        max_window = max(window for _, window in limits)
        events = [stamp for stamp in self._events.get(key, []) if stamp > now - max_window]

        for limit, window in limits:
            if sum(1 for stamp in events if stamp > now - window) >= limit:
                self._events[key] = events
                return False

        events.append(now)
        self._events[key] = events
        return True


rate_limiter = SimpleRateLimiter()
RATE_LIMIT_MESSAGE = "操作过于频繁，请稍后再试"


def validate_password(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "密码至少需要8位，并且必须包含字母和数字"
    if not any(char.isalpha() for char in password):
        return False, "密码必须包含字母和数字"
    if not any(char.isdigit() for char in password):
        return False, "密码必须包含字母和数字"
    return True, ""


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _user_agent(request: Request) -> str:
    return request.headers.get("user-agent", "")


def _upload_size_limit_bytes() -> int:
    return config.UPLOAD_MAX_SIZE_MB * 1024 * 1024


def _raise_if_upload_too_large(content: bytes) -> None:
    if len(content) > _upload_size_limit_bytes():
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"文件大小超过限制（最大 {config.UPLOAD_MAX_SIZE_MB}MB）",
        )


app = FastAPI(title="智能计划书生成器")
logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


class EmailRequest(BaseModel):
    email: str
    password: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str
    password: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class ApiKeyRequest(BaseModel):
    api_key: str


class UserPreferencesRequest(BaseModel):
    language: str


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        return user_from_token(credentials.credentials)
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


ADMIN_EMAILS = {"3406847927@qq.com"}


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.email not in ADMIN_EMAILS:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app.router.lifespan_context = lifespan

# ---------------------------------------------------------------------------
# 缓存实例（模拟 st.cache_resource）
# ---------------------------------------------------------------------------
_vs_cache: dict[str, VectorStore] = {}
_chunker = Chunker()
_analyzer = TemplateAnalyzer()
_filler = WordFiller()

# Template analysis cache: key=(template_path, mtime), value=tasks list
_template_analysis_cache: dict[tuple[str, float], list] = {}
_TEMPLATE_CACHE_MAX = 16


def _cached_analyze(template_path: str) -> list:
    """Analyze template with LRU-style cache keyed by path + mtime."""
    mtime = os.path.getmtime(template_path)
    key = (template_path, mtime)
    if key in _template_analysis_cache:
        return _template_analysis_cache[key]
    tasks = _analyzer.analyze(template_path)
    # Evict oldest entries if over limit
    while len(_template_analysis_cache) >= _TEMPLATE_CACHE_MAX:
        oldest = next(iter(_template_analysis_cache))
        del _template_analysis_cache[oldest]
    _template_analysis_cache[key] = tasks
    return tasks


def _get_vs(slug: str) -> VectorStore:
    if slug not in _vs_cache:
        _vs_cache[slug] = VectorStore(kb_slug=slug)
    return _vs_cache[slug]


# ---------------------------------------------------------------------------
# 静态文件 & 首页
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")
FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")


def _spa_index_path() -> str:
    frontend_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.isfile(frontend_index):
        return frontend_index
    # Fallback: serve a minimal safe page instead of the legacy static/index.html
    # which contains unescaped innerHTML and XSS risks.
    raise FileNotFoundError(
        "Frontend not built. Run 'cd frontend && npm run build' first."
    )


if os.path.isdir(FRONTEND_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="frontend-assets")


@app.get("/api/health")
async def health_check():
    return {"ok": True, "service": "xiangmushu", "status": "healthy"}


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(_spa_index_path(), media_type="text/html")


# ---------------------------------------------------------------------------
# 知识库 API
# ---------------------------------------------------------------------------
@app.post("/api/auth/request-code")
async def auth_request_code(payload: EmailRequest, request: Request):
    email_key = payload.email.lower().strip()
    if not rate_limiter.allow(f"request-code:{email_key}", [(1, 60), (5, 3600)]):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_MESSAGE)
    try:
        verification = create_verification_code(payload.email, password=payload.password)
        purpose = "reset_password" if payload.password is None else "register"
        send_verification_email(verification.email, verification.code, purpose=purpose)
        log_audit(
            CODE_REQUESTED,
            email=verification.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"purpose": purpose},
        )
        return {"ok": True, "email": verification.email, "expires_at": verification.expires_at}
    except (InvalidEmailError, InvalidPasswordError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AuthError as exc:
        logger.exception("Failed to request verification code")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@app.post("/api/auth/verify-code")
async def auth_verify_code(payload: VerifyCodeRequest, request: Request):
    password_ok, password_message = validate_password(payload.password)
    if not password_ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=password_message)
    try:
        user = consume_verification_code(payload.email, payload.code, payload.password)
        token = create_access_token(user)
        log_audit(
            REGISTER_SUCCESS,
            user_id=user.id,
            email=user.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "email": user.email},
        }
    except (InvalidEmailError, InvalidCodeError, InvalidPasswordError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        ) from exc


@app.post("/api/auth/reset-password")
async def auth_reset_password(payload: ResetPasswordRequest, request: Request):
    password_ok, password_message = validate_password(payload.new_password)
    if not password_ok:
        log_audit(
            PASSWORD_RESET_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "invalid_password"},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=password_message)
    try:
        user = reset_password_with_code(payload.email, payload.code, payload.new_password)
        token = create_access_token(user)
        log_audit(
            PASSWORD_RESET_SUCCESS,
            user_id=user.id,
            email=user.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "email": user.email},
        }
    except (InvalidEmailError, InvalidCodeError) as exc:
        log_audit(
            PASSWORD_RESET_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "invalid_code"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        ) from exc
    except AuthError as exc:
        log_audit(
            PASSWORD_RESET_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "auth_error"},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid verification code",
        ) from exc


@app.post("/api/auth/login")
async def auth_login(payload: LoginRequest, request: Request):
    """Login with email + password only (no verification code needed)."""
    if not rate_limiter.allow(f"login:{_client_ip(request)}", [(10, 60)]):
        log_audit(
            LOGIN_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "rate_limited"},
        )
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_MESSAGE)
    try:
        user = get_or_create_user(payload.email)
        if not verify_password(payload.password, _get_password_hash(user.email)):
            raise InvalidPasswordError("Email or password is incorrect")
        token = create_access_token(user)
        log_audit(
            LOGIN_SUCCESS,
            user_id=user.id,
            email=user.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
        )
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "email": user.email},
        }
    except InvalidPasswordError as exc:
        log_audit(
            LOGIN_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "invalid_credentials"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AuthError as exc:
        log_audit(
            LOGIN_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "auth_error"},
        )
        logger.exception("Login failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@app.get("/api/auth/me")
async def auth_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}


@app.get("/api/user/preferences")
async def user_preferences(current_user: User = Depends(get_current_user)):
    return get_user_preferences(current_user.id)


@app.put("/api/user/preferences")
async def user_preferences_update(
    payload: UserPreferencesRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return update_user_preferences(current_user.id, payload.language)
    except InvalidLanguageError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@app.get("/api/user/apikey")
async def user_apikey_status(current_user: User = Depends(get_current_user)):
    return get_user_api_key_status(current_user.id)


@app.post("/api/user/apikey")
async def user_apikey_save(
    payload: ApiKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    try:
        save_user_api_key(current_user.id, payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    log_audit(
        API_KEY_SAVED,
        user_id=current_user.id,
        email=current_user.email,
        ip=_client_ip(request),
        ua=_user_agent(request),
    )
    return {"ok": True, **get_user_api_key_status(current_user.id)}


@app.delete("/api/user/apikey")
async def user_apikey_delete(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    delete_user_api_key(current_user.id)
    log_audit(
        API_KEY_DELETED,
        user_id=current_user.id,
        email=current_user.email,
        ip=_client_ip(request),
        ua=_user_agent(request),
    )
    return {"ok": True, **get_user_api_key_status(current_user.id)}


@app.get("/api/billing/summary")
async def api_billing_summary(current_user: User = Depends(get_current_user)):
    return billing_summary(current_user.id)


@app.get("/api/kb/list")
async def kb_list(current_user: User = Depends(get_current_user)):
    return load_registry()


@app.post("/api/kb/create")
async def kb_create(
    label: str = Form(...),
    slug: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    try:
        created = add_kb(label.strip(), slug.strip() or None)
        return {"ok": True, "slug": created}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/kb/delete")
async def kb_delete(
    slug: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    try:
        remove_kb(slug)
        vs = VectorStore(kb_slug=slug)
        vs.delete_entire_collection()
        _vs_cache.pop(slug, None)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/kb/sources")
async def kb_sources(
    slug: str = "kb1",
    current_user: User = Depends(get_current_user),
):
    vs = _get_vs(slug)
    sources = vs.list_sources()
    count = vs.get_collection_count()
    return {"sources": sources, "chunk_count": count, "source_count": len(sources)}


@app.post("/api/kb/upload")
async def kb_upload(
    request: Request,
    slug: str = Form(...),
    files: list[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    vs = _get_vs(slug)
    results = []
    for f in files:
        fname = f.filename or getattr(f, "name", "unknown")
        save_path = os.path.join(config.HISTORICAL_DIR, fname)
        content = await f.read()
        _raise_if_upload_too_large(content)
        with open(save_path, "wb") as out:
            out.write(content)
        try:
            parsed = path_to_parsed_document(save_path, original_name=fname)
            chunks = _chunker.chunk(parsed)
            vs.add_documents(chunks)
            log_audit(
                FILE_UPLOADED,
                user_id=current_user.id,
                email=current_user.email,
                ip=_client_ip(request),
                ua=_user_agent(request),
                detail={"filename": fname, "chunks": len(chunks)},
            )
            results.append({"file": fname, "ok": True, "chunks": len(chunks)})
        except Exception as e:
            results.append({"file": fname, "ok": False, "error": str(e)})
    return {"results": results}


@app.post("/api/kb/remove-source")
async def kb_remove_source(
    slug: str = Form(...),
    source: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    vs = _get_vs(slug)
    vs.delete_by_source(source)
    return {"ok": True}


# ---------------------------------------------------------------------------
# 模板 API
# ---------------------------------------------------------------------------
@app.get("/api/template/list")
async def template_list(current_user: User = Depends(get_current_user)):
    if not os.path.exists(config.TEMPLATE_DIR):
        return {"templates": []}
    files = [f for f in os.listdir(config.TEMPLATE_DIR) if f.endswith(".docx")]
    items = []
    for f in files:
        p = os.path.join(config.TEMPLATE_DIR, f)
        try:
            mtime = os.path.getmtime(p)
        except OSError:
            mtime = 0
        items.append({"name": f, "mtime": mtime})
    items.sort(key=lambda x: -x["mtime"])
    return {"templates": items}


@app.post("/api/template/analyze")
async def template_analyze(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    fname = file.filename or getattr(file, "name", "unknown")
    save_path = os.path.join(config.TEMPLATE_DIR, fname)
    content = await file.read()
    _raise_if_upload_too_large(content)
    with open(save_path, "wb") as out:
        out.write(content)
    try:
        tasks = _cached_analyze(save_path)
        task_dicts = [asdict(t) for t in tasks]
        mode = "anchor" if tasks and tasks[0].location_hint.get(
            "anchor") else "infer"
        return {"ok": True, "tasks": task_dicts, "count": len(tasks), "mode": mode}
    except Exception as e:
        return {"ok": False, "error": str(e)}


# ---------------------------------------------------------------------------
# 生成 API（SSE 流式）
# ---------------------------------------------------------------------------
@app.post("/api/generate")
async def generate(
    slug: str = Form(...),
    template: str = Form(...),
    word_limit: int = Form(300),
    top_k: int = Form(4),
    max_distance: float = Form(1.25),
    enable_web: bool = Form(False),
    use_stream: bool = Form(True),
    enable_audit: bool = Form(False),
    enable_visual_audit: bool = Form(True),
    custom_instructions: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    vs = _get_vs(slug)
    template_path = os.path.join(config.TEMPLATE_DIR, template)
    if not os.path.isfile(template_path):
        return JSONResponse({"ok": False, "error": "模板不存在"}, status_code=400)

    # 分析模板
    try:
        tasks = _cached_analyze(template_path)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"模板分析失败: {e}"}, status_code=500)
    if not tasks:
        return JSONResponse({"ok": False, "error": "未找到待填位置"}, status_code=400)

    try:
        user_api_key = load_user_api_key(current_user.id)
    except Exception as exc:
        logger.exception("Failed to decrypt user API key")
        return JSONResponse(
            {"ok": False, "error": f"Failed to load saved API Key: {exc}"},
            status_code=500,
        )
    language = get_user_preferences(current_user.id)["language"]
    custom_instructions = (custom_instructions or "").strip()
    if custom_instructions:
        for task in tasks:
            task.description = f"{task.description}\n\n本次生成补充要求：{custom_instructions}"
    billing_lock = threading.Lock()

    def _generate_one_task(i, task):
        local_generator = ContentGenerator(vs, api_key=user_api_key)
        local_auditor = ContentAuditor() if enable_audit else None
        result = {
            "index": i,
            "content": "",
            "route_meta": {},
            "route": None,
            "billing": None,
            "audit": None,
            "trace": None,
            "error": None,
            "chunks": [],
        }
        try:
            gen_bundle = local_generator.prepare_generation_bundle(
                task,
                top_k=top_k,
                enable_web=enable_web,
                retrieval_max_distance=max_distance,
                language=language,
            )
            result["route_meta"] = gen_bundle.route_meta
            result["route"] = {
                "type": "route",
                "index": i,
                "model": gen_bundle.model,
                "tier": gen_bundle.route_meta.get("generation_tier"),
                "kb_hits": gen_bundle.route_meta.get("kb_hits", 0),
                "evidence_refs": gen_bundle.evidence_refs[:5],
            }
            if use_stream:
                acc: list[str] = []
                for piece in local_generator.stream_from_bundle(gen_bundle, route_hook=None):
                    acc.append(piece)
                content = "".join(acc).strip()
                result["chunks"] = acc
            else:
                content = local_generator.generate_from_bundle(gen_bundle, route_hook=None)
                result["chunks"] = [content]
            result["content"] = content

            billed_model, raw_usage = local_generator.pop_last_usage()
            with billing_lock:
                billing_record = record_billing(
                    current_user.id,
                    billed_model or gen_bundle.model,
                    normalize_usage(raw_usage),
                )
            result["billing"] = billing_record

            audit_issues = rule_audit(task, content, gen_bundle.route_meta)
            audit_verdict = "pass" if not audit_issues else "rule_issue"
            revised = False
            if local_auditor is not None and need_model_audit(task, gen_bundle.route_meta, audit_issues):
                ar = local_auditor.audit(
                    task,
                    content,
                    gen_bundle.ref_texts,
                    None,
                    gen_bundle.route_meta,
                )
                audit_verdict = ar.verdict
                audit_issues = audit_issues + list(ar.issues)
                if should_apply_revision(task, ar):
                    content = ar.revised_content.strip()
                    result["content"] = content
                    revised = True
            if audit_issues:
                result["audit"] = {
                    "type": "audit",
                    "index": i,
                    "verdict": audit_verdict,
                    "issues": audit_issues[:5],
                    "revised": revised,
                }
            result["trace"] = build_generation_trace(
                task,
                gen_bundle.route_meta,
                result["content"],
                audit_verdict=audit_verdict,
                audit_issues=audit_issues,
                revised=revised,
            )
        except Exception as e:
            content = f"（生成失败：{e}）"
            result["content"] = content
            result["error"] = str(e)
            result["route_meta"] = {"model": "", "generation_tier": "error", "evidence_refs": []}
            result["trace"] = build_generation_trace(
                task,
                result["route_meta"],
                content,
                audit_verdict="error",
                audit_issues=[str(e)],
            )
        return result

    def event_stream():
        task_results = []
        for i, task in enumerate(tasks):
            if task.word_limit <= 0:
                task.word_limit = word_limit
            yield _sse({"type": "task", "index": i, "total": len(tasks), "chapter": task.target_chapter})

        with concurrent.futures.ThreadPoolExecutor(max_workers=config.GENERATION_MAX_WORKERS) as executor:
            futures = [
                executor.submit(_generate_one_task, i, task)
                for i, task in enumerate(tasks)
            ]
            pending = set(futures)
            while pending:
                done, pending = concurrent.futures.wait(
                    pending, timeout=5.0, return_when=concurrent.futures.FIRST_COMPLETED,
                )
                if not done:
                    # Heartbeat: keep connection alive during long tasks
                    yield _sse({"type": "heartbeat"})
                    continue
                for future in done:
                    result = future.result()
                    task_results.append(result)
                    index = result["index"]
                    if result["route"] is not None:
                        yield _sse(result["route"])
                    for piece in result["chunks"]:
                        yield _sse({"type": "chunk", "index": index, "text": piece})
                    if result["billing"] is not None:
                        yield _sse({"type": "billing", "index": index, "billing": result["billing"]})
                    if result["error"] is not None:
                        yield _sse({"type": "error", "index": index, "error": result["error"]})
                    if result["audit"] is not None:
                        yield _sse(result["audit"])
                    yield _sse({"type": "progress", "index": index, "total": len(tasks)})

        task_results.sort(key=lambda item: item["index"])
        results: list[str] = [item["content"] for item in task_results]
        traces = [item["trace"] for item in task_results]
        billing_records = [
            item["billing"]
            for item in task_results
            if item["billing"] is not None
        ]

        # 回填 Word
        output_name = template.replace(".docx", "_已填写.docx")
        output_path = os.path.join(config.OUTPUT_DIR, output_name)
        try:
            _filler.fill_template(template_path, tasks, results, output_path)
            post_fill_checks = verify_filled_document(template_path, output_path, tasks)
            visual_payload = {}
            if enable_visual_audit and config.VISUAL_AUDIT_ENABLED:
                visual_result = audit_document_visual(output_path)
                visual_payload = asdict(visual_result)
            report = build_quality_report(
                template_name=template,
                output_path=output_path,
                traces=traces,
                post_fill_checks=post_fill_checks,
                visual_audit=visual_payload,
            )
            report_path = save_quality_report(output_path, report)
            yield _sse(
                {
                    "type": "done",
                    "filename": output_name,
                    "download": f"/api/download/{output_name}",
                    "report_download": f"/api/download/{os.path.basename(report_path)}",
                    "report_summary": quality_report_summary(report),
                    "post_fill_checks": post_fill_checks,
                    "visual_score": visual_payload.get("score"),
                    "billing": {
                        "records": billing_records,
                        "input_tokens": sum(int(item.get("input_tokens") or 0) for item in billing_records),
                        "output_tokens": sum(int(item.get("output_tokens") or 0) for item in billing_records),
                        "cost_cny": round(sum(float(item.get("cost_cny") or 0) for item in billing_records), 8),
                    },
                    "billing_summary": billing_summary(current_user.id),
                }
            )
        except Exception as e:
            yield _sse({"type": "error", "error": f"回填失败: {e}"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# 下载
# ---------------------------------------------------------------------------
@app.get("/api/download/{filename}")
async def download(
    filename: str,
    current_user: User = Depends(get_current_user),
):
    # Path traversal protection
    if ".." in filename or "/" in filename or "\\" in filename:
        return JSONResponse({"error": "非法文件名"}, status_code=400)
    path = os.path.normpath(os.path.join(config.OUTPUT_DIR, filename))
    output_dir = os.path.normpath(config.OUTPUT_DIR)
    if not path.startswith(output_dir + os.sep) and path != output_dir:
        return JSONResponse({"error": "非法文件路径"}, status_code=400)
    if not os.path.isfile(path):
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    media_type, _ = mimetypes.guess_type(path)
    return FileResponse(
        path,
        filename=filename,
        media_type=media_type
        or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/admin/stats")
async def admin_stats(
    request: Request,
    admin: User = Depends(require_admin),
):
    log_audit(
        ADMIN_ACCESS,
        user_id=admin.id,
        email=admin.email,
        ip=_client_ip(request),
        ua=_user_agent(request),
    )
    import sqlite3 as _sqlite3
    db = config.AUTH_DB_PATH
    with _sqlite3.connect(db) as conn:
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_generations = conn.execute("SELECT COUNT(*) FROM billing_records").fetchone()[0]
        total_cost = conn.execute("SELECT COALESCE(SUM(cost_cny), 0) FROM billing_records").fetchone()[0]
        total_input = conn.execute("SELECT COALESCE(SUM(input_tokens), 0) FROM billing_records").fetchone()[0]
        total_output = conn.execute("SELECT COALESCE(SUM(output_tokens), 0) FROM billing_records").fetchone()[0]
        # Last 7 days daily stats
        daily = conn.execute(
            "SELECT DATE(created_at) as day, COUNT(*) as gens, SUM(cost_cny) as cost, "
            "SUM(input_tokens) as inp, SUM(output_tokens) as outp "
            "FROM billing_records WHERE created_at >= DATE('now', '-7 days') "
            "GROUP BY day ORDER BY day"
        ).fetchall()
        # Top models
        models = conn.execute(
            "SELECT model, COUNT(*) as cnt, SUM(cost_cny) as cost "
            "FROM billing_records GROUP BY model ORDER BY cnt DESC LIMIT 5"
        ).fetchall()
        # Users with API keys
        users_with_key = conn.execute("SELECT COUNT(*) FROM user_api_keys").fetchone()[0]
    return {
        "total_users": total_users,
        "total_generations": total_generations,
        "total_cost_cny": round(total_cost, 4),
        "total_input_tokens": total_input,
        "total_output_tokens": total_output,
        "users_with_api_key": users_with_key,
        "daily": [{"day": r[0], "generations": r[1], "cost": round(r[2] or 0, 4), "input_tokens": r[3], "output_tokens": r[4]} for r in daily],
        "top_models": [{"model": r[0], "count": r[1], "cost": round(r[2] or 0, 4)} for r in models],
    }


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    if not full_path or full_path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)

    if os.path.isdir(FRONTEND_DIST_DIR):
        candidate = os.path.join(FRONTEND_DIST_DIR, full_path)
        if os.path.isfile(candidate):
            media_type, _ = mimetypes.guess_type(candidate)
            return FileResponse(candidate, media_type=media_type)

    return FileResponse(_spa_index_path(), media_type="text/html")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    print("启动服务器: http://localhost:8502")
    uvicorn.run(app, host="0.0.0.0", port=8502)
