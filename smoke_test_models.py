"""
冒烟测试：校验百炼/OpenAI 兼容网关下各模型可调、ContentGenerator 路由正确。

用法（在 xiangmushu 目录下）:
  python smoke_test_models.py
  python smoke_test_models.py --offline        # 不调外部 API：配置摘要 + 全链路离线断言（见下）
  python smoke_test_models.py --skip-vision   # 跳过多模态（省配额）
  python smoke_test_models.py --skip-chroma   # 跳过 Chroma+embedding

--offline 覆盖（与 docs/测试与验收.md 矩阵一致）:
  ContentGenerator 路由、审核修订辅助、rule_audit/need_model_audit、
  query_expander、_max_output_tokens、task_grouper、evidence_planner、
  prepare_bundle_from_evidence 与 _build_chat_request 路由对齐、
  WordFiller.clean_table_answer、batch_generator._strip_json_fence。

依赖：已配置 DASHSCOPE_API_KEY 或 OPENAI_API_KEY，且 .env 或环境变量可读。
"""
from __future__ import annotations

import argparse
import base64
import os
import struct
import sys
import tempfile
import traceback
import zlib
from typing import Any, List

# 保证以仓库内模块方式加载
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.chdir(_ROOT)

# 先加载 .env
from dotenv import load_dotenv

load_dotenv(os.path.join(_ROOT, ".env"))

import config  # noqa: E402
from openai import OpenAI  # noqa: E402
from core.dashscope_chat import chat_completions_create  # noqa: E402
from core.fill_task import FillTask  # noqa: E402
from core.generator import ContentGenerator, _max_output_tokens  # noqa: E402
from core.openai_embeddings import TimeoutOpenAIEmbedding  # noqa: E402


def _rgba_png_bytes(width: int, height: int) -> bytes:
    """生成纯色 RGBA PNG（百炼要求宽高均 > 10）。"""

    def _chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\xff\x00\x00\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )


def _mask(s: str, keep: int = 6) -> str:
    s = (s or "").strip()
    if len(s) <= keep:
        return "(空或过短)"
    return s[:keep] + "…" + f"（共{len(s)}字符）"


def _client() -> OpenAI:
    key = (config.OPENAI_COMPAT_API_KEY or "").strip()
    if not key:
        raise SystemExit("未配置 DASHSCOPE_API_KEY 或 OPENAI_API_KEY，退出。")
    return OpenAI(
        api_key=key,
        base_url=config.OPENAI_BASE_URL,
        timeout=config.OPENAI_TIMEOUT,
        max_retries=config.OPENAI_MAX_RETRIES,
    )


def _print_config():
    print("=== 配置摘要 ===")
    print(f"  OPENAI_BASE_URL: {config.OPENAI_BASE_URL}")
    print(f"  DASHSCOPE_API_KEY: {_mask(config.DASHSCOPE_API_KEY)}")
    print(f"  OPENAI_API_KEY:    {_mask(config.OPENAI_API_KEY)}")
    print(f"  实际调用 Key:      {_mask(config.OPENAI_COMPAT_API_KEY)}")
    print(f"  SMALL_LLM_MODEL:   {config.SMALL_LLM_MODEL}  T={config.TEMP_SMALL_LLM}")
    print(f"  LARGE_LLM_MODEL:   {config.LARGE_LLM_MODEL}  T={config.TEMP_LARGE_LLM}")
    print(f"  VISION_WEB_MODEL:  {config.VISION_WEB_MODEL}  T={config.TEMP_VISION}")
    print(f"  EMBEDDING_MODEL:   {config.EMBEDDING_MODEL}")
    print()


