"""
冒烟测试：校验百炼/OpenAI 兼容网关下各模型可调、ContentGenerator 路由正确。

用法（在 xiangmushu 目录下）:
  python smoke_test_models.py
  python smoke_test_models.py --offline        # 仅配置摘要 + 路由逻辑，不调外部 API
  python smoke_test_models.py --skip-vision   # 跳过多模态（省配额）
  python smoke_test_models.py --skip-chroma   # 跳过 Chroma+embedding

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
from core.generator import ContentGenerator  # noqa: E402
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

    # 有 KB 命中 -> 大模型
    g1 = ContentGenerator(_MockVS(5, [{"text": "参考资料", "metadata": {"source": "x"}, "distance": 0.3}]))
    _, m1, t1, _, _ = g1._build_chat_request(task, top_k=3, enable_web=True, retrieval_max_distance=1.0)
    print(f"  有命中 + 开联网: model={m1!r} temp={t1}")
    if m1 != config.LARGE_LLM_MODEL:
        print("  [FAIL] 预期 LARGE_LLM_MODEL")
        ok = False
    else:
        print("  [OK] 使用大模型")

    # 空库 + 开联网 -> VISION_WEB_MODEL + extra_body.enable_search（百炼内置联网）
    g2 = ContentGenerator(_MockVS(0, []))
    _, m2, t2, eb2, _ = g2._build_chat_request(task, top_k=3, enable_web=True, retrieval_max_distance=1.0)
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
    _, m3, t3, eb3, _ = g3._build_chat_request(task, top_k=3, enable_web=False, retrieval_max_distance=1.0)
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
    _, m4, t4, eb4, rm4 = g4._build_chat_request(
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
        help="不调外部 API：仅打印配置并跑 ContentGenerator 路由断言",
    )
    ap.add_argument("--skip-vision", action="store_true", help="跳过多模态视觉请求")
    ap.add_argument("--skip-chroma", action="store_true", help="跳过 Chroma 入库")
    ap.add_argument("--skip-embed-api", action="store_true", help="跳过仅 embedding API（仍可做 chroma）")
    args = ap.parse_args()

    _print_config()

    if args.offline:
        ok = _routing_tests()
        print()
        print("=== 汇总（offline）===")
        print("  [OK] 路由检查通过" if ok else "  [FAIL] 路由检查失败")
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

    results.append(_routing_tests())
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
