import os
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

# 百炼 OpenAI 兼容端点（嵌入默认固定走此，避免与网关向量维度不一致）
DASHSCOPE_COMPAT_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"

DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
# DeepSeek API（平台默认免费额度已用完，全局直连禁用；但 base_url 仍保留，
# 以便用户自带 Key (BYOK) 时能按 DeepSeek 自身的调用方式正确校验/调用）。
# DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "").strip()
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com").strip() or "https://api.deepseek.com"
MIMO_API_KEY = os.getenv("MIMO_API_KEY", "").strip()
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1").strip() or "https://api.xiaomimimo.com/v1"

# Provider → OpenAI 兼容 base_url 映射。
# 用于按 provider 校验/调用用户自带 Key 时，确保走各家自己的调用端点，
# 而不是在缺少 MySQL provider registry 时统统退化成阿里云百炼端点。
PROVIDER_BASE_URLS: dict[str, str] = {
    "dashscope": DASHSCOPE_COMPAT_BASE,
    "deepseek": DEEPSEEK_BASE_URL,
    "mimo": MIMO_BASE_URL,
}


def provider_base_url(provider_code: str) -> str:
    """返回指定 provider 的 OpenAI 兼容 base_url；未知 provider 回落到百炼。"""
    code = str(provider_code or "").strip().lower()
    return PROVIDER_BASE_URLS.get(code) or DASHSCOPE_COMPAT_BASE
# 嵌入 / 回落聊天：优先百炼 Key，兼容仅配 OPENAI_API_KEY
OPENAI_COMPAT_API_KEY = DASHSCOPE_API_KEY or OPENAI_API_KEY

# 兼容旧逻辑：未显式拆分时，默认仍指向百炼 compatible-mode
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", DASHSCOPE_COMPAT_BASE).strip() or DASHSCOPE_COMPAT_BASE

# 嵌入专用 base（不随聊天网关变；可用环境变量覆盖）
EMBEDDING_OPENAI_BASE_URL = (
    os.getenv("EMBEDDING_OPENAI_BASE_URL", "").strip() or DASHSCOPE_COMPAT_BASE
)


# Embedding 模型（百炼 compatible-mode 用 text-embedding-v3 等）
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-v4")
RERANK_MODEL = os.getenv("RERANK_MODEL", "qwen3-rerank")

# 场景 LLM / 视觉（均可 env 覆盖）
# 视觉/联网/大段：qwen3.7-plus；小模型/RAG/表格快批：qwen3.7-flash
_vw = os.getenv("VISION_WEB_MODEL", "").strip()
if not _vw:
    _vw = os.getenv("VISION_MODEL", "").strip()
