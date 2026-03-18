"""Unit tests for utility functions and constants."""
import os
import sys

import pytest

# Import after path setup in conftest
import main


class TestGetOutputDir:
    """Tests for get_output_dir()."""

    def test_returns_path_under_project_root_when_not_frozen(self, monkeypatch):
        monkeypatch.delattr(sys, "frozen", raising=False)
        # main.py 在 platforms/desktop/，项目根为 WallpaperDIY（上两级：desktop->platforms->WallpaperDIY）
        _f = os.path.abspath(main.__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(_f)))
        expected = os.path.join(project_root, "output")
        result = main.get_output_dir()
        assert result == expected
        assert os.path.exists(result)

    @pytest.mark.skip(reason="sys.frozen cannot be set on built-in module in standard pytest")
    def test_uses_executable_dir_when_frozen(self, monkeypatch, tmp_path):
        """Frozen app uses executable dir; skipped as sys.frozen is read-only in tests."""
        monkeypatch.setattr(sys, "frozen", True)
        monkeypatch.setattr(sys, "executable", str(tmp_path / "app.exe"))
        result = main.get_output_dir()
        assert result == str(tmp_path / "output")
        assert os.path.exists(result)


class TestGetAgentScreenshotPath:
    """Tests for get_agent_screenshot_path()."""

    def test_returns_path_under_output_dir(self):
        """Agent 截图路径位于 output/ 下"""
        result = main.get_agent_screenshot_path()
        assert result.endswith(main.AGENT_UI_SCREENSHOT_PATH)
        assert main.get_output_dir() in result
        assert os.path.dirname(result) == main.get_output_dir()


class TestGetArrowPath:
    """Tests for get_arrow_path()."""

    def test_returns_path_in_temp_dir(self):
        """箭头存于系统临时目录，不污染 output/相册"""
        import tempfile
        result = main.get_arrow_path()
        assert result.endswith("arrow_down.png")
        assert tempfile.gettempdir() in result
        assert "WallpaperDIY" in result
        assert os.path.exists(result)

    def test_creates_arrow_image_if_missing(self):
        path = main.get_arrow_path()
        assert os.path.isfile(path)
        from PIL import Image
        img = Image.open(path)
        assert img.size == (16, 16)
        assert img.mode == "RGBA"


class TestConstants:
    """Tests for module constants."""

    def test_aspect_ratios_has_expected_keys(self):
        assert "16:9" in main.ASPECT_RATIOS
        assert "1:1" in main.ASPECT_RATIOS
        assert "屏幕" in main.ASPECT_RATIOS
        assert main.ASPECT_RATIOS["16:9"] == (16, 9)
        assert main.ASPECT_RATIOS["屏幕"] is None

    def test_preview_profiles_structure(self):
        for name, cfg in main.PREVIEW_PROFILES.items():
            assert "ss_small" in cfg
            assert "ss_large" in cfg
            assert "steps_small" in cfg
            assert "steps_large" in cfg

    def test_builtin_presets_have_required_keys(self):
        for name, cfg in main.BUILTIN_COLOR_PRESETS.items():
            assert "bg_color" in cfg
            assert "text_color" in cfg


class TestMaterialYouTheme:
    """Tests for Material You 动态主题：颜色提取与衍生"""

    def test_extract_dominant_color_returns_hex(self):
        """提取主色返回 #RRGGBB 格式"""
        from PIL import Image
        import tempfile
        # 纯红图
        img = Image.new("RGB", (32, 32), (255, 0, 0))
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img.save(f.name)
            try:
                result = main.extract_dominant_color(f.name)
                assert result.startswith("#")
                assert len(result) == 7
                int(result[1:3], 16)  # 可解析为 hex
            finally:
                os.unlink(f.name)

    def test_extract_dominant_color_fallback_on_invalid(self):
        """无效路径返回 Fallback 颜色"""
        result = main.extract_dominant_color("/nonexistent/path.png")
        assert result == main.THEME_FALLBACK_HEX

    def test_derive_theme_colors_returns_dict(self):
        """衍生主题返回 primary/primary_hover/primary_bg"""
        colors = main.derive_theme_colors("#4A4E69")
        assert "primary" in colors
        assert "primary_hover" in colors
        assert "primary_bg" in colors
        assert colors["primary"].startswith("#")
        assert "rgba(" in colors["primary_bg"]

    def test_rgb_hsl_roundtrip(self):
        """RGB <-> HSL 转换可逆"""
        r, g, b = 74, 78, 105
        h, s, l = main.rgb_to_hsl(r, g, b)
        r2, g2, b2 = main.hsl_to_rgb(h, s, l)
        assert abs(r - r2) <= 1 and abs(g - g2) <= 1 and abs(b - b2) <= 1
