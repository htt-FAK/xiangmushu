import logging
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from openai import OpenAI

import config
from core.dashscope_chat import chat_completions_create
from core.fill_task import FillTask
from core.vector_store import VectorStore

_LOG = logging.getLogger(__name__)


def _ensure_gen_logger() -> None:
    if _LOG.handlers:
        return
    h = logging.StreamHandler()
    h.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    _LOG.addHandler(h)
    _LOG.setLevel(logging.INFO)


SYSTEM_PROMPT = """你是一位资深的项目计划书撰写专家，根据给定「参考资料」撰写申报类正文。
要求：
- **事实约束**：机构名、产品名、代码（如 ISIN）、日期、金额、比例、费率、监管状态、评级结果等，须能在「参考资料」中找到依据；不得编造与参考资料不一致或未出现的具体事实。
- **缺口处理**：参考资料未覆盖的要点，用简短语句标明「资料未载明」「检索片段未涉及」等，**不得用常识杜撰**具体数字或专有名称凑篇幅。
- 可对参考资料作忠实归纳、转述与必要衔接，但不得引入无据的细节。
- 语言符合政府/企业科技项目申报风格；直接输出正文，不要加「以下是…」等前缀。
- 禁止使用 Markdown（不要用 #、**、- 列表、[] 链接等），使用普通段落与中文标点；多级内容用「（一）（二）」或「一是…二是…」。
- 若同时给出网络摘要与知识库片段，**二者冲突时以知识库为准**；网络仅作补充且须标注性转述，不引入与知识库矛盾的事实。"""

USER_PROMPT = """【撰写任务】
章节：{target_chapter}
内容要求：{description}
字数要求：约 {word_limit} 字

【参考资料】
{retrieved_texts}

请完成本节撰写：**所有可核验的事实与专有表述须严格来源于上述【参考资料】**，不得与参考资料矛盾，不得虚构参考资料中不存在的关键事实。
若某要点在参考资料中无依据，明确说明无法从已给资料得出，不要臆造。"""


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
    ) -> Tuple[List[Dict[str, str]], str, float, Dict[str, Any], Dict[str, Any]]:
        query = f"{task.target_chapter} {task.description}"
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
                # 余弦距离族下常近似 sim ≈ 1 - d；其它度量下仅作可调启发式
                best_similarity_est = max(
                    0.0, min(1.0, 1.0 - best_hit_distance)
                )
                low_similarity = best_similarity_est < config.RETRIEVAL_WEB_SIMILARITY_THRESHOLD

        ref_texts = self._format_kb(results)

        word_limit = task.word_limit
        if task.task_type == "table_cell":
            word_limit = min(word_limit, 120)

        user_msg = USER_PROMPT.format(
            target_chapter=task.target_chapter,
            description=task.description,
            word_limit=word_limit,
            retrieved_texts=ref_texts,
        )
        if task.task_type == "table_cell":
            user_msg += (
                "\n\n【表格单元格】本任务只对应 Word 里的**一个格子**。"
                "请只输出应写入该格的**简短内容**（通常一行，不超过字数上限）；"
                "格内文字须**直接来自或可严格由【参考资料】推出**，不得编造与资料不符的名称、代码或数字；"
                "不要写长段分析、不要复述左侧表头，不要代替其它格子作答。"
            )

        has_kb_hit = len(results) > 0
        if has_kb_hit:
            user_msg += (
                "\n\n【知识库一致性】已提供检索片段，所有具体事实须与之相符；"
                "片段未出现的字段不要猜测填写，可写「资料未载明」类极短说明。"
            )
        else:
            user_msg += (
                "\n\n【无有效知识库命中】禁止编造具体机构/产品名称、ISIN、费率、日期、评级或监管结论。"
                "若模型已通过联网检索补充到公开信息，仅可谨慎采信其中已写明的事实，勿添加其中未出现的具体数据。"
            )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        # 弱知识库，或命中质量差且开启联网：走百炼内置联网（extra_body.enable_search），使用 VISION_WEB_MODEL
        use_plus = enable_web and (weak_kb or low_similarity)
        extra_body: Dict[str, Any] = {}
        if use_plus:
            extra_body["enable_search"] = True
            model = config.VISION_WEB_MODEL
            temperature = config.TEMP_WEB_GEN
        else:
            model = config.LARGE_LLM_MODEL
            temperature = config.TEMP_LARGE_LLM

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
        }
        _ensure_gen_logger()
        _LOG.info("content_gen_route %s", route_meta)

        return messages, model, temperature, extra_body, route_meta

    def generate_stream(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> Iterator[str]:
        (
            messages,
            model,
            temperature,
            extra_body,
            route_meta,
        ) = self._build_chat_request(task, top_k, enable_web, retrieval_max_distance)
        if route_hook:
            route_hook(route_meta)
        stream = chat_completions_create(
            self._client,
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
            extra_body=extra_body,
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
            route_meta.get("task_id"),
            route_meta.get("target_chapter"),
            model,
            route_meta.get("native_web_search"),
            acc_len,
        )

    def generate(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
        route_hook: Optional[Callable[[Dict[str, Any]], None]] = None,
    ) -> str:
        return "".join(
            self.generate_stream(
                task,
                top_k=top_k,
                enable_web=enable_web,
                retrieval_max_distance=retrieval_max_distance,
                route_hook=route_hook,
            )
        ).strip()

    @staticmethod
    def _format_kb(results: List[Dict]) -> str:
        if not results:
            return "（向量库中未检索到满足距离阈值的片段。）"
        parts = []
        for i, r in enumerate(results, 1):
            dist = r.get("distance")
            dist_s = f"{dist:.4f}" if dist is not None else "n/a"
            parts.append(
                f"【参考{i}】相似度距离={dist_s} 来源:{r['metadata'].get('source', '未知')}\n{r['text']}"
            )
        return "\n\n---\n\n".join(parts)
