"""并行处理模块：使用线程池并发执行LLM调用等耗时操作"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

import config

_LOG = logging.getLogger(__name__)

T = TypeVar("T")
V = TypeVar("V")


def parallel_execute(
    items: List[T],
    processor: Callable[[T], V],
    max_workers: Optional[int] = None,
    desc: str = "task",
) -> List[Tuple[T, Optional[V], Optional[Exception]]]:
    """并行执行多个任务

    Args:
        items: 要处理的项目列表
        processor: 处理单个项目的函数
        max_workers: 最大并行数，默认使用配置中的MAX_PARALLEL_TASKS
        desc: 任务描述，用于日志

    Returns:
        (item, result, exception) 元组列表
    """
    if max_workers is None:
        max_workers = getattr(config, "MAX_PARALLEL_TASKS", 4)

    if not items:
        return []

    _LOG.info("parallel_execute: starting %d %s(s) with %d workers", len(items), desc, max_workers)

    results: List[Tuple[T, Optional[V], Optional[Exception]]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_item = {executor.submit(processor, item): item for item in items}

        completed = 0
        for future in as_completed(future_to_item):
            item = future_to_item[future]
            completed += 1
            try:
                result = future.result()
                results.append((item, result, None))
                _LOG.debug("parallel_execute: %s %d/%d done", desc, completed, len(items))
            except Exception as e:
                _LOG.warning("parallel_execute: %s failed: %s", desc, e)
                results.append((item, None, e))

    _LOG.info("parallel_execute: all %d %s(s) completed", len(items), desc)
    return results


def parallel_execute_with_args(
    items: List[Tuple[T, Dict[str, Any]]],
    processor: Callable[[T, Dict[str, Any]], V],
    max_workers: Optional[int] = None,
    desc: str = "task",
) -> List[Tuple[T, Optional[V], Optional[Exception]]]:
    """并行执行带额外参数的任务

    Args:
        items: (item, kwargs) 元组列表
        processor: 处理单个项目的函数 (item, **kwargs) -> V
        max_workers: 最大并行数
        desc: 任务描述

    Returns:
        (item, result, exception) 元组列表
    """
    if max_workers is None:
        max_workers = getattr(config, "MAX_PARALLEL_TASKS", 4)

    if not items:
        return []

    def wrapped_processor(pair: Tuple[T, Dict[str, Any]]) -> V:
        item, kwargs = pair
        return processor(item, **kwargs)

    wrapped_items = [(pair,) for pair in items]
    return parallel_execute(wrapped_items, wrapped_processor, max_workers, desc)


def parallel_map(
    func: Callable[..., T],
    args_list: List[Tuple[Any, ...]],
    max_workers: Optional[int] = None,
    desc: str = "map",
) -> List[Tuple[int, Optional[T], Optional[Exception]]]:
    """并行执行同一函数的多个参数组合

    Args:
        func: 要执行的函数
        args_list: 参数元组列表，每个元组是 func 的一组参数
        max_workers: 最大并行数
        desc: 任务描述

    Returns:
        (index, result, exception) 元组列表，index 是 args_list 中的索引
    """
    if max_workers is None:
        max_workers = getattr(config, "MAX_PARALLEL_TASKS", 4)

    if not args_list:
        return []

    results: List[Tuple[int, Optional[T], Optional[Exception]]] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_idx = {executor.submit(func, *args): i for i, args in enumerate(args_list)}

        completed = 0
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            completed += 1
            try:
                result = future.result()
                results.append((idx, result, None))
                _LOG.debug("parallel_map: %s %d/%d done", desc, completed, len(args_list))
            except Exception as e:
                _LOG.warning("parallel_map: %s failed at index %d: %s", desc, idx, e)
                results.append((idx, None, e))

    results.sort(key=lambda x: x[0])
    return results
