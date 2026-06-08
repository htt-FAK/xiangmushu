import json
import logging
from collections import Counter
from typing import Any, List, Dict, Optional
import time

import chromadb
from chromadb.config import Settings

from core.chunker import Chunk
from core.kb_registry import collection_name_for_slug
from core.openai_embeddings import TimeoutOpenAIEmbedding
import config


_LOG = logging.getLogger(__name__)


def _patch_chromadb_sqlite_seq_id_decode() -> None:
    """部分持久化库在 SQLite 中 seq_id 已为 int，旧版 chromadb 仍按 bytes 解码会 TypeError。
    在创建 Client 前打补丁；新版已移除 _decode_seq_id 则跳过。"""
    try:
        from chromadb.segment.impl.metadata import sqlite as chroma_sqlite_meta
    except Exception:
        return
    orig = getattr(chroma_sqlite_meta, "_decode_seq_id", None)
    if orig is None or not callable(orig):
        return

    def _decode_seq_id_compat(seq_id_val):
        if isinstance(seq_id_val, int):
            return seq_id_val
        return orig(seq_id_val)

    chroma_sqlite_meta._decode_seq_id = _decode_seq_id_compat


_patch_chromadb_sqlite_seq_id_decode()

# 关闭产品遥测：chromadb 0.5 内置 PostHog 与新版 posthog 库不兼容，会刷
# 「capture() takes 1 positional argument but 3 were given」；改用空实现。
_CHROMA_SETTINGS = Settings(
    anonymized_telemetry=False,
    chroma_product_telemetry_impl=(
        "core.chroma_noop_product_telemetry.NoOpProductTelemetry"
    ),
    chroma_telemetry_impl="core.chroma_noop_product_telemetry.NoOpProductTelemetry",
)


def _first_row(val: Any) -> Optional[Any]:
    """Chroma query 返回的 distances/metadatas/documents 可能是 list 或 ndarray，避免对其做布尔判断。"""
    if val is None:
        return None
    try:
        n = len(val)
    except TypeError:
        return None
    if n < 1:
        return None
    return val[0]


