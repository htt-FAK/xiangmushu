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
import shutil
import threading
import time
from dataclasses import asdict

from contextlib import asynccontextmanager

from fastapi import BackgroundTasks
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from core.auth import (
    ACTIVE_ACCOUNT,
    AccountNotVerifiedError,
    AccountRestrictedError,
    AuthError,
    ChallengeConsumedError,
    ChallengeExpiredError,
    ChallengeSupersededError,
    EmailExistsError,
    EmailNotFoundError,
    InvalidCodeError,
    InvalidEmailError,
    InvalidLanguageError,
    InvalidPasswordError,
    InvalidTokenError,
    RecoveryTokenError,
    RECOVERY_CHALLENGE,
    SIGNUP_CHALLENGE,
    UNKNOWN_ACCOUNT,
    UNVERIFIED_ACCOUNT,
    User,
    authenticate_user,
    consume_verification_code,
    create_access_token,
    create_verification_code,
    get_account_state,
    get_user_preferences,
    get_or_create_user,
    init_db,
    reset_password_with_code,
    reset_password_with_token,
    send_verification_email,
    resend_signup_verification,
    start_password_recovery,
    start_signup,
    update_user_preferences,
    user_from_token,
    verify_password_recovery_code,
    verify_signup_code,
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
from core.api_key_validation import validate_user_api_key
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
from core.artifacts import (
    ArtifactError,
    ArtifactNotFoundError,
    get_artifact_for_user,
    materialize_artifact,
    put_bytes,
    put_file,
)
from core.generation_sessions import (
    ActiveGenerationExistsError,
    GenerationSession,
    session_manager,
)
from core.db import ensure_configured_database, mysql_enabled, mysql_transaction
from core.history import history_summary, list_history_articles
from core.provider_errors import classify_provider_error, validation_http_status
from core.provider_registry import model_options_map_for_user


def _safe_filename(raw: str) -> str:
    """Sanitize uploaded filename to prevent path traversal and injection."""
    import re as _re
    name = os.path.basename(raw or "unknown")
    # Remove null bytes and control characters
    name = name.replace("\x00", "").strip()
    # Only allow safe characters: alphanumeric, CJK, dots, hyphens, underscores, spaces
    name = _re.sub(r'[^\w.\-\s\u4e00-\u9fff]', '_', name)
    # Collapse multiple dots (prevent .. traversal)
    name = _re.sub(r'\.{2,}', '.', name)
    return name or "unnamed"


def _get_password_hash(email: str) -> str:
    """Look up password hash from DB for login verification."""
    from core.auth import get_password_hash

    return get_password_hash(email)
from core.chunker import Chunker
from core.content_auditor import (
    ContentAuditor,
    need_model_audit,
    rule_audit,
    should_apply_revision,
)
from core.filler import WordFiller
from core.generator import ContentGenerator
try:
    from core.generator import QuotaExceededError
except ImportError:  # Test stubs may provide only ContentGenerator.
    class QuotaExceededError(Exception):
        def __init__(self, message: str = "", model: str = "", detail: str = "", route_meta: dict | None = None):
            super().__init__(message)
            self.model = model
            self.detail = detail
            self.route_meta = route_meta or {}
from core.kb_extract import is_supported_kb_extension, path_to_parsed_document
from core.knowledge_repo import (
    create_knowledge_base,
    delete_knowledge_base,
    list_knowledge_bases,
    list_source_stats,
    remove_source,
    replace_source_chunks,
    upsert_knowledge_source,
)
from core.post_fill_verifier import verify_filled_document
from core.reporting import (
    build_generation_trace,
    build_quality_report,
    quality_report_summary,
    save_quality_report,
)
from core.template_analyzer import TemplateAnalyzer
from core.template_vision import (
    cache_bundle_dir,
    get_or_build_template_vision_profile,
    _cache_path as template_vision_cache_path,
)
from core.vector_store import VectorStore
from core.visual_auditor import audit_document_visual


class SimpleRateLimiter:
    _MAX_KEYS = 10000  # Prevent unbounded memory growth

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = {}
        self._last_cleanup = time.monotonic()

    def _cleanup_stale(self, now: float) -> None:
        """Periodically remove keys with no recent events."""
        if now - self._last_cleanup < 60:  # Every 60s
            return
        self._last_cleanup = now
        stale_keys = [
            k for k, stamps in self._events.items()
            if not stamps or stamps[-1] < now - 300  # No activity in 5min
        ]
        for k in stale_keys:
            del self._events[k]
        # Hard cap: evict oldest keys if over limit
        while len(self._events) > self._MAX_KEYS:
            oldest = next(iter(self._events))
            del self._events[oldest]

    def allow(self, key: str, limits: list[tuple[int, int]]) -> bool:
        now = time.monotonic()
        self._cleanup_stale(now)
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


class AuthIdentifyRequest(BaseModel):
    email: str


class LoginRequest(BaseModel):
    email: str
    password: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str
    password: str | None = None


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str


class RecoveryResetTokenRequest(BaseModel):
    email: str
    recovery_token: str
    new_password: str


def _auth_error(reason: str, message: str, *, status_code: int = status.HTTP_401_UNAUTHORIZED) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"reason": reason, "message": message})


def _raise_auth_http(exc: Exception) -> None:
    if isinstance(exc, InvalidEmailError):
        raise _auth_error("invalid_email", str(exc), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY) from exc
    if isinstance(exc, InvalidPasswordError):
        raise _auth_error("invalid_password", str(exc)) from exc
    if isinstance(exc, EmailExistsError):
        raise _auth_error("email_exists", "该邮箱已注册，请直接登录") from exc
    if isinstance(exc, EmailNotFoundError):
        raise _auth_error("email_not_found", "该邮箱尚未注册，请先创建账号") from exc
    if isinstance(exc, AccountNotVerifiedError):
        raise _auth_error("account_unverified", "该账号尚未完成邮箱验证，请继续验证") from exc
    if isinstance(exc, AccountRestrictedError):
        raise _auth_error("account_restricted", "该账号当前无法继续登录，请联系管理员") from exc
    if isinstance(exc, ChallengeExpiredError):
        raise _auth_error("challenge_expired", "验证码已过期，请重新发送") from exc
    if isinstance(exc, ChallengeSupersededError):
        raise _auth_error("challenge_superseded", "旧验证码已失效，请使用最新验证码") from exc
    if isinstance(exc, ChallengeConsumedError):
        raise _auth_error("challenge_consumed", "验证码已被使用，请重新发送") from exc
    if isinstance(exc, InvalidCodeError):
        raise _auth_error("invalid_code", "验证码不正确，请检查后重试") from exc
    if isinstance(exc, RecoveryTokenError):
        raise _auth_error("invalid_recovery_token", "重置凭证无效或已过期，请重新发起重置") from exc
    if isinstance(exc, AuthError):
        raise _auth_error("auth_error", str(exc), status_code=status.HTTP_400_BAD_REQUEST) from exc
    raise exc


