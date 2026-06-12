"""Post-generation content audit without web access."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import config
from core.dashscope_chat import chat_completions_create
from core.fill_task import FillTask
from core.model_router import AUDIT_TEXT, resolve_model_profile

_LOG = logging.getLogger(__name__)


@dataclass
class AuditResult:
    verdict: str  # pass | minor_fix | major_issue
    issues: List[str] = field(default_factory=list)
    revised_content: str = ""
    one_line_summary: str = ""
    parse_ok: bool = True


AUDIT_SYSTEM = """你是申报类文档质检员。根据“撰写任务”“参考资料”“模型草稿”判断是否可用。
规则：
1. 具体事实、数字、专有名词必须与参考资料一致；资料没有的不得编造。
2. 表格格内容应为简短答案，不得长段分析，不得答非所问。
3. 若草稿含 Markdown 符号或明显跑题，判为需要修正。
只输出一个 JSON 对象，键为：
- verdict: pass / minor_fix / major_issue
- issues: 字符串数组，列出问题
- revised_content: 仅当 verdict=minor_fix 且可直接替换时给出完整修订稿
- one_line_summary: 一句话说明本段/本格应该表达什么
不要输出 JSON 以外的内容。"""


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
        self._client = config.openai_client_for_chat()

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
            "web_creative_prompt": route_meta.get("web_creative_prompt"),
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

        raw = ""
        last_error: Optional[Exception] = None
        audit_profile = resolve_model_profile(
            AUDIT_TEXT,
            routing_reason="content audit",
        )
        model_chain = audit_profile.model_chain
        seen_models = set()
        for model in model_chain:
            model = (model or "").strip()
            if not model or model in seen_models:
                continue
            seen_models.add(model)
            try:
                resp = chat_completions_create(
                    self._client,
                    model=model,
                    messages=[
                        {"role": "system", "content": AUDIT_SYSTEM},
                        {"role": "user", "content": user_msg},
                    ],
                    temperature=audit_profile.temperature if audit_profile.temperature is not None else config.TEMP_AUDIT,
                    stream=False,
                )
                ch0 = resp.choices[0] if resp.choices else None
                raw = (ch0.message.content if ch0 and ch0.message else "") or ""
                if raw.strip():
                    break
                _LOG.warning("content_audit_empty model=%s, trying next fallback", model)
            except Exception as e:
                last_error = e
                _LOG.warning("content_audit_api_error model=%s err=%s", model, e)

        if not raw.strip():
            issue = "审核接口异常，已跳过"
            if last_error is not None:
                issue += f"：{last_error}"
            return AuditResult(verdict="pass", issues=[issue], parse_ok=False)

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
    "以下是",
    "如下所示",
    "根据资料可知",
    "根据以上资料",
    "作为AI",
    "作为人工智能",
    "我是AI",
    "暂无相关信息",
    "未提供",
    "无法确定",
    "填写内容：",
    "答案：",
    "该单元格应填写：",
    "综上所述，",
]

_HIGH_RISK_KEYWORDS = [
    "政策",
    "金额",
    "绩效指标",
    "风险",
    "合规",
    "ISIN",
    "费率",
    "评级",
    "比例",
    "利率",
    "监管",
]


def check_content_richness(content: str, word_limit: int) -> tuple[bool, str]:
    """Check whether the generated content is rich enough."""
    if not content or not word_limit:
        return True, ""

    actual_words = len(content.replace(" ", "").replace("\n", ""))
    threshold = word_limit * config.CONTENT_RICHNESS_THRESHOLD

    if actual_words < word_limit * 0.5:
        return False, f"内容严重不足：实际约 {actual_words} 字，要求约 {word_limit} 字（低于 50%）"
    if actual_words < threshold:
        return False, f"内容不够充实：实际约 {actual_words} 字，要求约 {word_limit} 字（低于 {int(config.CONTENT_RICHNESS_THRESHOLD * 100)}%）"
    return True, f"内容充实度合格：实际约 {actual_words} 字，要求约 {word_limit} 字"


def rule_audit(
    task: FillTask,
    answer: str,
    route_meta: Optional[Dict[str, Any]] = None,
) -> list[str]:
    """Cheap rule-based audit before model audit."""
    issues: list[str] = []
    text = (answer or "").strip()

    if not text:
        issues.append("内容为空")
        return issues

    cap = effective_word_cap(task)
    if len(text) > int(cap * 1.8):
        issues.append(f"内容过长（{len(text)} 字，上限约 {int(cap * 1.8)} 字）")

    relax_unavailable = bool(route_meta and route_meta.get("web_creative_prompt"))
    prefixes = list(_FORBIDDEN_PREFIXES)
    if relax_unavailable:
        prefixes = [p for p in prefixes if p not in ("暂无相关信息", "未提供", "无法确定")]

    for prefix in prefixes:
        if text.startswith(prefix) or prefix in text[:40]:
            issues.append(f"含禁用前缀或模型说明性语句：{prefix}")
            break

    if re.search(r"^#{1,6}\s", text, re.MULTILINE):
        issues.append("含 Markdown 标题符号 #")

    if task.task_type == "table_cell" and "\n" in text:
        issues.append("表格单元格含换行，可能导致 Word 格式错乱")

    if getattr(config, "CONTENT_RICHNESS_ENABLED", True) and task.word_limit:
        is_rich, richness_msg = check_content_richness(text, task.word_limit)
        if not is_rich:
            actual_chars = len(text.replace(" ", "").replace("\n", ""))
            if actual_chars < task.word_limit * 0.5:
                issues.append(f"[major_issue] {richness_msg}")
            else:
                issues.append(richness_msg)

    return issues


def need_model_audit(
    task: FillTask,
    route_meta: dict,
    rule_issues: list[str],
) -> bool:
    """Decide whether a model audit is necessary."""
    if rule_issues:
        return True
    if route_meta.get("native_web_search"):
        return True
    if route_meta.get("generation_tier") == "large" and (route_meta.get("best_similarity_est") or 1.0) < 0.5:
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
