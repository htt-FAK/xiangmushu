import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from openai import OpenAI

import config
from core.dashscope_chat import chat_completions_create
from core.fill_task import FillTask
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

USER_PROMPT_PARA = """【撰写任务】章节：{target_chapter}
要求：{description}
字数：约 {word_limit} 字{hint_block}{vision_block}

【参考资料】
{retrieved_texts}
{kb_note}
请完成本节正文。所有具体事实须来源于上述参考资料，无依据的要点请注明「资料未载明」，不得臆造。"""

USER_PROMPT_TABLE = """【表格填写任务】章节：{target_chapter}
单元格要求：{description}
字数上限：{word_limit} 字{hint_block}{vision_block}

【参考资料】
{retrieved_texts}
{table_ctx_block}{kb_note}
只输出应填入该格的**简短答案**（通常一行），直接依据参考资料，不写分析、不复述整行表头。
**只回答本列表头/本格要求所问**；勿粘贴其它列的问题全文或说明；勿输出「资料N：____」等模板占位骨架；勿在一格内写多列混合内容或长段方案叙述。"""


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

    messages: List[Dict[str, str]]
    model: str
    temperature: float
    extra_body: Dict[str, Any]
    route_meta: Dict[str, Any]
    ref_texts: str


class ContentGenerator:
    """RAG + 距离阈值；空库/无命中，或（开启联网且）最佳命中估算相似度过低时，走百炼内置搜索（enable_search + 联网档模型）。"""

    def __init__(self, vector_store: VectorStore):
        self._vs = vector_store
        self._client = OpenAI(
            api_key=config.OPENAI_COMPAT_API_KEY or "sk-placeholder",
            base_url=config.OPENAI_BASE_URL,
            timeout=config.OPENAI_TIMEOUT,
            max_retries=config.OPENAI_MAX_RETRIES,
        )

    def _build_chat_request(
        self,
        task: FillTask,
        top_k: int,
        enable_web: bool,
        retrieval_max_distance: Optional[float],
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
    ) -> Tuple[List[Dict[str, str]], str, float, Dict[str, Any], Dict[str, Any], str]:
        query = expand_query(task.target_chapter, task.description, task.task_type)
        max_d = (
            retrieval_max_distance
            if retrieval_max_distance is not None
            else config.RETRIEVAL_MAX_DISTANCE
        )

        kb_empty = self._vs.get_collection_count() == 0
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

        word_limit = task.word_limit
        if task.task_type == "table_cell":
            word_limit = min(word_limit, 120)

        has_kb_hit = len(results) > 0
        kb_note = (
            "\n【已提供检索片段，具体事实须与之相符；片段未涉及的请注明资料未载明。】"
            if has_kb_hit
            else "\n【无有效知识库命中，禁止编造机构名/ISIN/费率/日期/评级等具体数字。】"
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
            )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        use_plus = enable_web and (weak_kb or low_similarity)
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
    ) -> GenerationBundle:
        """使用预检索的 Evidence 构建 GenerationBundle，避免重复向量检索。"""
        from core.evidence_planner import compress_evidence, Evidence

        ref_texts = compress_evidence(evidence, task, max_chars=config.RAG_SNIPPET_MAX_CHARS)

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
        )

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

        kb_note = (
            "\n【已提供检索片段，具体事实须与之相符；片段未涉及的请注明资料未载明。】"
            if has_kb_hit
            else "\n【无有效知识库命中，禁止编造机构名/ISIN/费率/日期/评级等具体数字。】"
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
            )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
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
        )

    def prepare_generation_bundle(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
    ) -> GenerationBundle:
        messages, model, temperature, extra_body, route_meta, ref_texts = (
            self._build_chat_request(
                task,
                top_k,
                enable_web,
                retrieval_max_distance,
                table_context=table_context,
                correction_hint=correction_hint,
            )
        )
        return GenerationBundle(
            messages=messages,
            model=model,
            temperature=temperature,
            extra_body=extra_body,
            route_meta=route_meta,
            ref_texts=ref_texts,
        )

    def stream_from_bundle(
        self,
        bundle: GenerationBundle,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Iterator[str]:
        if route_hook:
            route_hook(bundle.route_meta)
        stream = chat_completions_create(
            self._client,
            model=bundle.model,
            messages=bundle.messages,
            temperature=bundle.temperature,
            stream=True,
            extra_body=bundle.extra_body,
            max_tokens=int(bundle.route_meta.get("gen_max_output_tokens") or 4096),
        )
        acc_len = 0
        for chunk in stream:
            ch = chunk.choices[0] if chunk.choices else None
            if not ch or not ch.delta:
                continue
            piece = ch.delta.content or ""
            if piece:
                acc_len += len(piece)
                yield piece
        _ensure_gen_logger()
        _LOG.info(
            "content_gen_stream_done task_id=%s chapter=%s model=%s native_web=%s approx_chars=%s",
            bundle.route_meta.get("task_id"),
            bundle.route_meta.get("target_chapter"),
            bundle.model,
            bundle.route_meta.get("native_web_search"),
            acc_len,
        )

    def generate_stream(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
    ) -> Iterator[str]:
        bundle = self.prepare_generation_bundle(
            task,
            top_k=top_k,
            enable_web=enable_web,
            retrieval_max_distance=retrieval_max_distance,
            table_context=table_context,
            correction_hint=correction_hint,
        )
        yield from self.stream_from_bundle(bundle, route_hook=route_hook)

    def generate_from_bundle(
        self,
        bundle: GenerationBundle,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        if route_hook:
            route_hook(bundle.route_meta)
        resp = chat_completions_create(
            self._client,
            model=bundle.model,
            messages=bundle.messages,
            temperature=bundle.temperature,
            stream=False,
            extra_body=bundle.extra_body,
            max_tokens=int(bundle.route_meta.get("gen_max_output_tokens") or 4096),
        )
        ch0 = resp.choices[0] if resp.choices else None
        text = (ch0.message.content if ch0 and ch0.message else "") or ""
        _ensure_gen_logger()
        _LOG.info(
            "content_gen_nonstream_done task_id=%s chapter=%s model=%s native_web=%s approx_chars=%s",
            bundle.route_meta.get("task_id"),
            bundle.route_meta.get("target_chapter"),
            bundle.model,
            bundle.route_meta.get("native_web_search"),
            len(text),
        )
        return text.strip()

    def generate(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
        table_context: Optional[str] = None,
        correction_hint: Optional[str] = None,
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
                )
            ).strip()
        bundle = self.prepare_generation_bundle(
            task,
            top_k=top_k,
            enable_web=enable_web,
            retrieval_max_distance=retrieval_max_distance,
            table_context=table_context,
            correction_hint=correction_hint,
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