class ApiKeyRequest(BaseModel):
    api_key: str
    provider_code: str | None = None


class UserPreferencesRequest(BaseModel):
    language: str | None = None
    model_choices: dict[str, str] | None = None


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
    ensure_configured_database()
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

# Template analysis cache: memory + disk persistence
_template_analysis_cache: dict[tuple[str, float], list] = {}
_TEMPLATE_CACHE_MAX = 16
_TEMPLATE_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", ".cache")


def _cache_key_str(template_path: str, mtime: float) -> str:
    """Deterministic filename-safe cache key from path + mtime."""
    import hashlib
    raw = f"{os.path.abspath(template_path)}:{mtime}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_cached_tasks(cache_file: str) -> list | None:
    """Load cached FillTask dicts from JSON file, return list of FillTask or None."""
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            return None
        from core.fill_task import FillTask
        return [FillTask(**item) for item in data]
    except Exception:
        return None


def _save_cached_tasks(cache_file: str, tasks: list) -> None:
    """Persist FillTask list to JSON file."""
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        from dataclasses import asdict
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump([asdict(t) for t in tasks], f, ensure_ascii=False)
    except Exception as e:
        logger.warning("Failed to save template cache: %s", e)


def _cached_analyze(template_path: str, analyzer: TemplateAnalyzer | None = None) -> list:
    """Analyze template with memory + disk cache keyed by path + mtime."""
    mtime = os.path.getmtime(template_path)
    key = (template_path, mtime)

    # 1. Memory cache hit
    if key in _template_analysis_cache:
        return _template_analysis_cache[key]

    # 2. Disk cache hit
    ck = _cache_key_str(template_path, mtime)
    cache_file = os.path.join(_TEMPLATE_CACHE_DIR, f"{ck}.json")
    if os.path.isfile(cache_file):
        tasks = _load_cached_tasks(cache_file)
        if tasks is not None:
            # Promote to memory cache
            while len(_template_analysis_cache) >= _TEMPLATE_CACHE_MAX:
                oldest = next(iter(_template_analysis_cache))
                del _template_analysis_cache[oldest]
            _template_analysis_cache[key] = tasks
            return tasks

    # 3. Cache miss — analyze
    tasks = (analyzer or _analyzer).analyze(template_path)

    # Save to memory
    while len(_template_analysis_cache) >= _TEMPLATE_CACHE_MAX:
        oldest = next(iter(_template_analysis_cache))
        del _template_analysis_cache[oldest]
    _template_analysis_cache[key] = tasks

    # Persist to disk
    _save_cached_tasks(cache_file, tasks)

    return tasks


def _template_path_for_name(template: str) -> str:
    name = _safe_filename(template)
    path = os.path.abspath(os.path.join(config.TEMPLATE_DIR, name))
    template_dir = os.path.abspath(config.TEMPLATE_DIR)
    if not path.startswith(template_dir + os.sep) and path != template_dir:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="非法模板名")
    if not name.lower().endswith(".docx"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 .docx 模板")
    return path


def _vision_model_options() -> list[str]:
    cfg = config.USER_MODEL_OPTIONS.get("vision") or {}
    models: list[str] = []
    seen: set[str] = set()
    for group in (cfg.get("tiers") or {}).values():
        for item in group:
            model = str((item or {}).get("model") or "").strip()
            if model and model not in seen:
                seen.add(model)
                models.append(model)
    for item in cfg.get("options") or []:
        model = str((item or {}).get("model") or "").strip()
        if model and model not in seen:
            seen.add(model)
            models.append(model)
    return models


def _resolve_vision_model(raw: str | None, user_id: int) -> str:
    allowed = _vision_model_options()
    selected = (raw or "").strip() or config.get_user_model_for_user(user_id, "vision_layout") or config.TEMPLATE_VISION_MODEL
    if selected not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"请选择视觉模型：{', '.join(allowed)}",
        )
    return selected


def _parsed_document_markdown(parsed) -> str:
    lines: list[str] = [f"# {getattr(parsed, 'filename', 'parsed document')}"]
    for section in getattr(parsed, "sections", []) or []:
        title = getattr(section, "title", "") or "Untitled"
        level = max(1, min(6, int(getattr(section, "level", 1) or 1)))
        lines.append("")
        lines.append(f"{'#' * level} {title}")
        content = getattr(section, "content", "") or ""
        if content:
            lines.append(content)
    for block in getattr(parsed, "blocks", []) or []:
        text = getattr(block, "text", "") or ""
        if text:
            lines.append("")
            lines.append(text)
    return "\n".join(lines).strip() + "\n"
    return selected


def _resolve_template_planner_model(raw: str | None, user_id: int) -> str:
    return (raw or "").strip() or config.get_user_model_for_user(user_id, "template_planner") or config.TEMPLATE_ANALYZE_MODEL


def _require_user_api_key(current_user: User | int) -> str:
    user_id = current_user.id if isinstance(current_user, User) else int(current_user)
    try:
        user_api_key = load_user_api_key(user_id)
    except Exception as exc:
        logger.exception("Failed to decrypt user API key")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to load saved API Key: {exc}",
        ) from exc
    if not user_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="请先在设置页保存你自己的 API Key，然后再进行模板分析或内容生成。",
        )
    return user_api_key


def _client_for_user_template_analysis(user_id: int):
    user_api_key = _require_user_api_key(user_id)
    from openai import OpenAI

    return OpenAI(
        api_key=user_api_key,
        base_url=config.DASHSCOPE_COMPAT_BASE,
        timeout=config.TEMPLATE_ANALYZE_TIMEOUT,
        max_retries=0,
    )


