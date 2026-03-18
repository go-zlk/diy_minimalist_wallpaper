"""Unit tests for 配方分享码 (share code encode/decode)."""
import base64
import json

import pytest


class TestShareCodeEncodeDecode:
    """Tests for preset JSON <-> Base64 share code."""

    def test_encode_decode_roundtrip(self, wallpaper_app):
        """编码后解码应得到相同结构。"""
        wallpaper_app.user_color_presets["测试"] = {
            "text_color": "#FF0000",
            "bg_color": "#00FF00",
            "bg_color2": "#0000FF",
            "gradient_mode": "线性渐变",
            "gradient_direction": "上->下",
        }
        payload = {"测试": wallpaper_app._preset_to_shareable_dict("测试", wallpaper_app.user_color_presets["测试"])}
        raw = json.dumps(payload, ensure_ascii=False)
        code = base64.b64encode(raw.encode("utf-8")).decode("ascii")
        decoded = json.loads(base64.b64decode(code.encode("ascii")).decode("utf-8"))
        assert decoded == payload

    def test_preset_to_shareable_dict(self, wallpaper_app):
        """_preset_to_shareable_dict 应规范化字段。"""
        cfg = {"text_color": "#111", "bg_color": "#222"}
        result = wallpaper_app._preset_to_shareable_dict("x", cfg)
        assert result["text_color"] == "#111"
        assert result["bg_color"] == "#222"
        assert result["bg_color2"] == "#222"
        assert result["gradient_mode"] == "纯色"
        assert result["gradient_direction"] == "上->下"
