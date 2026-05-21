import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

# 百炼 OpenAI 兼容端点（嵌入默认固定走此，避免与网关向量维度不一致）
DASHSCOPE_COMPAT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
# 嵌入 / 回落聊天：优先百炼 Key，兼容仅配 OPENAI_API_KEY
OPENAI_COMPAT_API_KEY = DASHSCOPE_API_KEY or OPENAI_API_KEY

# 兼容旧逻辑：未显式拆分时，默认仍指向百炼 compatible-mode
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", DASHSCOPE_COMPAT_BASE).strip() or DASHSCOPE_COMPAT_BASE

# 嵌入专用 base（不随聊天网关变；可用环境变量覆盖）
EMBEDDING_OPENAI_BASE_URL = (
    os.getenv("EMBEDDING_OPENAI_BASE_URL", "").strip() or DASHSCOPE_COMPAT_BASE
)

# 复星 AI 网关（OpenAI 兼容）；未设环境变量时使用默认 Base URL / Key
FOSUN_AIGW_BASE_URL = (
    os.getenv("FOSUN_AIGW_BASE_URL", "").strip() or "https://aigw.fosunwealth.com/v1"
)
_env_fosun_key = os.getenv("FOSUN_AIGW_API_KEY")
if _env_fosun_key is None:
    _DEFAULT_FOSUN_AIGW_API_KEY = "ak-d492348389a555b285fe216dcbe70d22"
    FOSUN_AIGW_API_KEY = _DEFAULT_FOSUN_AIGW_API_KEY.strip()
else:
    FOSUN_AIGW_API_KEY = _env_fosun_key.strip()

# Embedding 模型（百炼 compatible-mode 用 text-embedding-v3 等）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v3")

# 场景 LLM / 视觉（复星网关 ID，均可 env 覆盖；名称以网关文档为准）
_vw = os.getenv("VISION_WEB_MODEL", "").strip()
if not _vw:
    _vw = os.getenv("VISION_MODEL", "").strip()
# 弱知识库 + 联网档：enable_search（dashscope_chat 已关深度思考）
VISION_WEB_MODEL = _vw or "qwen3.5-plus-2026-04-20"
TEMPLATE_VISION_MODEL = os.getenv("TEMPLATE_VISION_MODEL", "").strip() or "qwen3.5-plus-2026-04-20"
VISION_EXTRACT_MODEL = os.getenv("VISION_EXTRACT_MODEL", "").strip() or "gemini-3-pro"
TABLE_CELL_VISION_MODEL = os.getenv("TABLE_CELL_VISION_MODEL", "").strip() or "qwen3.5-plus-2026-04-20"
TABLE_CELL_FALLBACK_MODEL = os.getenv("TABLE_CELL_FALLBACK_MODEL", "").strip() or "qwen3.5-plus"
SMALL_LLM_MODEL = os.getenv("SMALL_LLM_MODEL", "qwen3.6-plus").strip()
TEMPLATE_ANALYZE_MODEL = (
    os.getenv("TEMPLATE_ANALYZE_MODEL", "").strip() or "qwen3.6-27b"
)
LARGE_LLM_MODEL = os.getenv("LARGE_LLM_MODEL", "").strip() or "qwen3.6-max-preview"
FALLBACK_LLM_MODEL_1 = os.getenv("FALLBACK_LLM_MODEL_1", "").strip() or "glm-5"
FALLBACK_LLM_MODEL_2 = os.getenv("FALLBACK_LLM_MODEL_2", "").strip() or "glm-5.1"
AUDIT_LLM_MODEL = os.getenv("AUDIT_LLM_MODEL", "").strip() or "qwen3.5-flash-2026-02-23"
AUDIT_FALLBACK_1 = os.getenv("AUDIT_FALLBACK_1", "").strip() or "qwen3.5-flash"
AUDIT_FALLBACK_2 = os.getenv("AUDIT_FALLBACK_2", "").strip() or "qwen3.6-flash-2026-04-16"
AUDIT_FALLBACK_3 = os.getenv("AUDIT_FALLBACK_3", "").strip() or "qwen3.6-flash"
TEMP_AUDIT = float(os.getenv("TEMP_AUDIT", "0.2"))

