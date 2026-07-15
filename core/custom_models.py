"""
Multi-Custom-Models — user-configured OpenAI-compatible models for text, vision and embedding.

Public interface
----------------
- ``list_custom_models(user_id)``              GET /api/user/custom-models
- ``create_custom_model(user_id, ...)``        POST /api/user/custom-models
- ``get_custom_model(user_id, model_id)``      used by server for lookups
- ``update_custom_model(user_id, model_id, ..)`` PUT /api/user/custom-models/{id}
- ``delete_custom_model(user_id, model_id)``   DELETE /api/user/custom-models/{id}
- ``assign_model_roles(user_id, model_id, ..)`` POST /api/user/custom-models/{id}/assign
- ``test_model_capabilities(user_id, model_id, test_types)`` POST /api/user/custom-models/{id}/test
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import openai

from core.billing import decrypt_api_key, encrypt_api_key
from core.custom_audit import _build_key_hint, validate_base_url
from core.db import (
    create_custom_model as _db_create,
    delete_custom_model as _db_delete,
    get_custom_model_by_id as _db_get_by_id,
    get_custom_models_by_role as _db_by_role,
    get_custom_models_by_user as _db_by_user,
    update_custom_model as _db_update,
)

_LOG = logging.getLogger(__name__)

# Max models a single user may configure (Task 5.4).
MAX_MODELS_PER_USER = 20

# Allowed role identifiers.
ALLOWED_ROLES = ("text-gen", "vision", "embedding", "audit", "small-llm")

# Hardcoded 10×10 solid-cyan PNG (~100 bytes) for vision probe.
# Generated once offline and embedded to avoid external image fetch.
_TEST_IMAGE_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAoAAAAKCAYAAACNMs+9AAAA"
    "BmJLR0QA/wD/AP+gvaeTAAAAJklEQVQYV2P8//8/A"
    "31gGKzCgF8hAx5FjKMK8CtkHFWAXyEAAP1lFf2Q7Y0"
    "AAAAASUVORK5CYII="
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _to_dict(row: Any) -> Dict[str, Any]:
    """Map a ``CustomModel`` dataclass from db.py to the API-facing dict shape."""
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "base_url": row.base_url,
        "model_id": row.model_id,
        "default_model_id": row.default_model_id,
        "capabilities": row.capabilities_json or [],
        "assigned_roles": row.assigned_roles_json or [],
        "status": row.status,
        "last_tested_at": row.last_tested_at,
        "last_error": row.last_error,
        "api_key_preview": row.api_key_hint or "****",
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def _openai_client(base_url: str, api_key: str, timeout: float) -> openai.OpenAI:
    """Build an OpenAI SDK client with normalised URL."""
    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url = url + "/v1" if not url.endswith("/") else url + "v1"
    return openai.OpenAI(api_key=api_key, base_url=url, timeout=timeout, max_retries=0)


# ── List ──────────────────────────────────────────────────────────────────────


def list_custom_models(user_id: int) -> List[Dict[str, Any]]:
    """Return ``{"models": [...]}`` shape for a user — newest first."""
    rows = _db_by_user(user_id)
    return [_to_dict(r) for r in rows]


def get_custom_model_count(user_id: int) -> int:
    """Return the number of custom models for a user (for limit check)."""
    return len(_db_by_user(user_id))


# ── Get single ────────────────────────────────────────────────────────────────


def get_custom_model(user_id: int, model_id: int) -> Optional[Dict[str, Any]]:
    row = _db_get_by_id(model_id, user_id)
    return _to_dict(row) if row else None


def get_model_row(user_id: int, model_id: int) -> Any:
    """Return the raw ``CustomModel`` dataclass for internal use (decryption, etc.)."""
    return _db_get_by_id(model_id, user_id)


# ── Create ────────────────────────────────────────────────────────────────────


def create_custom_model(
    *,
    user_id: int,
    name: str,
    base_url: str,
    model_id: str,
    api_key: str,
    default_model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a model after validation. Raises ``ValueError`` with ``code`` attribute on failure."""
    if not name.strip():
        raise _ModelError("name_required", "Model name is required.")
    if not base_url.strip():
        raise _ModelError("url_format", "Base URL is required.")
    if not model_id.strip():
        raise _ModelError("model_id_required", "Model ID is required.")
    if not api_key or len(api_key) < 8:
        raise _ModelError("api_key_length", "API key must be at least 8 characters.")

    # SSRF guard (cheap synchronous check, no DB/network calls).
    err_kind, err_detail = validate_base_url(base_url)
    if err_kind:
        raise _ModelError(err_kind, err_detail or "Invalid base URL.")

    # Limit enforcement (DB-dependent — after SSRF to avoid wasted API calls).
    if get_custom_model_count(user_id) >= MAX_MODELS_PER_USER:
        raise _ModelError(
            "limit_exceeded",
            f"Maximum {MAX_MODELS_PER_USER} custom models allowed.",
        )

    # Determine default_model_id: first comma-separated entry when not provided.
    if not default_model_id:
        default_model_id = model_id.split(",")[0].strip()

    encrypted = encrypt_api_key(api_key)
    api_key_hint = _build_key_hint(api_key)

    row = _db_create(
        user_id=user_id,
        name=name.strip(),
        base_url=base_url.strip(),
        model_id=model_id.strip(),
        encrypted_api_key=encrypted,
        api_key_hint=api_key_hint,
        capabilities_json=[],
        assigned_roles_json=[],
        default_model_id=default_model_id.strip(),
        status="untested",
    )
    return _to_dict(row)