VISION_WEB_MODEL = _vw or "qwen3.6-flash"
VISION_WEB_FALLBACK_MODEL = os.getenv("VISION_WEB_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"
TEMPLATE_VISION_MODEL = os.getenv("TEMPLATE_VISION_MODEL", "").strip() or "qwen3.7-plus"
TEMPLATE_VISION_FALLBACK_MODEL = os.getenv("TEMPLATE_VISION_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"
VISION_EXTRACT_MODEL = os.getenv("VISION_EXTRACT_MODEL", "").strip() or "qwen3.7-plus"
VISION_EXTRACT_FALLBACK_MODEL = os.getenv("VISION_EXTRACT_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"
TABLE_CELL_VISION_MODEL = os.getenv("TABLE_CELL_VISION_MODEL", "").strip() or "qwen3.7-plus"
TABLE_CELL_VISION_FALLBACK_MODEL = os.getenv("TABLE_CELL_VISION_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"
TABLE_CELL_FALLBACK_MODEL = os.getenv("TABLE_CELL_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"
SMALL_LLM_MODEL = os.getenv("SMALL_LLM_MODEL", "qwen3.6-flash").strip()
SMALL_LLM_FALLBACK_MODEL = os.getenv("SMALL_LLM_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"
# 结构分析：默认 qwen3.6-flash，可环境变量覆盖
TEMPLATE_ANALYZE_MODEL = os.getenv("TEMPLATE_ANALYZE_MODEL", "").strip() or "qwen3.6-flash"
TEMPLATE_ANALYZE_FALLBACK_MODEL = (
    os.getenv("TEMPLATE_ANALYZE_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"
)
# 结构分析专用超时（秒），避免沿用 OPENAI_TIMEOUT=300 时界面长时间无反馈
TEMPLATE_ANALYZE_TIMEOUT = float(os.getenv("TEMPLATE_ANALYZE_TIMEOUT", "180"))
# 结构分析提示词上限（字符），避免超大模板 + 视觉摘要导致 API 超时
TEMPLATE_ANALYZE_MAX_PROMPT_CHARS = int(
    os.getenv("TEMPLATE_ANALYZE_MAX_PROMPT_CHARS", "8000")
)
MAIN_WRITER_MODEL = os.getenv("MAIN_WRITER_MODEL", "").strip() or "qwen3.7-plus"
MAIN_WRITER_FALLBACK_MODEL_1 = os.getenv("MAIN_WRITER_FALLBACK_MODEL_1", "").strip() or "qwen3.7-max"
MAIN_WRITER_FALLBACK_MODEL_2 = os.getenv("MAIN_WRITER_FALLBACK_MODEL_2", "").strip() or "qwen3.7-plus"
FAST_WRITER_MODEL = os.getenv("FAST_WRITER_MODEL", "").strip() or SMALL_LLM_MODEL
FAST_WRITER_FALLBACK_MODEL_1 = os.getenv("FAST_WRITER_FALLBACK_MODEL_1", "").strip() or SMALL_LLM_FALLBACK_MODEL
WEB_SEARCH_MODEL = os.getenv("WEB_SEARCH_MODEL", "").strip() or "qwen3.7-plus"
WEB_SEARCH_FALLBACK_MODEL_1 = os.getenv("WEB_SEARCH_FALLBACK_MODEL_1", "").strip() or VISION_WEB_FALLBACK_MODEL
VISION_LAYOUT_MODEL = os.getenv("VISION_LAYOUT_MODEL", "").strip() or TEMPLATE_VISION_MODEL
VISION_LAYOUT_FALLBACK_MODEL_1 = os.getenv("VISION_LAYOUT_FALLBACK_MODEL_1", "").strip() or TEMPLATE_VISION_FALLBACK_MODEL
TEMPLATE_PLANNER_MODEL = os.getenv("TEMPLATE_PLANNER_MODEL", "").strip() or TEMPLATE_ANALYZE_MODEL
TEMPLATE_PLANNER_FALLBACK_MODEL_1 = os.getenv("TEMPLATE_PLANNER_FALLBACK_MODEL_1", "").strip() or TEMPLATE_ANALYZE_FALLBACK_MODEL
AUDIT_TEXT_MODEL = os.getenv("AUDIT_TEXT_MODEL", "").strip() or "qwen3.6-flash"
AUDIT_TEXT_FALLBACK_MODEL_1 = os.getenv("AUDIT_TEXT_FALLBACK_MODEL_1", "").strip() or "qwen3.7-plus"
LARGE_LLM_MODEL = os.getenv("LARGE_LLM_MODEL", "").strip() or MAIN_WRITER_MODEL
FALLBACK_LLM_MODEL_1 = os.getenv("FALLBACK_LLM_MODEL_1", "").strip() or "qwen3.7-max"
FALLBACK_LLM_MODEL_2 = os.getenv("FALLBACK_LLM_MODEL_2", "").strip() or "qwen3.7-max"
FALLBACK_LLM_MODEL_3 = os.getenv("FALLBACK_LLM_MODEL_3", "").strip() or "qwen3.7-max"
AUDIT_LLM_MODEL = os.getenv("AUDIT_LLM_MODEL", "").strip() or "qwen3.7-max"
AUDIT_FALLBACK_1 = os.getenv("AUDIT_FALLBACK_1", "").strip() or "qwen3.7-max"
AUDIT_FALLBACK_2 = os.getenv("AUDIT_FALLBACK_2", "").strip() or "qwen3.7-max"
AUDIT_FALLBACK_3 = os.getenv("AUDIT_FALLBACK_3", "").strip() or "qwen3.7-max"
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
VECTOR_CACHE_MAX_SIZE = int(os.getenv("VECTOR_CACHE_MAX_SIZE", "64"))
VECTOR_CACHE_TTL_SECONDS = int(os.getenv("VECTOR_CACHE_TTL_SECONDS", "300"))
# 侧栏开启「联网补料」时：除空库/无命中外，若最佳命中的估算相似度低于该值也走百炼 enable_search。
# 估算式 sim ≈ 1 - min(distance)（夹在 0~1），与 Chroma 余弦距离族一致；其它度量下请用环境变量微调阈值。
RETRIEVAL_WEB_SIMILARITY_THRESHOLD = float(
    os.getenv("RETRIEVAL_WEB_SIMILARITY_THRESHOLD", "0.3")
)

# 省 token：强检索时正文生成可走小模型（同一套检索片段）；环境变量设为 0/false/off 关闭
_USE_SSR = os.getenv("USE_SMALL_LLM_FOR_STRONG_RAG", "1").strip().lower()
USE_SMALL_LLM_FOR_STRONG_RAG = _USE_SSR not in ("0", "false", "no", "off")
# 全量召回模式：跳过向量检索，将知识库所有文档直接拼入 prompt
_FULL_RECALL = os.getenv("FULL_RECALL_MODE", "1").strip().lower()
FULL_RECALL_MODE = _FULL_RECALL not in ("0", "false", "no", "off")
# 全量召回最大总字符数（0=不限制）
FULL_RECALL_MAX_CHARS = int(os.getenv("FULL_RECALL_MAX_CHARS", "80000"))
# 最佳估算相似度 >= 该值且非长段时，用 SMALL_LLM 写正文（弱库/低相似/联网档仍走大模型或联网档）
STRONG_RAG_SIMILARITY_FLOOR = float(os.getenv("STRONG_RAG_SIMILARITY_FLOOR", "0.5"))
# 段落任务字数超过该阈值时强制用大模型，减轻长文质量下降
LONG_PARAGRAPH_WORDS = int(os.getenv("LONG_PARAGRAPH_WORDS", "600"))
ABSTRACT_WORD_LIMIT = int(os.getenv("ABSTRACT_WORD_LIMIT", "650"))
_BAWK = os.getenv("BATCH_TABLE_ALLOW_WEAK_KB", "1").strip().lower()
BATCH_TABLE_ALLOW_WEAK_KB = _BAWK not in ("0", "false", "no", "off")
# 每条检索片段写入提示词的最大字符数（超出截断，减输入 token）
RAG_SNIPPET_MAX_CHARS = int(os.getenv("RAG_SNIPPET_MAX_CHARS", "1100"))
# 生成 max_tokens 上限（输出侧控费；实际取 min(硬顶, 字数×系数+余量)）
GEN_MAX_TOKENS_HARD_CAP = int(os.getenv("GEN_MAX_TOKENS_HARD_CAP", "4096"))
GEN_MAX_TOKENS_WORD_FACTOR = int(os.getenv("GEN_MAX_TOKENS_WORD_FACTOR", "5"))
GENERATION_MAX_WORKERS = int(os.getenv("GENERATION_MAX_WORKERS", "5"))

# OpenAI 客户端：超时与重试（embedding / 入库易触达默认短超时）
OPENAI_TIMEOUT = float(os.getenv("OPENAI_TIMEOUT", "180"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "4"))

# AI billing: yuan per 1K tokens.
AI_MODEL_PRICING: dict[str, dict[str, float]] = {
    "qwen-plus": {"input": 0.0008, "output": 0.002},
    "qwen-turbo": {"input": 0.0003, "output": 0.0006},
    "qwen3.6-flash": {"input": 0.0003, "output": 0.0006},
    "qwen3.5-plus": {"input": 0.0008, "output": 0.002},
    "qwen3.5-flash": {"input": 0.0003, "output": 0.0006},
    "deepseek-v4-flash": {"input": 0.0003, "output": 0.0006},
    "deepseek-v4-pro": {"input": 0.001, "output": 0.002},
    "deepseek-chat": {"input": 0.001, "output": 0.002},
    "deepseek-reasoner": {"input": 0.004, "output": 0.016},
    "qwen3.7-plus": {"input": 0.0008, "output": 0.002},
    "qwen3.7-max": {"input": 0.002, "output": 0.006},
    "qwen3.7-max-preview": {"input": 0.002, "output": 0.006},
    "qwen3.7-max-2026-05-17": {"input": 0.002, "output": 0.006},
    "qwen3.7-max-2026-05-20": {"input": 0.002, "output": 0.006},
    "mimo-v2.5-pro": {"input": 0.003, "output": 0.006},
    "mimo-v2.5-pro-ultraspeed": {"input": 0.001, "output": 0.002},
    "mimo-v2.5": {"input": 0.001, "output": 0.002},
}

USER_API_KEY_ENCRYPTION_KEY = os.getenv(
    "USER_API_KEY_ENCRYPTION_KEY",
    os.getenv("AUTH_JWT_SECRET", "dev-change-me-auth-secret"),
).strip()
UPLOAD_MAX_SIZE_MB = int(os.getenv("UPLOAD_MAX_SIZE_MB", "50"))

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
    os.getenv("BATCH_TABLE_FAST_MODEL", "").strip() or "qwen3.6-flash"
)

# ---------------------------------------------------------------------------
# 用户可选模型注册表
# ---------------------------------------------------------------------------
USER_MODEL_OPTIONS: dict[str, dict] = {
    "generation": {
        "label": "内容生成",
        "description": "用于文档核心内容的AI生成与填写，直接影响输出质量",
        "config_keys": ["LARGE_LLM_MODEL"],
        "tiers": {
            "高性能": [
                {"model": "qwen3.7-max"},
                {"model": "mimo-v2.5-pro"},
                {"model": "deepseek-v4-pro"},
            ],
            "性价比": [
                {"model": "qwen3.6-flash", "recommended": True},
                {"model": "qwen3.5-flash"},
                {"model": "deepseek-v4-flash"},
                {"model": "mimo-v2.5"},
                {"model": "qwen3.7-plus", "recommended": True},
            ],
        },
    },
    "main_writer": {
        "label": "主写作模型",
        "description": "负责最终正文和表格单元格内容输出，当前默认使用 qwen3.7-plus",
        "config_keys": ["MAIN_WRITER_MODEL", "LARGE_LLM_MODEL"],
        "tiers": {
            "高质量": [
                {"model": "qwen3.7-plus", "recommended": True},
                {"model": "deepseek-v4-pro"},
                {"model": "mimo-v2.5-pro"},
                {"model": "qwen3.7-max"},
            ],
            "性价比": [
                {"model": "deepseek-v4-flash"},
                {"model": "mimo-v2.5"},
                {"model": "qwen3.6-flash", "recommended": True},
                {"model": "qwen3.5-flash"},
            ],
        },
    },
    "fast_writer": {
        "label": "快速填充模型",
        "description": "用于强证据短内容、表格快填和低成本生成",
        "config_keys": ["FAST_WRITER_MODEL", "SMALL_LLM_MODEL", "BATCH_TABLE_FAST_MODEL"],
        "options": [
            {"model": "qwen3.6-flash", "recommended": True},
            {"model": "qwen3.5-flash"},
            {"model": "deepseek-v4-flash"},
            {"model": "mimo-v2.5"},
            {"model": "qwen3.6-35b-a3b"},
        ],
    },
    "web_search": {
        "label": "联网搜索模型",
        "description": "只负责搜索和抽取结构化网页证据，不直接写最终正文",
        "config_keys": ["WEB_SEARCH_MODEL", "VISION_WEB_MODEL"],
        "tiers": {
            "高质量": [
                {"model": "qwen3.7-plus", "recommended": True},
                {"model": "qwen3.6-plus"},
            ],
            "性价比": [
                {"model": "qwen3.6-flash", "recommended": True},
                {"model": "qwen3.5-flash"},
                {"model": "mimo-v2.5"},
            ],
        },
    },
    "vision_layout": {
        "label": "模板视觉模型",
        "description": "负责模板图片、截图和版式理解",
        "config_keys": ["VISION_LAYOUT_MODEL", "TEMPLATE_VISION_MODEL", "TABLE_CELL_VISION_MODEL"],
        "tiers": {
            "高质量": [
                {"model": "qwen3.7-plus", "recommended": True},
                {"model": "qwen3.6-plus"},
            ],
            "性价比": [
                {"model": "qwen3.5-flash"},
                {"model": "qwen3.6-flash"},
                {"model": "mimo-v2.5"},
            ],
        },
    },
    "template_planner": {
        "label": "模板拆解模型",
        "description": "负责把模板结构、扫描结果和视觉摘要拆解为 FillTask",
        "config_keys": ["TEMPLATE_PLANNER_MODEL", "TEMPLATE_ANALYZE_MODEL"],
        "options": [
            {"model": "qwen3.6-flash", "recommended": True},
            {"model": "qwen3.7-plus"},
            {"model": "qwen3.5-plus"},
            {"model": "deepseek-v4-flash"},
            {"model": "mimo-v2.5"},
        ],
    },
    "audit_text": {
        "label": "内容审核模型",
        "description": "负责生成后文本审核和必要的轻量修订建议",
        "config_keys": ["AUDIT_TEXT_MODEL", "AUDIT_LLM_MODEL"],
        "options": [
            {"model": "qwen3.6-flash", "recommended": True},
            {"model": "qwen3.5-flash"},
            {"model": "deepseek-v4-flash"},
            {"model": "mimo-v2.5"},
            {"model": "qwen3.7-plus"},
        ],
    },
    "lightweight": {
        "label": "轻度处理",
        "description": "查询扩展、槽位扫描等轻量推理任务，速度优先",
        "config_keys": ["SMALL_LLM_MODEL", "TEMPLATE_ANALYZE_MODEL", "BATCH_TABLE_FAST_MODEL"],
        "options": [
            {"model": "qwen3.6-flash", "recommended": True},
            {"model": "qwen3.5-flash"},
            {"model": "deepseek-v4-flash"},
            {"model": "qwen3.6-35b-a3b"},
            {"model": "mimo-v2.5"},
        ],
    },
    "vision": {
        "label": "视觉分析",
        "description": "模板图片识别、网页截图理解、表格内容提取",
        "config_keys": ["VISION_WEB_MODEL", "TEMPLATE_VISION_MODEL", "VISION_EXTRACT_MODEL", "TABLE_CELL_VISION_MODEL", "VISION_WEB_FALLBACK_MODEL", "TEMPLATE_VISION_FALLBACK_MODEL", "VISION_EXTRACT_FALLBACK_MODEL", "TABLE_CELL_VISION_FALLBACK_MODEL", "TABLE_CELL_FALLBACK_MODEL"],
        "tiers": {
            "高性能": [
                {"model": "qwen3.7-plus", "recommended": True},
                {"model": "qwen3.6-plus"},
            ],
            "性价比": [
                {"model": "qwen3.5-plus"},
                {"model": "qwen3.6-flash"},
                {"model": "qwen3.5-flash"},
                {"model": "mimo-v2.5"},
            ],
        },
    },
    "search": {
        "label": "联网搜索",
        "description": "实时检索网络信息，补充知识库内容",
        "config_keys": [],
        "tiers": {
            "高性能": [
                {"model": "qwen3.7-plus", "recommended": True},
                {"model": "qwen3.6-plus"},
                {"model": "mimo-v2.5-pro"},

            ],
            "性价比": [
                {"model": "qwen3.6-flash"},
                {"model": "qwen3.5-flash"},
                {"model": "mimo-v2.5"},
            ],
        },
    },
    "audit": {
        "label": "审核",
        "description": "文本合规检查与视觉内容安全审核",
        "config_keys": ["AUDIT_LLM_MODEL", "VISUAL_AUDIT_MODEL"],
        "options": [
            {"model": "qwen3.6-flash", "recommended": True},
            {"model": "qwen3.5-flash"},
            {"model": "qwen3.6-35b-a3b"},
            {"model": "mimo-v2.5"},
            {"model": "mimo-v2.5-pro"},
            {"model": "deepseek-v4-flash"},
            {"model": "deepseek-v4-pro"},
        ],
    },
}


def get_user_model(module: str) -> str:
    """从用户偏好中读取选定模型，如果没有则返回 config 默认值。"""
    # 延迟导入避免循环引用
    from core.auth import get_user_preferences as _get_prefs
    # 注意：此函数需要 user_id 参数；当无法获取时回退到默认值
    # 实际使用时应传入 user_id，这里提供无参便捷版本仅用于非请求上下文
    # 在请求上下文中请使用 get_user_model_for_user(user_id, module)
    return _get_default_model_for_module(module)


def get_user_model_for_user(user_id: int, module: str) -> str:
    """根据用户偏好返回指定模块的模型，未设置则返回默认值。"""
    from core.auth import get_user_preferences as _get_prefs
    try:
        prefs = _get_prefs(user_id)
        model_choices = prefs.get("model_choices", {})
        if isinstance(model_choices, str):
            import json as _json
            try:
                model_choices = _json.loads(model_choices)
            except (ValueError, TypeError):
                model_choices = {}
        try:
            from core.model_router import LEGACY_MODULE_TO_ROLE, ROLE_TO_LEGACY_MODULE

            role = LEGACY_MODULE_TO_ROLE.get(module, module)
            keys = [role]
            legacy = ROLE_TO_LEGACY_MODULE.get(role)
            if legacy and legacy not in keys:
                keys.append(legacy)
            if module not in keys:
                keys.append(module)
        except Exception:
            keys = [module]
        for key in keys:
            if key in model_choices and model_choices[key]:
                return model_choices[key]
    except Exception:
        pass
    return _get_default_model_for_module(module)


# 硬编码推荐默认值：用户未保存选择时，优先使用这些高性能推荐模型
_DEFAULT_MODEL_OVERRIDES: dict[str, str] = {
    "generation": MAIN_WRITER_MODEL,
    "lightweight": "qwen3.6-flash",
    "vision": "qwen3.7-plus",
    "search": "qwen3.7-plus",
    "audit": "qwen3.6-flash",
    "main_writer": MAIN_WRITER_MODEL,
    "fast_writer": FAST_WRITER_MODEL,
    "web_search": WEB_SEARCH_MODEL,
    "vision_layout": VISION_LAYOUT_MODEL,
    "template_planner": TEMPLATE_PLANNER_MODEL,
    "audit_text": AUDIT_TEXT_MODEL,
}


def _get_default_model_for_module(module: str) -> str:
    """返回模块的默认模型。

    优先级：
    1. _DEFAULT_MODEL_OVERRIDES 中的硬编码推荐值
    2. config_keys 第一个对应的当前环境变量值
    3. tiers/options 中 recommended=True 且位于高性能档的模型
    4. 任意 recommended 模型
    5. options/tiers 中第一个模型
    """
    module_def = USER_MODEL_OPTIONS.get(module)
    if not module_def:
        return ""
    # 1. 硬编码推荐默认值
    override = _DEFAULT_MODEL_OVERRIDES.get(module)
    if override:
        return override
    # 2. config_keys 环境变量
    config_keys = module_def.get("config_keys", [])
    if config_keys:
        first_key = config_keys[0]
        val = globals().get(first_key, "")
        if val:
            return val
    # 3/4. tiers 中优先高性能档的 recommended 模型
    tiers = module_def.get("tiers")
    if tiers:
        high_perf = tiers.get("高性能") or []
        for m in high_perf:
            if m.get("recommended"):
                return m["model"]
        for tier_models in tiers.values():
            for m in tier_models:
                if m.get("recommended"):
                    return m["model"]
    # options 中的 recommended
    options = module_def.get("options")
    if options:
        for m in options:
            if m.get("recommended"):
                return m["model"]
        if options:
            return options[0]["model"]
    return ""


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

# Structured persistence. SQLite remains the compatibility fallback; set
# PERSISTENCE_MODE=mysql to use the MySQL schema/migration path.
PERSISTENCE_MODE = os.getenv("PERSISTENCE_MODE", "sqlite").strip().lower() or "sqlite"
PERSISTENCE_SQLITE_FALLBACK = os.getenv("PERSISTENCE_SQLITE_FALLBACK", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
MYSQL_HOST = os.getenv("MYSQL_HOST", "").strip()
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "").strip()
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "").strip()
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "").strip()
MYSQL_CHARSET = os.getenv("MYSQL_CHARSET", "utf8mb4").strip() or "utf8mb4"
MYSQL_CONNECT_TIMEOUT = float(os.getenv("MYSQL_CONNECT_TIMEOUT", "5"))
MYSQL_READ_TIMEOUT = float(os.getenv("MYSQL_READ_TIMEOUT", "30"))
MYSQL_WRITE_TIMEOUT = float(os.getenv("MYSQL_WRITE_TIMEOUT", "30"))
MYSQL_AUTO_CREATE_DATABASE = os.getenv("MYSQL_AUTO_CREATE_DATABASE", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
MYSQL_AUTO_MIGRATE = os.getenv("MYSQL_AUTO_MIGRATE", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
MYSQL_MIGRATIONS_DIR = os.getenv(
    "MYSQL_MIGRATIONS_DIR",
    os.path.join(os.path.dirname(__file__), "migrations", "mysql"),
).strip()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Artifact storage configuration. Current code still writes generated files
# locally; these settings prepare the storage layer for Tencent COS/Object
# Storage integration.
STORAGE_PROVIDER = os.getenv("STORAGE_PROVIDER", "local").strip().lower() or "local"
ARTIFACT_LOCAL_ROOT = os.getenv(
    "ARTIFACT_LOCAL_ROOT",
    os.path.join(os.path.dirname(__file__), "data", "artifacts"),
).strip()
COS_BUCKET = os.getenv("COS_BUCKET", "").strip()
COS_REGION = os.getenv("COS_REGION", "").strip()
COS_ENDPOINT = os.getenv("COS_ENDPOINT", "").strip()
COS_SECRET_ID = os.getenv("COS_SECRET_ID", "").strip()
COS_SECRET_KEY = os.getenv("COS_SECRET_KEY", "").strip()
COS_PREFIX = os.getenv("COS_PREFIX", "prod/").strip()
COS_PRIVATE = os.getenv("COS_PRIVATE", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)
COS_SIGNED_URL_EXPIRE_SECONDS = int(os.getenv("COS_SIGNED_URL_EXPIRE_SECONDS", "600"))

AUTH_DB_PATH = os.getenv(
    "AUTH_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "auth.sqlite3"),
).strip()
_DEFAULT_JWT_SECRET = "dev-change-me-auth-secret"
AUTH_JWT_SECRET = os.getenv("AUTH_JWT_SECRET", _DEFAULT_JWT_SECRET).strip()
if AUTH_JWT_SECRET == _DEFAULT_JWT_SECRET:
    import sys
    # Check if running in development (localhost) or production
    _is_dev = os.getenv("ENV", "").lower() in ("dev", "development", "")
    if not _is_dev:
        print(
            "\n❌ FATAL: AUTH_JWT_SECRET must be set in production.\n"
            "   Set a strong secret in .env or environment variables.\n"
            "   Example: AUTH_JWT_SECRET=<random-64-char-string>\n",
            file=sys.stderr,
        )
        sys.exit(1)
    else:
        print(
            "\n⚠️  WARNING: AUTH_JWT_SECRET is using the default value.\n"
            "   Set a strong secret in .env for production use.\n"
            "   Example: AUTH_JWT_SECRET=<random-64-char-string>\n",
            file=sys.stderr,
        )
AUTH_JWT_EXPIRE_MINUTES = int(os.getenv("AUTH_JWT_EXPIRE_MINUTES", "1440"))
AUTH_CODE_TTL_MINUTES = int(os.getenv("AUTH_CODE_TTL_MINUTES", "10"))
AUTH_SMTP_HOST = os.getenv("AUTH_SMTP_HOST", "").strip()
AUTH_SMTP_PORT = int(os.getenv("AUTH_SMTP_PORT", "587"))
AUTH_SMTP_USERNAME = os.getenv("AUTH_SMTP_USERNAME", "").strip()
AUTH_SMTP_PASSWORD = os.getenv("AUTH_SMTP_PASSWORD", "").strip()
AUTH_SMTP_FROM = os.getenv("AUTH_SMTP_FROM", AUTH_SMTP_USERNAME).strip()
AUTH_SMTP_USE_TLS = os.getenv("AUTH_SMTP_USE_TLS", "1").strip().lower() not in (
    "0",
    "false",
    "no",
    "off",
)

# 确保目录存在
for d in [HISTORICAL_DIR, TEMPLATE_DIR, OUTPUT_DIR, ARTIFACT_LOCAL_ROOT]:
    os.makedirs(d, exist_ok=True)


# 视觉审核配置（测试阶段全部拉满）
_VISUAL_AUDIT = os.getenv("VISUAL_AUDIT_ENABLED", "1").strip().lower()
VISUAL_AUDIT_ENABLED = _VISUAL_AUDIT not in ("0", "false", "no", "off")
VISUAL_AUDIT_MAX_ROUNDS = int(os.getenv("VISUAL_AUDIT_MAX_ROUNDS", "3"))
VISUAL_AUDIT_PASS_SCORE = int(os.getenv("VISUAL_AUDIT_PASS_SCORE", "85"))
VISUAL_AUDIT_MODEL = os.getenv("VISUAL_AUDIT_MODEL", "qwen3.7-plus").strip()
VISUAL_AUDIT_FALLBACK_MODEL = os.getenv("VISUAL_AUDIT_FALLBACK_MODEL", "").strip() or "qwen3.7-plus"

# 内容充实度配置
_CONTENT_RICHNESS = os.getenv("CONTENT_RICHNESS_ENABLED", "1").strip().lower()
CONTENT_RICHNESS_ENABLED = _CONTENT_RICHNESS not in ("0", "false", "no", "off")
CONTENT_RICHNESS_THRESHOLD = float(os.getenv("CONTENT_RICHNESS_THRESHOLD", "0.8"))

# 格式保留配置
_PRESERVE_WATERMARK = os.getenv("PRESERVE_WATERMARK", "1").strip().lower()
PRESERVE_WATERMARK = _PRESERVE_WATERMARK not in ("0", "false", "no", "off")
_PRESERVE_TABLE_FORMAT = os.getenv("PRESERVE_TABLE_FORMAT", "1").strip().lower()
PRESERVE_TABLE_FORMAT = _PRESERVE_TABLE_FORMAT not in ("0", "false", "no", "off")


def chat_llm_configured() -> bool:
    """是否具备聊天/多模态调用所需 Key。"""
    return bool((OPENAI_COMPAT_API_KEY or "").strip())


def embedding_llm_configured() -> bool:
    """Chroma 嵌入是否可调（须百炼或兼容 Key）。"""
    return bool((OPENAI_COMPAT_API_KEY or "").strip())


# ----- OpenAI 客户端（聊天走网关优先；回落在 dashscope_chat 内用单例） -----
_chat_client_singleton: Optional[Any] = None
_dashscope_backup_chat_singleton: Optional[Any] = None
_dashscope_backup_chat_checked_none: bool = False


def openai_client_for_chat() -> Any:
    """聊天/视觉统一入口：走 OPENAI_BASE_URL（默认百炼 compatible-mode）。"""
    global _chat_client_singleton
    if _chat_client_singleton is not None:
        return _chat_client_singleton
    from openai import OpenAI

    _chat_client_singleton = OpenAI(
        api_key=OPENAI_COMPAT_API_KEY or "sk-placeholder",
        base_url=OPENAI_BASE_URL,
        timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_MAX_RETRIES,
    )
    return _chat_client_singleton


def is_deepseek_model(model_id: str) -> bool:
    """判断是否为 DeepSeek 模型。"""
    return "deepseek" in model_id.lower()


_deepseek_client_singleton: Optional[Any] = None
_deepseek_client_checked_none: bool = False


def deepseek_client() -> Optional[Any]:
    """DeepSeek API 客户端（OpenAI 兼容），未配置 Key 时返回 None。"""
    global _deepseek_client_singleton, _deepseek_client_checked_none
    if _deepseek_client_checked_none:
        return None
    if _deepseek_client_singleton is not None:
        return _deepseek_client_singleton
    key = (DEEPSEEK_API_KEY or "").strip()
    if not key:
        _deepseek_client_checked_none = True
        return None
    from openai import OpenAI

    _deepseek_client_singleton = OpenAI(
        api_key=key,
        base_url=DEEPSEEK_BASE_URL,
        timeout=OPENAI_TIMEOUT,
        max_retries=OPENAI_MAX_RETRIES,
    )
    return _deepseek_client_singleton


def openai_client_for_template_analyze() -> Any:
    """结构分析专用：优先百炼 compatible-mode，短超时、不重试。"""
    from openai import OpenAI

    key = (DASHSCOPE_API_KEY or OPENAI_API_KEY or "").strip()
    if key:
        return OpenAI(
            api_key=key,
            base_url=DASHSCOPE_COMPAT_BASE,
            timeout=TEMPLATE_ANALYZE_TIMEOUT,
            max_retries=0,
        )
    return openai_client_for_chat()


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
