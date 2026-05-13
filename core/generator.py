from typing import List, Dict, Optional, Iterator, Tuple
from openai import OpenAI
from core.vector_store import VectorStore
from core.fill_task import FillTask
from core.web_search import search_web
from core.dashscope_chat import chat_completions_create
import config


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
    """RAG + 可选联网检索 + 距离阈值；支持流式输出。"""

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
    ) -> Tuple[List[Dict[str, str]], str, float]:
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

        web_blocks: List[str] = []
        if enable_web and weak_kb:
            snippets = search_web(query, max_results=5)
            if snippets:
                for i, s in enumerate(snippets, 1):
                    title = s.get("title") or "来源"
                    url = s.get("url") or ""
                    body = s.get("content") or ""
                    web_blocks.append(f"【网络参考{i}】{title}\n{body}\n链接：{url}")
            else:
                web_blocks.append(
                    "（已开启联网但未配置 TAVILY_API_KEY 或检索失败，无网络摘要。）"
                )

        ref_texts = self._format_kb(results)
        if web_blocks:
            ref_texts = ref_texts + "\n\n---\n\n" + "\n\n".join(web_blocks)

        if ref_texts.strip() == "":
            ref_texts = (
                "（当前无向量库命中且无可用网络摘要。请仅作极短说明：无法依据资料填写，"
                "勿编造任何具体事实或专有名词。）"
            )

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
                "若文中有【网络参考】，仅可谨慎采信其中已写明的事实，勿添加其中未出现的具体数据。"
            )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ]

        # 弱知识库且开启联网（已并入网络侧提示）：与视觉同档 qwen-plus
        use_plus = enable_web and weak_kb
        if use_plus:
            return messages, config.VISION_WEB_MODEL, config.TEMP_WEB_GEN
        return messages, config.LARGE_LLM_MODEL, config.TEMP_LARGE_LLM

    def generate_stream(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
    ) -> Iterator[str]:
        messages, model, temperature = self._build_chat_request(
            task, top_k, enable_web, retrieval_max_distance
        )
        stream = chat_completions_create(
            self._client,
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            ch = chunk.choices[0] if chunk.choices else None
            if not ch or not ch.delta:
                continue
            piece = ch.delta.content or ""
            if piece:
                yield piece

    def generate(
        self,
        task: FillTask,
        top_k: int = 3,
        enable_web: bool = False,
        retrieval_max_distance: Optional[float] = None,
    ) -> str:
        return "".join(
            self.generate_stream(
                task,
                top_k=top_k,
                enable_web=enable_web,
                retrieval_max_distance=retrieval_max_distance,
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
