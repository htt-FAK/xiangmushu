"""模板样式档案数据模型。

定义 `RunStyle` 和 `TemplateStyleProfile`，用于替代 `docx_typography.py` 中的硬编码
宋体/字号规格，改为从模板动态提取并保留原始设计。

三级样式优先级：user_overrides > TemplateStyleProfile > SystemDefaults
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

_LOG = logging.getLogger(__name__)

# ── System Defaults（兜底线，与原 docx_typography 硬编码对齐）──────────
DEFAULT_FONT_ASCII = "SimSun"
DEFAULT_FONT_EAST_ASIA = "宋体"
DEFAULT_BODY_SIZE_PT = 12.0      # 小四
DEFAULT_H1_SIZE_PT = 15.0        # 小三
DEFAULT_H2_SIZE_PT = 14.0        # 四号
DEFAULT_H3_SIZE_PT = 12.0        # 小四
DEFAULT_LINE_SPACING = 1.0
DEFAULT_FIRST_LINE_INDENT_PT = 24.0


@dataclass(frozen=True)
class RunStyle:
    """单个 run 的字体规格快照。

    任何字段为 None 时表示"未显式设置，需从继承链或默认值解析"。
    """
    font_ascii: str = DEFAULT_FONT_ASCII
    font_east_asia: str = DEFAULT_FONT_EAST_ASIA
    size_pt: float = DEFAULT_BODY_SIZE_PT
    bold: Optional[bool] = False
    italic: Optional[bool] = False
    color_rgb: Optional[str] = None  # 6位十六进制，如 "000000"

    def half_point_size(self) -> int:
        """返回 w:sz 半磅值（pt × 2），供 XML 直接写入。"""
        return int(round(self.size_pt * 2))

    def merge(self, override: RunStyle | None) -> RunStyle:
        """返回一个新 RunStyle：本对象为基础，override 中非 None 字段覆盖。"""
        if override is None:
            return self
        return RunStyle(
            font_ascii=override.font_ascii or self.font_ascii,
            font_east_asia=override.font_east_asia or self.font_east_asia,
            size_pt=override.size_pt if override.size_pt > 0 else self.size_pt,
            bold=override.bold if override.bold is not None else self.bold,
            italic=override.italic if override.italic is not None else self.italic,
            color_rgb=override.color_rgb if override.color_rgb is not None else self.color_rgb,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any] | None) -> RunStyle:
        if not d:
            return cls()
        return cls(
            font_ascii=str(d.get("font_ascii") or DEFAULT_FONT_ASCII),
            font_east_asia=str(d.get("font_east_asia") or DEFAULT_FONT_EAST_ASIA),
            size_pt=float(d.get("size_pt") or DEFAULT_BODY_SIZE_PT),
            bold=d.get("bold"),
            italic=d.get("italic"),
            color_rgb=d.get("color_rgb"),
        )


@dataclass
class TemplateStyleProfile:
    """从 .docx 模板提取的完整样式档案。

    设计原则：
    - 所有字段均使用 RunStyle，保证样式表达统一
    - heading_styles 以 int level (1-3) 为 key
    - column_widths 以 table_index 为 key，值为 dxa 列表
    - 缓存友好：to_json / from_json 双向无损
    """
    # 正文默认样式
    body_style: RunStyle = field(default_factory=RunStyle)

    # 标题样式：{1: RunStyle(黑体 15pt bold), 2: ..., 3: ...}
    heading_styles: dict[int, RunStyle] = field(default_factory=dict)

    # 表格单元格默认样式（内容列使用）
    table_cell_style: RunStyle = field(default_factory=RunStyle)

    # 表格标签列样式（LABEL_VALUE_PAIR 表格的 col 0）
    table_label_style: RunStyle = field(default_factory=RunStyle)

    # 每张表各列原始宽度（dxa），{table_index: [col0_dxa, col1_dxa, ...]}
    column_widths: dict[int, list[int]] = field(default_factory=dict)

    # 行距倍数（1.0 / 1.25 / 1.5 / 2.0）
    line_spacing: float = DEFAULT_LINE_SPACING

    # 正文首行缩进（pt）
    first_line_indent_pt: float = DEFAULT_FIRST_LINE_INDENT_PT

    # 是否保护封面段落（检测到封面关键词时跳过样式应用）
    cover_protected: bool = True

    # 提取来源信息（便于调试）
    source_template: str = ""
    extracted_at: str = ""

    def heading_style_for_level(self, level: int) -> RunStyle:
        """返回指定层级的标题 RunStyle；未提取到时回退为 body_style。"""
        return self.heading_styles.get(level, self.body_style)

    def column_widths_for_table(self, table_index: int) -> list[int]:
        """返回指定表格的列宽列表；未提取到时返回空列表。"""
        return self.column_widths.get(table_index, [])

    def to_json(self) -> str:
        """序列化为 JSON 字符串，用于磁盘缓存。"""
        payload = {
            "body_style": self.body_style.to_dict(),
            "heading_styles": {
                str(k): v.to_dict() for k, v in self.heading_styles.items()
            },
            "table_cell_style": self.table_cell_style.to_dict(),
            "table_label_style": self.table_label_style.to_dict(),
            "column_widths": {str(k): v for k, v in self.column_widths.items()},
            "line_spacing": self.line_spacing,
            "first_line_indent_pt": self.first_line_indent_pt,
            "cover_protected": self.cover_protected,
            "source_template": self.source_template,
            "extracted_at": self.extracted_at,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, raw: str) -> TemplateStyleProfile:
        """从 JSON 字符串反序列化。"""
        d = json.loads(raw)
        heading_styles = {
            int(k): RunStyle.from_dict(v)
            for k, v in (d.get("heading_styles") or {}).items()
        }
        column_widths = {
            int(k): list(v)
            for k, v in (d.get("column_widths") or {}).items()
        }
        return cls(
            body_style=RunStyle.from_dict(d.get("body_style")),
            heading_styles=heading_styles,
            table_cell_style=RunStyle.from_dict(d.get("table_cell_style")),
            table_label_style=RunStyle.from_dict(d.get("table_label_style")),
            column_widths=column_widths,
            line_spacing=float(d.get("line_spacing") or DEFAULT_LINE_SPACING),
            first_line_indent_pt=float(d.get("first_line_indent_pt") or DEFAULT_FIRST_LINE_INDENT_PT),
            cover_protected=bool(d.get("cover_protected", True)),
            source_template=str(d.get("source_template") or ""),
            extracted_at=str(d.get("extracted_at") or ""),
        )

    def merge_user_overrides(self, overrides: dict[str, Any] | None) -> TemplateStyleProfile:
        """三级合并：用户覆盖 > 本 profile > system defaults。

        overrides 支持的字段（见 format_overrides.py）：
        - body_font_ascii, body_font_east_asia, body_size_pt, body_bold
        - heading_size_delta_pt（所有层级标题同步加减）
        - line_spacing, first_line_indent_pt

        返回新对象，不修改 self。
        """
        if not overrides:
            return self

        from copy import deepcopy
        new = deepcopy(self)

        # 正文样式覆盖
        body_override = RunStyle(
            font_ascii=str(overrides.get("body_font_ascii") or ""),
            font_east_asia=str(overrides.get("body_font_east_asia") or ""),
            size_pt=float(overrides.get("body_size_pt") or 0),
            bold=overrides.get("body_bold"),
        )
        new.body_style = new.body_style.merge(body_override)

        # 标题 delta（同步加减所有层级）
        delta = float(overrides.get("heading_size_delta_pt") or 0)
        if delta != 0:
            new.heading_styles = {
                lvl: RunStyle(
                    font_ascii=rs.font_ascii,
                    font_east_asia=rs.font_east_asia,
                    size_pt=max(8.0, min(24.0, rs.size_pt + delta)),
                    bold=rs.bold,
                    italic=rs.italic,
                    color_rgb=rs.color_rgb,
                )
                for lvl, rs in self.heading_styles.items()
            }

        # 行距/缩进覆盖
        if overrides.get("line_spacing") is not None:
            new.line_spacing = float(overrides["line_spacing"])
        if overrides.get("first_line_indent_pt") is not None:
            new.first_line_indent_pt = float(overrides["first_line_indent_pt"])

        return new


# ── System Defaults Profile（兜底，与旧 docx_typography 行为对齐）─────
_SYSTEM_DEFAULTS_PROFILE: Optional[TemplateStyleProfile] = None


def system_default_profile() -> TemplateStyleProfile:
    """返回与原 docx_typography.py 硬编码完全等价的 TemplateStyleProfile。

    当 APPLY_TEMPLATE_STYLE=False 或模板提取失败时使用此 profile，
    保证行为向后兼容。
    """
    global _SYSTEM_DEFAULTS_PROFILE
    if _SYSTEM_DEFAULTS_PROFILE is None:
        h1 = RunStyle(font_ascii=DEFAULT_FONT_ASCII, font_east_asia=DEFAULT_FONT_EAST_ASIA,
                       size_pt=DEFAULT_H1_SIZE_PT, bold=True)
        h2 = RunStyle(font_ascii=DEFAULT_FONT_ASCII, font_east_asia=DEFAULT_FONT_EAST_ASIA,
                       size_pt=DEFAULT_H2_SIZE_PT, bold=True)
        h3 = RunStyle(font_ascii=DEFAULT_FONT_ASCII, font_east_asia=DEFAULT_FONT_EAST_ASIA,
                       size_pt=DEFAULT_H3_SIZE_PT, bold=True)
        _SYSTEM_DEFAULTS_PROFILE = TemplateStyleProfile(
            body_style=RunStyle(),
            heading_styles={1: h1, 2: h2, 3: h3},
            table_cell_style=RunStyle(),
            table_label_style=RunStyle(bold=True),
            column_widths={},
            line_spacing=DEFAULT_LINE_SPACING,
            first_line_indent_pt=DEFAULT_FIRST_LINE_INDENT_PT,
            source_template="<system-defaults>",
        )
    return _SYSTEM_DEFAULTS_PROFILE
