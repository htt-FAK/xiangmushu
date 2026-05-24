"""文档优化模块：基于视觉审核和内容审核结果进行二轮优化。"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import config
from core.visual_auditor import VisualAuditResult, should_optimize, build_optimization_prompt

_LOG = logging.getLogger(__name__)


@dataclass
class OptimizationRound:
    """优化轮次记录"""
    round_num: int
    visual_score: int
    watermark_score: int
    format_score: int
    content_score: int
    table_score: int
    layout_score: int
    issues: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)


@dataclass
class OptimizationResult:
    """优化结果"""
    success: bool
    final_score: int
    rounds: List[OptimizationRound]
    best_docx_path: Optional[str] = None
    total_rounds: int = 0


def diagnose_issues(visual_result: VisualAuditResult) -> Dict[str, List[str]]:
    """诊断问题类型。

    Returns:
        {"visual": [...], "content": [...], "structure": [...]}
    """
    issues = {"visual": [], "content": [], "structure": []}

    # 视觉问题
    if visual_result.watermark_score < 15:
        issues["visual"].append(f"水印完整性不足 ({visual_result.watermark_score}/20)")
    if visual_result.format_score < 15:
        issues["visual"].append(f"格式正确性不足 ({visual_result.format_score}/20)")
    if visual_result.layout_score < 15:
        issues["visual"].append(f"排版美观度不足 ({visual_result.layout_score}/20)")

    # 内容问题
    if visual_result.content_score < 15:
        issues["content"].append(f"内容充实度不足 ({visual_result.content_score}/20)")

    # 结构问题
    if visual_result.table_score < 15:
        issues["structure"].append(f"表格规范性不足 ({visual_result.table_score}/20)")

    # 从 issues 列表中进一步分类
    for issue in visual_result.issues:
        issue_lower = issue.lower()
        if any(kw in issue_lower for kw in ["水印", "格式", "字体", "排版", "间距"]):
            issues["visual"].append(issue)
        elif any(kw in issue_lower for kw in ["内容", "充实", "简短", "空白"]):
            issues["content"].append(issue)
        elif any(kw in issue_lower for kw in ["表格", "边框", "对齐", "结构"]):
            issues["structure"].append(issue)
        else:
            issues["content"].append(issue)

    return issues


def optimize_document(
    docx_path: str,
    visual_audit_fn,
    regenerate_fn,
    max_rounds: int = 3,
    pass_score: int = 85,
) -> OptimizationResult:
    """对文档进行多轮优化。

    Args:
        docx_path: 文档路径
        visual_audit_fn: 视觉审核函数
        regenerate_fn: 重新生成函数
        max_rounds: 最大优化轮次
        pass_score: 通过分数线

    Returns:
        OptimizationResult: 优化结果
    """
    rounds: List[OptimizationRound] = []
    best_score = 0
    best_docx = docx_path

    for round_num in range(1, max_rounds + 1):
        _LOG.info("开始第 %s 轮优化", round_num)

        # 视觉审核
        visual_result = visual_audit_fn(best_docx)

        round_record = OptimizationRound(
            round_num=round_num,
            visual_score=visual_result.score,
            watermark_score=visual_result.watermark_score,
            format_score=visual_result.format_score,
            content_score=visual_result.content_score,
            table_score=visual_result.table_score,
            layout_score=visual_result.layout_score,
            issues=visual_result.issues.copy(),
        )

        # 检查是否通过
        if visual_result.score >= pass_score:
            _LOG.info("第 %s 轮优化通过，分数: %s", round_num, visual_result.score)
            round_record.improvements.append(f"通过审核，分数: {visual_result.score}")
            rounds.append(round_record)
            return OptimizationResult(
                success=True,
                final_score=visual_result.score,
                rounds=rounds,
                best_docx_path=best_docx,
                total_rounds=round_num,
            )

        # 诊断问题
        issues = diagnose_issues(visual_result)
        _LOG.info("第 %s 轮发现问题: visual=%s, content=%s, structure=%s",
                 round_num, len(issues["visual"]), len(issues["content"]), len(issues["structure"]))

        # 构建优化提示词
        optimization_hint = build_optimization_prompt(visual_result)

        # 尝试重新生成
        try:
            new_docx = regenerate_fn(best_docx, optimization_hint, issues)
            if new_docx and new_docx != best_docx:
                best_docx = new_docx
                round_record.improvements.append("已重新生成文档")
            else:
                round_record.improvements.append("重新生成未产生新文档")
        except Exception as e:
            _LOG.warning("第 %s 轮重新生成失败: %s", round_num, e)
            round_record.improvements.append(f"重新生成失败: {e}")

        rounds.append(round_record)

        # 检查分数是否有改善
        if round_num > 1:
            prev_score = rounds[-2].visual_score
            curr_score = visual_result.score
            if curr_score <= prev_score:
                _LOG.warning("第 %s 轮分数未改善 (%s -> %s)，停止优化", 
                           round_num, prev_score, curr_score)
                break

    # 达到最大轮次仍未通过
    final_score = rounds[-1].visual_score if rounds else 0
    _LOG.info("优化结束，共 %s 轮，最终分数: %s", len(rounds), final_score)

    return OptimizationResult(
        success=final_score >= pass_score,
        final_score=final_score,
        rounds=rounds,
        best_docx_path=best_docx,
        total_rounds=len(rounds),
    )


def format_optimization_report(result: OptimizationResult) -> str:
    """格式化优化报告。

    Args:
        result: 优化结果

    Returns:
        格式化后的报告文本
    """
    lines = [
        "=" * 50,
        "文档优化报告",
        "=" * 50,
        f"优化结果: {'通过' if result.success else '未通过'}",
        f"最终分数: {result.final_score}/100",
        f"总轮次: {result.total_rounds}",
        "",
    ]

    for round_record in result.rounds:
        lines.append(f"--- 第 {round_record.round_num} 轮 ---")
        lines.append(f"  总分: {round_record.visual_score}/100")
        lines.append(f"  水印: {round_record.watermark_score}/20")
        lines.append(f"  格式: {round_record.format_score}/20")
        lines.append(f"  内容: {round_record.content_score}/20")
        lines.append(f"  表格: {round_record.table_score}/20")
        lines.append(f"  排版: {round_record.layout_score}/20")

        if round_record.issues:
            lines.append("  问题:")
            for issue in round_record.issues:
                lines.append(f"    - {issue}")

        if round_record.improvements:
            lines.append("  改进:")
            for improvement in round_record.improvements:
                lines.append(f"    - {improvement}")

        lines.append("")

    lines.append("=" * 50)
    return "\n".join(lines)
