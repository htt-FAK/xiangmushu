from dataclasses import dataclass
from typing import List
from openai import OpenAI
from core.parser import DocumentParser
import config
import json
import uuid


@dataclass
class FillTask:
    task_id: str
    target_chapter: str
    task_type: str  # "paragraph" | "table_cell"
    description: str
    location_hint: dict
    word_limit: int


class TemplateAnalyzer:
    """分析模板，输出所有需要填写的任务。"""

    def __init__(self, model: str = None):
        self._client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            base_url=config.OPENAI_BASE_URL,
        )
        self._model = model or config.DEFAULT_LLM_MODEL
        self._parser = DocumentParser()

    def analyze(self, template_path: str) -> List[FillTask]:
        doc = self._parser.parse(template_path)

        # 构造文档结构文本
        structure_text = self._build_structure_text(doc)

        prompt = f"""你是一个文档分析助手。以下是项目计划书模板的结构：

{structure_text}

请找出所有需要填写内容的空位（如空白段落、包含"请填写"/"（ ）"/"____"等占位符的段落或表格单元格）。
对每个空位输出 JSON 数组，每个元素包含：
- chapter: 所属章节标题
- type: "paragraph" 或 "table_cell"
- description: 应该填写什么内容（根据上下文推断）
- location_hint: 定位信息（段落用 {{"paragraph_text": "上下文关键词"}}，表格用 {{"table_index": 数字, "row": 行号, "col": 列号}}）
- word_limit: 建议字数

只输出 JSON 数组，不要其他内容。"""

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {
                    "role": "system",
                    "content": "你是文档分析助手，只输出 JSON，不要任何解释。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content.strip()
        # 兼容 markdown 代码块
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]

        try:
            raw_tasks = json.loads(content)
        except json.JSONDecodeError:
            return []

        tasks = []
        for item in raw_tasks:
            tasks.append(
                FillTask(
                    task_id=str(uuid.uuid4()),
                    target_chapter=item.get("chapter", ""),
                    task_type=item.get("type", "paragraph"),
                    description=item.get("description", ""),
                    location_hint=item.get("location_hint", {}),
                    word_limit=item.get("word_limit", 300),
                )
            )
        return tasks

    def _build_structure_text(self, doc) -> str:
        lines = []
        for sec in doc.sections:
            prefix = "  " * max(sec.level - 1, 0)
            lines.append(f"{prefix}[Heading{sec.level}] {sec.title}")
            if sec.content:
                preview = sec.content[:200].replace("\n", " ")
                lines.append(f"{prefix}  内容预览: {preview}")
            for t_idx, table in enumerate(sec.tables):
                lines.append(f"{prefix}  [表格{t_idx}] {len(table)}行x{len(table[0]) if table else 0}列")
                if table:
                    for row in table[:3]:
                        lines.append(f"{prefix}    {' | '.join(row)}")
                    if len(table) > 3:
                        lines.append(f"{prefix}    ... (共{len(table)}行)")
        return "\n".join(lines)
