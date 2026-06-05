"""Quick model connectivity check using the configured model chains."""

import openai

import config
from core.dashscope_chat import direct_chat_completions_create


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


api_key = config.OPENAI_COMPAT_API_KEY
base_url = config.OPENAI_BASE_URL

print("Testing model connectivity...")
print(f"API Key: {api_key[:10]}..." if api_key else "API Key: not configured")
print(f"Base URL: {base_url}")
print()

if not api_key:
    print("No API key configured in .env")
    raise SystemExit(1)

client = openai.OpenAI(api_key=api_key, base_url=base_url)

models_to_test = _ordered_models(
    config.LARGE_LLM_MODEL,
    getattr(config, "FALLBACK_LLM_MODEL_1", ""),
    getattr(config, "FALLBACK_LLM_MODEL_2", ""),
    getattr(config, "FALLBACK_LLM_MODEL_3", ""),
    config.SMALL_LLM_MODEL,
    getattr(config, "SMALL_LLM_FALLBACK_MODEL", ""),
    config.VISION_WEB_MODEL,
    getattr(config, "VISION_WEB_FALLBACK_MODEL", ""),
    config.VISUAL_AUDIT_MODEL,
    getattr(config, "VISUAL_AUDIT_FALLBACK_MODEL", ""),
)

for model in models_to_test:
    print(f"Testing model: {model}...", end=" ")
    try:
        direct_chat_completions_create(
            client,
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": 'Reply with "model connection ok"'},
            ],
            max_tokens=50,
            timeout=30,
        )
        print("OK")
    except Exception as e:
        error_msg = str(e)
        if "model" in error_msg.lower() and "not exist" in error_msg.lower():
            print("MODEL_NOT_FOUND")
        elif "authentication" in error_msg.lower():
            print("AUTH_FAILED")
        else:
            print(f"ERROR: {error_msg[:80]}")
