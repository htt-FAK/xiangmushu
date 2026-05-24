"""验证结构分析修复：测试客户端能否正常创建并调用 API。"""
import os
import sys

# 强制重新加载 config 模块（避免缓存旧的单例）
if "config" in sys.modules:
    del sys.modules["config"]

import config

print("=== 配置检查 ===")
print(f"OPENAI_BASE_URL: {config.OPENAI_BASE_URL}")
print(f"DASHSCOPE_API_KEY: {'已配置' if config.DASHSCOPE_API_KEY else '未配置'}")
print(f"DEEPSEEK_API_KEY: {'已配置' if config.DEEPSEEK_API_KEY else '未配置(已禁用)'}")
print(f"FOSUN_AIGW_API_KEY: {'已配置' if config.FOSUN_AIGW_API_KEY else '未配置(已禁用)'}")
print(f"TEMPLATE_ANALYZE_MODEL: {config.TEMPLATE_ANALYZE_MODEL}")
print(f"LARGE_LLM_MODEL: {config.LARGE_LLM_MODEL}")
print(f"SMALL_LLM_MODEL: {config.SMALL_LLM_MODEL}")

print("\n=== 客户端创建测试 ===")
try:
    client = config.openai_client_for_template_analyze()
    print(f"结构分析客户端: OK (base_url={getattr(client, 'base_url', 'unknown')})")
except Exception as e:
    print(f"结构分析客户端: FAILED - {e}")

try:
    chat_client = config.openai_client_for_chat()
    print(f"聊天客户端: OK (base_url={getattr(chat_client, 'base_url', 'unknown')})")
except Exception as e:
    print(f"聊天客户端: FAILED - {e}")

try:
    ds_client = config.deepseek_client()
    print(f"DeepSeek客户端: {'None(已禁用)' if ds_client is None else 'OK'}")
except Exception as e:
    print(f"DeepSeek客户端: FAILED - {e}")

print("\n=== API 调用测试（轻量级） ===")
try:
    from core.dashscope_chat import chat_completions_create
    resp = chat_completions_create(
        client,
        model=config.TEMPLATE_ANALYZE_MODEL,
        messages=[
            {"role": "system", "content": "你是助手，只回答'OK'。"},
            {"role": "user", "content": "测试连通性，请回复'OK'。"},
        ],
        temperature=0.1,
        max_tokens=10,
        timeout=30,
    )
    content = (resp.choices[0].message.content or "").strip()
    print(f"API 调用: OK (响应内容: {content})")
except Exception as e:
    print(f"API 调用: FAILED - {type(e).__name__}: {e}")

print("\n=== 完成 ===")
