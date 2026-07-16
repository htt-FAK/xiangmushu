"""真实 LLM 端到端生成验收。

用真实的 DashScope LLM 调用走完整管线：
    template_analyzer → vector_store → ContentGenerator → WordFiller (smart_style on)

运行：
    python scripts/real_llm_generation.py

前置要求：
    .env 中有 DASHSCOPE_API_KEY 和 CHROMA DB
    （若无 KB 数据会用 FULL_RECALL_MODE 空跑 + Firecrawl 联网补料）
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv()

import config
from core.chunker import Chunk
from core.fill_task import FillTask
from core.filler import WordFiller
from core.generator import ContentGenerator
from core.table_semantic_analyzer import analyze_table
from core.template_analyzer import TemplateAnalyzer
from core.template_style_extractor import get_or_extract_style_profile
from core.smart_style import merge_style
from core.vector_store import VectorStore


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOG = logging.getLogger("real_llm_generation")


TEMPLATE_CHOICES = {
    "agent":  Path(__file__).parents[1] / "data/templates/智能体应用开发实践.docx",
    "innov":  Path(__file__).parents[1] / "docs/2.1.2024级广东理工学院创新计划书参考模板（通用）.docx",
    "anchor": Path(__file__).parents[1] / "data/templates/ai_eval_anchor_template.docx",
}


def load_or_init_vector_store(kb_slug: str = "kb1") -> VectorStore:
    """加载或创建 VectorStore (与 server.py 一致的方式)。"""
    LOG.info("VectorStore(slug=%s)", kb_slug)
    vs = VectorStore(kb_slug=kb_slug)
    LOG.info("KB count: %d chunks", vs.get_collection_count())
    return vs


def run_generation(template_key: str, chapters: list[str], dry_run: bool = False, kb_slug: str = "kb1") -> str:
    template_path = TEMPLATE_CHOICES[template_key]
    if not template_path.exists():
        raise FileNotFoundError(f"模板不存在: {template_path}")
    LOG.info("=== 真实 LLM E2E 生成 ===")
    LOG.info("  模板: %s", template_path.name)
    LOG.info("  章节: %s", chapters or "全部")

    # ── 1) 模板解析 ────────────────────────────────────────────────────────
    LOG.info("[1/6] 解析模板 → FillTask 列表")
    analyzer = TemplateAnalyzer()
    tasks: list[FillTask] = analyzer.analyze(str(template_path))
    if not tasks:
        raise RuntimeError("模板解析返回 0 个 FillTask")
    LOG.info("  共 %d 个 FillTask", len(tasks))

    # 按章节筛选
    if chapters:
        chapter_set = set(chapters)
        tasks = [t for t in tasks if t.target_chapter in chapter_set]
        LOG.info("  章节筛选后: %d 个任务", len(tasks))
    else:
        # 只取前 6 个任务做 demo，避免跑太久
        tasks = tasks[:6]
        LOG.info("  取前 %d 个任务做 demo", len(tasks))

    # ── 2) 表格语义分析 (注入 location_hint) ────────────────────────────────
    LOG.info("[2/6] 表格语义分析")
    from docx import Document as DocxDocument
    doc_for_analysis = DocxDocument(str(template_path))
    analyses = [
        analyze_table(t, i, tasks[0].target_chapter if tasks else "demo")
        for i, t in enumerate(doc_for_analysis.tables)
    ]
    # 把 fill_intent 注入到对应 table_cell 任务的 location_hint
    intent_cache = {a.table_index: a.fill_intents for a in analyses}
    skipped = 0
    remaining: list[FillTask] = []
    for t in tasks:
        if t.task_type == "table_cell":
            ti = t.location_hint.get("table_index")
            r = t.location_hint.get("row")
            c = t.location_hint.get("col")
            intents = intent_cache.get(ti, {})
            intent = intents.get((r, c))
            if intent:
                t.location_hint["fill_intent"] = intent.value
                t.location_hint["table_type"] = analyses[ti].table_type.value
                if intent.value != "fill":
                    LOG.info("    skip table_cell @ [%d]%d,%d intent=%s",
                             ti, r, c, intent.value)
                    skipped += 1
                    continue
        remaining.append(t)
    LOG.info("  表格过滤后: %d 个任务 (跳过 %d 个 LABEL/READ_ONLY)",
             len(remaining), skipped)
    tasks = remaining

    # ── 3) VectorStore + Generator ──────────────────────────────────────────
    LOG.info("[3/6] 初始化 VectorStore + ContentGenerator")
    vs = load_or_init_vector_store(kb_slug=kb_slug)
    gen = ContentGenerator(vs, api_key=None, user_id=None)

    # ── 4) 调用 LLM 生成各章节 ──────────────────────────────────────────
    LOG.info("[4/6] 调用 %s 生成 %d 段内容",
             config.LARGE_LLM_MODEL, len(tasks))
    results: list[str] = []
    for i, task in enumerate(tasks):
        LOG.info("  [%d/%d] 章节 '%s' 类型=%s wc=%d",
                 i + 1, len(tasks), task.target_chapter, task.task_type,
                 task.word_limit)
        if dry_run:
            results.append(f"[dry-run] {task.target_chapter} 章节正文 (字数≈{task.word_limit})")
            continue
        t0 = time.time()
        text = gen.generate(
            task, top_k=3, enable_web=True,
            retrieval_max_distance=1.5,
        )
        elapsed = time.time() - t0
        LOG.info("    → %d 字, %.1fs, model=%s",
                 len(text), elapsed, gen.last_model)
        results.append(text)
    LOG.info("  生成完成")

    # ── 5) 样式档案 + 合并 ────────────────────────────────────────────────
    LOG.info("[5/6] 提取模板样式 + merge (user 黑体 14pt demo)")
    profile = get_or_extract_style_profile(str(template_path))
    merged = merge_style(profile, {
        "body_font_east_asia": "黑体",
        "body_size_pt": 14.0,
    })
    LOG.info("  merged.body: %s %spt bold=%s",
             merged.body_style.font_east_asia,
             merged.body_style.size_pt,
             merged.body_style.bold)

    # ── 6) 回填 + 输出 ─────────────────────────────────────────────────────
    LOG.info("[6/6] WordFiller 回填 (smart_style=True)")
    out_dir = Path(__file__).parent.parent / "data" / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"real_llm_{template_path.stem}_{ts}.docx"
    WordFiller().fill_template(
        str(template_path),
        tasks=tasks,
        contents=results,
        output_path=str(out_path),
        merged_profile=merged,
    )
    kb = out_path.stat().st_size / 1024
    LOG.info("=" * 60)
    LOG.info("  输出: %s (%.1f KB)", out_path, kb)
    LOG.info("  任务数: %d", len(tasks))
    LOG.info("  总字数: %d", sum(len(r) for r in results))
    LOG.info("=" * 60)
    return str(out_path)


def main() -> int:
    ap = argparse.ArgumentParser(description="真实 LLM 端到端生成")
    ap.add_argument("--template", choices=list(TEMPLATE_CHOICES.keys()),
                    default="innov",
                    help="模板代号: agent / innov / anchor")
    ap.add_argument("--chapters", nargs="+", help="指定章节列表 (不传则取前 6 个)")
    ap.add_argument("--kb-slug", default="kb1",
                    help="知识库 slug (默认 kb1, 与 server 一致)")
    ap.add_argument("--dry-run", action="store_true",
                    help="不实际调用 LLM，只走完整管线 (验证不依赖网络的流程)")
    args = ap.parse_args()

    if not config.chat_llm_configured() and not args.dry_run:
        LOG.error("DASHSCOPE_API_KEY 未配置, 请传 --dry-run 或配置 Key")
        return 2

    try:
        run_generation(
            args.template,
            args.chapters or [],
            dry_run=args.dry_run,
            kb_slug=args.kb_slug,
        )
        return 0
    except Exception as e:
        LOG.exception("生成失败: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
