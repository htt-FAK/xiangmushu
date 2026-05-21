#!/usr/bin/env python3
"""性能优化功能演示脚本"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

# 确保项目根目录在路径中
sys.path.insert(0, str(Path(__file__).parent.parent))

import config

# 设置日志级别
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
_LOG = logging.getLogger(__name__)


def demo_parallel_processing():
    """演示并行处理功能"""
    from core.parallel_processor import parallel_execute
    import time

    _LOG.info("=== 并行处理演示 ===")

    def process_item(item: int) -> int:
        """模拟耗时处理"""
        time.sleep(0.5)
        return item * 2

    items = list(range(8))
    _LOG.info("开始处理 %d 个项目，使用 4 个并行线程...", len(items))

    # 串行处理（对比）
    start = time.time()
    for item in items:
        process_item(item)
    serial_time = time.time() - start

    # 并行处理
    start = time.time()
    results = parallel_execute(
        items=items,
        processor=process_item,
        max_workers=4,
        desc="demo"
    )
    parallel_time = time.time() - start

    _LOG.info("串行耗时: %.2f 秒", serial_time)
    _LOG.info("并行耗时: %.2f 秒", parallel_time)
    _LOG.info("速度提升: %.1fx", serial_time / parallel_time if parallel_time > 0 else 1)


def demo_cache():
    """演示缓存功能"""
    from core.cache import cached_query, get_query_cache, clear_all_caches
    import time

    _LOG.info("=== 缓存功能演示 ===")

    @cached_query
    def expensive_func(x: int) -> int:
        """模拟耗时函数"""
        time.sleep(0.3)
        return x * x

    # 第一次调用（缓存未命中）
    start = time.time()
    result1 = expensive_func(10)
    time1 = time.time() - start

    # 第二次调用（缓存命中）
    start = time.time()
    result2 = expensive_func(10)
    time2 = time.time() - start

    _LOG.info("第一次调用: result=%d, time=%.3fs", result1, time1)
    _LOG.info("第二次调用: result=%d, time=%.3fs", result2, time2)
    _LOG.info("缓存加速: %.1fx", time1 / time2 if time2 > 0 else 1)

    clear_all_caches()


def check_config():
    """检查当前配置"""
    _LOG.info("=== 当前性能配置 ===")
    _LOG.info("MAX_PARALLEL_TASKS = %d", getattr(config, "MAX_PARALLEL_TASKS", 4))
    _LOG.info("ENABLE_QUERY_CACHE = %s", getattr(config, "ENABLE_QUERY_CACHE", True))
    _LOG.info("QUERY_CACHE_SIZE = %d", getattr(config, "QUERY_CACHE_SIZE", 100))
    _LOG.info("ENABLE_AUDIT = %s", getattr(config, "ENABLE_AUDIT", True))
    _LOG.info("BATCH_MAX_CELLS = %d", getattr(config, "BATCH_MAX_CELLS", 8))


def main():
    """主函数"""
    _LOG.info("🚀 性能优化功能演示")
    _LOG.info("=" * 50)

    check_config()
    _LOG.info("")

    demo_cache()
    _LOG.info("")

    demo_parallel_processing()
    _LOG.info("")

    _LOG.info("=" * 50)
    _LOG.info("✅ 演示完成！")
    _LOG.info("")
    _LOG.info("💡 性能优化使用建议：")
    _LOG.info("1. 修改 .env 文件中的性能配置")
    _LOG.info("2. 在 server.py 或 app.py 中使用 core.parallel_processor")
    _LOG.info("3. 查看 PERFORMANCE_GUIDE.md 了解更多")


if __name__ == "__main__":
    main()