# ── Update ────────────────────────────────────────────────────────────────────


def update_custom_model(
    *,
    user_id: int,
    model_id: int,
    **fields: Any,
) -> Optional[Dict[str, Any]]:
    """Partial update. Returns updated dict or None if not found."""
    # Normalise field names: accept ``capabilities`` → ``capabilities_json`` etc.
    remapped: Dict[str, Any] = {}
    connection_changed = False

    for key, value in fields.items():
        if value is None:
            continue
        if key == "capabilities":
            remapped["capabilities_json"] = value
        elif key == "assigned_roles":
            remapped["assigned_roles_json"] = value
        else:
            if key in ("base_url", "model_id", "api_key"):
                connection_changed = True
            if key == "api_key":
                remapped["encrypted_api_key"] = encrypt_api_key(value)
                remapped["api_key_hint"] = _build_key_hint(value)
            else:
                remapped[key] = value

    # If capabilities are manually overridden, flip status → 'override'.
    if "capabilities" in fields and fields["capabilities"] is not None:
        remapped["status"] = "override"

    if not remapped:
        row = _db_get_by_id(model_id, user_id)
        return _to_dict(row) if row else None

    row = _db_update(model_id, user_id, **remapped)
    return _to_dict(row) if row else None


def needs_probe(user_id: int, model_id: int, fields: Dict[str, Any]) -> bool:
    """Return True if an update changes connection-level fields (base_url/model_id/api_key)."""
    return any(k in fields and fields[k] is not None for k in ("base_url", "model_id", "api_key"))


# ── Delete ────────────────────────────────────────────────────────────────────


def delete_custom_model(*, user_id: int, model_id: int) -> bool:
    return _db_delete(model_id, user_id)


# ── Assign roles ──────────────────────────────────────────────────────────────


