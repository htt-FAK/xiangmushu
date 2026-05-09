from typing import List, Dict
from openai import OpenAI
from core.vector_store import VectorStore
from core.template_analyzer import FillTask
import config


SYSTEM_PROMPT = """你是一位资深的项目计划书撰写专家，擅长根据历史资料撰写高质量的项目申报内容。
要求：
- 内容专业、具体，避免空泛
- 适当引用数据、指标、技术参数
- 语言符合政府/企业科技项目申报风格
- 直接输出内容，不要加"以下是..."等前缀"""

USER_PROMPT = """【撰写任务】
章节：{target_chapter}
内容要求：{description}
字数要求：约 {word_limit} 字

【历史参考资料】
{retrieved_texts}

请根据以上资料，撰写该部分的内容。如果参考资料不足，请基于你的专业知识合理补充，但要保持专业性和可信度。"""


class ContentGenerator:
    """RAG 内容生成：检索 + LLM。"""

    def __init__(self, vector_store: VectorStore, model: str = None):
        self._vs = vector_store
        self._client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
        self._model = model or config.DEFAULT_LLM_MODEL

    def generate(self, task: FillTask, top_k: int = 3) -> str:
        # 1. 检索
        query = f"{task.target_chapter} {task.description}"
        results = self._vs.search(query, top_k=top_k)

        # 2. 拼接参考文本
        if results:
            ref_texts = "\n\n---\n\n".join(
                f"【参考{i+1}】(来源:{r['metadata'].get('source', '未知')})\n{r['text']}"
                for i, r in enumerate(results)
            )
        else:
            ref_texts = "（未找到相关历史资料）"

        # 3. 根据任务类型调整字数
        word_limit = task.word_limit
        if task.task_type == "table_cell":
            word_limit = min(word_limit, 80)

        # 4. 调用 LLM
        user_msg = USER_PROMPT.format(
            target_chapter=task.target_chapter,
            description=task.description,
            word_limit=word_limit,
            retrieved_texts=ref_texts,
        )

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.7,
        )

        return response.choices[0].message.content.strip()
