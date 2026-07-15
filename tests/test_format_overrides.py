"""Tests for core.format_overrides — FormatOverrides model & build_overrides_from_api."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.format_overrides import FormatOverrides, build_overrides_from_api


# ---------------------------------------------------------------------------
# TestFormatOverridesValidation
# ---------------------------------------------------------------------------
class TestFormatOverridesValidation:
    """Boundary / constraint tests on every field."""

    def test_valid_full_construction(self):
        obj = FormatOverrides(
            body_font_ascii="Times New Roman",
            body_font_east_asia="宋体",
            body_size_pt=14.0,
            body_bold=True,
            heading_size_delta_pt=2.0,
            line_spacing=1.5,
            first_line_indent_pt=24.0,
        )
        dumped = obj.model_dump()
        assert dumped == {
            "body_font_ascii": "Times New Roman",
            "body_font_east_asia": "宋体",
            "body_size_pt": 14.0,
            "body_bold": True,
            "heading_size_delta_pt": 2.0,
            "line_spacing": 1.5,
            "first_line_indent_pt": 24.0,
        }

    def test_valid_partial_construction(self):
        obj = FormatOverrides(body_size_pt=12.0, body_bold=False)
        assert obj.body_size_pt == 12.0
        assert obj.body_bold is False
        assert obj.body_font_ascii is None
        assert obj.body_font_east_asia is None
        assert obj.heading_size_delta_pt is None
        assert obj.line_spacing is None
        assert obj.first_line_indent_pt is None

    def test_empty_construction(self):
        obj = FormatOverrides()
        for field_name in FormatOverrides.model_fields:
            assert getattr(obj, field_name) is None

    # -- body_size_pt boundaries (8.0 – 24.0) ---------------------------------

    def test_body_size_pt_lower_bound(self):
        with pytest.raises(ValidationError):
            FormatOverrides(body_size_pt=7.9)

    def test_body_size_pt_upper_bound(self):
        with pytest.raises(ValidationError):
            FormatOverrides(body_size_pt=24.1)

    def test_body_size_pt_boundary_values(self):
        lo = FormatOverrides(body_size_pt=8.0)
        hi = FormatOverrides(body_size_pt=24.0)
        assert lo.body_size_pt == 8.0
        assert hi.body_size_pt == 24.0

    # -- heading_size_delta_pt boundaries (-4.0 ~ +4.0) -----------------------

    def test_heading_size_delta_bounds(self):
        with pytest.raises(ValidationError):
            FormatOverrides(heading_size_delta_pt=-5.0)
        with pytest.raises(ValidationError):
            FormatOverrides(heading_size_delta_pt=4.1)

    # -- line_spacing boundaries (1.0 ~ 2.5) ----------------------------------

    def test_line_spacing_bounds(self):
        with pytest.raises(ValidationError):
            FormatOverrides(line_spacing=0.9)
        with pytest.raises(ValidationError):
            FormatOverrides(line_spacing=2.6)

    # -- first_line_indent_pt boundaries (0.0 ~ 48.0) -------------------------

    def test_first_line_indent_bounds(self):
        with pytest.raises(ValidationError):
            FormatOverrides(first_line_indent_pt=-1.0)
        with pytest.raises(ValidationError):
            FormatOverrides(first_line_indent_pt=49.0)

    # -- extra="forbid" -------------------------------------------------------

    def test_unknown_field_rejected(self):
        with pytest.raises(ValidationError) as exc_info:
            FormatOverrides(unknown="x")  # type: ignore[call-arg]
        assert "extra_forbidden" in str(exc_info.value) or "unknown" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# TestFormatOverridesFonts
# ---------------------------------------------------------------------------
class TestFormatOverridesFonts:
    """Font validator tests (allowlist + CJK fallback + length cap)."""

    @pytest.mark.parametrize("font", [
        "宋体", "黑体", "楷体", "仿宋", "微软雅黑", "华文中宋",
    ])
    def test_valid_east_asia_fonts(self, font):
        obj = FormatOverrides(body_font_east_asia=font)
        assert obj.body_font_east_asia == font

    def test_arbitrary_chinese_font_accepted(self):
        """Non-allowlisted name containing CJK chars → accepted (fallback)."""
        obj = FormatOverrides(body_font_east_asia="华文中宋加自定义")
        assert obj.body_font_east_asia == "华文中宋加自定义"

    def test_non_chinese_invalid_font(self):
        with pytest.raises(ValidationError):
            FormatOverrides(body_font_east_asia="Comic Sans MS")

    @pytest.mark.parametrize("font", ["Times New Roman", "Arial", "Calibri"])
    def test_valid_ascii_fonts(self, font):
        obj = FormatOverrides(body_font_ascii=font)
        assert obj.body_font_ascii == font

    def test_font_too_long(self):
        long_name = "A" * 33
        with pytest.raises(ValidationError, match="过长"):
            FormatOverrides(body_font_ascii=long_name)
        with pytest.raises(ValidationError, match="过长"):
            FormatOverrides(body_font_east_asia="宋" * 33)


# ---------------------------------------------------------------------------
# TestFormatOverridesSerialization
# ---------------------------------------------------------------------------
class TestFormatOverridesSerialization:
    """to_merge_dict() behavior."""

    def test_to_merge_dict_excludes_none(self):
        obj = FormatOverrides(body_size_pt=14.0)
        d = obj.to_merge_dict()
        assert d == {"body_size_pt": 14.0}

    def test_to_merge_dict_complete(self):
        obj = FormatOverrides(
            body_font_ascii="Arial",
            body_font_east_asia="黑体",
            body_size_pt=12.0,
            body_bold=True,
            heading_size_delta_pt=1.0,
            line_spacing=1.5,
            first_line_indent_pt=24.0,
        )
        d = obj.to_merge_dict()
        assert len(d) == 7
        assert d["body_font_ascii"] == "Arial"
        assert d["body_font_east_asia"] == "黑体"
        assert d["body_size_pt"] == 12.0
        assert d["body_bold"] is True
        assert d["heading_size_delta_pt"] == 1.0
        assert d["line_spacing"] == 1.5
        assert d["first_line_indent_pt"] == 24.0

    def test_empty_to_merge_dict(self):
        obj = FormatOverrides()
        assert obj.to_merge_dict() == {}


# ---------------------------------------------------------------------------
# TestBuildOverridesFromApi
# ---------------------------------------------------------------------------
class TestBuildOverridesFromApi:
    """build_overrides_from_api() helper."""

    def test_empty_payload(self):
        obj = build_overrides_from_api({})
        assert obj == FormatOverrides()
        for field_name in FormatOverrides.model_fields:
            assert getattr(obj, field_name) is None

    def test_filters_none_values(self):
        obj = build_overrides_from_api({"body_size_pt": None, "line_spacing": 1.5})
        assert obj.body_size_pt is None
        assert obj.line_spacing == 1.5

    def test_valid_api_payload(self):
        obj = build_overrides_from_api({
            "body_font_east_asia": "楷体",
            "body_size_pt": 14.0,
        })
        assert obj.body_font_east_asia == "楷体"
        assert obj.body_size_pt == 14.0

    def test_invalid_api_payload_raises(self):
        with pytest.raises(ValidationError):
            build_overrides_from_api({"body_size_pt": 5.0})