def _clear_template_caches(template_path: str) -> None:
    abs_path = os.path.abspath(template_path)
    for key in list(_template_analysis_cache.keys()):
        if os.path.abspath(key[0]) == abs_path:
            del _template_analysis_cache[key]
    try:
        mtime = os.path.getmtime(template_path)
        cache_file = os.path.join(_TEMPLATE_CACHE_DIR, f"{_cache_key_str(template_path, mtime)}.json")
        if os.path.isfile(cache_file):
            os.remove(cache_file)
    except OSError:
        pass
    shutil.rmtree(cache_bundle_dir(template_path), ignore_errors=True)
    try:
        flat_cache = template_vision_cache_path(template_path)
        if os.path.isfile(flat_cache):
            os.remove(flat_cache)
    except OSError:
        pass


def _billing_total(records: list[dict | None]) -> dict[str, object]:
    clean = [r for r in records if r]
    return {
        "records": clean,
        "input_tokens": sum(int(r.get("input_tokens") or 0) for r in clean),
        "output_tokens": sum(int(r.get("output_tokens") or 0) for r in clean),
        "cost_cny": round(sum(float(r.get("cost_cny") or 0) for r in clean), 8),
    }


def _analyze_template_now(
    template_path: str,
    current_user: User,
    *,
    vision_model: str,
    planner_model: str,
    force_refresh: bool,
) -> dict[str, object]:
    if force_refresh:
        _clear_template_caches(template_path)
    client = _client_for_user_template_analysis(current_user.id)

    vision_profile, vision_status = get_or_build_template_vision_profile(
        template_path,
        force_refresh=force_refresh,
        model=vision_model,
        client=client,
    )
    vision_billing = vision_profile.pop("_billing", None) if isinstance(vision_profile, dict) else None
    billing_records: list[dict | None] = []
    if isinstance(vision_billing, dict):
        billing_records.append(
            record_billing(
                current_user.id,
                str(vision_billing.get("model") or vision_model),
                normalize_usage(vision_billing.get("usage")),
            )
        )

    analyzer = TemplateAnalyzer(client=client)
    tasks = analyzer.analyze(template_path, vision_profile=vision_profile, analyze_model=planner_model)
    billing_records.append(
        record_billing(
            current_user.id,
            analyzer.last_model or planner_model,
            normalize_usage(analyzer.last_usage),
        )
    )

    mtime = os.path.getmtime(template_path)
    key = (template_path, mtime)
    while len(_template_analysis_cache) >= _TEMPLATE_CACHE_MAX:
        oldest = next(iter(_template_analysis_cache))
        del _template_analysis_cache[oldest]
    _template_analysis_cache[key] = tasks
    _save_cached_tasks(os.path.join(_TEMPLATE_CACHE_DIR, f"{_cache_key_str(template_path, mtime)}.json"), tasks)

    mode = "anchor" if tasks and tasks[0].location_hint.get("anchor") else "infer"
    return {
        "ok": True,
        "template": os.path.basename(template_path),
        "tasks": [asdict(t) for t in tasks],
        "count": len(tasks),
        "mode": mode,
        "vision_model": vision_model,
        "planner_model": analyzer.last_model or planner_model,
        "vision_status": vision_status,
        "billing": _billing_total(billing_records),
    }


def _get_vs(slug: str) -> VectorStore:
    if slug not in _vs_cache:
        _vs_cache[slug] = VectorStore(kb_slug=slug)
    return _vs_cache[slug]


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


def _ensure_session_owned(session_id: str, current_user: User) -> GenerationSession:
    session = session_manager.get_session_for_user(current_user.id, session_id)
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Generation session not found")
    return session


def _build_generation_params(
    slug: str,
    template: str,
    word_limit: int,
    top_k: int,
    max_distance: float,
    enable_web: bool,
    use_stream: bool,
    enable_audit: bool,
    enable_visual_audit: bool,
    custom_instructions: str,
) -> dict[str, object]:
    return {
        "slug": slug,
        "template": template,
        "word_limit": word_limit,
        "top_k": top_k,
        "max_distance": max_distance,
        "enable_web": enable_web,
        "use_stream": use_stream,
        "enable_audit": enable_audit,
        "enable_visual_audit": enable_visual_audit,
        "custom_instructions": custom_instructions.strip(),
    }


def _serialize_session(session: GenerationSession | None) -> dict[str, object]:
    return {"session": session.snapshot() if session is not None else None}


def _available_models_for_module(module: str) -> list[str]:
    try:
        from core.model_router import available_models_for_role

        role_models = available_models_for_role(module)
        if role_models:
            return role_models
    except Exception:
        pass
    module_config = config.USER_MODEL_OPTIONS.get(module) or {}
    models: list[str] = []
    seen: set[str] = set()
    for tier_models in (module_config.get("tiers") or {}).values():
        for item in tier_models:
            model = str((item or {}).get("model") or "").strip()
            if not model or model in seen:
                continue
            seen.add(model)
            models.append(model)
    for item in module_config.get("options") or []:
        model = str((item or {}).get("model") or "").strip()
        if not model or model in seen:
            continue
        seen.add(model)
        models.append(model)
    return models


def _quota_alert_event(user_id: int, exc: QuotaExceededError) -> dict[str, object]:
    module = str(exc.module or "").strip()
    current_model = (config.get_user_model_for_user(user_id, module) if module else exc.model).strip() or exc.model
    provider_error = getattr(exc, "provider_error", {}) or {}
    if provider_error.get("code") == "quota_exceeded":
        message = "当前 API Key 的模型额度已用尽，或已开启仅使用免费额度模式。请切换模型，或到百炼控制台关闭“仅使用免费额度”。"
    else:
        message = str(provider_error.get("message") or "").strip()
    if not message:
        message = exc.detail.strip() or f"Quota exceeded for model: {current_model}"
    return {
        "type": "quota_alert",
        "module": module,
        "current_model": current_model,
        "available_models": _available_models_for_module(module),
        "message": message,
    }


