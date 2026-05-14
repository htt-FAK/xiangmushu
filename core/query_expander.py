"""轻量级查询扩展：不调用 LLM，基于规则与关键词映射扩充检索 query。

目标：提升向量检索命中率，无额外 API 开销。
"""
from __future__ import annotations

import re
from typing import Optional

_SYNONYM_MAP: dict[str, list[str]] = {
    "项目": ["工程", "方案", "计划", "研究"],
    "技术": ["技术路线", "技术方案", "研发"],
    "资金": ["经费", "投入", "预算", "资助"],
    "目标": ["目的", "预期成果", "成效"],
    "风险": ["挑战", "不确定性", "隐患"],
    "团队": ["人员", "成员", "人才", "骨干"],
    "进度": ["计划安排", "时间节点", "里程碑"],
    "产出": ["成果", "交付物", "产品"],
    "政策": ["规定", "法规", "标准", "依据"],
    "合规": ["合法", "监管", "审批", "许可"],
    "费率": ["收费", "费用", "定价", "价格"],
    "评级": ["评估", "等级", "信用"],
    "背景": ["现状", "环境", "基础", "形势"],
    "意义": ["重要性", "价值", "必要性"],
    "应用": ["场景", "落地", "实施", "推广"],
}

_STOP_WORDS = {
    "的", "了", "在", "是", "和", "与", "对", "为", "以",
    "等", "可以", "需要", "进行", "开展", "实现", "通过",
    "请", "填写", "简述", "描述", "说明", "介绍",
}


def _extract_keywords(text: str, max_kw: int = 6) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,6}", text)
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in _STOP_WORDS and t not in seen:
            seen.add(t)
            out.append(t)
            if len(out) >= max_kw:
                break
    return out


def expand_query(
    chapter: str,
    description: str,
    task_type: Optional[str] = None,
    max_extra: int = 5,
) -> str:
    """
    返回扩展后的检索 query 字符串（原始内容 + 同义词补充）。

    保证不超过 256 个字符，避免向量化截断。
    """
    base = f"{chapter} {description}".strip()
    kws = _extract_keywords(base)

    extras: list[str] = []
    for kw in kws:
        for key, synonyms in _SYNONYM_MAP.items():
            if key in kw:
                extras.extend(s for s in synonyms if s not in base and s not in extras)
                break
        if len(extras) >= max_extra:
            break

    if task_type == "table_cell":
        extras = [e for e in extras if len(e) <= 4][:3]

    expanded = base
    if extras:
        expanded = base + " " + " ".join(extras)

    return expanded[:256]
