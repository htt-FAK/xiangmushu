"""
FastAPI 后端 — 为 HTML 前端提供 REST + SSE 接口
运行: python server.py  →  http://localhost:8502
"""
from __future__ import annotations

import json
import logging
import mimetypes
import os
from dataclasses import asdict

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from core.auth import (
    AuthError,
    InvalidCodeError,
    InvalidEmailError,
    InvalidPasswordError,
    InvalidTokenError,
    User,
    consume_verification_code,
    create_access_token,
    create_verification_code,
    get_or_create_user,
    init_db,
    send_verification_email,
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


class ApiKeyRequest(BaseModel):
    api_key: str


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


@app.on_event("startup")
async def startup_auth_db() -> None:
    init_db()

# ---------------------------------------------------------------------------
# 缓存实例（模拟 st.cache_resource）
# ---------------------------------------------------------------------------
_vs_cache: dict[str, VectorStore] = {}
_chunker = Chunker()
_analyzer = TemplateAnalyzer()
_filler = WordFiller()


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
    return os.path.join(STATIC_DIR, "index.html")


if os.path.isdir(FRONTEND_ASSETS_DIR):
    app.mount("/assets", StaticFiles(directory=FRONTEND_ASSETS_DIR), name="frontend-assets")


@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(_spa_index_path(), media_type="text/html")


# ---------------------------------------------------------------------------
# 知识库 API
# ---------------------------------------------------------------------------
@app.post("/api/auth/request-code")
async def auth_request_code(payload: EmailRequest):
    try:
        verification = create_verification_code(payload.email, password=payload.password)
        send_verification_email(verification.email, verification.code)
        return {"ok": True, "email": verification.email, "expires_at": verification.expires_at}
    except (InvalidEmailError, InvalidPasswordError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except AuthError as exc:
        logger.exception("Failed to request verification code")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@app.post("/api/auth/verify-code")
async def auth_verify_code(payload: VerifyCodeRequest):
    try:
        user = consume_verification_code(payload.email, payload.code, payload.password)
        token = create_access_token(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "email": user.email},
        }
    except (InvalidEmailError, InvalidCodeError, InvalidPasswordError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@app.post("/api/auth/login")
async def auth_login(payload: LoginRequest):
    """Login with email + password only (no verification code needed)."""
    try:
        user = get_or_create_user(payload.email)
        if not verify_password(payload.password, _get_password_hash(user.email)):
            raise InvalidPasswordError("Email or password is incorrect")
        token = create_access_token(user)
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {"id": user.id, "email": user.email},
        }
    except InvalidPasswordError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    except AuthError as exc:
        logger.exception("Login failed")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc


@app.get("/api/auth/me")
async def auth_me(current_user: User = Depends(get_current_user)):
    return {"id": current_user.id, "email": current_user.email}


@app.get("/api/user/apikey")
async def user_apikey_status(current_user: User = Depends(get_current_user)):
    return get_user_api_key_status(current_user.id)


@app.post("/api/user/apikey")
async def user_apikey_save(
    payload: ApiKeyRequest,
    current_user: User = Depends(get_current_user),
):
    try:
        save_user_api_key(current_user.id, payload.api_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return {"ok": True, **get_user_api_key_status(current_user.id)}


@app.delete("/api/user/apikey")
async def user_apikey_delete(current_user: User = Depends(get_current_user)):
    delete_user_api_key(current_user.id)
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
        with open(save_path, "wb") as out:
            out.write(content)
        try:
            parsed = path_to_parsed_document(save_path, original_name=fname)
            chunks = _chunker.chunk(parsed)
            vs.add_documents(chunks)
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
    with open(save_path, "wb") as out:
        out.write(content)
    try:
        tasks = _analyzer.analyze(save_path)
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
    current_user: User = Depends(get_current_user),
):
    vs = _get_vs(slug)
    template_path = os.path.join(config.TEMPLATE_DIR, template)
    if not os.path.isfile(template_path):
        return JSONResponse({"ok": False, "error": "模板不存在"}, status_code=400)

    # 分析模板
    try:
        tasks = _analyzer.analyze(template_path)
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
    generator = ContentGenerator(vs, api_key=user_api_key)
    auditor = ContentAuditor() if enable_audit else None

    def event_stream():
        results: list[str] = []
        traces = []
        billing_records = []
        for i, task in enumerate(tasks):
            if task.word_limit <= 0:
                task.word_limit = word_limit
            # 通知前端当前任务
            yield _sse({"type": "task", "index": i, "total": len(tasks), "chapter": task.target_chapter})

            try:
                gen_bundle = generator.prepare_generation_bundle(
                    task,
                    top_k=top_k,
                    enable_web=enable_web,
                    retrieval_max_distance=max_distance,
                )
                yield _sse(
                    {
                        "type": "route",
                        "index": i,
                        "model": gen_bundle.model,
                        "tier": gen_bundle.route_meta.get("generation_tier"),
                        "kb_hits": gen_bundle.route_meta.get("kb_hits", 0),
                        "evidence_refs": gen_bundle.evidence_refs[:5],
                    }
                )
                if use_stream:
                    acc: list[str] = []
                    for piece in generator.stream_from_bundle(gen_bundle, route_hook=None):
                        acc.append(piece)
                        yield _sse({"type": "chunk", "index": i, "text": piece})
                    content = "".join(acc).strip()
                else:
                    content = generator.generate_from_bundle(gen_bundle, route_hook=None)
                    yield _sse({"type": "chunk", "index": i, "text": content})
                billed_model, raw_usage = generator.pop_last_usage()
                billing_record = record_billing(
                    current_user.id,
                    billed_model or gen_bundle.model,
                    normalize_usage(raw_usage),
                )
                if billing_record is not None:
                    billing_records.append(billing_record)
                    yield _sse({"type": "billing", "index": i, "billing": billing_record})
            except Exception as e:
                content = f"（生成失败：{e}）"
                yield _sse({"type": "error", "index": i, "error": str(e)})
                results.append(content)
                traces.append(
                    build_generation_trace(
                        task,
                        {"model": "", "generation_tier": "error", "evidence_refs": []},
                        content,
                        audit_verdict="error",
                        audit_issues=[str(e)],
                    )
                )
                yield _sse({"type": "progress", "index": i, "total": len(tasks)})
                continue

            audit_issues = rule_audit(task, content, gen_bundle.route_meta)
            audit_verdict = "pass" if not audit_issues else "rule_issue"
            revised = False
            if auditor is not None and need_model_audit(task, gen_bundle.route_meta, audit_issues):
                ar = auditor.audit(
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
                    revised = True
            if audit_issues:
                yield _sse(
                    {
                        "type": "audit",
                        "index": i,
                        "verdict": audit_verdict,
                        "issues": audit_issues[:5],
                        "revised": revised,
                    }
                )

            results.append(content)
            traces.append(
                build_generation_trace(
                    task,
                    gen_bundle.route_meta,
                    content,
                    audit_verdict=audit_verdict,
                    audit_issues=audit_issues,
                    revised=revised,
                )
            )
            yield _sse({"type": "progress", "index": i, "total": len(tasks)})

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
    path = os.path.join(config.OUTPUT_DIR, filename)
    if not os.path.isfile(path):
        return JSONResponse({"error": "文件不存在"}, status_code=404)
    media_type, _ = mimetypes.guess_type(path)
    return FileResponse(
        path,
        filename=filename,
        media_type=media_type
        or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )


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