def _resolve_generation_request(current_user: User, params: dict[str, object]) -> dict[str, object]:
    slug = str(params["slug"])
    template = str(params["template"])
    vs = _get_vs(slug)
    template_path = os.path.join(config.TEMPLATE_DIR, template)
    user_api_key = _require_user_api_key(current_user)
    if not os.path.isfile(template_path):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="模板不存在")
    try:
        tasks = _cached_analyze(
            template_path,
            analyzer=TemplateAnalyzer(client=_client_for_user_template_analysis(current_user.id)),
        )
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"模板分析失败: {exc}") from exc
    if not tasks:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未找到待填位置")
    language = get_user_preferences(current_user.id)["language"]
    return {
        "vs": vs,
        "tasks": tasks,
        "template_path": template_path,
        "template": template,
        "user_api_key": user_api_key,
        "language": language,
    }


def _run_generation_session(session_id: str, current_user: User, params: dict[str, object], resolved: dict[str, object]) -> None:
    vs = resolved["vs"]
    tasks = resolved["tasks"]
    template_path = str(resolved["template_path"])
    template = str(resolved["template"])
    user_api_key = resolved["user_api_key"]
    language = str(resolved["language"])
    custom_instructions = str(params["custom_instructions"] or "").strip()
    word_limit = int(params["word_limit"])
    top_k = int(params["top_k"])
    max_distance = float(params["max_distance"])
    enable_web = bool(params["enable_web"])
    use_stream = bool(params["use_stream"])
    enable_audit = bool(params["enable_audit"])
    enable_visual_audit = bool(params["enable_visual_audit"])
    billing_lock = threading.Lock()

    def emit(event: dict[str, object]) -> None:
        session_manager.append_event(session_id, event)

    def _generate_one_task(i, task):
        import copy

        task = copy.deepcopy(task)
        if task.word_limit <= 0:
            task.word_limit = word_limit
        if custom_instructions:
            task.description = f"{task.description}\n\n本次生成补充要求：{custom_instructions}"
        local_generator = ContentGenerator(
            vs,
            api_key=user_api_key,
            user_id=current_user.id,
        )
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
                "role": gen_bundle.route_meta.get("model_role"),
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
        except QuotaExceededError:
            raise
        except Exception as exc:
            logger.exception("Task %d generation failed", i)
            content = "（生成失败，请重试）"
            classified = classify_provider_error(exc)
            result["content"] = content
            result["error"] = classified
            result["route_meta"] = {"model": "", "generation_tier": "error", "evidence_refs": []}
            result["trace"] = build_generation_trace(
                task,
                result["route_meta"],
                content,
                audit_verdict="error",
                audit_issues=[classified["detail"]],
            )
        return result

    try:
        task_results = []
        for i, task in enumerate(tasks):
            emit({"type": "task", "index": i, "total": len(tasks), "chapter": task.target_chapter})

        abort_generation = False
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=config.GENERATION_MAX_WORKERS)
        try:
            futures = [executor.submit(_generate_one_task, i, task) for i, task in enumerate(tasks)]
            pending = set(futures)
            while pending:
                done, pending = concurrent.futures.wait(pending, timeout=5.0, return_when=concurrent.futures.FIRST_COMPLETED)
                if not done:
                    emit({"type": "heartbeat"})
                    continue
                for future in done:
                    try:
                        result = future.result()
                    except QuotaExceededError as exc:
                        emit(_quota_alert_event(current_user.id, exc))
                        abort_generation = True
                        for pending_future in pending:
                            pending_future.cancel()
                        return
                    task_results.append(result)
                    index = result["index"]
                    if result["route"] is not None:
                        emit(result["route"])
                    for piece in result["chunks"]:
                        emit({"type": "chunk", "index": index, "text": piece})
                    if result["billing"] is not None:
                        emit({"type": "billing", "index": index, "billing": result["billing"]})
                    if result["error"] is not None:
                        emit({"type": "error", "index": index, "error": result["error"], "terminal": False})
                    if result["audit"] is not None:
                        emit(result["audit"])
                    emit({"type": "progress", "index": index, "total": len(tasks)})
        finally:
            executor.shutdown(wait=not abort_generation, cancel_futures=abort_generation)

        task_results.sort(key=lambda item: item["index"])
        results: list[str] = [item["content"] for item in task_results]
        traces = [item["trace"] for item in task_results]
        billing_records = [item["billing"] for item in task_results if item["billing"] is not None]

        ts = time.strftime("%Y%m%d_%H%M%S")
        base_name = template.replace(".docx", "")
        output_name = f"{base_name}_u{current_user.id}_{ts}.docx"
        output_path = os.path.join(config.OUTPUT_DIR, output_name)
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
        legacy_download = f"/api/download/{output_name}"
        legacy_report_download = f"/api/download/{os.path.basename(report_path)}"
        download_url = legacy_download
        report_download_url = legacy_report_download
        artifact_payload: dict[str, object] = {}
        if mysql_enabled():
            try:
                doc_artifact = put_file(
                    output_path,
                    owner_user_id=current_user.id,
                    artifact_type="generated_doc",
                    original_filename=output_name,
                    content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    metadata={"session_id": session_id, "template": template},
                )
                report_artifact = put_file(
                    report_path,
                    owner_user_id=current_user.id,
                    artifact_type="quality_report",
                    original_filename=os.path.basename(report_path),
                    content_type="application/json",
                    metadata={"session_id": session_id, "template": template},
                )
                download_url = f"/api/artifacts/{doc_artifact.artifact_uuid}/download"
                report_download_url = f"/api/artifacts/{report_artifact.artifact_uuid}/download"
                artifact_payload = {
                    "artifact_id": doc_artifact.artifact_uuid,
                    "report_artifact_id": report_artifact.artifact_uuid,
                    "legacy_download": legacy_download,
                    "legacy_report_download": legacy_report_download,
                }
            except Exception:
                logger.exception("Failed to store generation artifacts; falling back to legacy downloads")
        emit(
            {
                "type": "done",
                "filename": output_name,
                "download": download_url,
                "report_download": report_download_url,
                **artifact_payload,
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
    except QuotaExceededError as exc:
        emit(_quota_alert_event(current_user.id, exc))
    except Exception as exc:
        logger.exception("Generation session %s failed", session_id)
        emit({"type": "error", "error": classify_provider_error(exc), "terminal": True})


def _start_generation_session(current_user: User, params: dict[str, object]) -> GenerationSession:
    resolved = _resolve_generation_request(current_user, params)
    session = session_manager.create_session(current_user.id, params)
    worker = threading.Thread(
        target=_run_generation_session,
        args=(session.session_id, current_user, params, resolved),
        daemon=True,
    )
    worker.start()
    return session


# ---------------------------------------------------------------------------
# 静态文件 & 首页
# ---------------------------------------------------------------------------
BASE_DIR = os.path.dirname(__file__)
STATIC_DIR = os.path.join(BASE_DIR, "static")
FRONTEND_DIST_DIR = os.path.join(BASE_DIR, "frontend", "dist")
FRONTEND_ASSETS_DIR = os.path.join(FRONTEND_DIST_DIR, "assets")
BLOCKED_PATH_PARTS = {
    ".env",
    ".git",
    ".svn",
    ".hg",
    "_ignition",
    "vendor",
    "phpunit",
}


def _spa_index_path() -> str:
    frontend_index = os.path.join(FRONTEND_DIST_DIR, "index.html")
    if os.path.isfile(frontend_index):
        return frontend_index
    # Fallback: serve a minimal safe page instead of the legacy static/index.html
    # which contains unescaped innerHTML and XSS risks.
    raise FileNotFoundError(
        "Frontend not built. Run 'cd frontend && npm run build' first."
    )


def _should_serve_spa(full_path: str) -> bool:
    normalized = full_path.strip().strip("/")
    if not normalized:
        return True

    parts = [part for part in normalized.split("/") if part]
    if any(part.startswith(".") for part in parts):
        return False
    if any(part.lower() in BLOCKED_PATH_PARTS for part in parts):
        return False

    basename = parts[-1]
    if "." in basename:
        return False

    return True


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
        if payload.password is None:
            verification = start_password_recovery(payload.email)
            purpose = "reset_password"
        else:
            verification = start_signup(payload.email, payload.password)
            purpose = "register"
        send_verification_email(verification.email, verification.code, purpose=purpose)
        log_audit(
            CODE_REQUESTED,
            email=verification.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"purpose": purpose},
        )
        return {"ok": True, "email": verification.email, "expires_at": verification.expires_at}
    except (InvalidEmailError, InvalidPasswordError, EmailExistsError, EmailNotFoundError, AccountNotVerifiedError, AccountRestrictedError) as exc:
        _raise_auth_http(exc)
    except AuthError as exc:
        logger.exception("Failed to request verification code")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@app.post("/api/auth/identify")
async def auth_identify(payload: AuthIdentifyRequest):
    try:
        state = get_account_state(payload.email)
        return {"email": payload.email.strip().lower(), "account_state": state}
    except InvalidEmailError as exc:
        _raise_auth_http(exc)


@app.post("/api/auth/signup/start")
async def auth_signup_start(payload: EmailRequest, request: Request):
    email_key = payload.email.lower().strip()
    if not rate_limiter.allow(f"signup-start:{email_key}", [(1, 60), (5, 3600)]):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_MESSAGE)
    if not payload.password:
        raise _auth_error("invalid_password", "Password is required")
    password_ok, password_message = validate_password(payload.password)
    if not password_ok:
        raise _auth_error("invalid_password", password_message, status_code=status.HTTP_400_BAD_REQUEST)
    try:
        verification = start_signup(payload.email, payload.password)
        send_verification_email(verification.email, verification.code, purpose="register")
        log_audit(CODE_REQUESTED, email=verification.email, ip=_client_ip(request), ua=_user_agent(request), detail={"purpose": "signup"})
        return {"ok": True, "email": verification.email, "expires_at": verification.expires_at}
    except (InvalidEmailError, InvalidPasswordError, EmailExistsError, AccountRestrictedError) as exc:
        _raise_auth_http(exc)


