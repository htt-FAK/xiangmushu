"""申报模板待填槽位识别（段落/表格），供 slot_scanner 与 WordFiller 共用。"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

# 与 WordFiller 历史行为对齐的占位模式
PLACEHOLDER_PATTERNS: List[re.Pattern] = [
    re.compile(r"请在此填写"),
    re.compile(r"在此填写"),
    re.compile(r"请在此"),
    re.compile(r"填写.{0,8}正文"),
    re.compile(r"（\s*请[^）]{0,16}填写[^）]*）"),
    re.compile(r"请填写"),
    re.compile(r"（\s*）"),
    re.compile(r"\(\s*\)"),
    re.compile(r"_{3,}"),
    re.compile(r"待填写"),
    re.compile(r"待补充"),
    re.compile(r"此处填写"),
    re.compile(r"在以下填写"),
    re.compile(r"以下填写"),
    re.compile(r"以下空白"),
    re.compile(r"[X×]{4,}"),
    re.compile(r"请.{0,12}填写"),
]

BRACKET_FILL_RE = re.compile(r"^【\s*请在此填写[^】]{0,60}】\s*$")
SUBSECTION_HEADING_RE = re.compile(
    r"^\d+(?:\.\d+)*\s+.{1,80}$"
)

PURE_HINT_MAX_LEN = 40
FILL_INSTRUCTION_MAX_LEN = 120


def normalize_visible_text(s: str) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", "", s.strip())


def text_has_placeholder(text: str) -> bool:
    if not text:
        return False
    return any(p.search(text) for p in PLACEHOLDER_PATTERNS)


def is_bracket_fill_slot(text: str) -> bool:
    return bool(BRACKET_FILL_RE.match((text or "").strip()))


def is_subsection_heading(text: str) -> bool:
    """小节编号标题（无占位），不应作为正文写入槽。"""
    t = (text or "").strip()
    if not t or len(t) > 90:
        return False
    if text_has_placeholder(t):
        return False
    if not SUBSECTION_HEADING_RE.match(t):
        return False
    # 排除「第N章」级
    if re.match(r"^第\s*\d+\s*章", t):
        return False
    return True


def first_placeholder_span(text: str) -> Optional[Tuple[int, int]]:
    if not text:
        return None
    best: Optional[Tuple[int, int]] = None
    for pat in PLACEHOLDER_PATTERNS:
        m = pat.search(text)
        if m:
            span = (m.start(), m.end())
            if best is None or span[0] < best[0]:
                best = span
    return best


def is_pure_hint_line(text: str) -> bool:
    t = (text or "").strip()
    if is_bracket_fill_slot(t):
        return True
    if not t or len(t) > PURE_HINT_MAX_LEN:
        return False
    if not text_has_placeholder(t):
        return False
    span = first_placeholder_span(t)
    if not span:
        return False
    start, end = span
    remainder = (t[:start] + t[end:]).strip()
    remainder_clean = re.sub(
        r"[（）()\s_。，,、：:【】《》\[\]「」]", "", remainder
    )
    remainder_clean = re.sub(r"(摘要|正文|此处|的)+", "", remainder_clean)
    return len(remainder_clean) <= 2


def looks_like_fill_instruction_line(text: str) -> bool:
    if is_pure_hint_line(text):
        return True
    t = (text or "").strip()
    if not t or len(t) > FILL_INSTRUCTION_MAX_LEN:
        return False
    if len(t) > 80 and re.search(r"(本项目|本系统|系统旨在|系统实现了)", t):
        return False
    if re.search(r"在以下填写|以下填写|以下空白", t):
        return True
    if re.search(r"[X×]{4,}", t):
        return True
    if re.match(r"^摘\s*要\s*[:：]", t) and re.search(r"填写|以下|空白|正文", t):
        return True
    if text_has_placeholder(t):
        span = first_placeholder_span(t)
        if span:
            start, end = span
            prefix = (t[:start] or "").strip()
            suffix = (t[end:] or "").strip()
            if len(prefix) >= 4 or len(suffix) >= 2:
                return False
        if len(t) <= 90:
            return True
    return False


def classify_paragraph_slot(text: str) -> str:
    """bracket_fill | pure_hint | fill_instruction | rubric | subsection_heading | empty | other"""
    t = (text or "").strip()
    if not t:
        return "empty"
    if is_bracket_fill_slot(t):
        return "bracket_fill"
    if is_subsection_heading(t):
        return "subsection_heading"
    if looks_like_fill_instruction_line(t) or is_pure_hint_line(t):
        return "fill_instruction" if looks_like_fill_instruction_line(t) else "pure_hint"
    if text_has_placeholder(t):
        return "pure_hint"
    return "other"


def paragraph_slot_score(
    text: str,
    para_text_hint: str = "",
    *,
    writing_rubric_fn=None,
    template_guidance_fn=None,
) -> int:
    """分数越高越适合写入正文。subsection_heading 为 0。"""
    t = (text or "").strip()
    hint = (para_text_hint or "").strip()
    if hint and normalize_visible_text(hint) == normalize_visible_text(t):
        return 40
    if hint and hint in (text or ""):
        if is_bracket_fill_slot(t):
            return 50
        return 35
    kind = classify_paragraph_slot(t)
    if kind == "bracket_fill":
        return 50
    if kind == "subsection_heading":
        return 0
    if kind in ("fill_instruction", "pure_hint"):
        return 30
    if writing_rubric_fn and writing_rubric_fn(t):
        return 28
    if template_guidance_fn and template_guidance_fn(t):
        return 22
    if text_has_placeholder(t):
        return 20
    if not t:
        return 10
    return 0


def cell_needs_fill(raw: str) -> bool:
    from core.slot_scanner import is_semantic_empty_text

    if is_semantic_empty_text(raw):
        return True
    t = (raw or "").strip()
    if text_has_placeholder(t):
        return True
    if is_bracket_fill_slot(t):
        return True
    if re.search(r"[_]{4,}", t) and len(t) < 120:
        return True
    if re.search(r"[:：]\s*[_]{3,}", t):
        return True
    return False


def default_word_limit_for_paragraph(chapter: str, slot_text: str) -> int:
    c = normalize_visible_text(chapter).lower()
    if "摘要" in c or c == "abstract":
        return int(getattr(__import__("config"), "ABSTRACT_WORD_LIMIT", 650))
    if is_bracket_fill_slot(slot_text):
        if any(k in chapter for k in ("总结", "反思", "展望", "收获", "挑战")):
            return 500
        return 400
    return 300
