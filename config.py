import os
from dotenv import load_dotenv

load_dotenv()

# API：百炼 compatible-mode 默认；可用 OPENAI_BASE_URL 覆盖
DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
# 聊天 / 视觉 / embedding 客户端：优先百炼 Key，兼容仅配 OPENAI_API_KEY
OPENAI_COMPAT_API_KEY = DASHSCOPE_API_KEY or OPENAI_API_KEY

_DEFAULT_COMPAT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", _DEFAULT_COMPAT_BASE)

# Embedding 模型（百炼 compatible-mode 用 text-embedding-v3 等）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")

# 场景 LLM / 视觉（均可 env 覆盖）
_vw = os.getenv("VISION_WEB_MODEL", "").strip()
if not _vw:
    _vw = os.getenv("VISION_MODEL", "").strip()
# 弱知识库 + 联网分支：须使用百炼支持 extra_body.enable_search 的 qwen-plus 系（见阿里云「大模型如何联网搜索」）
VISION_WEB_MODEL = _vw or "qwen3.5-plus-2026-04-20"
SMALL_LLM_MODEL = os.getenv("SMALL_LLM_MODEL", "qwen3.6-flash-2026-04-16").strip()
LARGE_LLM_MODEL = os.getenv("LARGE_LLM_MODEL", "").strip() or "glm-5"

TEMP_VISION = float(os.getenv("TEMP_VISION", "0.25"))
TEMP_WEB_GEN = float(os.getenv("TEMP_WEB_GEN", "0.4"))
TEMP_SMALL_LLM = float(os.getenv("TEMP_SMALL_LLM", "0.1"))
TEMP_LARGE_LLM = float(os.getenv("TEMP_LARGE_LLM", "0.65"))

# 检索：Chroma 返回的 distance，越小通常越相似（与距离度量有关）；超过则视为弱相关
RETRIEVAL_MAX_DISTANCE = float(os.getenv("RETRIEVAL_MAX_DISTANCE", "1.25"))
# 侧栏开启「联网补料」时：除空库/无命中外，若最佳命中的估算相似度低于该值也走百炼 enable_search。
# 估算式 sim ≈ 1 - min(distance)（夹在 0~1），与 Chroma 余弦距离族一致；其它度量下请用环境变量微调阈值。
RETRIEVAL_WEB_SIMILARITY_THRESHOLD = float(
    os.getenv("RETRIEVAL_WEB_SIMILARITY_THRESHOLD", "0.3")
)

# OpenAI 客户端：超时与重试（embedding / 入库易触达默认短超时）
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "180"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "4"))

# 单次入库写入 Chroma 的最大 chunk 数（减小单次 embedding 体积，降低超时概率）
EMBED_ADD_BATCH_SIZE = int(os.getenv("EMBED_ADD_BATCH_SIZE", "12"))

# 路径配置
HISTORICAL_DIR = os.path.join(os.path.dirname(__file__), "data", "historical")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "data", "templates")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "outputs")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

# 确保目录存在
for d in [HISTORICAL_DIR, TEMPLATE_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)