@app.post("/api/auth/signup/resend")
async def auth_signup_resend(payload: AuthIdentifyRequest, request: Request):
    email_key = payload.email.lower().strip()
    if not rate_limiter.allow(f"signup-resend:{email_key}", [(1, 60), (5, 3600)]):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_MESSAGE)
    try:
        verification = resend_signup_verification(payload.email)
        send_verification_email(verification.email, verification.code, purpose="register")
        log_audit(CODE_REQUESTED, email=verification.email, ip=_client_ip(request), ua=_user_agent(request), detail={"purpose": "signup_resend"})
        return {"ok": True, "email": verification.email, "expires_at": verification.expires_at}
    except (InvalidEmailError, EmailExistsError, EmailNotFoundError, AccountRestrictedError) as exc:
        _raise_auth_http(exc)


@app.post("/api/auth/signup/verify")
async def auth_signup_verify(payload: VerifyCodeRequest, request: Request):
    try:
        user = verify_signup_code(payload.email, payload.code)
        token = create_access_token(user)
        log_audit(REGISTER_SUCCESS, user_id=user.id, email=user.email, ip=_client_ip(request), ua=_user_agent(request))
        return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}}
    except (InvalidEmailError, InvalidCodeError, EmailExistsError, EmailNotFoundError, AccountRestrictedError) as exc:
        _raise_auth_http(exc)


@app.post("/api/auth/verify-code")
async def auth_verify_code(payload: VerifyCodeRequest, request: Request):
    try:
        return await auth_signup_verify(payload, request)
    except HTTPException:
        raise


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
        recovery_token = verify_password_recovery_code(payload.email, payload.code)
        user = reset_password_with_token(payload.email, recovery_token, payload.new_password)
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
    except (InvalidEmailError, InvalidCodeError, EmailNotFoundError, AccountNotVerifiedError, AccountRestrictedError, RecoveryTokenError) as exc:
        log_audit(
            PASSWORD_RESET_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "invalid_code"},
        )
        _raise_auth_http(exc)
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
            detail={"reason": "auth_error", "message": str(exc)},
        ) from exc


@app.post("/api/auth/recovery/start")
async def auth_recovery_start(payload: AuthIdentifyRequest, request: Request):
    email_key = payload.email.lower().strip()
    if not rate_limiter.allow(f"recovery-start:{email_key}", [(1, 60), (5, 3600)]):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=RATE_LIMIT_MESSAGE)
    try:
        verification = start_password_recovery(payload.email)
        send_verification_email(verification.email, verification.code, purpose="reset_password")
        log_audit(CODE_REQUESTED, email=verification.email, ip=_client_ip(request), ua=_user_agent(request), detail={"purpose": "recovery"})
        return {"ok": True, "email": verification.email, "expires_at": verification.expires_at}
    except (InvalidEmailError, EmailNotFoundError, AccountNotVerifiedError, AccountRestrictedError) as exc:
        _raise_auth_http(exc)