TEMP_VISION = float(os.getenv("TEMP_VISION", "0.25"))
TEMP_WEB_GEN = float(os.getenv("TEMP_WEB_GEN", "0.4"))
# 联网档写作默认：calm=缺口标「资料未载明」；creative=仅在实际 enable_search 时由生成器切换提示词
_WSM = os.getenv("WEB_SEARCH_WRITING_MODE", "calm").strip().lower()
WEB_SEARCH_WRITING_MODE = "creative" if _WSM == "creative" else "calm"
TEMP_SMALL_LLM = float(os.getenv("TEMP_SMALL_LLM", "0.1"))
TEMP_TEMPLATE_ANALYZE = float(os.getenv("TEMP_TEMPLATE_ANALYZE", "0.1"))
TEMP_LARGE_LLM = float(os.getenv("TEMP_LARGE_LLM", "0.65"))

# 检索：Chroma 返回的 distance，越小通常越相似（与距离度量有关）；超过则视为弱相关
RETRIEVAL_MAX_DISTANCE = float(os.getenv("RETRIEVAL_MAX_DISTANCE", "1.25"))
# 侧栏开启「联网补料」时：除空库/无命中外，若最佳命中的估算相似度低于该值也走百炼 enable_search。
# 估算式 sim ≈ 1 - min(distance)（夹在 0~1），与 Chroma 余弦距离族一致；其它度量下请用环境变量微调阈值。
RETRIEVAL_WEB_SIMILARITY_THRESHOLD = float(
    os.getenv("RETRIEVAL_WEB_SIMILARITY_THRESHOLD", "0.3")
)

# 省 token：强检索时正文生成可走小模型（同一套检索片段）；环境变量设为 0/false/off 关闭
_USE_SSR = os.getenv("USE_SMALL_LLM_FOR_STRONG_RAG", "1").strip().lower()
USE_SMALL_LLM_FOR_STRONG_RAG = _USE_SSR not in ("0", "false", "no", "off")
# 最佳估算相似度 >= 该值且非长段时，用 SMALL_LLM 写正文（弱库/低相似/联网档仍走大模型或联网档）
STRONG_RAG_SIMILARITY_FLOOR = float(os.getenv("STRONG_RAG_SIMILARITY_FLOOR", "0.5"))
# 段落任务字数超过该阈值时强制用大模型，减轻长文质量下降
LONG_PARAGRAPH_WORDS = int(os.getenv("LONG_PARAGRAPH_WORDS", "600"))
# 每条检索片段写入提示词的最大字符数（超出截断，减输入 token）
RAG_SNIPPET_MAX_CHARS = int(os.getenv("RAG_SNIPPET_MAX_CHARS", "1100"))
# 生成 max_tokens 上限（输出侧控费；实际取 min(硬顶, 字数×系数+余量)）
GEN_MAX_TOKENS_HARD_CAP = int(os.getenv("GEN_MAX_TOKENS_HARD_CAP", "4096"))
GEN_MAX_TOKENS_WORD_FACTOR = int(os.getenv("GEN_MAX_TOKENS_WORD_FACTOR", "5"))

# OpenAI 客户端：超时与重试（embedding / 入库易触达默认短超时）
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "180"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "4"))

# 单次入库写入 Chroma 的最大 chunk 数（减小单次 embedding 体积，降低超时概率）
EMBED_ADD_BATCH_SIZE = int(os.getenv("EMBED_ADD_BATCH_SIZE", "12"))