class VectorStore:
    """ChromaDB：按 kb_slug 隔离 collection（plan_kb__{slug}）。"""

    def __init__(self, persist_dir: str = None, kb_slug: str = "kb1"):
        persist_dir = persist_dir or config.CHROMA_DIR
        self.kb_slug = kb_slug
        self._collection_name = collection_name_for_slug(kb_slug)
        self._client = chromadb.PersistentClient(
            path=persist_dir, settings=_CHROMA_SETTINGS
        )
        self._embedding_fn = TimeoutOpenAIEmbedding(
            api_key=config.OPENAI_COMPAT_API_KEY,
            base_url=config.EMBEDDING_OPENAI_BASE_URL or None,
            model_name=config.EMBEDDING_MODEL,
            timeout=config.OPENAI_TIMEOUT,
            max_retries=config.OPENAI_MAX_RETRIES,
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_fn,
        )
        self._search_cache: Dict[str, tuple[float, List[Dict]]] = {}
        self._search_cache_max_size = int(config.VECTOR_CACHE_MAX_SIZE)
        self._search_cache_ttl_seconds = int(config.VECTOR_CACHE_TTL_SECONDS)

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def cache_clear(self) -> None:
        self._search_cache.clear()

    def _search_cache_key(
        self,
        query: str,
        top_k: int,
        max_distance: Optional[float],
        filter_dict: Optional[Dict],
    ) -> str:
        return json.dumps([query, top_k, max_distance, filter_dict], sort_keys=True)

    def _search_cache_get(self, cache_key: str) -> Optional[List[Dict]]:
        if self._search_cache_max_size <= 0 or self._search_cache_ttl_seconds <= 0:
            return None
        cached = self._search_cache.get(cache_key)
        if cached is None:
            return None
        cached_at, items = cached
        if time.time() - cached_at > self._search_cache_ttl_seconds:
            self._search_cache.pop(cache_key, None)
            return None
        self._search_cache.pop(cache_key, None)
        self._search_cache[cache_key] = (cached_at, items)
        _LOG.debug("Vector search cache hit: %s", cache_key)
        return [dict(item) for item in items]

    def _search_cache_set(self, cache_key: str, items: List[Dict]) -> None:
        if self._search_cache_max_size <= 0 or self._search_cache_ttl_seconds <= 0:
            return
        self._search_cache.pop(cache_key, None)
        self._search_cache[cache_key] = (time.time(), [dict(item) for item in items])
        while len(self._search_cache) > self._search_cache_max_size:
            oldest_key = next(iter(self._search_cache))
            self._search_cache.pop(oldest_key, None)

    def add_documents(self, chunks: List[Chunk]):
        if not chunks:
            return
        self.cache_clear()
        sources = set(c.metadata.get("source", "") for c in chunks)
        for src in sources:
            self.delete_by_source(src)

        batch = max(1, int(config.EMBED_ADD_BATCH_SIZE))
        for i in range(0, len(chunks), batch):
            part = chunks[i : i + batch]
            self._add_batch_with_retry(part)

    def _add_batch_with_retry(self, part: List[Chunk], attempts: int = 4):
        last_err: Exception | None = None
        for attempt in range(attempts):
            try:
                self._collection.add(
                    ids=[c.id for c in part],
                    documents=[c.text for c in part],
                    metadatas=[c.metadata for c in part],
                )
                return
            except Exception as e:
                last_err = e
                time.sleep(min(8.0, 1.5 ** attempt))
        assert last_err is not None
        raise last_err

    def search(
        self,
        query: str,
        top_k: int = 3,
        filter_dict: Optional[Dict] = None,
        max_distance: Optional[float] = None,
    ) -> List[Dict]:
        cache_key = self._search_cache_key(query, top_k, max_distance, filter_dict)
        cached_items = self._search_cache_get(cache_key)
        if cached_items is not None:
            return cached_items

        kwargs: Dict = {
            "query_texts": [query],
            "n_results": top_k,
        }
        if filter_dict:
            kwargs["where"] = filter_dict

        try:
            results = self._collection.query(**kwargs)
        except Exception:
            return []

        items: List[Dict] = []
        docs_outer = results.get("documents") if results else None
        doc_row = _first_row(docs_outer)
        if doc_row is None:
            self._search_cache_set(cache_key, items)
            return items
        dist_row = _first_row(results.get("distances"))
        meta_row = _first_row(results.get("metadatas"))
        try:
            row_len = len(doc_row)
        except TypeError:
            self._search_cache_set(cache_key, items)
            return items
        for i in range(row_len):
            try:
                doc_text = doc_row[i]
            except (IndexError, TypeError):
                continue
            dist = None
            if dist_row is not None and i < len(dist_row):
                try:
                    dist = dist_row[i]
                except (IndexError, TypeError):
                    dist = None
            if max_distance is not None and dist is not None and float(dist) > max_distance:
                continue
            meta: Dict = {}
            if meta_row is not None and i < len(meta_row):
                try:
                    m = meta_row[i]
                    if isinstance(m, dict):
                        meta = m
                except (IndexError, TypeError):
                    pass
            items.append(
                {
                    "text": doc_text,
                    "metadata": meta,
                    "distance": float(dist) if dist is not None else None,
                }
            )
        self._search_cache_set(cache_key, items)
        return items

    def list_sources(self) -> List[str]:
        return sorted(self.source_chunk_counts().keys())

    def source_chunk_counts(self) -> Dict[str, int]:
        """每个来源文件名对应的向量片段条数。"""
        try:
            results = self._collection.get()
        except Exception:
            return {}
        if not results or not results.get("metadatas"):
            return {}
        c = Counter()
        for m in results["metadatas"]:
            if not m:
                continue
            src = (m.get("source") or "").strip()
            if not src:
                src = "(未知来源)"
            c[src] += 1
        return dict(c)

    def delete_by_source(self, source: str):
        self.cache_clear()
        try:
            self._collection.delete(where={"source": source})
        except Exception:
            pass

    def get_collection_count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0

    def get_all_documents(self, max_chars: int = 0) -> List[Dict]:
        """全量召回：返回知识库中所有文档片段。

        Args:
            max_chars: 最大总字符数，0 表示不限制。
        """
        try:
            results = self._collection.get()
        except Exception:
            return []
        if not results:
            return []

        docs = results.get("documents") or []
        metas = results.get("metadatas") or []
        items: List[Dict] = []
        total_chars = 0
        for i, doc_text in enumerate(docs):
            if not doc_text:
                continue
            meta = metas[i] if i < len(metas) and isinstance(metas[i], dict) else {}
            if max_chars > 0 and total_chars + len(doc_text) > max_chars:
                break
            items.append({"text": doc_text, "metadata": meta})
            total_chars += len(doc_text)
        return items

    def delete_entire_collection(self):
        """删除当前 kb 对应的整个 Chroma collection。"""
        self.cache_clear()
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:
            pass

    @staticmethod
    def list_kb_collection_names(persist_dir: str = None) -> List[str]:
        """列出持久化目录下名称以 plan_kb__ 开头的 collection。"""
        persist_dir = persist_dir or config.CHROMA_DIR
        client = chromadb.PersistentClient(
            path=persist_dir, settings=_CHROMA_SETTINGS
        )
        try:
            cols = client.list_collections()
        except Exception:
            return []
        names = []
        for c in cols:
            n = getattr(c, "name", None) or (c if isinstance(c, str) else str(c))
            if isinstance(n, str) and n.startswith("plan_kb__"):
                names.append(n)
        return sorted(names)
