"""使用 dashscope SDK 的 Embedding，供 Chroma 使用。

`name()` 必须返回与 Chroma 内置 `OpenAIEmbeddingFunction` 相同的注册名 `"openai"`，
否则对已存在的集合调用 `get_or_create_collection(..., embedding_function=...)` 会触发
persisted `openai` vs 新函数名的 ValueError。
"""
from __future__ import annotations

from http import HTTPStatus
from typing import List, Optional

import dashscope


class TimeoutOpenAIEmbedding:
    """Chroma 可调用 embedding；内部使用 dashscope.TextEmbedding 而非 OpenAI API。
    类名、`name()` / `default_space()` 与 Chroma 持久化兼容。
    """

    def __init__(
        self,
        api_key: str,
        base_url: Optional[str],
        model_name: str,
        timeout: float,
        max_retries: int,
        dimensions: Optional[int] = None,
    ):
        self._api_key = api_key
        self._model_name = model_name
        self._timeout = timeout
        self._max_retries = max_retries
        self._dimensions = dimensions

    def __call__(self, input: List[str]) -> List[List[float]]:
        if not input:
            return []
        resp = dashscope.TextEmbedding.call(
            model=self._model_name,
            input=input,
            api_key=self._api_key,
        )
        if resp.status_code != HTTPStatus.OK:
            raise RuntimeError(
                f"DashScope TextEmbedding 调用失败: "
                f"status={resp.status_code}, message={resp}"
            )
        return [list(item.get("embedding")) for item in resp.output.get("embeddings", [])]

    def embed_query(self, input: List[str]) -> List[List[float]]:
        """Chroma 0.5+ 查询路径调用 embed_query；与官方 EmbeddingFunction 默认语义一致。"""
        return self.__call__(input)

    @staticmethod
    def name() -> str:
        # 与 chromadb OpenAIEmbeddingFunction.name() 一致，避免 get_or_create_collection 冲突
        return "openai"

    def default_space(self) -> str:
        return "cosine"
