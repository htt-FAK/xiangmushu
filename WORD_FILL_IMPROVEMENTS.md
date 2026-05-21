# Word 回填改进说明

## 改进内容

### 1. 语义章节匹配 ✅
新增多种匹配策略，不再依赖简单的字符串包含：

```python
# 策略1: 精确匹配（去空白）
"第一章 项目背景" in "第一章 项目背景与实施计划"  # ✅

# 策略2: 关键词重叠匹配
keywords("项目背景") ∩ keywords("项目背景及实施")  # ≥2个关键词

# 策略3: 标准化文本匹配
_normalize("第一章 项目背景") ≈ _normalize("一、项目背景与意义")  # ✅
```

### 2. 表格定位校验 + 回退机制 ✅
当 LLM 分析的 table_index/row/col 超出范围时，自动回退：

```python
# 原始定位失败
table_index=5  # 但文档只有3个表
row=10          # 但表格只有5行

# 回退策略1: 在所有表格中按描述关键词搜索
# 回退策略2: 在指定表格中按行内容匹配
# 回退策略3: 找到第一个空单元格
```

### 3. 段落填充回退机制 ✅
章节匹配失败时，自动全局搜索最匹配的段落：

```python
# 章节未找到 → 全局搜索
# 章节内无有效段落 → 按描述关键词搜索
# 完全无匹配 → 找第一个空段落
```

### 4. 调试日志 ✅
每个填充操作都有详细日志，便于排查问题。

## 使用方法

### 启用调试日志

```bash
# 方式1: 环境变量
export APP_CONSOLE_LOG=1
streamlit run app.py

# 方式2: 在代码中
import logging
logging.getLogger('core.filler').setLevel(logging.DEBUG)
```

### 日志输出示例

```
2026-05-21 10:30:15 INFO [core.filler] [段落填充] 任务=abc123 章节='项目背景' 内容长度=350
2026-05-21 10:30:15 DEBUG [core.filler] 章节精确匹配成功: 项目背景 <-> 项目背景与实施计划
2026-05-21 10:30:15 INFO [core.filler] 选择段落5(score=3): '请在此填写项目背景...'
2026-05-21 10:30:15 INFO [core.filler] [段落填充] 成功

2026-05-21 10:30:16 WARNING [core.filler] [表格填充] row=10 超出范围(共5行), 尝试回退...
2026-05-21 10:30:16 INFO [core.filler] [行回退] 找到最佳行=3 (score=2)
2026-05-21 10:30:16 INFO [core.filler] [表格填充] 成功
```

### 日志级别说明

| 级别 | 含义 | 示例 |
|------|------|------|
| INFO | 主要操作 | "开始填充段落"、"找到匹配" |
| WARNING | 异常但已处理 | "行号超出范围，使用回退" |
| DEBUG | 详细匹配过程 | "关键词匹配成功: {'项目', '背景'}" |
| ERROR | 严重错误 | "完全没有可用段落" |

## 最佳实践

### 1. 使用显式锚点（最可靠）

```docx
项目背景：{{BACKGROUND}}

风险披露：{{RISK_DISCLOSURE}}
```

### 2. 统一章节标题格式

```docx
✅ 第一章 项目背景
✅ 一、项目背景与实施计划
❌ 第一章项目背景
```

### 3. 表格描述要具体

```json
{
  "description": "基金管理人名称"
}
```

### 4. 查看日志排查问题

```bash
# 查看所有日志
APP_CONSOLE_LOG=1 python smoke_test_models.py

# 只看WARNING和ERROR
APP_CONSOLE_LOG=1 python app.py 2>&1 | grep -E "(WARNING|ERROR)"
```

## 故障排查

### 问题1: 段落没有被填充

```bash
# 启用DEBUG日志查看匹配过程
APP_CONSOLE_LOG=debug streamlit run app.py
```

检查日志中是否有：
- `[段落填充] 章节'xxx'未找到匹配段落`
- `[段落回退] 未找到匹配段落`

### 问题2: 表格填充到错误位置

```bash
# 查看表格定位信息
APP_CONSOLE_LOG=1 python app.py 2>&1 | grep "表格填充"
```

检查日志中：
- LLM分析输出的 table_index/row/col 是否正确
- 回退机制是否生效

### 问题3: 内容被填充到错误位置

1. 检查模板格式是否规范
2. 启用 DEBUG 日志查看评分详情
3. 使用更具体的描述（description）

## 后续优化计划

- [ ] 增加 embedding 语义相似度匹配
- [ ] 支持模板格式自动规范化
- [ ] 增加可视化调试工具
- [ ] 优化回退策略的准确性
