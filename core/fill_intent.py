"""表格语义标注枚举。

定义表格整体类型和单元格级 fill_intent，供 `table_semantic_analyzer` 和
`filler` / `table_slot_expand` / `generator` 共用，解决"什么该写什么不该写"的核心问题。

表格类型（TableSemanticType）：
    LABEL_VALUE_PAIR  - 2列，col 0 为窄标签，col 1 为内容（如项目基本信息、实施方案）
    DATA_GRID         - ≥3列，row 0 为表头，数据行待填（如团队成员列表）
    INNOVATION_TRIPLE - 3列，表头含"创新点/实现/应用"（专项三列表）
    RUBRIC_SCORING    - 评分表，列含"评分/评价/总分"，只读不填
    COVER_INFO        - 封面表，含学号/姓名/学院等身份信息，只读不填
    UNKNOWN           - 未识别，回退到旧 cell_needs_fill() 逻辑

单元格意图（FillIntent）：
    FILL       - 需要 LLM 生成内容并写入
    LABEL      - 仅作为标签/标题，不填内容，filler 跳过
    READ_ONLY  - 封面/评分等不应修改，filler 跳过
    USER_INPUT - 用户手动填写字段（姓名/学号），filler 跳过
"""
from __future__ import annotations

from enum import Enum


class TableSemanticType(str, Enum):
    """表格整体结构类型，决定列宽保护策略和 fill_intent 分配规则。"""

    LABEL_VALUE_PAIR = "label_value_pair"
    DATA_GRID = "data_grid"
    INNOVATION_TRIPLE = "innovation_triple"
    RUBRIC_SCORING = "rubric_scoring"
    COVER_INFO = "cover_info"
    UNKNOWN = "unknown"

    @property
    def is_read_only(self) -> bool:
        """封面表和评分表整表只读。"""
        return self in (self.RUBRIC_SCORING, self.COVER_INFO)

    @property
    def has_label_column(self) -> bool:
        """含独立标签列（col 0 为标签，不应填内容）。"""
        return self in (self.LABEL_VALUE_PAIR, self.INNOVATION_TRIPLE)


class FillIntent(str, Enum):
    """单元格级填写意图，由 table_semantic_analyzer 标注。"""

    FILL = "fill"
    LABEL = "label"
    READ_ONLY = "read_only"
    USER_INPUT = "user_input"

    @property
    def should_generate(self) -> bool:
        """是否应为该单元格调用 LLM 生成内容。"""
        return self == self.FILL

    @property
    def should_write(self) -> bool:
        """filler 是否应写入内容到该单元格。

        FILL 以外的所有意图都不应写入，避免误填标签/封面/评分表。
        """
        return self == self.FILL


# ── 封面/评分表关键词（与现有 filler._is_cover_table / _is_rating_table 对齐）───
COVER_KEYWORDS = (
    "学号", "姓名", "学院", "专业", "班级", "指导教师", "联系电话",
    "作品名称", "应用平台", "总分", "任课教师",
    "结课报告", "课程报告", "实验报告",
)

RUBRIC_KEYWORDS = (
    "评分", "评价", "打分", "得分", "总分", "等级",
    "优秀", "良好", "中等", "及格", "不及格",
)

INNOVATION_HEADERS_HINTS = ("创新", "实现", "应用", "价值", "证据")


# ── 覆盖表列宽阈值 ──────────────────────────────────────────────────────────
# LABEL_VALUE_PAIR 的判断条件：col 0 宽度 < 总宽 × LABEL_COLUMN_RATIO_THRESHOLD
LABEL_COLUMN_RATIO_THRESHOLD = 0.40