# 模板视觉：docx→PDF→栅格化页数上限与缩放（PyMuPDF Matrix）
TEMPLATE_VISION_MAX_PAGES = int(os.getenv("TEMPLATE_VISION_MAX_PAGES", "4"))
TEMPLATE_VISION_ZOOM = float(os.getenv("TEMPLATE_VISION_ZOOM", "1.2"))
# 栅格化后长边像素上限（0=不缩放）；缩小可明显加快多模态上传与推理
_TEMPLATE_VISION_MLE = os.getenv("TEMPLATE_VISION_MAX_LONG_EDGE", "1280").strip()
TEMPLATE_VISION_MAX_LONG_EDGE = (
    0 if _TEMPLATE_VISION_MLE in ("0", "", "off", "no") else int(_TEMPLATE_VISION_MLE)
)
# 多模态模板视觉 API 硬超时（秒），避免网关无响应时界面长期卡在第一步
TEMPLATE_VISION_API_TIMEOUT = float(os.getenv("TEMPLATE_VISION_API_TIMEOUT", "120"))
# 设为 0/false/off 则不做 PDF/截图/视觉模型，仅用 OOXML 文本摘要（快，版式信息弱）
_TVE = os.getenv("TEMPLATE_VISION_ENABLED", "0").strip().lower()
TEMPLATE_VISION_ENABLED = _TVE not in ("0", "false", "no", "off")
# 表格生成附带模板页截图（多模态）；关则仅 OOXML 文本上下文
_TCV = os.getenv("TABLE_CELL_VISION", "1").strip().lower()
TABLE_CELL_VISION = _TCV not in ("0", "false", "no", "off")
# 表格行批量：默认快速（不 enable_search、不传页图），显著缩短 batch_table_row 耗时
_BTF = os.getenv("BATCH_TABLE_FAST", "1").strip().lower()
BATCH_TABLE_FAST = _BTF not in ("0", "false", "no", "off")
BATCH_TABLE_FAST_MODEL = (
    os.getenv("BATCH_TABLE_FAST_MODEL", "").strip() or "qwen3.5-plus"
)
# 每格请求最多附带几页 PNG（减延迟；默认同模板视觉页数上限）
TABLE_VISION_MAX_PAGES = int(os.getenv("TABLE_VISION_MAX_PAGES", str(TEMPLATE_VISION_MAX_PAGES)))
# 正文首行缩进（pt），约 2 个中文字宽；0 表示不自动加
BODY_FIRST_LINE_INDENT_PT = float(os.getenv("BODY_FIRST_LINE_INDENT_PT", "24"))
# 回填后是否调整表格列宽/换行（关闭则更尊重原模板版式）
_ADJ_TR = os.getenv("ADJUST_TABLE_READABILITY", "1").strip().lower()
ADJUST_TABLE_READABILITY = _ADJ_TR not in ("0", "false", "no", "off")
# 回填保存前全文档统一宋体字号（正文小四、标题加粗分档）
_APPLY_TYPO = os.getenv("APPLY_UNIFIED_TYPOGRAPHY", "1").strip().lower()
APPLY_UNIFIED_TYPOGRAPHY = _APPLY_TYPO not in ("0", "false", "no", "off")

# 路径配置
HISTORICAL_DIR = os.path.join(os.path.dirname(__file__), "data", "historical")
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "data", "templates")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data", "outputs")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

# 确保目录存在
for d in [HISTORICAL_DIR, TEMPLATE_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)


def chat_llm_configured() -> bool:
    """是否具备聊天/多模态调用所需 Key（网关或百炼其一）。"""
    return bool((FOSUN_AIGW_API_KEY or OPENAI_COMPAT_API_KEY or "").strip())


def embedding_llm_configured() -> bool:
    """Chroma 嵌入是否可调（须百炼或兼容 Key）。"""
    return bool((OPENAI_COMPAT_API_KEY or "").strip())


# ----- OpenAI 客户端（聊天走网关优先；回落在 dashscope_chat 内用单例） -----
_chat_client_singleton: Optional[Any] = None
_dashscope_backup_chat_singleton: Optional[Any] = None
_dashscope_backup_chat_checked_none: bool = False


def openai_client_for_chat() -> Any:
    """聊天/视觉统一入口：已配置复星网关 Key 时走网关，否则走 OPENAI_BASE_URL（默认百炼）。"""
    global _chat_client_singleton
    if _chat_client_singleton is not None:
        return _chat_client_singleton
    from openai import OpenAI

    if FOSUN_AIGW_API_KEY:
        _chat_client_singleton = OpenAI(
            api_key=FOSUN_AIGW_API_KEY,
            base_url=FOSUN_AIGW_BASE_URL,
            timeout=OPENAI_TIMEOUT,
            max_retries=OPENAI_MAX_RETRIES,
        )
    else:
        _chat_client_singleton = OpenAI(
            api_key=OPENAI_COMPAT_API_KEY or "sk-placeholder",
            base_url=OPENAI_BASE_URL,
            timeout=OPENAI_TIMEOUT,
            max_retries=OPENAI_MAX_RETRIES,
        )
    return _chat_client_singleton


def dashscope_backup_chat_client() -> Optional[Any]:
    """百炼 compatible-mode 客户端，供网关失败时回落；无百炼 Key 时返回 None。"""
    global _dashscope_backup_chat_singleton, _dashscope_backup_chat_checked_none
    if _dashscope_backup_chat_checked_none:
        return None
    if _dashscope_backup_chat_singleton is not None:
        return _dashscope_backup_chat_singleton
    key = (DASHSCOPE_API_KEY or OPENAI_API_KEY or "").strip()
    if not key:
        _dashscope_backup_chat_checked_none = True
        return None
    from openai import OpenAI

    _dashscope_backup_chat_singleton = OpenAI(
        api_key=key,
        base_url=DASHSCOPE_COMPAT_BASE,
        timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_MAX_RETRIES,
    )
    return _dashscope_backup_chat_singleton