def assign_model_roles(
    *,
    user_id: int,
    model_id: int,
    assigned_roles: List[str],
    default_model_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Assign roles to a custom model (Task 2.11).

    Returns ``(updated_dict, warnings)`` where ``warnings`` is a list of
    strings for roles assigned without a matching tested capability.
    """
    # Validate roles.
    invalid = [r for r in assigned_roles if r not in ALLOWED_ROLES]
    if invalid:
        raise _ModelError(
            "invalid_role",
            f"Unsupported role(s): {', '.join(invalid)}. Allowed: {', '.join(ALLOWED_ROLES)}",
        )

    row = _db_get_by_id(model_id, user_id)
    if not row:
        return None

    capabilities = row.capabilities_json or []

    warnings: List[str] = []
    role_cap_map = {
        "text-gen": "text",
        "vision": "vision",
        "embedding": "embedding",
    }
    for role in assigned_roles:
        needed_cap = role_cap_map.get(role)
        if needed_cap and needed_cap not in capabilities:
            warnings.append(
                f"{role} role assigned but model has not been tested for {needed_cap} capability"
            )

    update_fields: Dict[str, Any] = {"assigned_roles_json": assigned_roles}
    if default_model_id:
        update_fields["default_model_id"] = default_model_id.strip()

    updated = _db_update(model_id, user_id, **update_fields)
    return _to_dict(updated) if updated else None


# ── Capability testing (Tasks 2.5–2.9) ───────────────────────────────────────


async def test_model_capabilities(
    *,
    user_id: int,
    model_id: int,
    test_types: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run capability probes for text / vision / embedding.

    Returns a dict matching the ``POST /api/user/custom-models/{id}/test`` response schema.
    """
    row = _db_get_by_id(model_id, user_id)
    if not row:
        raise _ModelError("not_found", "Model not found or does not belong to this user.")

    api_key = decrypt_api_key(row.encrypted_api_key)
    base_url = row.base_url
    default_model_id = row.default_model_id or row.model_id

    # Default: run all three.
    if not test_types:
        test_types = ["text", "vision", "embedding"]

    test_results: Dict[str, Dict[str, Any]] = {}
    capabilities: List[str] = []
    first_error: Optional[str] = None
    auth_failed = False

    # Sequential execution (spec: respect rate limits).
    for ttype in test_types:
        if ttype == "text":
            result = await _probe_text(base_url, api_key, default_model_id)
        elif ttype == "vision":
            result = await _probe_vision(base_url, api_key, default_model_id)
        elif ttype == "embedding":
            result = await _probe_embedding(base_url, api_key, default_model_id)
        else:
            result = {"passed": False, "latency_ms": 0, "detail": f"Unknown test type: {ttype}"}

        test_results[ttype] = result

        if result["passed"]:
            capabilities.append(ttype)
        elif result.get("auth_error"):
            # Per spec: auth failure rejects the entire test with 422.
            auth_failed = True
            first_error = result["detail"]
            break
        else:
            if first_error is None:
                first_error = f"{ttype}: {result['detail']}"

    if auth_failed:
        raise _ModelError("auth", "API key is invalid or expired. Please update the model configuration.")

    # Persist tested capabilities.
    now = datetime.now(timezone.utc).isoformat()
    update_kwargs: Dict[str, Any] = {
        "capabilities_json": capabilities,
        "status": "tested" if capabilities else "untested",
        "last_tested_at": now,
    }
    if first_error:
        update_kwargs["last_error"] = first_error

    updated_row = _db_update(model_id, user_id, **update_kwargs)
    row_data = _to_dict(updated_row) if updated_row else _to_dict(row)

    return {
        "id": model_id,
        "capabilities": capabilities,
        "status": row_data["status"],
        "last_tested_at": now,
        "last_error": first_error,
        "suggested_roles": suggest_roles(capabilities, row.name, row.model_id),
        "test_results": test_results,
    }


# ── Individual probes (Tasks 2.7, 2.8, 2.9) ─────────────────────────────────


async def _probe_text(base_url: str, api_key: str, model_id: str) -> Dict[str, Any]:
    """Task 2.7 — text capability probe."""
    started = time.monotonic()
    try:
        client = _openai_client(base_url, api_key, timeout=30.0)
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Say hello in one sentence."}],
            max_tokens=50,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return {"passed": False, "latency_ms": _ms(started), "detail": "empty response"}
        _LOG.debug("text probe ok model=%s latency=%dms", model_id, _ms(started))
        return {"passed": True, "latency_ms": _ms(started), "detail": None}
    except Exception as exc:
        detail, is_auth = _classify_probe_error(exc)
        return {
            "passed": False,
            "latency_ms": _ms(started),
            "detail": detail,
            "auth_error": is_auth,
        }


async def _probe_vision(base_url: str, api_key: str, model_id: str) -> Dict[str, Any]:
    """Task 2.8 — vision capability probe with embedded test image."""
    started = time.monotonic()
    try:
        client = _openai_client(base_url, api_key, timeout=60.0)
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Describe the color of this image in one word."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{_TEST_IMAGE_B64}"},
                        },
                    ],
                }
            ],
            max_tokens=30,
            temperature=0,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            return {"passed": False, "latency_ms": _ms(started), "detail": "empty response"}
        _LOG.debug("vision probe ok model=%s latency=%dms", model_id, _ms(started))
        return {"passed": True, "latency_ms": _ms(started), "detail": None}
    except Exception as exc:
        detail, is_auth = _classify_probe_error(exc)
        # Model may reject image input with a 400/422.
        if "image" in detail.lower() or "vision" in detail.lower() or "multimodal" in detail.lower():
            detail = "model does not support image input"
        return {
            "passed": False,
            "latency_ms": _ms(started),
            "detail": detail,
            "auth_error": is_auth,
        }