@app.post("/api/auth/recovery/verify")
async def auth_recovery_verify(payload: VerifyCodeRequest):
    try:
        recovery_token = verify_password_recovery_code(payload.email, payload.code)
        return {"ok": True, "email": payload.email.strip().lower(), "recovery_token": recovery_token}
    except (InvalidEmailError, InvalidCodeError, EmailNotFoundError, AccountNotVerifiedError, AccountRestrictedError) as exc:
        _raise_auth_http(exc)


@app.post("/api/auth/recovery/complete")
async def auth_recovery_complete(payload: RecoveryResetTokenRequest, request: Request):
    password_ok, password_message = validate_password(payload.new_password)
    if not password_ok:
        raise _auth_error("invalid_password", password_message, status_code=status.HTTP_400_BAD_REQUEST)
    try:
        user = reset_password_with_token(payload.email, payload.recovery_token, payload.new_password)
        token = create_access_token(user)
        log_audit(PASSWORD_RESET_SUCCESS, user_id=user.id, email=user.email, ip=_client_ip(request), ua=_user_agent(request))
        return {"access_token": token, "token_type": "bearer", "user": {"id": user.id, "email": user.email}}
    except (InvalidEmailError, EmailNotFoundError, RecoveryTokenError, AccountRestrictedError) as exc:
        log_audit(PASSWORD_RESET_FAILED, email=payload.email, ip=_client_ip(request), ua=_user_agent(request), detail={"reason": "recovery_complete_failed"})
        _raise_auth_http(exc)


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
        user = authenticate_user(payload.email, payload.password)
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
    except (InvalidPasswordError, EmailNotFoundError, AccountNotVerifiedError, AccountRestrictedError, InvalidEmailError) as exc:
        log_audit(
            LOGIN_FAILED,
            email=payload.email,
            ip=_client_ip(request),
            ua=_user_agent(request),
            detail={"reason": "invalid_credentials"},
        )
        _raise_auth_http(exc)
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


@app.get("/api/user/model-options")
async def user_model_options(current_user: User = Depends(get_current_user)):
    """返回 USER_MODEL_OPTIONS 注册表，供前端渲染模型选择下拉框。"""
    return model_options_map_for_user(current_user.id)


@app.get("/api/user/preferences")
async def user_preferences(current_user: User = Depends(get_current_user)):
    return get_user_preferences(current_user.id)


