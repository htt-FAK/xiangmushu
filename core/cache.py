"""缓存模块：用于缓存查询、嵌入计算等耗时操作"""
from __future__ import annotations

import hashlib
import json
import logging
from collections import OrderedDict
from typing import Any, Callable, Generic, Optional, TypeVar

import config

_LOG = logging.getLogger(__name__)

T = TypeVar("T")


class LRUCache(Generic[T]):
    """LRU缓存：最近最少使用策略"""

    def __init__(self, maxsize: int = 100):
        self._cache: OrderedDict[str, T] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[T]:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: T) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        while len(self._cache) > self._maxsize:
            removed = self._cache.popitem(last=False)
            _LOG.debug("cache evicted: %s", removed[0])

    def clear(self) -> None:
        self._cache.clear()

    def __contains__(self, key: str) -> bool:
        return key in self._cache

    def __len__(self) -> int:
        return len(self._cache)


def _hash_key(*args: Any, **kwargs: Any) -> str:
    """生成参数的hash作为缓存key"""
    key_data = {"args": args, "kwargs": sorted(kwargs.items()) if kwargs else {}}
    key_str = json.dumps(key_data, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(key_str.encode("utf-8")).hexdigest()


# 全局缓存实例
_query_cache: Optional[LRUCache] = None


def get_query_cache() -> LRUCache:
    """获取查询缓存单例"""
    global _query_cache
    if _query_cache is None:
        maxsize = getattr(config, "QUERY_CACHE_SIZE", 100)
        _query_cache = LRUCache(maxsize=maxsize)
    return _query_cache


def cached_query(func: Callable[..., T]) -> Callable[..., T]:
    """查询缓存装饰器"""

    def wrapper(*args: Any, **kwargs: Any) -> T:
        if not getattr(config, "ENABLE_QUERY_CACHE", True):
            return func(*args, **kwargs)

        cache = get_query_cache()
        key = _hash_key(func.__name__, *args, **kwargs)
        cached = cache.get(key)
        if cached is not None:
            _LOG.debug("query cache hit: %s", key[:16])
            return cached
        result = func(*args, **kwargs)
        cache.set(key, result)
        return result

    return wrapper


def clear_all_caches() -> None:
    """清空所有缓存"""
    global _query_cache
    if _query_cache is not None:
        _query_cache.clear()
        _query_cache = None
    _LOG.info("all caches cleared")
