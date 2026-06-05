"""Simple connectivity checks for the currently configured model defaults."""

import config
from core.dashscope_chat import chat_completions_create


def test_model(client, model, name):
    print(f"\n{'=' * 50}")
    print(f"Testing {name} (model={model})")
    print("=" * 50)
    try:
        resp = chat_completions_create(
            client,
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Reply with: model ok"},
            ],
            temperature=0.1,
            stream=False,
            max_tokens=50,
        )
        content = resp.choices[0].message.content if resp.choices else ""
        print(f"OK: {content[:100]}")
        return True
    except Exception as e:
        print(f"FAIL: {e}")
        return False


print("\n" + "=" * 50)
print("Testing DashScope")
print("=" * 50)
dashscope_client = config.dashscope_backup_chat_client()
if dashscope_client:
    test_model(dashscope_client, config.LARGE_LLM_MODEL, f"DashScope {config.LARGE_LLM_MODEL}")
    test_model(dashscope_client, config.SMALL_LLM_MODEL, f"DashScope {config.SMALL_LLM_MODEL}")
    test_model(dashscope_client, config.VISUAL_AUDIT_MODEL, f"DashScope {config.VISUAL_AUDIT_MODEL}")
else:
    print("FAIL: DashScope client not configured")


print("\n" + "=" * 50)
print("Testing Primary Chat Client")
print("=" * 50)
primary_client = config.openai_client_for_chat()
if primary_client:
    test_model(primary_client, config.LARGE_LLM_MODEL, f"Primary {config.LARGE_LLM_MODEL}")
    test_model(primary_client, config.SMALL_LLM_MODEL, f"Primary {config.SMALL_LLM_MODEL}")
    test_model(primary_client, config.VISION_WEB_MODEL, f"Primary {config.VISION_WEB_MODEL}")
else:
    print("FAIL: primary client not configured")


print("\n" + "=" * 50)
print("Done")
print("=" * 50)
