import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

import config
from core.dashscope_chat import chat_completions_create
from core.fill_task import FillTask
from core.reporting import evidence_refs_from_results
from core.template_vision import build_table_cell_user_content
from core.query_expander import expand_query
from core.vector_store import VectorStore

# Lazy import to avoid circular: evidence_planner imports VectorStore too
# import inside method when needed

_LOG = logging.getLogger(__name__)


def _max_output_tokens(word_limit: int, task_type: str) -> int:
    """按任务类型分档计算 max_tokens，避免无谓续写。

    table_cell : 上限 180（简短答案）
    short_para : 字数 ≤ 300，factor=3，上限 1024
    long_para  : 字数 > 300，factor=4，上限 GEN_MAX_TOKENS_HARD_CAP
    """
    cap = int(config.GEN_MAX_TOKENS_HARD_CAP)
    if task_type == "table_cell":
        return 180

    wl = max(1, int(word_limit))
    if wl <= 300:
        raw = wl * 3 + 200
        return max(256, min(1024, raw))

    raw = wl * int(config.GEN_MAX_TOKENS_WORD_FACTOR) + 400
    return max(512, min(cap, raw))


def _fast_table_cell_route(task: FillTask, fast_mode: bool) -> bool:
    return bool(fast_mode and task.task_type == "table_cell")


def _ensure_gen_logger() -> None:
    if _LOG.handlers:
        return
    h = logging.StreamHandler()
    h.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    _LOG.addHandler(h)
    _LOG.setLevel(logging.INFO)


SYSTEM_PROMPT = """你是项目申报文档撰写专家。严格规则：
1. 所有事实须来自【参考资料】，无据不编造；缺口用「资料未载明」简短说明。
2. 禁止 Markdown（#、**、列表符），用普通段落和中文标点；多级内容用（一）（二）。
3. 直接输出正文，不加「以下是…」前缀。
4. 知识库与网络冲突时，以知识库为准。"""

SYSTEM_PROMPT_WEB_CREATIVE = """你是项目申报文档撰写专家（联网创意模式，本请求已开启内置联网检索）：
1. 综合【参考资料】与联网检索到的公开信息完成正文，写满约订字数；不要用「资料未载明」「资料未提供」「未提供」等占位句敷衍。
2. 禁止 Markdown（#、**、列表符），用普通段落和中文标点。
3. 直接输出正文，不加「以下是…」前缀。
4. 知识库与联网结果冲突时以知识库为准；无确切依据时不得编造机构全称、ISIN、费率、合同编号、精确日期等。"""

SYSTEM_PROMPT_EN = """You are an expert writer for project application documents. Strict rules:
1. All factual claims must come from [Reference Materials]. Do not fabricate unsupported facts; briefly state "not specified in the materials" when evidence is missing.
2. Do not use Markdown (#, *, or list markers). Use plain paragraphs and standard English punctuation; use clear paragraphing for multi-level content.
3. Output the document body directly. Do not add prefixes such as "The following is...".
4. If the knowledge base conflicts with web information, rely on the knowledge base.
5. Write all generated project document content in English."""

SYSTEM_PROMPT_WEB_CREATIVE_EN = """You are an expert writer for project application documents in web-assisted creative mode. Built-in web search is enabled for this request.
1. Use [Reference Materials] together with public information retrieved through web search to complete the body text and meet the approximate word target. Do not use filler phrases such as "not specified in the materials", "not provided", or similar placeholders.
2. Do not use Markdown (#, *, or list markers). Use plain paragraphs and standard English punctuation.
3. Output the document body directly. Do not add prefixes such as "The following is...".
4. If the knowledge base conflicts with web results, rely on the knowledge base. Without reliable evidence, do not fabricate organization names, ISINs, fees, contract numbers, exact dates, or similar precise facts.
5. Write all generated project document content in English."""

PARA_CLOSING_CALM = (
    "请完成本节正文。所有具体事实须来源于上述参考资料，无依据的要点请注明「资料未载明」，不得臆造。"
)
PARA_CLOSING_CREATIVE = (
    "请完成本节正文：在参考资料与联网检索基础上写满约订字数；勿用「资料未载明」「资料未提供」等占位句；"
    "说不清处用稳妥概括表述，仍勿编造编码、费率、精确日期等。"
)