async def _probe_embedding(base_url: str, api_key: str, model_id: str) -> Dict[str, Any]:
    """Task 2.9 — embedding capability probe with fallback name variants."""
    started = time.monotonic()

    # Candidate model IDs: primary + text-embedding- prefixed variants.
    candidates = [model_id]
    if not model_id.startswith("text-embedding"):
        candidates.append(f"text-embedding-{model_id}")

    last_detail = ""
    for candidate in candidates:
        try:
            client = _openai_client(base_url, api_key, timeout=30.0)
            response = client.embeddings.create(
                model=candidate,
                input="Test embedding for capability detection.",
            )
            if response.data and response.data[0].embedding and len(response.data[0].embedding) > 0:
                _LOG.debug("embedding probe ok model=%s latency=%dms", candidate, _ms(started))
                return {"passed": True, "latency_ms": _ms(started), "detail": None}
            last_detail = "empty embedding array"
        except Exception as exc:
            detail, is_auth = _classify_probe_error(exc)
            if is_auth:
                # Auth error is terminal — no point trying fallback variants.
                return {
                    "passed": False,
                    "latency_ms": _ms(started),
                    "detail": detail,
                    "auth_error": True,
                }
            last_detail = detail

    return {
        "passed": False,
        "latency_ms": _ms(started),
        "detail": last_detail or "endpoint /embeddings returned 404",
    }


# ── Role suggestion (Task 2.10) ──────────────────────────────────────────────


def suggest_roles(
    capabilities: List[str], model_name: str = "", model_id: str = ""
) -> List[str]:
    """Compute advisory role list from detected capabilities.

    Order: text-gen, vision, embedding, audit, small-llm.
    """
    suggestions: List[str] = []
    name_lower = (model_name or "").lower()
    id_lower = (model_id or "").lower()

    if "text" in capabilities:
        suggestions.append("text-gen")
        # Heuristic: full-cap LLM → also suggest audit.
        if any(token in name_lower or token in id_lower for token in ("qwen", "gpt", "claude", "deepseek")):
            suggestions.append("audit")
        # Heuristic: lightweight model → suggest small-llm.
        if any(token in id_lower for token in ("small", "mini", "turbo", "flash", "nano")):
            suggestions.append("small-llm")

    if "vision" in capabilities:
        suggestions.append("vision")
    if "embedding" in capabilities:
        suggestions.append("embedding")

    # Re-sort using spec confidence order.
    order = ["text-gen", "vision", "embedding", "audit", "small-llm"]
    suggestions.sort(key=lambda r: order.index(r) if r in order else 99)
    return suggestions


# ── Internal helpers ──────────────────────────────────────────────────────────


def _ms(started: float) -> int:
    return int((time.monotonic() - started) * 1000)


def _classify_probe_error(exc: BaseException) -> tuple[str, bool]:
    """Return ``(detail, is_auth)``. ``is_auth=True`` signals 401/403."""
    msg = str(exc).lower()
    # OpenAI SDK raises API errors with ``.status_code`` attribute.
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return "API key is invalid or expired. Please update the model configuration.", True
    if "authentication" in msg or "unauthorized" in msg or "invalid_api_key" in msg:
        return "API key is invalid or expired. Please update the model configuration.", True
    if "timeout" in msg or "timed out" in msg:
        return "connection timeout", False
    if "connection" in msg or "network" in msg:
        return "network error", False
    if "model_not_found" in msg or "does not exist" in msg:
        return "model not found", False
    return str(exc)[:200], False


class _ModelError(ValueError):
    """Typed error for create/update/test operations."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)
