"""文档类型推断器。

从模板文件名（或显式传入）推断文档类型字符串，注入到 LLM System Prompt
解决"创新创业书被写成介绍/申报书"的内容偏题问题。

核心方法：
    infer_document_type(template_path, explicit_type=None) -> str
        返回文档类型（如 "创新创业计划书"、"项目申报书"、"结课报告" 等）
        explicit_type 非空时直接返回，不做推断
"""
from __future__ import annotations

import logging
import os
import re
from typing import Optional

_LOG = logging.getLogger(__name__)

# ── 文件名 → 文档类型映射表（按匹配优先级排序，先匹配先返回）────────────────
_FILENAME_PATTERNS: list[tuple[re.Pattern, str]] = [
    # 大学生创新创业类（优先于通用创新创业，避免"大学生"被忽略）
    (re.compile(r"大创|大学生创新|大学生创新创业|创新大赛", re.IGNORECASE), "大学生创新创业项目计划书"),
    (re.compile(r"挑战杯|互联网\+|互联网\+大赛", re.IGNORECASE), "创新创业竞赛计划书"),
    # 创新创业类（通用）
    (re.compile(r"创新(创业)?计划书|创新创业", re.IGNORECASE), "创新创业计划书"),
    # 项目申报类
    (re.compile(r"项目申报(书|材料)|申报(书|材料)", re.IGNORECASE), "项目申报书"),
    (re.compile(r"基金(申请|申报)(书)?", re.IGNORECASE), "基金申请书"),
    (re.compile(r"科研(项目)?(申报|计划)书", re.IGNORECASE), "科研项目申报书"),
    # 课程/结课类
    (re.compile(r"结课报告|课程报告|实验报告", re.IGNORECASE), "课程实验/结课报告"),
    (re.compile(r"课程设计(报告)?", re.IGNORECASE), "课程设计报告"),
    (re.compile(r"毕业设计|毕业论文|学位论文", re.IGNORECASE), "毕业设计/学位论文"),
    # 智能体应用类
    (re.compile(r"智能体(应用)?(开发)?实践", re.IGNORECASE), "智能体应用开发实践报告"),
    (re.compile(r"(AI|大模型|智能)应用(开发)?(报告|实践)" , re.IGNORECASE), "AI应用开发实践报告"),
    # 项目计划书（通用）
    (re.compile(r"项目(计划|规划)书", re.IGNORECASE), "项目计划书"),
    (re.compile(r"可行性(分析)?报告|可行性(研究)?", re.IGNORECASE), "可行性研究报告"),
    (re.compile(r"商业计划(书)?|BP", re.IGNORECASE), "商业计划书"),
]

_Fallback_DOC_TYPE = "项目申报文档（通用）"


def infer_document_type(
    template_path: str,
    explicit_type: Optional[str] = None,
) -> str:
    """从模板文件名推断文档类型，explicit_type 非空时直接返回。

    Args:
        template_path: .docx 模板文件路径（basename 用于匹配）
        explicit_type: 用户/调用方显式指定的文档类型，优先使用

    Returns:
        文档类型字符串，如 "创新创业计划书"、"项目申报书" 等
    """
    if explicit_type and explicit_type.strip():
        result = explicit_type.strip()
        _LOG.info("document_type: explicit=%r", result)
        return result

    basename = os.path.basename(template_path or "")
    for pattern, doc_type in _FILENAME_PATTERNS:
        if pattern.search(basename):
            _LOG.info("document_type: inferred=%r from basename=%r", doc_type, basename)
            return doc_type

    _LOG.info("document_type: fallback=%r (no pattern matched basename=%r)",
              _Fallback_DOC_TYPE, basename)
    return _Fallback_DOC_TYPE


def format_document_type_block(doc_type: str) -> str:
    """将文档类型格式化为注入 Prompt 的文本块。"""
    if not doc_type:
        return ""
    return f"⚠️ 文档类型：{doc_type}"