@app.put("/api/user/preferences")
async def user_preferences_update(
    payload: UserPreferencesRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        return update_user_preferences(
            current_user.id,
            language=payload.language,
            model_choices=payload.model_choices,
        )
    except InvalidLanguageError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@app.get("/api/user/apikey")
async def user_apikey_status(current_user: User = Depends(get_current_user)):
    return get_user_api_key_status(current_user.id)


@app.post("/api/user/apikey/validate")
async def user_apikey_validate(
    payload: ApiKeyRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        result = validate_user_api_key(payload.api_key, payload.provider_code or "dashscope")
    except TypeError:
        result = validate_user_api_key(payload.api_key)
    if result.get("ok"):
        return result
    return JSONResponse(result, status_code=validation_http_status(result))


@app.post("/api/user/apikey")
async def user_apikey_save(
    payload: ApiKeyRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    provider_code = payload.provider_code or "dashscope"
    try:
        validation = validate_user_api_key(payload.api_key, provider_code)
    except TypeError:
        validation = validate_user_api_key(payload.api_key)
    if not validation.get("ok"):
        return JSONResponse(validation, status_code=validation_http_status(validation))
    try:
        save_user_api_key(current_user.id, payload.api_key, validation=validation, provider_code=provider_code)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    log_audit(
        API_KEY_SAVED,
        user_id=current_user.id,
        email=current_user.email,
        ip=_client_ip(request),
        ua=_user_agent(request),
    )
    return {"ok": True, "validation": validation, **get_user_api_key_status(current_user.id)}


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


@app.get("/api/history/articles")
async def history_articles(
    status_filter: str = "all",
    query: str = "",
    current_user: User = Depends(get_current_user),
):
    status_value = (status_filter or "all").strip()
    if status_value not in {"all", "completed", "review", "failed"}:
        status_value = "all"
    articles = list_history_articles(current_user.id, status=status_value, query=(query or "").strip())
    return {"articles": articles, "summary": history_summary(articles)}


@app.get("/api/history/articles/{article_id}")
async def history_article_detail(
    article_id: str,
    current_user: User = Depends(get_current_user),
):
    articles = list_history_articles(current_user.id)
    article = next((item for item in articles if str(item.get("id")) == str(article_id)), None)
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="History article not found")
    return article


@app.get("/api/kb/list")
async def kb_list(current_user: User = Depends(get_current_user)):
    return list_knowledge_bases(current_user.id)


@app.post("/api/kb/create")
async def kb_create(
    label: str = Form(...),
    slug: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    try:
        created = create_knowledge_base(current_user.id, label.strip(), slug.strip() or None)
        return {"ok": True, "slug": created}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/kb/delete")
async def kb_delete(
    slug: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    try:
        delete_knowledge_base(current_user.id, slug)
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
    if not mysql_enabled():
        vs = _get_vs(slug)
        sources = vs.list_sources()
        count = vs.get_collection_count()
        return {"sources": sources, "chunk_count": count, "source_count": len(sources)}
    inspector = VectorStore(kb_slug=slug, create_collection=False)
    collection_exists = inspector.collection_exists()
    vs = _get_vs(slug)
    count = vs.get_collection_count() if collection_exists else 0
    metadata_summary = vs.knowledge_metadata_summary() if collection_exists else {"source_ids": [], "chunk_keys": []}
    return list_source_stats(current_user.id, slug, collection_exists, count, metadata_summary)


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
        fname = _safe_filename(f.filename or getattr(f, "name", "unknown"))
        ext = os.path.splitext(fname)[1].lower()
        if not is_supported_kb_extension(ext):
            results.append({
                "file": fname,
                "ok": False,
                "error": f"不支持的文件类型: {ext or '(无扩展名)'}",
                "unsupported_format": True,
            })
            continue
        save_path = os.path.join(config.HISTORICAL_DIR, fname)
        content = await f.read()
        _raise_if_upload_too_large(content)
        with open(save_path, "wb") as out:
            out.write(content)
        try:
            parsed = path_to_parsed_document(save_path, original_name=fname)
            artifact_info: dict[str, object] = {}
            source_record: dict[str, object] | None = None
            if mysql_enabled():
                try:
                    source_artifact = put_file(
                        save_path,
                        owner_user_id=current_user.id,
                        artifact_type="uploaded_source",
                        original_filename=fname,
                        content_type=f.content_type,
                        metadata={"slug": slug},
                    )
                    parsed_artifact = put_bytes(
                        _parsed_document_markdown(parsed),
                        owner_user_id=current_user.id,
                        artifact_type="source_markdown",
                        original_filename=f"{os.path.splitext(fname)[0]}.md",
                        content_type="text/markdown; charset=utf-8",
                        metadata={"slug": slug, "source_filename": fname},
                    )
                    artifact_info = {
                        "artifact_id": source_artifact.artifact_uuid,
                        "parsed_artifact_id": parsed_artifact.artifact_uuid,
                    }
                    source_record = upsert_knowledge_source(
                        current_user.id,
                        slug,
                        fname,
                        original_artifact_uuid=source_artifact.artifact_uuid,
                        parsed_artifact_uuid=parsed_artifact.artifact_uuid,
                        content_type=f.content_type,
                        byte_size=len(content),
                        status="uploaded",
                        metadata={"slug": slug},
                    )
                except Exception:
                    logger.exception("Failed to store KB upload artifacts")
            chunks = _chunker.chunk(parsed)
            if source_record:
                for index, chunk in enumerate(chunks):
                    chunk.metadata["knowledge_base_id"] = int(source_record["knowledge_base_id"])
                    chunk.metadata["knowledge_source_id"] = int(source_record["id"])
                    if source_record.get("vector_collection_id") is not None:
                        chunk.metadata["vector_collection_id"] = int(source_record["vector_collection_id"])
                    chunk.metadata["knowledge_chunk_key"] = f"{source_record['id']}:{index}"
            vs.add_documents(chunks)
            if source_record:
                replace_source_chunks(
                    int(source_record["id"]),
                    int(source_record["knowledge_base_id"]),
                    int(source_record["vector_collection_id"]) if source_record.get("vector_collection_id") else None,
                    chunks,
                )
            log_audit(
                FILE_UPLOADED,
                user_id=current_user.id,
                email=current_user.email,
                ip=_client_ip(request),
                ua=_user_agent(request),
                detail={"filename": fname, "chunks": len(chunks)},
            )
            results.append({"file": fname, "ok": True, "chunks": len(chunks), **artifact_info})
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
    removal = remove_source(current_user.id, slug, source)
    if removal and removal.get("source_id"):
        vs.delete_by_source(source, int(removal["source_id"]))
    else:
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
    vision_model: str = Form(""),
    planner_model: str = Form(""),
    force_refresh: bool = Form(True),
    current_user: User = Depends(get_current_user),
):
    fname = _safe_filename(file.filename or getattr(file, "name", "unknown"))
    save_path = os.path.join(config.TEMPLATE_DIR, fname)
    content = await file.read()
    _raise_if_upload_too_large(content)
    os.makedirs(config.TEMPLATE_DIR, exist_ok=True)
    with open(save_path, "wb") as out:
        out.write(content)
    try:
        selected_model = _resolve_vision_model(vision_model, current_user.id)
        selected_planner_model = _resolve_template_planner_model(planner_model, current_user.id)
        result = _analyze_template_now(
            save_path,
            current_user,
            vision_model=selected_model,
            planner_model=selected_planner_model,
            force_refresh=force_refresh,
        )
        if mysql_enabled() and isinstance(result, dict) and result.get("ok", True):
            try:
                template_artifact = put_file(
                    save_path,
                    owner_user_id=current_user.id,
                    artifact_type="uploaded_source",
                    original_filename=fname,
                    content_type=file.content_type,
                    metadata={"surface": "template_analyze"},
                )
                preview_ids: list[str] = []
                bundle = cache_bundle_dir(save_path)
                if os.path.isdir(bundle):
                    for preview_name in sorted(os.listdir(bundle)):
                        if preview_name.lower().endswith(".png"):
                            preview_artifact = put_file(
                                os.path.join(bundle, preview_name),
                                owner_user_id=current_user.id,
                                artifact_type="preview_image",
                                original_filename=preview_name,
                                content_type="image/png",
                                metadata={"template": fname},
                            )
                            preview_ids.append(preview_artifact.artifact_uuid)
                result["artifact_id"] = template_artifact.artifact_uuid
                result["preview_artifact_ids"] = preview_ids
            except Exception:
                logger.exception("Failed to store template analysis artifacts")
        return result
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/template/reanalyze")
async def template_reanalyze(
    template: str = Form(...),
    vision_model: str = Form(""),
    planner_model: str = Form(""),
    current_user: User = Depends(get_current_user),
):
    save_path = _template_path_for_name(template)
    if not os.path.isfile(save_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    try:
        selected_model = _resolve_vision_model(vision_model, current_user.id)
        selected_planner_model = _resolve_template_planner_model(planner_model, current_user.id)
        return _analyze_template_now(
            save_path,
            current_user,
            vision_model=selected_model,
            planner_model=selected_planner_model,
            force_refresh=True,
        )
    except HTTPException:
        raise
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.post("/api/template/delete")
async def template_delete(
    template: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    save_path = _template_path_for_name(template)
    if not os.path.isfile(save_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="模板不存在")
    _clear_template_caches(save_path)
    os.remove(save_path)
    return {"ok": True, "template": os.path.basename(save_path)}


# ---------------------------------------------------------------------------
# 生成 API（会话 + SSE）
# ---------------------------------------------------------------------------
@app.post("/api/generate/sessions")
async def generate_session_start(
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
    try:
        session = _start_generation_session(
            current_user,
            _build_generation_params(
                slug,
                template,
                word_limit,
                top_k,
                max_distance,
                enable_web,
                use_stream,
                enable_audit,
                enable_visual_audit,
                custom_instructions,
            ),
        )
    except ActiveGenerationExistsError as exc:
        return JSONResponse(
            {
                "ok": False,
                "code": "active_generation_exists",
                "message": "当前已有一个正在进行的生成任务，请先返回查看该任务。",
                "session_id": exc.session_id,
                **_serialize_session(session_manager.get_session_for_user(current_user.id, exc.session_id)),
            },
            status_code=409,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            {
                "ok": False,
                "code": "request_blocked",
                "message": detail,
            },
            status_code=exc.status_code,
        )
    return {
        "ok": True,
        "session_id": session.session_id,
        **_serialize_session(session),
    }


@app.get("/api/generate/sessions/active")
async def generate_session_active(current_user: User = Depends(get_current_user)):
    session = session_manager.get_active_session(current_user.id) or session_manager.get_latest_session(current_user.id)
    return _serialize_session(session)


@app.get("/api/generate/sessions/{session_id}")
async def generate_session_snapshot(
    session_id: str,
    current_user: User = Depends(get_current_user),
):
    session = _ensure_session_owned(session_id, current_user)
    return _serialize_session(session)


@app.get("/api/generate/sessions/{session_id}/stream")
async def generate_session_stream(
    session_id: str,
    after_seq: int = 0,
    current_user: User = Depends(get_current_user),
):
    session = _ensure_session_owned(session_id, current_user)

    def event_stream():
        for event in session.stream_events(after_seq=after_seq):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
    try:
        session = _start_generation_session(
            current_user,
            _build_generation_params(
                slug,
                template,
                word_limit,
                top_k,
                max_distance,
                enable_web,
                use_stream,
                enable_audit,
                enable_visual_audit,
                custom_instructions,
            ),
        )
    except ActiveGenerationExistsError as exc:
        active = session_manager.get_session_for_user(current_user.id, exc.session_id)
        return JSONResponse(
            {
                "ok": False,
                "code": "active_generation_exists",
                "message": "当前已有一个正在进行的生成任务，请先返回查看该任务。",
                "session_id": exc.session_id,
                **_serialize_session(active),
            },
            status_code=409,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            {
                "ok": False,
                "code": "request_blocked",
                "message": detail,
            },
            status_code=exc.status_code,
        )

    def event_stream():
        for event in session.stream_events(after_seq=0):
            yield _sse(event)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


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
    # 校验文件归属：文件名包含 _u{user_id}_ 时只允许本人下载
    import re as _re
    owner_match = _re.search(r'_u(\d+)_', filename)
    if owner_match and int(owner_match.group(1)) != current_user.id:
        return JSONResponse({"error": "无权访问该文件"}, status_code=403)
    media_type, _ = mimetypes.guess_type(path)
    return FileResponse(
        path,
        filename=filename,
        media_type=media_type
        or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


@app.get("/api/artifacts/{artifact_uuid}/download")
async def download_artifact(
    artifact_uuid: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    artifact = get_artifact_for_user(artifact_uuid, current_user.id)
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    try:
        path, should_cleanup = materialize_artifact(artifact)
    except ArtifactNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file is missing") from exc
    except ArtifactError as exc:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=str(exc)) from exc
    if should_cleanup:
        background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(
        path,
        filename=artifact.original_filename,
        media_type=artifact.content_type or "application/octet-stream",
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
    if mysql_enabled():
        with mysql_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS count FROM users")
                total_users = int(cur.fetchone()["count"] or 0)
                cur.execute("SELECT COUNT(*) AS count FROM billing_records")
                total_generations = int(cur.fetchone()["count"] or 0)
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(cost_cny), 0) AS cost,
                        COALESCE(SUM(input_tokens), 0) AS input_tokens,
                        COALESCE(SUM(output_tokens), 0) AS output_tokens
                    FROM billing_records
                    """
                )
                totals = cur.fetchone()
                total_cost = float(totals["cost"] or 0)
                total_input = int(totals["input_tokens"] or 0)
                total_output = int(totals["output_tokens"] or 0)
                cur.execute(
                    """
                    SELECT DATE(created_at) AS day, COUNT(*) AS gens, SUM(cost_cny) AS cost,
                           SUM(input_tokens) AS inp, SUM(output_tokens) AS outp
                    FROM billing_records
                    WHERE created_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY)
                    GROUP BY DATE(created_at)
                    ORDER BY day
                    """
                )
                daily_rows = cur.fetchall()
                cur.execute(
                    """
                    SELECT model, COUNT(*) AS cnt, SUM(cost_cny) AS cost
                    FROM billing_records
                    GROUP BY model
                    ORDER BY cnt DESC
                    LIMIT 5
                    """
                )
                model_rows = cur.fetchall()
                cur.execute("SELECT COUNT(*) AS count FROM provider_credentials WHERE owner_user_id IS NOT NULL")
                users_with_key = int(cur.fetchone()["count"] or 0)
        return {
            "total_users": total_users,
            "total_generations": total_generations,
            "total_cost_cny": round(total_cost, 4),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "users_with_api_key": users_with_key,
            "daily": [
                {
                    "day": str(r["day"]),
                    "generations": int(r["gens"] or 0),
                    "cost": round(float(r["cost"] or 0), 4),
                    "input_tokens": int(r["inp"] or 0),
                    "output_tokens": int(r["outp"] or 0),
                }
                for r in daily_rows
            ],
            "top_models": [
                {"model": r["model"], "count": int(r["cnt"] or 0), "cost": round(float(r["cost"] or 0), 4)}
                for r in model_rows
            ],
        }
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
        candidate = os.path.normpath(os.path.join(FRONTEND_DIST_DIR, full_path))
        dist_dir = os.path.normpath(FRONTEND_DIST_DIR)
        if not candidate.startswith(dist_dir + os.sep) and candidate != dist_dir:
            return JSONResponse({"error": "not found"}, status_code=404)
        if os.path.isfile(candidate):
            media_type, _ = mimetypes.guess_type(candidate)
            return FileResponse(candidate, media_type=media_type)

    if not _should_serve_spa(full_path):
        return JSONResponse({"error": "not found"}, status_code=404)

    return FileResponse(_spa_index_path(), media_type="text/html")


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    print("启动服务器: http://localhost:8502")
    uvicorn.run(app, host="0.0.0.0", port=8502)
