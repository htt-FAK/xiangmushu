"""V 榜：项目原生视觉任务（硬判定为主）。"""
from __future__ import annotations

import json
import os
import re
from glob import glob
from typing import Any, Dict, List, Optional

from core.leaderboard.harness import (
    CallMetrics,
    chat_completion_text,
    client_for_channel,
    probe_vision,
    vision_data_url,
)
from core.leaderboard.models_registry import ModelEntry


def _score_json_keys(raw: str, required: List[str]) -> float:
    s = raw.strip()
    if s.startswith("```"):
        parts = s.split("```")
        if len(parts) >= 2:
            s = parts[1]
            if s.lstrip().startswith("json"):
                s = s.lstrip()[4:].lstrip()
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    hit = sum(1 for k in required if k in data and data[k])
    return hit / max(1, len(required))


def _template_docx_path() -> Optional[str]:
    root = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "templates")
    root = os.path.abspath(root)
    for pat in ("*.docx",):
        files = glob(os.path.join(root, pat))
        if files:
            return files[0]
    return None


def run_vision_suite(
    entry: ModelEntry,
    channel: str,
    *,
    dry_run: bool = False,
) -> Dict[str, float]:
    """返回子项得分 0~1。"""
    if dry_run:
        return {k: 0.5 for k in (
            "doc_ocr_table", "chart_data", "vqa", "spatial_reasoning",
            "gui_screenshot", "multi_image_video", "multimodal_math_science",
            "safety_anti_hallucination",
        )}

    client = client_for_channel(channel)
    if client is None:
        return {}

    mid = entry.resolve_id(channel)
    scores: Dict[str, float] = {}

    # vqa + safety：探针图
    vm = probe_vision(client, mid)
    scores["vqa"] = 1.0 if vm.ok else 0.0
    if vm.ok:
        low = vm.text.lower()
        blank_kw = ("空白", "无内容", "没有", "纯", "单色")
        scores["safety_anti_hallucination"] = (
            1.0 if any(k in low for k in blank_kw) else 0.3
        )
    else:
        scores["safety_anti_hallucination"] = 0.0

    tpl = _template_docx_path()
    doc_prompt = (
        "你是模板分析专家。根据用户提供的说明，输出仅一个 JSON 对象，键必须包含："
        "layout_notes, chapter_hints, table_page_hints。"
        "chapter_hints 为数组；table_page_hints 为数组且每项含 table_ordinal。"
    )
    if tpl:
        try:
            from core.template_vision import ensure_template_page_pngs, load_table_cell_vision_pngs
            from core.template_vision import build_table_cell_user_content

            ensure_template_page_pngs(tpl)
            pngs = load_table_cell_vision_pngs(tpl, 0) or []
            user_text = f"模板文件：{os.path.basename(tpl)}。请输出 layout/chapter/table_page_hints JSON。"
            if pngs:
                content = build_table_cell_user_content(user_text, pngs[:4])
            else:
                content = user_text
            ok, raw, _ = chat_completion_text(
                client, mid,
                [{"role": "system", "content": doc_prompt}, {"role": "user", "content": content}],
                max_tokens=800,
            )
            if ok:
                scores["doc_ocr_table"] = _score_json_keys(
                    raw, ["layout_notes", "chapter_hints", "table_page_hints"]
                )
                try:
                    data = json.loads(re.sub(r"^```json|```$", "", raw.strip(), flags=re.M))
                    hints = data.get("table_page_hints") or []
                    valid_ord = all(
                        isinstance(h, dict) and isinstance(h.get("table_ordinal"), int)
                        for h in hints
                    ) if hints else True
                    scores["multi_image_video"] = 1.0 if valid_ord else 0.5
                except Exception:
                    scores["multi_image_video"] = 0.3
                low = raw.lower()
                scores["gui_screenshot"] = (
                    1.0 if any(k in low for k in ("待填", "空白", "下划线", "填空")) else 0.4
                )
            else:
                scores["doc_ocr_table"] = 0.0
                scores["multi_image_video"] = 0.0
                scores["gui_screenshot"] = 0.0
        except Exception:
            scores["doc_ocr_table"] = 0.0
            scores["multi_image_video"] = 0.0
            scores["gui_screenshot"] = 0.0
    else:
        scores["doc_ocr_table"] = 0.0
        scores["multi_image_video"] = 0.0
        scores["gui_screenshot"] = 0.0

    # chart_data / spatial：表格上下文硬题
    try:
        from core.table_context import build_table_cell_context

        if tpl:
            ctx = build_table_cell_context(tpl, 0, 1, 1)
            ok, raw, _ = chat_completion_text(
                client, mid,
                [
                    {"role": "system", "content": "根据表格上下文简短回答，只输出一个词。"},
                    {"role": "user", "content": ctx + "\n问：表头通常在第几行？只答「第一行」或「其他」。"},
                ],
                max_tokens=32,
            )
            scores["spatial_reasoning"] = 1.0 if ok and "一" in raw else (0.5 if ok else 0.0)
            scores["chart_data"] = scores.get("spatial_reasoning", 0.0)
        else:
            scores["spatial_reasoning"] = 0.0
            scores["chart_data"] = 0.0
    except Exception:
        scores["spatial_reasoning"] = 0.0
        scores["chart_data"] = 0.0

    scores["multimodal_math_science"] = scores.get("doc_ocr_table", 0.0) * 0.8
    return scores
