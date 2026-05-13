from typing import List, Dict, Optional
import time

import chromadb

from core.chunker import Chunk
from core.kb_registry import collection_name_for_slug
from core.openai_embeddings import TimeoutOpenAIEmbedding
import config


def _patch_chromadb_sqlite_seq_id_decode() -> None:
    """部分持久化库在 SQLite 中 seq_id 已为 int，chromadb 0.5.0 仍按 bytes 解码会 TypeError。
    在创建 Client 前打补丁，避免 collection.get / list_sources 等崩溃。"""
    try:
        from chromadb.segment.impl.metadata import sqlite as chroma_sqlite_meta
    except Exception:
        return
    orig = chroma_sqlite_meta._decode_seq_id

    def _decode_seq_id_compat(seq_id_val):
        if isinstance(seq_id_val, int):
            return seq_id_val
        return orig(seq_id_val)

    chroma_sqlite_meta._decode_seq_id = _decode_seq_id_compat


_patch_chromadb_sqlite_seq_id_decode()


class VectorStore:
    """ChromaDB：按 kb_slug 隔离 collection（plan_kb__{slug}）。"""

    def __init__(self, persist_dir: str = None, kb_slug: str = "kb1"):
        persist_dir = persist_dir or config.CHROMA_DIR
        self.kb_slug = kb_slug
        self._collection_name = collection_name_for_slug(kb_slug)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embedding_fn = TimeoutOpenAIEmbedding(
            api_key=config.OPENAI_COMPAT_API_KEY,
            base_url=config.OPENAI_BASE_URL or None,
            model_name=config.EMBEDDING_MODEL,
            timeout=config.OPENAI_TIMEOUT,
            max_retries=config.OPENAI_MAX_RETRIES,
        )
        self._collection = self._client.get_or_create_collection(
            name=self._collection_name,
            embedding_function=self._embedding_fn,
        )

    @property
    def collection_name(self) -> str:
        return self._collection_name

    def add_documents(self, chunks: List[Chunk]):
        if not chunks:
            return
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

        items = []
        if results and results["documents"]:
            dist_row = results.get("distances") and results["distances"][0]
            meta_row = results.get("metadatas") and results["metadatas"][0]
            for i, doc_text in enumerate(results["documents"][0]):
                dist = dist_row[i] if dist_row is not None and i < len(dist_row) else None
                if max_distance is not None and dist is not None and dist > max_distance:
                    continue
                items.append(
                    {
                        "text": doc_text,
                        "metadata": meta_row[i] if meta_row is not None and i < len(meta_row) else {},
                        "distance": dist,
                    }
                )
        return items

    def list_sources(self) -> List[str]:
        try:
            results = self._collection.get()
        except Exception:
            return []
        sources = set()
        if results and results["metadatas"]:
            for m in results["metadatas"]:
                if not m:
                    continue
                src = m.get("source", "")
                if src:
                    sources.add(src)
        return sorted(sources)

    def delete_by_source(self, source: str):
        try:
            self._collection.delete(where={"source": source})
        except Exception:
            pass

    def get_collection_count(self) -> int:
        try:
            return self._collection.count()
        except Exception:
            return 0

    def delete_entire_collection(self):
        """删除当前 kb 对应的整个 Chroma collection。"""
        try:
            self._client.delete_collection(self._collection_name)
        except Exception:
            pass

    @staticmethod
    def list_kb_collection_names(persist_dir: str = None) -> List[str]:
        """列出持久化目录下名称以 plan_kb__ 开头的 collection。"""
        persist_dir = persist_dir or config.CHROMA_DIR
        client = chromadb.PersistentClient(path=persist_dir)
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
