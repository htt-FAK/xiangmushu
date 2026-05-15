"""测试模型连接"""
import openai
import config

# 使用 config 中的配置
api_key = config.OPENAI_COMPAT_API_KEY
base_url = config.OPENAI_BASE_URL

print('测试模型连接...')
print(f'API Key: {api_key[:10]}...' if api_key else 'API Key: 未设置')
print(f'Base URL: {base_url}')
print()

if not api_key:
    print('❌ API Key 未设置，请在 .env 文件中配置')
    exit(1)

client = openai.OpenAI(
    api_key=api_key,
    base_url=base_url,
)

# 测试多个可能的模型
models_to_test = [
    "gpt-5.4",
    "gpt-5.3",
    "gpt-5.2",
    "gpt-5.1",
    "gpt-5",
    "gpt-4",
    "qwen-max",
    "qwen-plus",
    "deepseek-v4-pro",
]

for model in models_to_test:
    print(f'测试模型: {model}...', end=' ')
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {'role': 'system', 'content': '你是一个 helpful assistant'},
                {'role': 'user', 'content': '你好，请回复"模型连接成功"'}
            ],
            max_tokens=50,
            timeout=30
        )
        print(f'✅ 成功！')
    except Exception as e:
        error_msg = str(e)
        if "model" in error_msg.lower() and "not exist" in error_msg.lower():
            print(f'❌ 模型不存在')
        elif "authentication" in error_msg.lower():
            print(f'❌ 认证失败')
        else:
            print(f'❌ 错误: {error_msg[:50]}')
