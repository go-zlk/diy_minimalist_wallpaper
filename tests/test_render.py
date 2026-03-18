"""Unit tests for rendering logic (gradient, text metrics)."""
import pytest

from PIL import Image, ImageDraw


class TestGradientRendering:
    """Tests for _get_cached_gradient_mask and _build_gradient_background."""

    def test_gradient_mask_pure_color_returns_solid(self, wallpaper_app):
        """纯色模式应直接返回纯色图，不经过 mask。"""
        img = wallpaper_app._build_gradient_background(
            100, 100,
            (255, 0, 0), (0, 255, 0),
            "纯色", "上->下"
        )
        assert img.size == (100, 100)
        assert img.mode == "RGB"
        # 纯色应全为 bg_rgb
        px = img.getpixel((50, 50))
        assert px == (255, 0, 0)

    def test_gradient_mask_linear_vertical(self, wallpaper_app):
        """线性渐变 上->下 应产生从 bg 到 bg2 的过渡。"""
        img = wallpaper_app._build_gradient_background(
            100, 100,
            (255, 0, 0), (0, 255, 0),
            "线性渐变", "上->下"
        )
        assert img.size == (100, 100)
        top_px = img.getpixel((50, 5))
        bottom_px = img.getpixel((50, 95))
        # 上端应偏红，下端应偏绿
        assert top_px[0] > top_px[1]
        assert bottom_px[1] > bottom_px[0]

    def test_gradient_mask_cached(self, wallpaper_app):
        """同一 mode/direction 的 mask 应被缓存复用。"""
        mask1 = wallpaper_app._get_cached_gradient_mask("线性渐变", "左->右")
        mask2 = wallpaper_app._get_cached_gradient_mask("线性渐变", "左->右")
        assert mask1 is mask2
        assert mask1.size == (256, 256)
        assert mask1.mode == "L"

    def test_gradient_masks_initialized(self, wallpaper_app):
        """_gradient_masks 应在 __init__ 中初始化。"""
        assert hasattr(wallpaper_app, "_gradient_masks")
        assert isinstance(wallpaper_app._gradient_masks, dict)


class TestTextMetrics:
    """Tests for _get_text_metrics."""

    def test_text_metrics_returns_char_widths(self, wallpaper_app):
        """_get_text_metrics 应返回 char_widths 列表。"""
        draw = ImageDraw.Draw(Image.new("RGB", (100, 100)))
        font_path = "C:/Windows/Fonts/msyhbd.ttc"
        metrics = wallpaper_app._get_text_metrics(
            draw, font_path, 24, "ABC", 0
        )
        assert "char_widths" in metrics
        assert metrics["char_widths"] is not None
        assert len(metrics["char_widths"]) == 3
        assert "total_w" in metrics
        assert "bbox" in metrics

    def test_text_metrics_empty_string(self, wallpaper_app):
        """空字符串应返回空 char_widths。"""
        draw = ImageDraw.Draw(Image.new("RGB", (100, 100)))
        font_path = "C:/Windows/Fonts/msyhbd.ttc"
        metrics = wallpaper_app._get_text_metrics(
            draw, font_path, 24, "", 0
        )
        assert metrics["char_widths"] == []
        assert metrics["total_w"] == 0 or metrics["total_w"] >= 0
