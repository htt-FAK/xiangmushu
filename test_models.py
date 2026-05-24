"""测试各模型可用性"""
import config
from core.dashscope_chat import chat_completions_create

def test_model(client, model, name):
    """测试单个模型"""
    print(f"\n{'='*50}")
    print(f"测试 {name} (model={model})")
    print('='*50)
    try:
        resp = chat_completions_create(
            client,
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "你好，请回复'测试成功'"},
            ],
            temperature=0.1,
            stream=False,
            max_tokens=50,
        )
        content = resp.choices[0].message.content if resp.choices else ""
        print(f"✅ 成功: {content[:100]}")
        return True
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False

# 测试百炼
print("\n" + "="*50)
print("测试百炼 (DashScope)")
print("="*50)
dashscope_client = config.dashscope_backup_chat_client()
if dashscope_client:
    test_model(dashscope_client, "qwen3.6-plus", "百炼 qwen3.6-plus")
    test_model(dashscope_client, "qwen3.5-plus", "百炼 qwen3.5-plus")
else:
    print("❌ 百炼客户端未配置")

# 测试复星网关
print("\n" + "="*50)
print("测试复星网关")
print("="*50)
fosun_client = config.openai_client_for_chat()
if fosun_client:
    test_model(fosun_client, "deepseek-chat", "复星 deepseek-chat")
    test_model(fosun_client, "qwen3.6-plus", "复星 qwen3.6-plus")
    test_model(fosun_client, "kimi-k2.6", "复星 kimi-k2.6")
else:
    print("❌ 复星网关客户端未配置")

# 测试MiMo
print("\n" + "="*50)
print("测试 MiMo")
print("="*50)
mimo_client = config.mimo_client()
if mimo_client:
    test_model(mimo_client, "mimo-v2.5-pro", "MiMo v2.5-pro")
else:
    print("❌ MiMo客户端未配置")

print("\n" + "="*50)
print("测试完成")
print("="*50)
