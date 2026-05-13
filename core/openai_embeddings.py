"""带超时与重试的 OpenAI Embedding，供 Chroma 使用（避免默认短超时导致入库失败）。

`name()` 必须返回与 Chroma 内置 `OpenAIEmbeddingFunction` 相同的注册名 `"openai"`，
否则对已存在的集合调用 `get_or_create_collection(..., embedding_function=...)` 会触发
persisted `openai` vs 新函数名的 ValueError。本实现仍为 OpenAI embeddings API，仅客户端
超时/重试与官方封装不同。
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np
from openai import OpenAI


class TimeoutOpenAIEmbedding:
    """Chroma 可调用 embedding；与持久化 `openai` 名称兼容，使用可配置 timeout 的 OpenAI 客户端。"""

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str],
        model_name: str,
        timeout: float,
        max_retries: int,
        dimensions: Optional[int] = None,
    ):
        kw: dict = {
            "api_key": api_key or "sk-placeholder",
            "timeout": timeout,
            "max_retries": max_retries,
        }
        if base_url:
            kw["base_url"] = base_url
        self._client = OpenAI(**kw)
        self._model_name = model_name
        self._dimensions = dimensions

    def __call__(self, input: List[str]) -> List[np.ndarray]:
        if not input:
            return []
        params: dict = {"model": self._model_name, "input": input}
        if self._dimensions is not None and (
            "text-embedding-3" in self._model_name or "text-embedding-v3" in self._model_name
        ):
            params["dimensions"] = self._dimensions
        response = self._client.embeddings.create(**params)
        return [np.array(d.embedding, dtype=np.float32) for d in response.data]

    def embed_query(self, input: List[str]) -> List[np.ndarray]:
        """Chroma 0.5+ 查询路径调用 embed_query；与官方 EmbeddingFunction 默认语义一致。"""
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        # 与 chromadb OpenAIEmbeddingFunction.name() 一致，避免 get_or_create_collection 冲突
        return "openai"

    def default_space(self) -> str:
        return "cosine"
