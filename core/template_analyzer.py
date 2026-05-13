from typing import List
from openai import OpenAI

from core.dashscope_chat import chat_completions_create
from core.parser import DocumentParser
from core.fill_task import FillTask
from core.slot_scanner import scan_anchor_tasks, build_decorative_hints_for_llm
import config
import json
import uuid


class TemplateAnalyzer:
    """分析模板：优先锚点 {{NAME}} 扫描；否则 LLM + 装饰性空位提示。"""

    def __init__(self):
        self._client = OpenAI(
            api_key=config.OPENAI_COMPAT_API_KEY or "sk-placeholder",
            base_url=config.OPENAI_BASE_URL,
            timeout=config.OPENAI_TIMEOUT,
            max_retries=config.OPENAI_MAX_RETRIES,
        )
        self._parser = DocumentParser()

    def analyze(self, template_path: str) -> List[FillTask]:
        anchor_tasks = scan_anchor_tasks(template_path)
        if anchor_tasks:
            return anchor_tasks

        doc = self._parser.parse(template_path)
        structure_text = self._build_structure_text(doc)
        deco = build_decorative_hints_for_llm(template_path)
        if deco.strip():
            structure_text += (
                "\n\n【程序化检测】以下位置为装饰性空白（仅空格/下划线等），"
                "必须输出为待填写，并给出正确的 table_index/row/col 或段落关键词：\n"
                + deco
            )

        prompt = f"""你是一个文档分析助手。以下是项目计划书模板的结构：

{structure_text}

请找出所有需要填写内容的空位（如空白段落、包含"请填写"/"（ ）"/"____"等占位符的段落或表格单元格）。
对每个空位输出 JSON 数组，每个元素包含：
- chapter: 所属章节标题
- type: "paragraph" 或 "table_cell"
- description: 应该填写什么内容（根据上下文推断）
- location_hint: 定位信息（段落用 {{"paragraph_text": "上下文关键词"}}，表格用 {{"table_index": 数字, "row": 行号, "col": 列号}}）
- word_limit: 建议字数

重要（表格）：
- location_hint.table_index **必须**等于上文中「doc.tables索引=」后面的整数，与整篇文档中表格的全局顺序一致，**绝不是**每个章节内从 0 重新编号。
- row、col 均为 **0 起算**。多列表格中，**左侧列多为标题/说明**，待填的简短答案、勾选说明通常在 **第 1 列或最右列**；不要把长段正文写进明显仅为标题的窄列。
- table_cell 类任务的 word_limit 建议不超过 120。

只输出 JSON 数组，不要其他内容。"""

        response = chat_completions_create(
            self._client,
            model=config.SMALL_LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "你是文档分析助手，只输出 JSON，不要任何解释。",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=config.TEMP_SMALL_LLM,
        )

        content = (response.choices[0].message.content or "").strip()
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
            ttype = item.get("type", "paragraph")
            try:
                wl = int(item.get("word_limit", 300) or 300)
            except (TypeError, ValueError):
                wl = 300
            if ttype == "table_cell":
                wl = min(max(wl, 1), 120)
            tasks.append(
                FillTask(
                    task_id=str(uuid.uuid4()),
                    target_chapter=item.get("chapter", ""),
                    task_type=ttype,
                    description=item.get("description", ""),
                    location_hint=item.get("location_hint", {}),
                    word_limit=wl,
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
                doc_ti = (
                    sec.table_doc_indices[t_idx]
                    if t_idx < len(sec.table_doc_indices)
                    else t_idx
                )
                lines.append(
                    f"{prefix}  [表格 doc.tables索引={doc_ti}] {len(table)}行x"
                    f"{len(table[0]) if table else 0}列"
                )
                if table:
                    for row in table[:5]:
                        lines.append(f"{prefix}    {' | '.join(row)}")
                    if len(table) > 5:
                        lines.append(f"{prefix}    ... (共{len(table)}行)")
        return "\n".join(lines)