TABLE_CLOSING_CALM = "无可靠片段依据该格所问时，可填「资料未载明」。"
TABLE_CLOSING_CREATIVE = (
    "优先依据片段与联网检索作答，写满该格；勿单写「资料未载明」敷衍；仍勿编造编码、费率、精确日期等。"
)

USER_PROMPT_PARA = """【撰写任务】章节：{target_chapter}
要求：{description}
字数：约 {word_limit} 字{hint_block}{vision_block}

【内容要求】
- 内容要充实，避免简短或过于概括
- 请详细展开，不要只写要点或提纲
- 每个要点需有具体说明和数据支撑
- 确保内容完整，达到指定字数要求

【参考资料】
{retrieved_texts}
{kb_note}
{para_closing}"""

USER_PROMPT_TABLE = """【表格填写任务】章节：{target_chapter}
单元格要求：{description}
字数上限：{word_limit} 字{hint_block}{vision_block}

【参考资料】
{retrieved_texts}
{table_ctx_block}{kb_note}
只输出应填入该格的**简短答案**（通常一行），直接依据参考资料，不写分析、不复述整行表头。
**只回答本列表头/本格要求所问**；勿粘贴其它列的问题全文或说明；勿输出「资料N：____」等模板占位骨架；勿在一格内写多列混合内容或长段方案叙述。
{table_closing}"""


def _normalize_web_writing_mode(mode: Optional[str]) -> str:
    raw = (
        mode
        if mode is not None
        else getattr(config, "WEB_SEARCH_WRITING_MODE", "calm")
    )
    return "creative" if str(raw or "").strip().lower() == "creative" else "calm"


def _normalize_language(language: Optional[str]) -> str:
    return "en" if str(language or "").strip().lower() == "en" else "zh"


def _web_gen_prompt_parts(
    use_plus: bool,
    web_writing_mode: Optional[str],
    has_kb_hit: bool,
    language: Optional[str] = None,
) -> Tuple[bool, str, str, str, str]:
    """返回 (web_creative_prompt, system_text, kb_note, para_closing, table_closing)。"""
    wm = _normalize_web_writing_mode(web_writing_mode)
    creative = bool(use_plus and wm == "creative")
    lang = _normalize_language(language)
    if creative:
        sys_t = SYSTEM_PROMPT_WEB_CREATIVE_EN if lang == "en" else SYSTEM_PROMPT_WEB_CREATIVE
        if has_kb_hit:
            kb = (
                "\n【已提供知识库检索片段；可同时使用内置联网检索补充。"
                "二者未覆盖处请用概括性表述写全，勿反复堆砌「资料未载明」。】"
            )
        else:
            kb = (
                "\n【知识库无命中；请充分使用内置联网检索与合理概括完成正文，"
                "勿用「资料未载明」「未提供」等占篇幅；具体编码、费率、精确日期无据时仍勿编造。】"
            )
        return True, sys_t, kb, PARA_CLOSING_CREATIVE, TABLE_CLOSING_CREATIVE
    kb = (
        "\n【已提供检索片段，具体事实须与之相符；片段未涉及的请注明资料未载明。】"
        if has_kb_hit
        else "\n【无有效知识库命中，禁止编造机构名/ISIN/费率/日期/评级等具体数字。】"
    )
    sys_t = SYSTEM_PROMPT_EN if lang == "en" else SYSTEM_PROMPT
    return False, sys_t, kb, PARA_CLOSING_CALM, TABLE_CLOSING_CALM


def format_template_vision_block(task: FillTask) -> str:
    """来自模板视觉/降级的版式与章节提示，拼入用户提示。"""
    lh = task.location_hint or {}
    parts: List[str] = []
    tv = (lh.get("template_vision_compact") or "").strip()
    if tv:
        parts.append("【模板版式与填写说明（视觉摘要）】" + tv)
    ch = (lh.get("chapter_style_hint") or "").strip()
    if ch:
        parts.append("【本章写作/格式提示（来自模板视觉）】" + ch)
    if not parts:
        return ""
    return "\n" + "\n".join(parts) + "\n"


