import os
from dotenv import load_dotenv

load_dotenv()

# API 配置
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")

# Embedding 模型
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

# LLM 模型
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "gpt-4o")

# 路径配置
HISTORICAL_DIR = os.path.join(os.path.dirname(__file__), "data", "historical")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "data", "templates")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "outputs")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

# 确保目录存在
for d in [HISTORICAL_DIR, TEMPLATE_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)
