# ⚡ 性能优化指南

## 📊 性能瓶颈分析

| 问题 | 影响 | 已优化 |
|------|------|--------|
| 所有任务串行处理 | 慢 ⏱️ | ✅ |
| LLM调用没有并行 | 浪费时间 | ✅ |
| 没有查询缓存 | 重复计算 | ✅ |
| 审核步骤耗时 | 可选关闭 | ✅ |
| 表格单元格逐个生成 | 批量优化 | ✅ |

---

## 🚀 快速优化方案

### 方案1：调整配置参数（无需改代码）

修改 `.env` 文件：

```bash
# ===== 性能配置 =====

# 并行任务数（同时进行的LLM调用数，建议4-8）
MAX_PARALLEL_TASKS=4

# 是否启用查询缓存（相同query复用结果，0=关/1=开）
ENABLE_QUERY_CACHE=1

# 是否启用审核（0=关/1=开，关闭可节省约30-50%时间）
ENABLE_AUDIT=1

# 批量表格单元格上限（同行多个单元格合并为一次调用）
BATCH_MAX_CELLS=8

# 减少RAG片段长度，加速LLM（可选，默认1100）
RAG_SNIPPET_MAX_CHARS=800
```

---

### 方案2：使用批量表格生成（已内置）

系统已经支持将同一行的多个表格单元格合并为一次LLM调用：

- 默认配置：`BATCH_MAX_CELLS=8`
- 优化效果：8个单元格只需1次调用，节省约75%表格生成时间

---

## 📈 预期性能提升

| 场景 | 优化前 | 优化后 | 提升 |
|------|--------|--------|------|
| 10个段落任务（串行） | ~100秒 | ~25秒（4并发） | 4x ⚡ |
| 20个表格单元格（逐格） | ~60秒 | ~15秒（批量+并发） | 4x ⚡ |
| 开启缓存后重复查询 | ~2秒/次 | ~0.01秒/次 | 200x ⚡ |
| 关闭审核（可选） | ~基准 | ~快30-50% | 1.3-2x ⚡ |

---

## 🔧 如何在代码中使用新功能

### 并行处理示例

```python
from core.parallel_processor import parallel_execute, parallel_map

# 示例1：并行处理多个任务
def process_single(item):
    # 处理单个项目
    return result

results = parallel_execute(
    items=[task1, task2, task3],
    processor=process_single,
    max_workers=4,
    desc="task"
)

# 示例2：并行执行同一函数的多个参数组合
def my_func(a, b):
    return a + b

args_list = [(1, 2), (3, 4), (5, 6)]
results = parallel_map(my_func, args_list, desc="calc")
```

### 缓存使用示例

```python
from core.cache import cached_query, get_query_cache

# 在查询函数上使用装饰器
@cached_query
def expensive_query(query):
    # 耗时的查询操作
    return result
```

---

## ⚙️ 调优建议

### MAX_PARALLEL_TASKS 设置

| 网络速度 | API限流 | 推荐值 |
|---------|--------|--------|
| 快 | 高 | 6-8 |
| 中 | 中 | 4 |
| 慢 | 低 | 2-3 |

### 何时关闭审核

| 场景 | 建议 | 原因 |
|------|------|------|
| 快速原型 | 关 ⚡ | 节省时间 |
| 最终产出 | 开 ✅ | 保证质量 |
| 重复模板 | 关 ⚡ | 熟悉结果 |

---

## 📊 性能监控

日志中会显示以下信息：

```
202X-XX-XX INFO - parallel_execute: starting 10 task(s) with 4 workers
202X-XX-XX INFO - content_gen_route {...}
202X-XX-XX INFO - batch_table_row done: model=... cells=...
```

---

## 💡 其他优化技巧

1. **使用更快的小模型**：对于简单任务，可以用小模型
2. **优化提示词**：更简洁的提示词能减少token和时间
3. **减少top_k**：减少RAG返回的片段数（默认3，可改为2）
4. **预处理数据**：提前处理好数据，避免运行时处理

---

## 🎯 最佳实践总结

| 操作 | 收益 | 代价 |
|------|------|------|
| 开启并发 | 2-4x | 无 |
| 开启缓存 | 2-200x | 少量内存 |
| 批量表格 | 2-8x | 无 |
| 关闭审核 | 1.3-2x | 可能降低质量 |

---

**推荐配置**（平衡质量与速度）：
```env
MAX_PARALLEL_TASKS=4
ENABLE_QUERY_CACHE=1
ENABLE_AUDIT=1
BATCH_MAX_CELLS=8
```
