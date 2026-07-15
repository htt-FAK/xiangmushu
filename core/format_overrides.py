"""用户格式偏好校验模型（Pydantic v2）。

定义 `FormatOverrides` 数据模型，供 `/api/generate` 使用，校验用户输入
的字体/字号/行距等覆盖项，并传递给 `TemplateStyleProfile.merge_user_overrides()`。

字段：
    body_font_ascii:        正文西文字体（英文/数字）
    body_font_east_asia:    正文东亚字体（中文字符）
    body_size_pt:           正文字号 (pt)，范围 8.0–24.0
    body_bold:              正文是否粗体
    heading_size_delta_pt:  标题字号相对正文的增减 (-4.0 ~ +4.0)
    line_spacing:           行距倍数 (1.0 ~ 2.5)
    first_line_indent_pt:   正文首行缩进 (pt)，范围 0.0–48.0

所有字段均为 Optional，未传时 template_style_extractor 提取的模板原始值生效。
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, field_validator


_BODY_FONTS_ASCII = frozenset({
    "Times New Roman", "Arial", "Calibri", "Helvetica", "Georgia",
    "SimSun", "NSimSun", "DengXian",
})
_BODY_FONTS_EAST_ASIA = frozenset({
    "宋体", "NSimSun",
    "黑体", "SimHei",
    "楷体", "KaiTi",
    "仿宋", "FangSong",
    "仿宋_GB2312",
    "微软雅黑", "Microsoft YaHei",
    "华文宋体",
    "华文楷体",
    "华文中宋",
})


class FormatOverrides(BaseModel):
    """用户侧格式偏好，可选字段。"""

    body_font_ascii: Optional[str] = Field(
        default=None,
        description="正文西文字体（如 'Times New Roman'、'Arial'）",
    )
    body_font_east_asia: Optional[str] = Field(
        default=None,
        description="正文东亚字体（如 '宋体'、'黑体'、'楷体'、'仿宋'）",
    )
    body_size_pt: Optional[float] = Field(
        default=None,
        ge=8.0,
        le=24.0,
        description="正文字号 (pt)，范围 8.0–24.0，步进 0.5",
    )
    body_bold: Optional[bool] = Field(
        default=None,
        description="正文是否粗体，默认 False",
    )
    heading_size_delta_pt: Optional[float] = Field(
        default=None,
        ge=-4.0,
        le=4.0,
        description="标题字号相对正文的增减 (pt)，范围 -4.0 ~ +4.0",
    )
    line_spacing: Optional[float] = Field(
        default=None,
        ge=1.0,
        le=2.5,
        description="行距倍数 (1.0 ~ 2.5)，常用 1.0 / 1.5",
    )
    first_line_indent_pt: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=48.0,
        description="正文首行缩进 (pt)，范围 0.0–48.0",
    )

    model_config = {"extra": "forbid"}  # 拒绝未声明字段

    @field_validator("body_font_ascii")
    @classmethod
    def _validate_font_ascii(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        # 仅允许常见 ASCII 字体名 + 自定义标识（长度限制）
        if len(v) > 32:
            raise ValueError("body_font_ascii 过长（最多 32 字符）")
        if v not in _BODY_FONTS_ASCII and not v.replace(" ", "").isalpha():
            raise ValueError(
                f"不支持的西文字体：{v!r}。常见字体：Times New Roman/Arial/Calibri"
            )
        return v

    @field_validator("body_font_east_asia")
    @classmethod
    def _validate_font_east_asia(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        v = v.strip()
        if not v:
            return None
        if len(v) > 32:
            raise ValueError("body_font_east_asia 过长（最多 32 字符）")
        # 常见中文字体或在已知集合中
        if v not in _BODY_FONTS_EAST_ASIA:
            # 允许任意汉字字体名（Word 会 fallback 到默认字体）
            if any("\u4e00" <= c <= "\u9fff" for c in v):
                return v
            raise ValueError(
                f"不支持的东亚字体：{v!r}。常见字体：宋体/黑体/楷体/仿宋/微软雅黑"
            )
        return v

    def to_merge_dict(self) -> dict:
        """转为 `TemplateStyleProfile.merge_user_overrides()` 所需的 dict。"""
        data = self.model_dump(exclude_none=True)
        return data


def build_overrides_from_api(payload: dict) -> FormatOverrides:
    """从 API 请求 dict 构造 FormatOverrides，过滤非空字段。"""
    if not payload:
        return FormatOverrides()
    # 只保留非 None 字段
    cleaned = {k: v for k, v in payload.items() if v is not None}
    return FormatOverrides(**cleaned)
