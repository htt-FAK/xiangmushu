from typing import List, Dict, Optional
import chromadb
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from core.chunker import Chunk
import config


class VectorStore:
    """ChromaDB 封装，本地 SQLite 文件存储，零配置。"""

    def __init__(self, persist_dir: str = None):
        persist_dir = persist_dir or config.CHROMA_DIR
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._embedding_fn = OpenAIEmbeddingFunction(
            api_key=config.OPENAI_API_KEY,
            api_base=config.OPENAI_BASE_URL,
            model_name=config.EMBEDDING_MODEL,
        )
        self._collection = self._client.get_or_create_collection(
            name="plan_kb",
            embedding_function=self._embedding_fn,
        )

    def add_documents(self, chunks: List[Chunk]):
        """批量入库，重复入库前先按 source 删除旧数据。"""
        if not chunks:
            return
        # 按 source 去重
        sources = set(c.metadata.get("source", "") for c in chunks)
        for src in sources:
            self.delete_by_source(src)

        self._collection.add(
            ids=[c.id for c in chunks],
            documents=[c.text for c in chunks],
            metadatas=[c.metadata for c in chunks],
        )

    def search(
        self, query: str, top_k: int = 3, filter_dict: Optional[Dict] = None
    ) -> List[Dict]:
        kwargs = {
            "query_texts": [query],
            "n_results": top_k,
        }
        if filter_dict:
            kwargs["where"] = filter_dict

        results = self._collection.query(**kwargs)

        items = []
        if results and results["documents"]:
            for i, doc_text in enumerate(results["documents"][0]):
                items.append(
                    {
                        "text": doc_text,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "distance": results["distances"][0][i] if results["distances"] else 0,
                    }
                )
        return items

    def list_sources(self) -> List[str]:
        """返回已入库的所有文件名。"""
        results = self._collection.get()
        sources = set()
        if results and results["metadatas"]:
            for m in results["metadatas"]:
                src = m.get("source", "")
                if src:
                    sources.add(src)
        return sorted(sources)

    def delete_by_source(self, source: str):
        """按文件名删除所有相关 chunks。"""
        try:
            self._collection.delete(where={"source": source})
        except Exception:
            pass

    def get_collection_count(self) -> int:
        return self._collection.count()