@dataclass
class GenerationBundle:
    """单次检索 + 组装后的请求包；生成与审核共用 ref_texts，避免重复 search。"""

    messages: List[Dict[str, Any]]
    model: str
    temperature: float
    extra_body: Dict[str, Any]
    route_meta: Dict[str, Any]
    ref_texts: str
    evidence_refs: List[str]


class ContentGenerator:
    """RAG generation with route-aware model fallback chains."""

    def __init__(self, vector_store: VectorStore, api_key: str | None = None):
        self._vs = vector_store
        self._client = self._client_for_api_key(api_key) if api_key else config.openai_client_for_chat()
        self.last_usage: Any = None
        self.last_model: str = ""

    @staticmethod
    def _client_for_api_key(api_key: str) -> Any:
        from openai import OpenAI

        return OpenAI(
            api_key=api_key,
            base_url=config.DASHSCOPE_COMPAT_BASE,
            timeout=config.OPENAI_TIMEOUT,
            max_retries=config.OPENAI_MAX_RETRIES,
        )

    def _get_client(self) -> Any:
        """Return the active chat client."""
        return self._client

    def pop_last_usage(self) -> tuple[str, Any]:
        usage = self.last_usage
        model = self.last_model
        self.last_usage = None
        self.last_model = ""
        return model, usage

    def _candidate_models(
        self,
        default_model: str,
        route_meta: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """Return the ordered fallback chain for the current route."""
        models = [default_model]
        tier = str((route_meta or {}).get("generation_tier") or "")
        if tier == "large":
            models.extend(
                [
                    getattr(config, "FALLBACK_LLM_MODEL_1", ""),
                    getattr(config, "FALLBACK_LLM_MODEL_2", ""),
                    getattr(config, "FALLBACK_LLM_MODEL_3", ""),
                ]
            )
        elif tier in ("small_rag", "table_cell_fast"):
            models.extend(
                [
                    getattr(config, "SMALL_LLM_FALLBACK_MODEL", ""),
                    getattr(config, "VISION_WEB_FALLBACK_MODEL", ""),
                ]
            )
        elif tier == "vision_web":
            models.extend(
                [
                    getattr(config, "VISION_WEB_FALLBACK_MODEL", ""),
                    getattr(config, "SMALL_LLM_FALLBACK_MODEL", ""),
                ]
            )
        elif tier == "table_cell_vision":
            models.extend(
                [
                    getattr(config, "TABLE_CELL_VISION_FALLBACK_MODEL", ""),
                    getattr(config, "TABLE_CELL_FALLBACK_MODEL", ""),
                ]
            )
        seen = set()
        ordered: List[str] = []
        for model in models:
            mid = (model or "").strip()
            if not mid or mid in seen:
                continue
            seen.add(mid)
            ordered.append(mid)
        return ordered

    def _build_chat_request(
        self,
        task: FillTask,
        top_k: int,
        enable_web: bool,
        retrieval_max_distance: Optional[float],
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
        web_writing_mode: Optional[str] = None,
        table_cell_vision_pngs: Optional[List[bytes]] = None,
        fast_mode: bool = False,
        language: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], str, float, Dict[str, Any], Dict[str, Any], str]:
        query = expand_query(task.target_chapter, task.description, task.task_type)
        max_d = (
            retrieval_max_distance
            if retrieval_max_distance is not None
            else config.RETRIEVAL_MAX_DISTANCE
        )

        kb_empty = self._vs.get_collection_count() == 0

        # 全量召回模式：跳过向量检索，直接读取知识库全部文档
        if config.FULL_RECALL_MODE and not kb_empty:
            all_docs = self._vs.get_all_documents(
                max_chars=config.FULL_RECALL_MAX_CHARS
            )
            results = all_docs
            ref_texts = self._format_full_recall(all_docs)
            weak_kb = False
            best_hit_distance = None
            best_similarity_est = 1.0
            low_similarity = False
        else:
            if kb_empty:
                results = []
            else:
                results = self._vs.search(
                    query, top_k=top_k, max_distance=max_d
                )

            weak_kb = kb_empty or len(results) == 0

            best_hit_distance: Optional[float] = None
            best_similarity_est: Optional[float] = None
            low_similarity = False
            if results:
                dists = [
                    float(r["distance"])
                    for r in results
                    if r.get("distance") is not None
                ]
                if dists:
                    best_hit_distance = min(dists)
                    best_similarity_est = max(
                        0.0, min(1.0, 1.0 - best_hit_distance)
                    )
                    low_similarity = best_similarity_est < config.RETRIEVAL_WEB_SIMILARITY_THRESHOLD

            ref_texts = self._format_kb(results)
        evidence_refs = evidence_refs_from_results(results)

        word_limit = task.word_limit
        if task.task_type == "table_cell":
            word_limit = min(word_limit, 120)

        has_kb_hit = len(results) > 0
        use_plus = enable_web and (weak_kb or low_similarity)
        if fast_mode:
            use_plus = False
        web_creative, system_prompt, kb_note, para_closing, table_closing = (
            _web_gen_prompt_parts(use_plus, web_writing_mode, has_kb_hit, language)
        )

        hint_block = (
            ("\n上轮审核意见：" + correction_hint.strip())
            if correction_hint and correction_hint.strip()
            else ""
        )
        vision_block = format_template_vision_block(task)

        if task.task_type == "table_cell":
            table_ctx_block = (
                "\n【本格表格上下文】\n" + (table_context or "").strip() + "\n"
                if table_context and table_context.strip()
                else ""
            )
            user_msg = USER_PROMPT_TABLE.format(
                target_chapter=task.target_chapter,
                description=task.description,
                word_limit=word_limit,
                hint_block=hint_block,
                vision_block=vision_block,
                retrieved_texts=ref_texts,
                table_ctx_block=table_ctx_block,
                kb_note=kb_note,
                table_closing=table_closing,
            )
            use_tbl_vis = (
                not _fast_table_cell_route(task, fast_mode)
                and getattr(config, "TABLE_CELL_VISION", True)
                and table_cell_vision_pngs
            )
            user_content: Any = (
                build_table_cell_user_content(user_msg, table_cell_vision_pngs)
                if use_tbl_vis
                else user_msg
            )
        else:
            user_msg = USER_PROMPT_PARA.format(
                target_chapter=task.target_chapter,
                description=task.description,
                word_limit=word_limit,
                hint_block=hint_block,
                vision_block=vision_block,
                retrieved_texts=ref_texts,
                kb_note=kb_note,
                para_closing=para_closing,
            )
            user_content = user_msg

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        extra_body: Dict[str, Any] = {}
        long_paragraph = (
            task.task_type == "paragraph"
            and int(word_limit) > config.LONG_PARAGRAPH_WORDS
        )
        strong_sim = (
            best_similarity_est is not None
            and best_similarity_est >= config.STRONG_RAG_SIMILARITY_FLOOR
        )
        use_small_rag = (
            config.USE_SMALL_LLM_FOR_STRONG_RAG
            and has_kb_hit
            and not low_similarity
            and strong_sim
            and not long_paragraph
            and not fast_mode
        )

        if use_plus:
            extra_body["enable_search"] = True
            model = config.VISION_WEB_MODEL
            temperature = config.TEMP_WEB_GEN
            generation_tier = "vision_web"
        elif use_small_rag:
            model = config.SMALL_LLM_MODEL
            temperature = config.TEMP_SMALL_LLM
            generation_tier = "small_rag"
        else:
            model = config.LARGE_LLM_MODEL
            temperature = config.TEMP_LARGE_LLM
            generation_tier = "large"

        table_cell_mm = (
            task.task_type == "table_cell"
            and getattr(config, "TABLE_CELL_VISION", True)
            and table_cell_vision_pngs
            and isinstance(user_content, list)
        )
        if table_cell_mm:
            generation_tier = "table_cell_vision"
            if not use_plus:
                model = config.TABLE_CELL_VISION_MODEL
                temperature = float(getattr(config, "TEMP_VISION", 0.25))
        if _fast_table_cell_route(task, fast_mode):
            extra_body.pop("enable_search", None)
            table_cell_mm = False
            model = getattr(config, "BATCH_TABLE_FAST_MODEL", config.TABLE_CELL_VISION_MODEL)
            temperature = 0.1
            generation_tier = "table_cell_fast"

        gen_max_out = _max_output_tokens(word_limit, task.task_type)
        route_meta: Dict[str, Any] = {
            "task_id": task.task_id,
            "target_chapter": task.target_chapter,
            "kb_empty": kb_empty,
            "kb_hits": len(results),
            "weak_kb": weak_kb,
            "low_similarity": low_similarity,
            "best_hit_distance": best_hit_distance,
            "best_similarity_est": best_similarity_est,
            "retrieval_web_similarity_threshold": config.RETRIEVAL_WEB_SIMILARITY_THRESHOLD,
            "enable_web_requested": enable_web,
            "native_web_search": bool(extra_body.get("enable_search")),
            "model": model,
            "temperature": temperature,
            "top_k": top_k,
            "retrieval_max_distance": max_d,
            "extra_body_keys": list(extra_body.keys()),
            "generation_tier": generation_tier,
            "use_small_llm_for_rag": bool(use_small_rag),
            "gen_max_output_tokens": gen_max_out,
            "web_writing_mode": _normalize_web_writing_mode(web_writing_mode),
            "language": _normalize_language(language),
            "web_creative_prompt": web_creative,
            "table_cell_multimodal": bool(table_cell_mm),
            "table_vision_n_images": len(table_cell_vision_pngs or []),
            "fast_mode": bool(fast_mode),
            "full_recall_mode": bool(config.FULL_RECALL_MODE),
            "evidence_refs": evidence_refs,
        }
        _ensure_gen_logger()
        _LOG.info("content_gen_route %s", route_meta)

        return messages, model, temperature, extra_body, route_meta, ref_texts

    def prepare_bundle_from_evidence(
        self,
        task: FillTask,
        evidence: "Any",
        enable_web: bool = False,
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
        web_writing_mode: Optional[str] = None,
        table_cell_vision_pngs: Optional[List[bytes]] = None,
        fast_mode: bool = False,
        language: Optional[str] = None,
    ) -> GenerationBundle:
        """使用预检索的 Evidence 构建 GenerationBundle，避免重复向量检索。"""
        from core.evidence_planner import compress_evidence, Evidence

        ref_texts = compress_evidence(evidence, task, max_chars=config.RAG_SNIPPET_MAX_CHARS)
        evidence_refs = evidence_refs_from_results(evidence.raw_results)

        word_limit = task.word_limit
        if task.task_type == "table_cell":
            word_limit = min(word_limit, 120)

        low_similarity = (
            evidence.best_similarity is not None
            and evidence.best_similarity < config.RETRIEVAL_WEB_SIMILARITY_THRESHOLD
        )
        has_kb_hit = evidence.kb_hits > 0
        weak_kb = evidence.weak_kb

        use_plus = enable_web and (weak_kb or low_similarity)
        if fast_mode:
            use_plus = False
        strong_sim = (
            evidence.best_similarity is not None
            and evidence.best_similarity >= config.STRONG_RAG_SIMILARITY_FLOOR
        )
        long_paragraph = (
            task.task_type == "paragraph" and int(word_limit) > config.LONG_PARAGRAPH_WORDS
        )
        use_small_rag = (
            config.USE_SMALL_LLM_FOR_STRONG_RAG
            and has_kb_hit
            and not low_similarity
            and strong_sim
            and not long_paragraph
            and not fast_mode
        )

        web_creative, system_prompt, kb_note, para_closing, table_closing = (
            _web_gen_prompt_parts(use_plus, web_writing_mode, has_kb_hit, language)
        )
        hint_block = (
            ("\n上轮审核意见：" + correction_hint.strip())
            if correction_hint and correction_hint.strip()
            else ""
        )
        vision_block = format_template_vision_block(task)

        if task.task_type == "table_cell":
            table_ctx_block = (
                "\n【本格表格上下文】\n" + (table_context or "").strip() + "\n"
                if table_context and table_context.strip()
                else ""
            )
            user_msg = USER_PROMPT_TABLE.format(
                target_chapter=task.target_chapter,
                description=task.description,
                word_limit=word_limit,
                hint_block=hint_block,
                vision_block=vision_block,
                retrieved_texts=ref_texts,
                table_ctx_block=table_ctx_block,
                kb_note=kb_note,
                table_closing=table_closing,
            )
            use_tbl_vis = (
                not _fast_table_cell_route(task, fast_mode)
                and getattr(config, "TABLE_CELL_VISION", True)
                and table_cell_vision_pngs
            )
            user_content: Any = (
                build_table_cell_user_content(user_msg, table_cell_vision_pngs)
                if use_tbl_vis
                else user_msg
            )
        else:
            user_msg = USER_PROMPT_PARA.format(
                target_chapter=task.target_chapter,
                description=task.description,
                word_limit=word_limit,
                hint_block=hint_block,
                vision_block=vision_block,
                retrieved_texts=ref_texts,
                kb_note=kb_note,
                para_closing=para_closing,
            )
            user_content = user_msg

        extra_body: Dict[str, Any] = {}
        if use_plus:
            extra_body["enable_search"] = True
            model = config.VISION_WEB_MODEL
            temperature = config.TEMP_WEB_GEN
            generation_tier = "vision_web"
        elif use_small_rag:
            model = config.SMALL_LLM_MODEL
            temperature = config.TEMP_SMALL_LLM
            generation_tier = "small_rag"
        else:
            model = config.LARGE_LLM_MODEL
            temperature = config.TEMP_LARGE_LLM
            generation_tier = "large"

        table_cell_mm = (
            task.task_type == "table_cell"
            and getattr(config, "TABLE_CELL_VISION", True)
            and table_cell_vision_pngs
            and isinstance(user_content, list)
        )
        if table_cell_mm:
            generation_tier = "table_cell_vision"
            if not use_plus:
                model = config.TABLE_CELL_VISION_MODEL
                temperature = float(getattr(config, "TEMP_VISION", 0.25))
        if _fast_table_cell_route(task, fast_mode):
            extra_body.pop("enable_search", None)
            table_cell_mm = False
            model = getattr(config, "BATCH_TABLE_FAST_MODEL", config.TABLE_CELL_VISION_MODEL)
            temperature = 0.1
            generation_tier = "table_cell_fast"

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        gen_max_out = _max_output_tokens(word_limit, task.task_type)
        route_meta: Dict[str, Any] = {
            "task_id": task.task_id,
            "target_chapter": task.target_chapter,
            "kb_empty": weak_kb,
            "kb_hits": evidence.kb_hits,
            "weak_kb": weak_kb,
            "low_similarity": low_similarity,
            "best_similarity_est": evidence.best_similarity,
            "enable_web_requested": enable_web,
            "native_web_search": bool(extra_body.get("enable_search")),
            "model": model,
            "temperature": temperature,
            "generation_tier": generation_tier,
            "use_small_llm_for_rag": bool(use_small_rag),
            "gen_max_output_tokens": gen_max_out,
            "from_shared_evidence": True,
            "web_writing_mode": _normalize_web_writing_mode(web_writing_mode),
            "language": _normalize_language(language),
            "web_creative_prompt": web_creative,
            "table_cell_multimodal": bool(table_cell_mm),
            "table_vision_n_images": len(table_cell_vision_pngs or []),
            "fast_mode": bool(fast_mode),
            "evidence_refs": evidence_refs,
        }
        _ensure_gen_logger()
        _LOG.info("content_gen_route_evidence %s", route_meta)
        return GenerationBundle(
            messages=messages,
            model=model,
            temperature=temperature,
            extra_body=extra_body,
            route_meta=route_meta,
            ref_texts=ref_texts,
            evidence_refs=evidence_refs,
        )

    def prepare_generation_bundle(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
        web_writing_mode: Optional[str] = None,
        table_cell_vision_pngs: Optional[List[bytes]] = None,
        fast_mode: bool = False,
        language: Optional[str] = None,
    ) -> GenerationBundle:
        messages, model, temperature, extra_body, route_meta, ref_texts = (
            self._build_chat_request(
                task,
                top_k,
                enable_web,
                retrieval_max_distance,
                table_context=table_context,
                correction_hint=correction_hint,
                web_writing_mode=web_writing_mode,
                table_cell_vision_pngs=table_cell_vision_pngs,
                fast_mode=fast_mode,
                language=language,
            )
        )
        return GenerationBundle(
            messages=messages,
            model=model,
            temperature=temperature,
            extra_body=extra_body,
            route_meta=route_meta,
            ref_texts=ref_texts,
            evidence_refs=list(route_meta.get("evidence_refs") or []),
        )

    def stream_from_bundle(
        self,
        bundle: GenerationBundle,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Iterator[str]:
        if route_hook:
            route_hook(bundle.route_meta)
        client = self._get_client()
        model_chain = self._candidate_models(bundle.model, bundle.route_meta)
        last_error: Optional[Exception] = None
        for model in model_chain:
            acc_len = 0
            self.last_usage = None
            self.last_model = ""
            try:
                stream = chat_completions_create(
                    client,
                    model=model,
                    messages=bundle.messages,
                    temperature=bundle.temperature,
                    stream=True,
                    extra_body=bundle.extra_body,
                    max_tokens=int(bundle.route_meta.get("gen_max_output_tokens") or 4096),
                )
                for chunk in stream:
                    usage = getattr(chunk, "usage", None)
                    if usage is not None:
                        self.last_usage = usage
                        self.last_model = str(getattr(chunk, "model", None) or model)
                    ch = chunk.choices[0] if chunk.choices else None
                    if not ch or not ch.delta:
                        continue
                    piece = ch.delta.content or ""
                    if piece:
                        acc_len += len(piece)
                        yield piece
                if acc_len > 0:
                    self.last_model = self.last_model or model
                    _ensure_gen_logger()
                    _LOG.info(
                        "content_gen_stream_done task_id=%s chapter=%s model=%s native_web=%s approx_chars=%s",
                        bundle.route_meta.get("task_id"),
                        bundle.route_meta.get("target_chapter"),
                        model,
                        bundle.route_meta.get("native_web_search"),
                        acc_len,
                    )
                    return
                _LOG.warning("content_gen_stream_empty model=%s, trying next fallback", model)
            except Exception as e:
                last_error = e
                _LOG.warning("content_gen_stream_error model=%s err=%s", model, e)
        if last_error is not None:
            raise last_error

    def generate_stream(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
        web_writing_mode: Optional[str] = None,
        table_cell_vision_pngs: Optional[List[bytes]] = None,
        language: Optional[str] = None,
    ) -> Iterator[str]:
        bundle = self.prepare_generation_bundle(
            task,
            top_k=top_k,
            enable_web=enable_web,
            retrieval_max_distance=retrieval_max_distance,
            table_context=table_context,
            correction_hint=correction_hint,
            web_writing_mode=web_writing_mode,
            table_cell_vision_pngs=table_cell_vision_pngs,
            language=language,
        )
        yield from self.stream_from_bundle(bundle, route_hook=route_hook)

    @staticmethod
    def _is_error_content(text: str) -> bool:
        """检测内容是否为 API 错误信息。"""
        if not text:
            return False
        error_markers = [
            "Error code:",
            "error:",
            "'error':",
            "AllocationQuota",
            "FreeTierOnly",
            "exhausted",
            "chatcmpl-",
            "request_id",
        ]
        return any(marker in text for marker in error_markers)

    def generate_from_bundle(
        self,
        bundle: GenerationBundle,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        if route_hook:
            route_hook(bundle.route_meta)
        client = self._get_client()
        last_error: Optional[Exception] = None
        for model in self._candidate_models(bundle.model, bundle.route_meta):
            try:
                self.last_usage = None
                self.last_model = ""
                resp = chat_completions_create(
                    client,
                    model=model,
                    messages=bundle.messages,
                    temperature=bundle.temperature,
                    stream=False,
                    extra_body=bundle.extra_body,
                    max_tokens=int(bundle.route_meta.get("gen_max_output_tokens") or 4096),
                )
                ch0 = resp.choices[0] if resp.choices else None
                text = (ch0.message.content if ch0 and ch0.message else "") or ""
                if not text.strip():
                    _LOG.warning("content_gen_nonstream_empty model=%s, trying next fallback", model)
                    continue
                if self._is_error_content(text):
                    _LOG.warning("content_gen_nonstream_error_text model=%s text=%s", model, text[:200])
                    continue
                self.last_usage = getattr(resp, "usage", None)
                self.last_model = str(getattr(resp, "model", None) or model)
                _ensure_gen_logger()
                _LOG.info(
                    "content_gen_nonstream_done task_id=%s chapter=%s model=%s native_web=%s approx_chars=%s",
                    bundle.route_meta.get("task_id"),
                    bundle.route_meta.get("target_chapter"),
                    model,
                    bundle.route_meta.get("native_web_search"),
                    len(text),
                )
                return text.strip()
            except Exception as e:
                last_error = e
                _LOG.warning("content_gen_nonstream_error model=%s err=%s", model, e)
        if last_error is not None:
            _LOG.error("content_gen_all_models_failed err=%s", last_error)
        return "(generation failed; check model config and retry)"

    def generate(

        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
        web_writing_mode: Optional[str] = None,
        table_cell_vision_pngs: Optional[List[bytes]] = None,
        language: Optional[str] = None,
    ) -> str:
        if route_hook is not None:
            return "".join(
                self.generate_stream(
                    task,
                    top_k=top_k,
                    enable_web=enable_web,
                    retrieval_max_distance=retrieval_max_distance,
                    route_hook=route_hook,
                    table_context=table_context,
                    correction_hint=correction_hint,
                    web_writing_mode=web_writing_mode,
                    table_cell_vision_pngs=table_cell_vision_pngs,
                    language=language,
                )
            ).strip()
        bundle = self.prepare_generation_bundle(
            task,
            top_k=top_k,
            enable_web=enable_web,
            retrieval_max_distance=retrieval_max_distance,
            table_context=table_context,
            correction_hint=correction_hint,
            web_writing_mode=web_writing_mode,
            table_cell_vision_pngs=table_cell_vision_pngs,
            language=language,
        )
        return self.generate_from_bundle(bundle, route_hook=None)

    @staticmethod
    def _format_kb(results: List[Dict]) -> str:
        if not results:
            return "（向量库中未检索到满足距离阈值的片段。）"
        cap = max(200, int(config.RAG_SNIPPET_MAX_CHARS))
        parts = []
        for i, r in enumerate(results, 1):
            dist = r.get("distance")
            dist_s = f"{dist:.4f}" if dist is not None else "n/a"
            body = r.get("text") or ""
            if len(body) > cap:
                body = body[:cap] + "\n…(片段已截断以节省上下文长度)"
            parts.append(
                f"【参考{i}】相似度距离={dist_s} 来源:{r['metadata'].get('source', '未知')}\n{body}"
            )
        return "\n\n---\n\n".join(parts)

    @staticmethod
    def _format_full_recall(docs: List[Dict]) -> str:
        """全量召回格式化：按来源文件分组拼接，不显示距离分数。"""
        if not docs:
            return "（知识库中无可用文档。）"
        # 按来源文件分组
        by_source: Dict[str, List[str]] = {}
        for d in docs:
            src = (d.get("metadata") or {}).get("source", "未知来源")
            text = (d.get("text") or "").strip()
            if text:
                by_source.setdefault(src, []).append(text)
        parts = []
        for src, texts in by_source.items():
            body = "\n\n".join(texts)
            parts.append(f"【文档：{src}】\n{body}")
        return "\n\n===\n\n".join(parts)