def _chat_ping(client: OpenAI, model: str, temperature: float, label: str) -> bool:
    print(f"=== {label} ({model}) ===")
    try:
        r = chat_completions_create(
            client,
            model=model,
            messages=[{"role": "user", "content": "只回复一个字：好"}],
            temperature=temperature,
            max_tokens=16,
        )
        text = (r.choices[0].message.content or "").strip()
        print(f"  回复: {text!r}")
        if not text:
            print("  [FAIL] 空回复")
            return False
        print("  [OK]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        if os.getenv("SMOKE_VERBOSE"):
            traceback.print_exc()
        return False


def _vision_ping(client: OpenAI) -> bool:
    print(f"=== 视觉模型 ({config.VISION_WEB_MODEL}) ===")
    try:
        png = _rgba_png_bytes(16, 16)
        url = "data:image/png;base64," + base64.standard_b64encode(png).decode("ascii")
        r = chat_completions_create(
            client,
            model=config.VISION_WEB_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "请用一句话描述这张图里有什么（若几乎空白则说明）。",
                        },
                        {"type": "image_url", "image_url": {"url": url}},
                    ],
                }
            ],
            temperature=config.TEMP_VISION,
            max_tokens=128,
        )
        text = (r.choices[0].message.content or "").strip()
        print(f"  回复片段: {text[:120]!r}…")
        if not text:
            print("  [FAIL] 空回复")
            return False
        print("  [OK]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        if os.getenv("SMOKE_VERBOSE"):
            traceback.print_exc()
        return False


def _embedding_ping() -> bool:
    print(f"=== Embedding ({config.EMBEDDING_MODEL}) ===")
    try:
        fn = TimeoutOpenAIEmbedding(
            api_key=config.OPENAI_COMPAT_API_KEY or "sk-placeholder",
            base_url=config.OPENAI_BASE_URL or None,
            model_name=config.EMBEDDING_MODEL,
            timeout=config.OPENAI_TIMEOUT,
            max_retries=config.OPENAI_MAX_RETRIES,
        )
        vecs = fn(["测试向量入库用的短句。"])
        if not vecs or len(vecs[0]) < 8:
            print("  [FAIL] 向量维度过短或空")
            return False
        print(f"  向量维度: {len(vecs[0])}")
        print("  [OK]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        if os.getenv("SMOKE_VERBOSE"):
            traceback.print_exc()
        return False


class _MockVS:
    """模拟向量库：控制 weak_kb 与检索命中。"""

    def __init__(self, count: int, results: List[dict[str, Any]]):
        self._count = count
        self._results = results

    def get_collection_count(self) -> int:
        return self._count

    def search(self, *args: Any, **kwargs: Any) -> List[dict[str, Any]]:
        return list(self._results)


def _routing_tests() -> bool:
    print("=== ContentGenerator 路由（无真实检索/联网）===")
    ok = True
    task = FillTask(
        task_id="t1",
        target_chapter="测试章",
        task_type="paragraph",
        description="写一句项目背景",
        location_hint={},
        word_limit=50,
    )

    # 有 KB 命中且相似度足够 -> 默认走小模型省 token（关 USE_SMALL_LLM_FOR_STRONG_RAG 则仍用大模型）
    g1 = ContentGenerator(_MockVS(5, [{"text": "参考资料", "metadata": {"source": "x"}, "distance": 0.3}]))
    _, m1, t1, _, rm1, _ = g1._build_chat_request(task, top_k=3, enable_web=True, retrieval_max_distance=1.0)
    exp1 = (
        config.SMALL_LLM_MODEL
        if config.USE_SMALL_LLM_FOR_STRONG_RAG
        else config.LARGE_LLM_MODEL
    )
    print(f"  有命中+高相似+联网开关(未触发弱库联网): model={m1!r} tier={rm1.get('generation_tier')}")
    if m1 != exp1:
        print(f"  [FAIL] 预期模型 {exp1!r}")
        ok = False
    else:
        print("  [OK] 路由模型符合预期")

    # 空库 + 开联网 -> VISION_WEB_MODEL + extra_body.enable_search（百炼内置联网）
    g2 = ContentGenerator(_MockVS(0, []))
    _, m2, t2, eb2, _, _ = g2._build_chat_request(task, top_k=3, enable_web=True, retrieval_max_distance=1.0)
    print(f"  空库 + 开联网: model={m2!r} temp={t2}")
    if m2 != config.VISION_WEB_MODEL:
        print("  [FAIL] 预期 VISION_WEB_MODEL（弱库联网档）")
        ok = False
    else:
        print("  [OK] 使用 qwen-plus 档")
    if not eb2.get("enable_search"):
        print("  [FAIL] 预期 extra_body.enable_search=True")
        ok = False
    else:
        print("  [OK] enable_search 已开启")

    # 空库 + 不开联网 -> 大模型
    g3 = ContentGenerator(_MockVS(0, []))
    _, m3, t3, eb3, _, _ = g3._build_chat_request(task, top_k=3, enable_web=False, retrieval_max_distance=1.0)
    print(f"  空库 + 关联网: model={m3!r} temp={t3}")
    if m3 != config.LARGE_LLM_MODEL:
        print("  [FAIL] 预期 LARGE_LLM_MODEL")
        ok = False
    else:
        print("  [OK] 使用大模型")
    if eb3.get("enable_search"):
        print("  [FAIL] 关联网不应设置 enable_search")
        ok = False

    # 有命中但 distance 大 -> 估算相似度低 + 开联网 -> 仍走联网档
    g4 = ContentGenerator(
        _MockVS(
            5,
            [{"text": "弱相关片段", "metadata": {"source": "x"}, "distance": 0.86}],
        )
    )
    _, m4, t4, eb4, rm4, _ = g4._build_chat_request(
        task, top_k=3, enable_web=True, retrieval_max_distance=1.0
    )
    print(f"  有命中但低相似 + 开联网: model={m4!r} low_sim={rm4.get('low_similarity')}")
    if m4 != config.VISION_WEB_MODEL:
        print("  [FAIL] 预期 VISION_WEB_MODEL（低相似度联网档）")
        ok = False
    else:
        print("  [OK] 低相似触发联网档")
    if not eb4.get("enable_search"):
        print("  [FAIL] 预期 extra_body.enable_search=True")
        ok = False

    return ok


def _audit_offline_helpers() -> bool:
    """不调 API：审核修订策略与字数上限。"""
    print("=== 审核辅助（offline）===")
    from core.content_auditor import AuditResult, effective_word_cap, should_apply_revision
    from core.fill_task import FillTask

    t_cell = FillTask(
        task_id="a1",
        target_chapter="表",
        task_type="table_cell",
        description="填一格",
        location_hint={"table_index": 0, "row": 1, "col": 1},
        word_limit=300,
    )
    if effective_word_cap(t_cell) != 120:
        print("  [FAIL] table_cell 字数上限应为 120")
        return False
    ar_long = AuditResult(
        verdict="minor_fix",
        issues=[],
        revised_content="x" * 300,
        one_line_summary="",
    )
    if should_apply_revision(t_cell, ar_long):
        print("  [FAIL] 过长修订稿不应采纳")
        return False
    ar_ok = AuditResult(
        verdict="minor_fix",
        issues=[],
        revised_content="符合资料",
        one_line_summary="",
    )
    if not should_apply_revision(t_cell, ar_ok):
        print("  [FAIL] 短修订稿应可采纳")
        return False
    print("  [OK]")
    return True


def _offline_query_expander() -> bool:
    print("=== query_expander（offline）===")
    from core.query_expander import expand_query

    q = expand_query("第一章", "项目实施背景与资金风险分析", "paragraph")
    if len(q) > 256:
        print(f"  [FAIL] 扩展 query 超长 len={len(q)}")
        return False
    if "项目" in q and "工程" not in q and "方案" not in q:
        print(f"  [FAIL] 预期含项目相关扩展词，得 {q!r}")
        return False
    q2 = expand_query("表", "技术路线简述", "table_cell")
    if len(q2) > 256:
        print("  [FAIL] table_cell query 超长")
        return False
    print("  [OK]")
    return True


def _offline_rule_and_need_model_audit() -> bool:
    print("=== rule_audit / need_model_audit（offline）===")
    from core.content_auditor import need_model_audit, rule_audit

    t_para = FillTask(
        task_id="p1",
        target_chapter="章",
        task_type="paragraph",
        description="简述",
        location_hint={},
        word_limit=300,
    )
    if len(rule_audit(t_para, "")) == 0:
        print("  [FAIL] 空答案应产生 rule_issues")
        return False
    issues = rule_audit(t_para, "以下是正文内容很长" + "x" * 10)
    if not any("禁用" in x or "前缀" in x for x in issues):
        print(f"  [FAIL] 禁用前缀未检出 issues={issues}")
        return False

    t_cell = FillTask(
        task_id="c1",
        target_chapter="表",
        task_type="table_cell",
        description="填格",
        location_hint={"table_index": 0, "row": 0, "col": 1},
        word_limit=40,
    )
    ni = rule_audit(t_cell, "第一行\n第二行")
    if not ni or "换行" not in ni[0]:
        print(f"  [FAIL] 表格换行未检出 {ni}")
        return False

    meta_web = {"native_web_search": True, "generation_tier": "large", "best_similarity_est": 0.9}
    if not need_model_audit(t_para, meta_web, []):
        print("  [FAIL] 联网应触发模型审核")
        return False
    meta_safe = {
        "native_web_search": False,
        "generation_tier": "small_rag",
        "best_similarity_est": 0.7,
    }
    if need_model_audit(t_para, meta_safe, []):
        print("  [FAIL] 低风险场景不应强制模型审核")
        return False
    t_policy = FillTask(
        task_id="p2",
        target_chapter="章",
        task_type="paragraph",
        description="政策合规要点",
        location_hint={},
        word_limit=100,
    )
    if not need_model_audit(t_policy, meta_safe, []):
        print("  [FAIL] 描述含高风险词应触发模型审核")
        return False
    print("  [OK]")
    return True


def _offline_max_output_tokens() -> bool:
    print("=== _max_output_tokens（offline）===")
    if _max_output_tokens(999, "table_cell") != 180:
        print("  [FAIL] table_cell 应为 180")
        return False
    v50 = _max_output_tokens(50, "paragraph")
    if not (256 <= v50 <= 1024):
        print(f"  [FAIL] 短段 50 字异常 {v50}")
        return False
    v300 = _max_output_tokens(300, "paragraph")
    if v300 > 1024:
        print(f"  [FAIL] 300 字段 cap 1024 违反 {v300}")
        return False
    v800 = _max_output_tokens(800, "paragraph")
    if v800 > int(config.GEN_MAX_TOKENS_HARD_CAP):
        print(f"  [FAIL] 长段超过硬顶 {v800}")
        return False
    if v800 < 512:
        print(f"  [FAIL] 长段 floor 512 违反 {v800}")
        return False
    print("  [OK]")
    return True


def _offline_task_grouper() -> bool:
    print("=== task_grouper（offline）===")
    from core.task_grouper import group_tasks

    tasks = [
        FillTask(
            task_id="a",
            target_chapter="同一章",
            task_type="table_cell",
            description="格1",
            location_hint={"table_index": 0, "row": 1, "col": 0},
            word_limit=20,
        ),
        FillTask(
            task_id="b",
            target_chapter="同一章",
            task_type="table_cell",
            description="格2",
            location_hint={"table_index": 0, "row": 1, "col": 1},
            word_limit=20,
        ),
        FillTask(
            task_id="c",
            target_chapter="同一章",
            task_type="paragraph",
            description="段1",
            location_hint={},
            word_limit=100,
        ),
    ]
    groups = group_tasks(tasks)
    if len(groups) != 2:
        print(f"  [FAIL] 预期 2 组（同行表+段落）得 {len(groups)}")
        return False
    row_group = next(g for g in groups if g.is_table_group)
    if len(row_group.tasks) != 2:
        print("  [FAIL] 同行应 2 个任务")
        return False
    print("  [OK]")
    return True


def _offline_evidence_planner() -> bool:
    print("=== evidence_planner（offline）===")
    from core.evidence_planner import compress_evidence, format_evidence, retrieve_for_group
    from core.task_grouper import TaskGroup

    grp = TaskGroup(
        group_id="table_0_row_1",
        tasks=[],
        shared_query="项目 风险 应对措施",
        table_index=0,
    )
    t = FillTask(
        task_id="t",
        target_chapter="风险",
        task_type="paragraph",
        description="项目风险与应对措施",
        location_hint={},
        word_limit=80,
    )
    ev = retrieve_for_group(
        _MockVS(
            3,
            [
                {
                    "text": "无关句子。项目风险主要包括技术风险。应对措施已明确。",
                    "distance": 0.25,
                },
                {"text": "另一段。", "distance": 0.4},
            ],
        ),
        grp,
        top_k=3,
        max_distance=1.0,
    )
    if ev.weak_kb or ev.kb_hits < 1:
        print("  [FAIL] 应有 KB 命中")
        return False
    comp = compress_evidence(ev, t, max_chars=200)
    if len(comp) > 200 or "风险" not in comp:
        print(f"  [FAIL] 压缩结果异常 {comp!r}")
        return False
    fmt = format_evidence(ev, max_chars=500)
    if len(fmt) < 5:
        print(f"  [FAIL] format_evidence 异常 {fmt!r}")
        return False
    print("  [OK]")
    return True


def _offline_bundle_evidence_route_parity() -> bool:
    """prepare_bundle_from_evidence 与 _build_chat_request 在相同检索语义下模型/联网档一致。"""
    print("=== prepare_bundle_from_evidence 路由对齐（offline）===")
    from core.evidence_planner import Evidence

    task = FillTask(
        task_id="t1",
        target_chapter="测试章",
        task_type="paragraph",
        description="写一句项目背景",
        location_hint={},
        word_limit=50,
    )

    def _cmp(vs: _MockVS, enable_web: bool, ev: Evidence, label: str) -> bool:
        g = ContentGenerator(vs)
        _, m1, _, eb1, rm1, _ = g._build_chat_request(
            task, top_k=3, enable_web=enable_web, retrieval_max_distance=1.0
        )
        b2 = g.prepare_bundle_from_evidence(task, ev, enable_web=enable_web)
        if m1 != b2.model:
            print(f"  [FAIL] {label} model 不一致 build={m1!r} bundle={b2.model!r}")
            return False
        if bool(eb1.get("enable_search")) != bool(b2.extra_body.get("enable_search")):
            print(f"  [FAIL] {label} enable_search 不一致")
            return False
        if rm1.get("generation_tier") != b2.route_meta.get("generation_tier"):
            print(
                f"  [FAIL] {label} tier 不一致 {rm1.get('generation_tier')} vs {b2.route_meta.get('generation_tier')}"
            )
            return False
        if rm1.get("use_small_llm_for_rag") != b2.route_meta.get("use_small_llm_for_rag"):
            print(f"  [FAIL] {label} use_small 不一致")
            return False
        return True

    hits = [{"text": "参考资料", "metadata": {"source": "x"}, "distance": 0.3}]
    vs1 = _MockVS(5, hits)
    ev1 = Evidence(
        group_id="g1",
        raw_results=list(hits),
        kb_hits=1,
        weak_kb=False,
        best_similarity=0.7,
    )
    if not _cmp(vs1, True, ev1, "强命中"):
        return False

    vs2 = _MockVS(0, [])
    ev2 = Evidence(group_id="g2", raw_results=[], kb_hits=0, weak_kb=True, best_similarity=None)
    if not _cmp(vs2, True, ev2, "弱库"):
        return False

    low_hits = [{"text": "弱相关", "metadata": {"source": "x"}, "distance": 0.86}]
    vs3 = _MockVS(5, low_hits)
    ev3 = Evidence(
        group_id="g3",
        raw_results=list(low_hits),
        kb_hits=1,
        weak_kb=False,
        best_similarity=0.14,
    )
    if not _cmp(vs3, True, ev3, "低相似"):
        return False

    t_cell = FillTask(
        task_id="tc",
        target_chapter="表",
        task_type="table_cell",
        description="填一格",
        location_hint={"table_index": 0, "row": 0, "col": 0},
        word_limit=40,
    )
    g4 = ContentGenerator(_MockVS(5, hits))
    ev4 = Evidence(
        group_id="g4",
        raw_results=list(hits),
        kb_hits=1,
        weak_kb=False,
        best_similarity=0.7,
    )
    b4 = g4.prepare_bundle_from_evidence(t_cell, ev4, enable_web=False, table_context="表头:名称")
    user = b4.messages[1]["content"]
    if "表格填写任务" not in user:
        print("  [FAIL] 表格任务 user 应含表格填写任务")
        return False
    print("  [OK]")
    return True


def _offline_filler_clean_table() -> bool:
    print("=== WordFiller.clean_table_answer（offline）===")
    from core.filler import WordFiller

    raw = "答案：\n\n某值"
    out = WordFiller.clean_table_answer(raw, word_limit=40)
    if out.startswith("答案"):
        print(f"  [FAIL] 前缀未剥离 {out!r}")
        return False
    long_in = "x" * 500
    short = WordFiller.clean_table_answer(long_in, word_limit=20)
    if len(short) > 90:
        print(f"  [FAIL] 超长未截断 len={len(short)}")
        return False
    print("  [OK]")
    return True


def _offline_batch_json_fence() -> bool:
    print("=== batch_generator._strip_json_fence（offline）===")
    import json

    from core import batch_generator as bg

    raw = '```json\n{"0": "甲", "1": "乙"}\n```'
    data = json.loads(bg._strip_json_fence(raw))
    if data.get("0") != "甲":
        print(f"  [FAIL] 解析失败 {data}")
        return False
    print("  [OK]")
    return True


def _run_all_offline() -> bool:
    steps = [
        ("路由", _routing_tests),
        ("审核辅助", _audit_offline_helpers),
        ("query_expander", _offline_query_expander),
        ("rule/need_model_audit", _offline_rule_and_need_model_audit),
        ("max_output_tokens", _offline_max_output_tokens),
        ("task_grouper", _offline_task_grouper),
        ("evidence_planner", _offline_evidence_planner),
        ("bundle 路由对齐", _offline_bundle_evidence_route_parity),
        ("clean_table_answer", _offline_filler_clean_table),
        ("batch_json_fence", _offline_batch_json_fence),
    ]
    ok_all = True
    for name, fn in steps:
        try:
            if not fn():
                ok_all = False
        except Exception as e:
            print(f"  [FAIL] {name} 异常: {e}")
            if os.getenv("SMOKE_VERBOSE"):
                traceback.print_exc()
            ok_all = False
    return ok_all


def _stream_smoke(client: OpenAI) -> bool:
    """流式 + extra_body 路径（主生成同款）。"""
    print(f"=== 流式大模型 ({config.LARGE_LLM_MODEL}) ===")
    try:
        stream = chat_completions_create(
            client,
            model=config.LARGE_LLM_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": "请用一句话说明：什么是「项目申报书」（不超过40字）。",
                }
            ],
            temperature=config.TEMP_LARGE_LLM,
            max_tokens=32,
            stream=True,
        )
        buf: list[str] = []
        for chunk in stream:
            ch = chunk.choices[0] if chunk.choices else None
            if ch and ch.delta and ch.delta.content:
                buf.append(ch.delta.content)
        text = "".join(buf).strip()
        print(f"  拼接: {text!r}")
        if not text:
            print("  [FAIL] 流式无内容")
            return False
        print("  [OK]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        if os.getenv("SMOKE_VERBOSE"):
            traceback.print_exc()
        return False


def _chroma_minimal_embed() -> bool:
    """独立临时目录：add + query.search（走 embed_query）。"""
    print("=== Chroma 持久化 + add + search（embedding / embed_query）===")
    try:
        from core.vector_store import VectorStore
        from core.chunker import Chunk
        import uuid

        d = tempfile.mkdtemp(prefix="smoke_chroma_")
        slug = f"smoke_{uuid.uuid4().hex[:8]}"
        vs = VectorStore(persist_dir=d, kb_slug=slug)
        ch = Chunk(
            id=f"id_{uuid.uuid4().hex[:12]}",
            text="冒烟测试片段，仅验证入库链路。",
            metadata={"source": "smoke_test_models.py"},
        )
        vs.add_documents([ch])
        n = vs.get_collection_count()
        print(f"  collection={vs.collection_name} count={n}")
        if n < 1:
            print("  [FAIL] count 未增长")
            return False
        hits = vs.search("冒烟测试", top_k=2, max_distance=2.5)
        print(f"  search 命中数: {len(hits)}")
        if not hits:
            print("  [FAIL] search 无结果（embed_query 或检索链异常）")
            return False
        print("  [OK]")
        return True
    except Exception as e:
        print(f"  [FAIL] {e}")
        if os.getenv("SMOKE_VERBOSE"):
            traceback.print_exc()
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="模型与链路冒烟测试")
    ap.add_argument(
        "--offline",
        action="store_true",
        help="不调外部 API：配置摘要 + 路由/审核/query/分组证据/bundle 对齐等离线断言",
    )
    ap.add_argument("--skip-vision", action="store_true", help="跳过多模态视觉请求")
    ap.add_argument("--skip-chroma", action="store_true", help="跳过 Chroma 入库")
    ap.add_argument("--skip-embed-api", action="store_true", help="跳过仅 embedding API（仍可做 chroma）")
    args = ap.parse_args()

    _print_config()

    if args.offline:
        ok = _run_all_offline()
        print()
        print("=== 汇总（offline）===")
        print("  [OK] offline 检查通过" if ok else "  [FAIL] offline 检查失败")
        return 0 if ok else 1

    if not (config.OPENAI_COMPAT_API_KEY or "").strip():
        print("[FAIL] 无可用 API Key")
        return 1

    results: list[bool] = []
    client = _client()

    results.append(_chat_ping(client, config.SMALL_LLM_MODEL, config.TEMP_SMALL_LLM, "小模型"))
    results.append(_chat_ping(client, config.LARGE_LLM_MODEL, config.TEMP_LARGE_LLM, "大模型"))
    if not args.skip_vision:
        results.append(_vision_ping(client))
    else:
        print("=== 视觉模型 === [SKIP]")
        results.append(True)

    if not args.skip_embed_api:
        results.append(_embedding_ping())
    else:
        print("=== Embedding API === [SKIP]")
        results.append(True)

    results.append(_run_all_offline())
    results.append(_stream_smoke(client))

    if not args.skip_chroma:
        results.append(_chroma_minimal_embed())
    else:
        print("=== Chroma 入库 === [SKIP]")
        results.append(True)

    passed = sum(1 for x in results if x)
    total = len(results)
    print()
    print(f"=== 汇总: {passed}/{total} 通过 ===")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
