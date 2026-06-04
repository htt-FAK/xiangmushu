"""生成后过滤：去除模板指引类文字，替换为实际内容或占位标记。"""
import re
from typing import List, Tuple

# 典型的模板指引模式
_GUIDANCE_PATTERNS = [
    # "说明..."、"描述..."、"展示..." 开头的指令句
    r"^说明[项目本].{2,}(。|；)",
    r"^描述[目标用户].{2,}(。|；)",
    r"^展示[智能体角色].{2,}(。|；)",
    r"^填写[应用的].{2,}(。|；)",
    r"^请[粘贴在此].{2,}(。|；)",
    r"^本节[应把需].{2,}(。|；)",
    r"^至少[给出设计包含上传].{2,}(。|；)",
    r"^建议[从至少写].{2,}(。|；)",
    r"^围绕[智能体].{2,}(。|；)",
    r"^客观分析[不足].{2,}(。|；)",
    r"^展望[智能体].{2,}(。|；)",
    r"^学生提交时.{2,}(。|；)",
    r"^总分\d+分.{2,}(。|；)",
    # "建议包含…" 类型
    r"建议至少包含[：:].+",
    r"建议从.+展开",
    r"建议写.+创新点",
    r"建议至少.+",
    # "应体现…" 类型
    r"应[完整体现展示].+",
    r"应[把把].+写成",
    # "不要只写…" 类型
    r"不要只写.+",
    r"不能只写.+",
    # "至少给出/设计/包含…" 类型
    r"至少给出.+",
    r"至少设计.+",
    r"至少包含.+",
    r"至少上传.+",
    # 图片占位符
    r"^图\d+\.\d+.+截图$",
    r"^请在此处粘贴.+",
]

_COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in _GUIDANCE_PATTERNS]


def is_guidance_text(text: str) -> bool:
    """判断一段文字是否为模板指引/建议类文字。"""
    if not text or len(text.strip()) < 5:
        return False
    
    text = text.strip()
    
    # 匹配已知模式
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True
    
    # 额外启发式：包含"建议"且较短（<150字）的段落
    if "建议" in text and len(text) < 150:
        return True
    
    # 包含"至少"且是指导性语气
    if "至少" in text and any(kw in text for kw in ["包含", "给出", "设计", "上传", "展示"]):
        return True
    
    return False


def filter_guidance_paragraphs(paragraphs: List[Tuple[int, str, str]]) -> List[Tuple[int, str, str, str]]:
    """过滤模板指引段落。
    
    Args:
        paragraphs: [(段落索引, 样式名, 文本), ...]
    
    Returns:
        [(段落索引, 样式名, 文本, 状态), ...]
        状态: "keep" | "remove" | "replace"
    """
    results = []
    for idx, style, text in paragraphs:
        if is_guidance_text(text):
            results.append((idx, style, text, "remove"))
        else:
            results.append((idx, style, text, "keep"))
    return results


def get_filter_report(paragraphs: List[Tuple[int, str, str]]) -> str:
    """生成过滤报告。"""
    filtered = filter_guidance_paragraphs(paragraphs)
    removed = [(idx, style, text) for idx, style, text, status in filtered if status == "remove"]
    kept = [(idx, style, text) for idx, style, text, status in filtered if status == "keep"]
    
    report = f"总段落: {len(paragraphs)}\n保留: {len(kept)}\n需移除: {len(removed)}\n\n"
    report += "=== 需移除的模板指引段落 ===\n"
    for idx, style, text in removed:
        report += f"\n[段落 {idx}] {style}\n{text[:100]}...\n"
    
    return report
