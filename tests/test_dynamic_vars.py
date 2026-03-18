"""Unit tests for dynamic variable processing (_process_dynamic_variables)."""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest


class TestProcessDynamicVariables:
    """Tests for _process_dynamic_variables."""

    def test_empty_string_returns_empty(self, wallpaper_app):
        assert wallpaper_app._process_dynamic_variables("") == ""
        assert wallpaper_app._process_dynamic_variables(None) is None

    def test_time_replacement(self, wallpaper_app):
        import main
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2025, 3, 15, 14, 30)
        mock_dt.strptime = datetime.strptime
        with patch("main.datetime", mock_dt):
            result = wallpaper_app._process_dynamic_variables("现在 [TIME]")
            assert "[TIME]" not in result
            assert "14:30" in result

    def test_date_replacement(self, wallpaper_app):
        import main
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2025, 3, 15)
        mock_dt.strptime = datetime.strptime
        with patch("main.datetime", mock_dt):
            result = wallpaper_app._process_dynamic_variables("今天 [DATE]")
            assert "[DATE]" not in result
            assert "2025-03-15" in result

    def test_countdown_replacement(self, wallpaper_app):
        import main
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2025, 3, 15)
        mock_dt.strptime = datetime.strptime
        with patch("main.datetime", mock_dt):
            result = wallpaper_app._process_dynamic_variables("[COUNTDOWN:2025-03-20] 天")
            assert "[COUNTDOWN:" not in result
            assert "5" in result

    def test_countdown_past_returns_zero(self, wallpaper_app):
        import main
        mock_dt = MagicMock()
        mock_dt.now.return_value = datetime(2025, 3, 15)
        mock_dt.strptime = datetime.strptime
        with patch("main.datetime", mock_dt):
            result = wallpaper_app._process_dynamic_variables("[COUNTDOWN:2025-03-10]")
            assert "0" in result


class TestFontFallback:
    """Tests for _use_fallback_font and _need_cjk_fallback."""

    def test_use_fallback_font_symbol_fonts(self, wallpaper_app):
        assert wallpaper_app._use_fallback_font("Wingdings") is True
        assert wallpaper_app._use_fallback_font("Webdings") is True
        assert wallpaper_app._use_fallback_font("Symbol") is True
        assert wallpaper_app._use_fallback_font("Microsoft YaHei") is False

    def test_need_cjk_fallback_empty_text(self, wallpaper_app):
        """Empty or None text should return falsy (no CJK fallback needed)."""
        assert not wallpaper_app._need_cjk_fallback("Arial", "")
        assert not wallpaper_app._need_cjk_fallback("Arial", None)
