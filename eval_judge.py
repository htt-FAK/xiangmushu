import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import config
from core.dashscope_chat import prepare_raw_chat_body


PASS_THRESHOLD = 80


def _ordered_models(*models: str) -> list[str]:
    out: list[str] = []
    seen = set()
    for model in models:
        mid = (model or "").strip()
        if not mid or mid in seen:
            continue
        seen.add(mid)
        out.append(mid)
    return out


VISION_MODELS = _ordered_models(
    config.VISUAL_AUDIT_MODEL,
    getattr(config, "VISUAL_AUDIT_FALLBACK_MODEL", ""),
)

TEXT_MODELS = _ordered_models(
    config.AUDIT_LLM_MODEL,
    getattr(config, "AUDIT_FALLBACK_1", ""),
    getattr(config, "AUDIT_FALLBACK_2", ""),
    getattr(config, "AUDIT_FALLBACK_3", ""),
)


def _read_deepseek_tui_key() -> str:
    config_path = Path.home() / ".deepseek" / "config.toml"
    if not config_path.exists():
        return ""
    text = config_path.read_text(encoding="utf-8", errors="ignore")
    current_section = ""
    top_level_key = ""
    openai_key = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line.strip("[]")
            continue
        match = re.match(r'api_key\s*=\s*"(ak-[^"]+)"', line)
        if not match:
            continue
        key = match.group(1)
        if not current_section and not top_level_key:
            top_level_key = key
        if current_section == "providers.openai":
            openai_key = key
    return top_level_key or openai_key


def _api_key() -> str:
    return (
        os.environ.get("EVAL_JUDGE_API_KEY")
        or os.environ.get("DASHSCOPE_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or _read_deepseek_tui_key()
        or getattr(config, "OPENAI_COMPAT_API_KEY", "")
    )


def _base_url() -> str:
    return os.environ.get("EVAL_JUDGE_BASE_URL") or getattr(config, "OPENAI_BASE_URL", "")


def _extract_content(data: dict[str, Any]) -> str:
    try:
        return ((data.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    except AttributeError:
        return ""


def _request_once(body: dict[str, Any], headers: dict[str, str]) -> tuple[str, str]:
    base_url = _base_url().rstrip("/")
    request_body = prepare_raw_chat_body(base_url, body)
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return "", str(exc)
    return _extract_content(data).strip(), ""


def _call_model(model: str, prompt: str, image_path: Path | None = None) -> tuple[str, str]:
    key = _api_key()
    if not key:
        return "", "missing judge api key"

    user_content: Any = prompt
    if image_path is not None and image_path.exists():
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        user_content = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded}"}},
        ]

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a strict software test judge. Return JSON only."},
            {"role": "user", "content": user_content},
        ],
        "temperature": 0,
        "max_tokens": 512,
    }
    auth_variants = [
        {"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        {"Content-Type": "application/json", "api-key": key},
    ]
    errors = []
    for headers in auth_variants:
        content, error = _request_once(body, headers)
        if content or not error:
            return content, error
        errors.append(error)
        if "401" not in error and "Unauthorized" not in error:
            break
    return "", " | ".join(errors)


def _parse_judge_json(content: str) -> dict[str, Any] | None:
    match = re.search(r"\{.*\}", content, re.S)
    raw = match.group(0) if match else content
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def judge_payload(payload: dict[str, Any], target: str, screenshot_path: Path | None = None) -> dict[str, Any]:
    prompt = (
        f"Judge this {target} automated test result. Score 0-100. "
        "Return JSON with fields: score, passed, summary. "
        f"Passing threshold is {PASS_THRESHOLD}. "
        "If pytest/function assertions passed but visual/model judging is uncertain, explain that clearly.\n"
        + json.dumps(payload, ensure_ascii=False)
    )

    candidates: list[tuple[str, str, Path | None]] = []
    if target == "ui" and screenshot_path is not None and screenshot_path.exists():
        candidates.extend((model, "vision", screenshot_path) for model in VISION_MODELS)
    candidates.extend((model, "text", None) for model in TEXT_MODELS)

    attempts = []
    for model, modality, image in candidates:
        for attempt in range(1, 3):
            content, error = _call_model(model, prompt, image)
            attempts.append(
                {
                    "model": model,
                    "modality": modality,
                    "attempt": attempt,
                    "error": error,
                    "empty": not bool(content),
                }
            )
            if error or not content:
                continue
            parsed = _parse_judge_json(content)
            if parsed is None:
                attempts[-1]["parse_error"] = True
                attempts[-1]["raw_preview"] = content[:200]
                continue
            score = int(float(parsed.get("score", 0) or 0))
            return {
                "score": score,
                "passed": score >= PASS_THRESHOLD,
                "status": "judge_ok",
                "summary": str(parsed.get("summary", "")),
                "raw": content,
                "model": model,
                "modality": modality,
                "attempts": attempts,
            }

    return {
        "score": None,
        "passed": None,
        "status": "judge_unavailable",
        "summary": "all configured judge models failed or returned empty/non-json content",
        "raw": "",
        "attempts": attempts,
    }
