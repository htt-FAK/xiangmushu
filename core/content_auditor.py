"""生成后审核：对照检索片段与表格上下文，不启用联网。"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import OpenAI

import config
from core.dashscope_chat import chat_completions_create
from core.fill_task import FillTask

_LOG = logging.getLogger(__name__)


@dataclass
class AuditResult:
    verdict: str  # pass | minor_fix | major_issue
    issues: List[str] = field(default_factory=list)
    revised_content: str = ""
    one_line_summary: str = ""
    parse_ok: bool = True


AUDIT_SYSTEM = """你是申报类文档质检员。根据「撰写任务」「参考资料」「模型草稿」判断是否可用。
规则：
1. 具体事实、数字、专有名称须与参考资料一致；参考资料没有的不得编造。
2. 表格格应是简短答案，不得长段分析、不得答非所问。
3. 若草稿含 Markdown 符号或明显跑题，判为需修正。
只输出一个 JSON 对象，键为：
- verdict: 字符串，必须是 pass、minor_fix、major_issue 之一
- issues: 字符串数组，简短列出问题（中文）
- revised_content: 字符串；仅当 verdict 为 minor_fix 且能局部替换时给出修订后的完整可替换正文，否则为空字符串
- one_line_summary: 字符串，一句话说明本格/本段应表达什么（人话）
不要输出 JSON 以外的任何文字。"""


def _strip_json_fence(raw: str) -> str:
    s = (raw or "").strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            if s.lstrip().startswith("json"):
                s = s.lstrip()[4:].lstrip()
    return s.strip()


class ContentAuditor:
    def __init__(self) -> None:
        self._client = OpenAI(
            api_key=config.OPENAI_COMPAT_API_KEY or "sk-placeholder",
            base_url=config.OPENAI_BASE_URL,
            timeout=config.OPENAI_TIMEOUT,
            max_retries=config.OPENAI_MAX_RETRIES,
        )

    def audit(
        self,
        task: FillTask,
        draft_text: str,
        retrieved_texts: str,
        table_context: Optional[str],
        route_meta: Dict[str, Any],
    ) -> AuditResult:
        meta_brief = {
            "native_web_search": route_meta.get("native_web_search"),
            "kb_hits": route_meta.get("kb_hits"),
            "task_type": task.task_type,
        }
        user_parts = [
            f"【撰写任务】章节={task.target_chapter}\n类型={task.task_type}\n要求={task.description}\n字数上限约={task.word_limit}",
            f"【路由摘要】{json.dumps(meta_brief, ensure_ascii=False)}",
            "【参考资料】\n" + retrieved_texts,
        ]
        if table_context and table_context.strip():
            user_parts.append("【表格上下文】\n" + table_context.strip())
        user_parts.append("【模型草稿】\n" + (draft_text or "").strip())
        user_msg = "\n\n".join(user_parts)

        try:
            resp = chat_completions_create(
                self._client,
                model=config.AUDIT_LLM_MODEL,
                messages=[
                    {"role": "system", "content": AUDIT_SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                temperature=config.TEMP_AUDIT,
                stream=False,
            )
            ch0 = resp.choices[0] if resp.choices else None
            raw = (ch0.message.content if ch0 and ch0.message else "") or ""
        except Exception as e:
            _LOG.warning("content_audit_api_error %s", e)
            return AuditResult(
                verdict="pass",
                issues=[f"审核接口异常，已跳过：{e}"],
                parse_ok=False,
            )

        try:
            data = json.loads(_strip_json_fence(raw))
        except json.JSONDecodeError:
            _LOG.warning("content_audit_json_parse_fail raw_prefix=%r", raw[:200])
            return AuditResult(
                verdict="pass",
                issues=["审核 JSON 解析失败，已跳过"],
                parse_ok=False,
            )

        verdict = str(data.get("verdict", "pass")).strip().lower()
        if verdict not in ("pass", "minor_fix", "major_issue"):
            verdict = "pass"
        issues = data.get("issues") or []
        if not isinstance(issues, list):
            issues = [str(issues)]
        issues = [str(x) for x in issues if str(x).strip()]
        revised = str(data.get("revised_content", "") or "").strip()
        summary = str(data.get("one_line_summary", "") or "").strip()

        out = AuditResult(
            verdict=verdict,
            issues=issues,
            revised_content=revised,
            one_line_summary=summary,
            parse_ok=True,
        )
        _LOG.info(
            "content_gen_audit task_id=%s verdict=%s issues_n=%s",
            task.task_id,
            verdict,
            len(issues),
        )
        return out


_FORBIDDEN_PREFIXES = [
    "以下是", "如下所示", "根据资料可知", "根据以上资料",
    "作为AI", "作为人工智能", "我是AI",
    "暂无相关信息", "未提供", "无法确定",
    "填写内容：", "答案：", "该单元格应填写：",
    "综上所述，",
]

_HIGH_RISK_KEYWORDS = [
    "政策", "金额", "绩效指标", "风险", "合规",
    "ISIN", "费率", "评级", "比例", "利率", "监管",
]


def rule_audit(task: FillTask, answer: str) -> list[str]:
    """免费的规则审核，返回 issue 列表（空列表表示通过）。"""
    issues: list[str] = []
    text = (answer or "").strip()

    if not text:
        issues.append("内容为空")
        return issues

    cap = effective_word_cap(task)
    if len(text) > int(cap * 1.8):
        issues.append(f"内容过长（{len(text)} 字，上限约 {int(cap * 1.8)} 字）")

    for prefix in _FORBIDDEN_PREFIXES:
        if text.startswith(prefix) or prefix in text[:40]:
            issues.append(f"含禁用前缀或模型说明性语句：「{prefix}」")
            break

    if re.search(r"^#{1,6}\s", text, re.MULTILINE):
        issues.append("含 Markdown 标题符号 #")

    if task.task_type == "table_cell" and "\n" in text:
        issues.append("表格单元格含换行（可能导致 Word 格式错乱）")

    return issues


def need_model_audit(
    task: FillTask,
    route_meta: dict,
    rule_issues: list[str],
) -> bool:
    """判断是否需要调模型审核（规则审核有问题时一定需要）。"""
    if rule_issues:
        return True
    if route_meta.get("native_web_search"):
        return True
    if route_meta.get("generation_tier") == "large" and (
        route_meta.get("best_similarity_est") or 1.0
    ) < 0.5:
        return True
    if (task.word_limit or 0) >= 500:
        return True
    desc = (task.description or "") + (task.target_chapter or "")
    if any(kw in desc for kw in _HIGH_RISK_KEYWORDS):
        return True
    return False


def effective_word_cap(task: FillTask) -> int:
    wl = int(task.word_limit or 300)
    if task.task_type == "table_cell":
        return min(max(wl, 1), 120)
    return max(wl, 1)


def should_apply_revision(task: FillTask, ar: AuditResult) -> bool:
    if ar.verdict != "minor_fix" or not ar.revised_content:
        return False
    cap = effective_word_cap(task)
    if len(ar.revised_content) > int(cap * 1.15) + 20:
        return False
    if re.search(r"^#{1,6}\s", ar.revised_content, re.MULTILINE):
        return False
    return True
