import sys
import os
import base64
import ctypes
import subprocess
import math
import threading
import time
import json
import traceback
import urllib.request
import re
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPlainTextEdit, QLineEdit, QPushButton, QLabel, QComboBox, QSlider,
                             QFrame, QCheckBox, QScrollArea, QFileDialog, QMenu, QInputDialog,
                             QDialog, QMessageBox, QGridLayout, QButtonGroup)
from PyQt6.QtGui import (QPixmap, QImage, QColor, QPainter, QConicalGradient,
                         QLinearGradient, QBrush, QPen, QPainterPath, QMouseEvent)
from PyQt6.QtCore import (Qt, QPointF, pyqtSignal, QTimer, QRectF,
                          QObject, QRunnable, QThreadPool, QVariantAnimation, QEasingCurve, QEvent)
from datetime import datetime

# 项目根目录（main.py 在 platforms/desktop/ 下，上两级为根）
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_SCRIPT_DIR)) if not getattr(sys, "frozen", False) else None
OUTPUT_DIR = "output"
# Agent 自动化截图保存路径（供 Cursor/Agent 直接读取当前 UI 状态）
AGENT_UI_SCREENSHOT_PATH = "agent_ui_screenshot.png"

def get_output_dir():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = _PROJECT_ROOT or _SCRIPT_DIR
    out = os.path.join(base, OUTPUT_DIR)
    if not os.path.exists(out):
        os.makedirs(out)
    return out

def get_agent_screenshot_path():
    """返回 Agent 自动化截图的完整路径，存于 output/ 下。"""
    return os.path.join(get_output_dir(), AGENT_UI_SCREENSHOT_PATH)


def get_arrow_path():
    """返回下拉箭头图片路径，存于系统临时目录（非 output），不污染相册"""
    import tempfile
    cache_dir = os.path.join(tempfile.gettempdir(), "WallpaperDIY")
    os.makedirs(cache_dir, exist_ok=True)
    path = os.path.join(cache_dir, "arrow_down.png")
    if not os.path.exists(path):
        try:
            img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            draw = ImageDraw.Draw(img)
            draw.polygon([(2, 5), (8, 12), (14, 5)], fill=(160, 160, 160, 255))
            img.save(path)
        except Exception:
            pass
    return path


# --- Material You 动态主题：图片主色提取与色彩衍生 ---
# Fallback 颜色：提取失败或未导入背景图时使用
THEME_FALLBACK_HEX = "#4A4E69"


def rgb_to_hsl(r, g, b):
    """RGB [0-255] -> HSL [H:0-360, S:0-1, L:0-1]"""
    r, g, b = r / 255.0, g / 255.0, b / 255.0
    mx = max(r, g, b)
    mn = min(r, g, b)
    l = (mx + mn) / 2.0
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    h /= 6.0
    return h * 360, s, l


def hsl_to_rgb(h, s, l):
    """HSL -> RGB [0-255]"""
    h = (h % 360) / 360.0
    if s == 0:
        r = g = b = l
    else:
        def hue2rgb(p, q, t):
            if t < 0:
                t += 1
            if t > 1:
                t -= 1
            if t < 1/6:
                return p + (q - p) * 6 * t
            if t < 1/2:
                return q
            if t < 2/3:
                return p + (q - p) * (2/3 - t) * 6
            return p
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r = hue2rgb(p, q, h + 1/3)
        g = hue2rgb(p, q, h)
        b = hue2rgb(p, q, h - 1/3)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


def hex_to_rgb(hex_str):
    """#RRGGBB -> (r, g, b)"""
    if hex_str is None:
        return (74, 78, 105)
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 6:
        return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))
    return (74, 78, 105)  # THEME_FALLBACK_HEX


def rgb_to_hex(r, g, b):
    """(r, g, b) -> #RRGGBB"""
    return "#%02X%02X%02X" % (max(0, min(255, r)), max(0, min(255, g)), max(0, min(255, b)))


def extract_dominant_color(image_src):
    """
    从图片中提取主色调（Material You 风格）。
    - image_src: 本地文件路径或 PIL.Image 对象
    - 返回: Hex 字符串如 "#4A4E69"，失败时返回 THEME_FALLBACK_HEX
    - 使用缩小采样 + 简单聚类取众数，避免引入第三方库
    """
    try:
        if isinstance(image_src, str):
            img = Image.open(image_src).convert("RGB")
        else:
            img = image_src.convert("RGB") if hasattr(image_src, "convert") else None
        if img is None:
            return THEME_FALLBACK_HEX
        # 缩小到 64x64 加速处理
        img = img.resize((64, 64), Image.Resampling.LANCZOS)
        pixels = list(img.getdata())
        # 量化到 32 级，减少色阶
        buckets = {}
        for r, g, b in pixels:
            q = (r // 8, g // 8, b // 8)
            buckets[q] = buckets.get(q, 0) + 1
        # 取出现次数最多的色块，转回中心色
        best = max(buckets.items(), key=lambda x: x[1])[0]
        r, g, b = best[0] * 8 + 4, best[1] * 8 + 4, best[2] * 8 + 4
        return rgb_to_hex(r, g, b)
    except Exception:
        return THEME_FALLBACK_HEX


def derive_theme_colors(primary_hex):
    """
    从主色衍生 Material You 风格的主题色。
    - primary_hex: 主色 Hex
    - 返回: dict { primary, primary_hover, primary_bg }
    """
    if primary_hex is None:
        primary_hex = THEME_FALLBACK_HEX
    r, g, b = hex_to_rgb(primary_hex)
    h, s, l = rgb_to_hsl(r, g, b)
    # primary: 保持色相，略微提高亮度便于在深色背景上显示
    l_adj = min(0.55, l + 0.15) if l < 0.4 else l
    primary = rgb_to_hex(*hsl_to_rgb(h, s, l_adj))
    # primary_hover: 提高亮度作为悬浮态
    l_hover = min(0.75, l_adj + 0.12)
    primary_hover = rgb_to_hex(*hsl_to_rgb(h, s * 0.9, l_hover))
    # primary_bg: 低透明度背景，用于 Tab 选中等
    r2, g2, b2 = hsl_to_rgb(h, s * 0.6, min(0.5, l_adj + 0.1))
    primary_bg = "rgba(%d,%d,%d,0.18)" % (r2, g2, b2)
    return {"primary": primary, "primary_hover": primary_hover, "primary_bg": primary_bg}

# 壁纸比例 (宽:高)，None 表示使用屏幕实际尺寸
ASPECT_RATIOS = {
    "21:9": (21, 9), "16:9": (16, 9), "16:10": (16, 10),
    "4:3": (4, 3), "3:4": (3, 4), "3:2": (3, 2), "2:3": (2, 3),
    "1:1": (1, 1),
    "9:16": (9, 16), "9:21": (9, 21),
    "屏幕": None,
}

PREVIEW_PROFILES = {
    "速度优先": {"ss_small": 1, "ss_large": 1, "steps_small": 4, "steps_large": 6},
    "平衡": {"ss_small": 1, "ss_large": 2, "steps_small": 6, "steps_large": 8},
    "所见即所得": {"ss_small": 2, "ss_large": 2, "steps_small": 8, "steps_large": 10},
}

# 预设文案（供下拉选择，避免与字体下拉混淆）
PRESET_TEXTS = [
    "INFINITE PROGRESS",
    "今日事今日毕",
    "FOCUS",
    "DO IT NOW",
    "自定义",
]

BUILTIN_COLOR_PRESETS = {
    "苹果灰阶": {
        "bg_color": "#F7F7F8", "bg_color2": "#EDEDF0", "gradient_mode": "线性渐变", "gradient_direction": "上->下",
        "text_color": "#212122", "stack": False
    },
    "极夜霓虹": {"bg_color": "#0D0D12", "text_color": "#64FFDA", "stack": True},
    "浅色蓝调": {
        "bg_color": "#EEF2FF", "bg_color2": "#DDE7FF", "gradient_mode": "径向渐变", "gradient_direction": "左上->右下",
        "text_color": "#1E2A8A", "stack": True, "shadow": 80
    },
}


class NoWheelComboBox(QComboBox):
    """禁用滚轮切换选项，避免误触"""
    def wheelEvent(self, event):
        event.ignore()


class NoWheelSlider(QSlider):
    """禁用滚轮调节，避免误触"""
    def wheelEvent(self, event):
        event.ignore()


# --- iOS 风格分段控制器（胶囊容器 + 平滑滑动块）---
class SegmentedControl(QWidget):
    """类似 iOS 的 Segmented Control：胶囊容器、凹陷质感、滑动块位移动画。"""
    currentIndexChanged = pyqtSignal(int)

    def __init__(self, options, parent=None):
        super().__init__(parent)
        self._options = list(options)
        self._index = 0
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)

        self.setFixedHeight(36)
        self.setMinimumWidth(120)

        # 胶囊容器：极暗灰 + 内阴影凹陷感
        self._container = QFrame(self)
        self._container.setStyleSheet("""
            QFrame {
                background: #1C1C1E;
                border-radius: 18px;
                border: none;
            }
        """)
        self._container.raise_()

        # 滑动块：浮在凹槽内，浅灰 + 轻微外阴影
        self._indicator = QFrame(self)
        self._indicator.setStyleSheet("""
            QFrame {
                background: #2C2C2E;
                border-radius: 14px;
                border: none;
            }
        """)
        self._indicator.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        # 选项按钮（透明背景，文字居中）
        self._btn_group = QButtonGroup(self)
        self._buttons = []
        _btn_style = (
            "QPushButton { background: transparent; color: #9CA3AF; font-size: 12px; "
            "font-weight: 500; border: none; border-radius: 14px; } "
            "QPushButton:hover { color: #D1D5DB; } "
            "QPushButton:checked { color: #FFFFFF; }"
        )
        for i, opt in enumerate(self._options):
            btn = QPushButton(opt)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setStyleSheet(_btn_style)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._on_segment_clicked(idx))
            self._btn_group.addButton(btn)
            self._buttons.append(btn)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(4, 4, 4, 4)
        self._layout.setSpacing(0)
        for btn in self._buttons:
            self._layout.addWidget(btn, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._container.setGeometry(self.rect())
        self._update_indicator_geometry(animate=False)

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, lambda: self._update_indicator_geometry(animate=False))

    def _update_indicator_geometry(self, animate=True):
        if not self._buttons:
            return
        n = len(self._buttons)
        seg_w = (self.width() - 8) / n
        ind_w = max(20, seg_w - 4)
        gap = (seg_w - ind_w) / 2
        target_x = 4 + self._index * seg_w + gap

        if animate and self._indicator.x() != target_x:
            self._anim.stop()
            self._anim.setStartValue(float(self._indicator.x()))
            self._anim.setEndValue(target_x)
            self._anim.start()
        else:
            self._indicator.setGeometry(
                int(target_x), 4,
                int(ind_w), self.height() - 8
            )

    def _on_anim_value(self, value):
        seg_w = (self.width() - 8) / max(1, len(self._buttons))
        ind_w = max(20, seg_w - 4)
        self._indicator.setGeometry(
            int(value), 4,
            int(ind_w), self.height() - 8
        )

    def _on_segment_clicked(self, idx):
        if idx == self._index:
            return
        self._index = idx
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == idx)
            btn.blockSignals(False)
        self._update_indicator_geometry(animate=True)
        self.currentIndexChanged.emit(idx)

    def currentIndex(self):
        return self._index

    def setCurrentIndex(self, idx):
        if idx == self._index or idx < 0 or idx >= len(self._buttons):
            return
        self._index = idx
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == idx)
            btn.blockSignals(False)
        self._update_indicator_geometry(animate=True)
        self.currentIndexChanged.emit(idx)


# --- 现代调色盘组件（超大圆角 SV + 呼吸感双环手柄）---
class ColorWheelPicker(QWidget):
    colorChanged = pyqtSignal(QColor)
    interactionChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self.hue = 0.0  # 0.0 - 1.0 (Red)
        self.sat = 1.0
        self.val = 1.0
        self.update_color()

    def update_color(self):
        self.current_color = QColor.fromHsvF(self.hue, self.sat, self.val)

    def set_color_externally(self, color):
        h = color.hueF()
        self.hue = h if h >= 0 else 0
        self.sat = color.saturationF()
        self.val = color.valueF()
        self.update_color()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        rect = self.rect()
        center = QPointF(rect.center())
        radius = rect.width() / 2 - 12
        inner_radius = radius - 18

        # 1. 绘制色相环
        grad = QConicalGradient(center, 0.0)
        for i in range(361):
            grad.setColorAt(i / 360.0, QColor.fromHsvF(i / 360.0, 1.0, 1.0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius, radius)

        painter.setBrush(QBrush(QColor("#1A1A1A")))
        painter.drawEllipse(center, inner_radius, inner_radius)

        # 2. 绘制中间 S/V 超大圆角矩形（圆角半径 = 宽度的 25%-30%）
        box_size = int(inner_radius * 1.2)
        bx, by = center.x() - box_size / 2, center.y() - box_size / 2
        corner_radius = box_size * 0.28  # 约 28%

        path = QPainterPath()
        path.addRoundedRect(QRectF(bx, by, box_size, box_size),
                           corner_radius, corner_radius)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setClipPath(path)

        pad = 8
        h_grad = QLinearGradient(bx - pad, 0, bx + box_size + pad, 0)
        h_grad.setColorAt(0, Qt.GlobalColor.white)
        h_grad.setColorAt(1, QColor.fromHsvF(self.hue, 1.0, 1.0))
        v_grad = QLinearGradient(0, by - pad, 0, by + box_size + pad)
        v_grad.setColorAt(0, QColor(0, 0, 0, 0))
        v_grad.setColorAt(1, Qt.GlobalColor.black)

        painter.fillRect(int(bx) - pad, int(by) - pad,
                         box_size + pad * 2, box_size + pad * 2, h_grad)
        painter.fillRect(int(bx) - pad, int(by) - pad,
                         box_size + pad * 2, box_size + pad * 2, v_grad)

        painter.setClipping(False)
        painter.setPen(QPen(QColor("#1A1A1A"), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        # 3. 色相环手柄：呼吸感双环（外环白空心+发光，内环实心当前色）
        angle_rad = self.hue * 2 * math.pi
        hx = center.x() + (radius - 9) * math.cos(angle_rad)
        hy = center.y() - (radius - 9) * math.sin(angle_rad)
        handle_pos = QPointF(hx, hy)

        for r in range(12, 4, -2):
            glow_color = QColor(255, 255, 255, 25 - r)
            painter.setPen(QPen(glow_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(handle_pos, r, r)
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(handle_pos, 6, 6)
        painter.setBrush(QBrush(self.current_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(handle_pos, 4, 4)

        # 4. SV 方块手柄：呼吸感双环
        sx = bx + self.sat * box_size
        sy = by + (1.0 - self.val) * box_size
        sv_pos = QPointF(sx, sy)

        for r in range(14, 4, -2):
            glow_color = QColor(255, 255, 255, 30 - r * 2)
            painter.setPen(QPen(glow_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(sv_pos, r, r)
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(sv_pos, 6, 6)
        painter.setBrush(QBrush(self.current_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(sv_pos, 4, 4)

    def handle_mouse(self, pos):
        center = QPointF(self.rect().center())
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > (self.width() / 2 - 35):
            angle = math.atan2(-dy, dx)
            if angle < 0:
                angle += 2 * math.pi
            self.hue = angle / (2 * math.pi)
            self.sat = 1.0
            self.val = 1.0
        else:
            inner_r = self.width() / 2 - 30
            box_s = int(inner_r * 1.2)
            bx = center.x() - box_s / 2
            by = center.y() - box_s / 2
            self.sat = max(0.0, min(1.0, (pos.x() - bx) / box_s))
            self.val = max(0.0, min(1.0, 1.0 - (pos.y() - by) / box_s))

        self.update_color()
        self.colorChanged.emit(self.current_color)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.interactionChanged.emit(True)
            self.handle_mouse(event.pos())

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.handle_mouse(event.pos())

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.interactionChanged.emit(False)


# --- 色块 + 浮层取色器（点击色块弹出）---
class ColorSwatchWidget(QWidget):
    """默认显示小色块和 Hex，点击后弹出取色器"""
    colorChanged = pyqtSignal(QColor)
    interactionChanged = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.swatch_btn = QPushButton()
        self.swatch_btn.setFixedSize(36, 36)
        self.swatch_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.swatch_btn.setStyleSheet(
            "QPushButton { border-radius: 8px; border: 2px solid rgba(255,255,255,0.2); } "
            "QPushButton:hover { border-color: rgba(255,255,255,0.5); }"
        )
        self.swatch_btn.clicked.connect(self._show_picker)
        layout.addWidget(self.swatch_btn)
        self.hex_input = QLineEdit()
        self.hex_input.setPlaceholderText("#RRGGBB")
        self.hex_input.setMaxLength(9)
        self.hex_input.setStyleSheet(
            "background: rgba(50, 50, 55, 0.9); border-radius: 8px; "
            "padding: 8px 10px; border: 1px solid rgba(255,255,255,0.08); color: #E0E0E0;"
        )
        self.hex_input.editingFinished.connect(self._on_hex_edited)
        layout.addWidget(self.hex_input, 1)
        self._color = QColor("#212122")
        self._picker_popup = None
        self.set_color(self._color)

    def set_color(self, color):
        self._color = color
        self.swatch_btn.setStyleSheet(
            "QPushButton { background: %s; border-radius: 8px; border: 2px solid rgba(255,255,255,0.2); } "
            "QPushButton:hover { border-color: rgba(255,255,255,0.5); }" % color.name()
        )
        self.hex_input.setText(color.name())

    def _show_picker(self):
        self.show_picker_at(self)

    def _on_picker_color(self, color):
        self.set_color(color)
        self.colorChanged.emit(color)

    def _on_hex_edited(self):
        raw = self.hex_input.text().strip()
        if raw and not raw.startswith("#"):
            raw = "#" + raw
        c = QColor(raw)
        if c.isValid():
            self.set_color(c)
            self.colorChanged.emit(c)

    def set_color_externally(self, color):
        """供外部同步颜色（如切换编辑目标时）"""
        self.set_color(color)

    def show_picker_at(self, anchor_widget):
        """在指定锚点控件位置弹出取色器（供 InlineColorPickerRow 调用）"""
        if self._picker_popup is None:
            self._picker_popup = QFrame(self, Qt.WindowType.Popup)
            self._picker_popup.setFrameShape(QFrame.Shape.StyledPanel)
            self._picker_popup.setStyleSheet(
                "QFrame { background: rgba(35, 35, 40, 0.98); border-radius: 12px; "
                "border: 1px solid rgba(255,255,255,0.12); }"
            )
            popup_layout = QVBoxLayout(self._picker_popup)
            popup_layout.setContentsMargins(12, 12, 12, 12)
            self._picker_widget = ColorWheelPicker(self._picker_popup)
            self._picker_widget.colorChanged.connect(self._on_picker_color)
            self._picker_widget.interactionChanged.connect(self.interactionChanged.emit)
            popup_layout.addWidget(self._picker_widget)
        self._picker_widget.set_color_externally(self._color)
        pt = anchor_widget.mapToGlobal(anchor_widget.rect().bottomLeft())
        self._picker_popup.move(pt)
        self._picker_popup.show()


# --- 单行内联取色器（左 Label，右 色块+Hex 触发器，恢复大尺寸样式）---
class InlineColorPickerRow(QWidget):
    """单行布局：左侧 Label，右侧可点击触发器（色块 + Hex 文本），点击弹出取色器"""
    def __init__(self, label, get_color_cb, on_click_cb, parent=None):
        super().__init__(parent)
        self.get_color_cb = get_color_cb
        self.on_click_cb = on_click_cb
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(10)
        lbl = QLabel(label)
        lbl.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        layout.addWidget(lbl)
        layout.addStretch()
        self.trigger = QPushButton()
        self.trigger.setCursor(Qt.CursorShape.PointingHandCursor)
        self.trigger.setStyleSheet(
            "QPushButton { background: rgba(50,50,55,0.8); border-radius: 8px; "
            "border: 1px solid rgba(255,255,255,0.12); padding: 8px 12px; } "
            "QPushButton:hover { background: rgba(255,255,255,0.1); border-color: rgba(255,255,255,0.2); }"
        )
        self.trigger.setFixedHeight(40)
        self.trigger.setMinimumWidth(120)
        self.trigger.clicked.connect(self._on_trigger_clicked)
        trigger_layout = QHBoxLayout(self.trigger)
        trigger_layout.setContentsMargins(8, 4, 12, 4)
        trigger_layout.setSpacing(10)
        self.swatch = QLabel()
        self.swatch.setFixedSize(28, 28)
        self.swatch.setStyleSheet("border-radius: 6px; border: 1px solid rgba(255,255,255,0.25);")
        self.hex_label = QLabel("#212122")
        self.hex_label.setStyleSheet("color: #E0E0E0; font-size: 13px; font-family: monospace;")
        trigger_layout.addWidget(self.swatch)
        trigger_layout.addWidget(self.hex_label)
        layout.addWidget(self.trigger)
        self._refresh_display()

    def _refresh_display(self):
        c = self.get_color_cb()
        if c is not None and c.isValid():
            self.swatch.setStyleSheet(
                "background: %s; border-radius: 4px; border: 1px solid rgba(255,255,255,0.2);" % c.name()
            )
            self.hex_label.setText(c.name())

    def _on_trigger_clicked(self):
        self.on_click_cb(self)

    def refresh(self):
        """供外部在颜色变化后调用，刷新显示"""
        self._refresh_display()


# --- 带标题的可折叠面板 (Collapsible Accordion) ---
class CollapsibleBox(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.toggle_button = QPushButton(title)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 13px; color: #EAEAEA;
                text-align: left; padding: 10px 12px;
                background: rgba(255, 255, 255, 0.05);
                border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.02);
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.1); }
            QPushButton:checked { color: #FFFFFF; }
        """)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(True)

        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(4, 12, 4, 12)
        self.content_layout.setSpacing(12)

        self.toggle_button.toggled.connect(self.content_area.setVisible)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 10)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

    def addWidget(self, widget, stretch=0, alignment=Qt.AlignmentFlag.AlignTop):
        self.content_layout.addWidget(widget, stretch, alignment)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)

    def addSpacing(self, size):
        self.content_layout.addSpacing(size)


# --- 高级特效折叠面板：默认折叠，带箭头图标与平滑动画 ---
class CollapsibleAdvancedBox(QWidget):
    """渐进式展示：低频特效控件收纳，默认折叠，点击展开/收起，带平滑高度动画"""

    def __init__(self, title="✨ 高级特效", parent=None):
        super().__init__(parent)
        self._title = title
        self._arrow_collapsed = "▶"
        self._arrow_expanded = "▼"
        self.toggle_button = QPushButton(f"{self._arrow_collapsed}  {title}")
        self.toggle_button.setStyleSheet("""
            QPushButton {
                font-weight: bold; font-size: 12px; color: #A0A0A0;
                text-align: left; padding: 8px 12px;
                background: rgba(255, 255, 255, 0.03);
                border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.04);
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.06); color: #C0C0C0; }
            QPushButton:checked { color: #E0E0E0; }
        """)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)  # 默认折叠

        self.content_area = QWidget()
        self.content_area.setStyleSheet("background: transparent;")
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(4, 8, 4, 12)
        self.content_layout.setSpacing(10)

        self._anim = QVariantAnimation(self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_anim_value)
        self._anim.finished.connect(self._on_anim_finished)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 8)
        main_layout.addWidget(self.toggle_button)
        main_layout.addWidget(self.content_area)

        self.content_area.setMaximumHeight(0)
        self.toggle_button.toggled.connect(self._on_toggled)
        self._update_arrow()

    def _update_arrow(self):
        arrow = self._arrow_expanded if self.toggle_button.isChecked() else self._arrow_collapsed
        self.toggle_button.setText(f"{arrow}  {self._title}")

    def _on_toggled(self, checked):
        self._update_arrow()
        if checked:
            self.content_area.setMaximumHeight(9999)
            self.content_area.adjustSize()
            target_h = self.content_area.sizeHint().height()
            self.content_area.setMaximumHeight(0)
            self._anim.setStartValue(0)
            self._anim.setEndValue(min(target_h, 600))
            self._anim.start()
        else:
            cur = self.content_area.height()
            self._anim.setStartValue(cur)
            self._anim.setEndValue(0)
            self._anim.start()

    def _on_anim_value(self, val):
        self.content_area.setMaximumHeight(int(val))

    def _on_anim_finished(self):
        if self.toggle_button.isChecked():
            self.content_area.setMaximumHeight(16777215)  # Qt 默认无限制

    def addWidget(self, widget, stretch=0, alignment=Qt.AlignmentFlag.AlignTop):
        self.content_layout.addWidget(widget, stretch, alignment)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)

    def addSpacing(self, size):
        self.content_layout.addSpacing(size)


class PreviewRenderSignals(QObject):
    finished = pyqtSignal(int, int, int, bytes)
    error = pyqtSignal(int, str)


class PreviewRenderTask(QRunnable):
    def __init__(self, req_id, payload, render_fn):
        super().__init__()
        self.req_id = req_id
        self.payload = payload
        self.render_fn = render_fn
        self.signals = PreviewRenderSignals()

    def run(self):
        try:
            w, h, data = self.render_fn(self.payload)
            self.signals.finished.emit(self.req_id, w, h, data)
        except Exception as e:
            self.signals.error.emit(self.req_id, str(e))


class WorkerSignals(QObject):
    finished = pyqtSignal(object)
    error = pyqtSignal(str)


class WorkerTask(QRunnable):
    def __init__(self, fn, payload):
        super().__init__()
        self.fn = fn
        self.payload = payload
        self.signals = WorkerSignals()

    def run(self):
        try:
            result = self.fn(self.payload)
            self.signals.finished.emit(result)
        except Exception as e:
            self.signals.error.emit(str(e))

# 移动端安全区：归一化坐标 (x0, y0, x1, y1)，0-1 表示占预览区域比例
SAFE_ZONE_OVERLAYS = [
    ("iPhone 刘海", 0.15, 0.0, 0.85, 0.08),
    ("iPhone 底部横条", 0.35, 0.92, 0.65, 1.0),
    ("Android 挖孔", 0.42, 0.0, 0.58, 0.05),
]


class PreviewLabel(QWidget):
    interactionStarted = pyqtSignal()
    interactionEnded = pyqtSignal()
    interactionUpdate = pyqtSignal(float, float) # norm_x, norm_y

    def __init__(self, parent=None):
        super().__init__(parent)
        self._custom_text = None
        self._show_safe_zone = False
        self.setStyleSheet(
            "background: transparent; border-radius: 16px; "
            "border: 1px solid rgba(0,0,0,0.08);"
        )
        self.setMinimumSize(400, 300)
        self._is_dragging = False
        self._snap_lines = []
        self._gradient_line = None
        self._noise_indicator = None
        self._radial_ellipse = None
        
        self._anim = QVariantAnimation(self)
        self._anim.setDuration(300)
        self._anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self._anim.valueChanged.connect(self._on_anim_step)
        self._first_preview_done = False
        self._custom_pixmap = None

    def setPixmapAnimated(self, pixmap, animate=True):
        self._custom_pixmap = pixmap
        
        if not animate:
            self._anim.stop()
            self._anim_scale = 1.0
            self.update()
            return
            
        if not self._first_preview_done:
            self._anim_scale = 1.0
            self._first_preview_done = True
            self.update()
            return

        self._anim.stop()
        self._anim.setStartValue(0.96)
        self._anim.setEndValue(1.0)
        self._anim.start()

    def setText(self, text):
        self._custom_text = text
        self.update()

    def _on_anim_step(self, val):
        self._anim_scale = val
        self.update()

    def setSnapLines(self, lines):
        self._snap_lines = lines
        self.update()

    def setShowSafeZone(self, show):
        if self._show_safe_zone != show:
            self._show_safe_zone = show
            self.update()

    def setGradientLine(self, line):
        """line: [start_x, start_y, end_x, end_y] 归一化 0-1，或 None 隐藏"""
        self._gradient_line = line
        self.update()

    def setNoiseIndicator(self, intensity):
        """intensity: 0-100 或 None 隐藏"""
        self._noise_indicator = intensity
        self.update()

    def setRadialEllipse(self, ellipse):
        """ellipse: [cx, cy, ex, ey] 中心+边缘点，或 None 隐藏"""
        self._radial_ellipse = ellipse
        self.update()

    def _notify_pos(self, pos):
        pm = self._custom_pixmap
        if pm is None or pm.isNull():
            return
        
        pw = pm.width()
        ph = pm.height()
        
        px = (self.width() - pw) / 2.0
        py = (self.height() - ph) / 2.0
        
        # Local pos inside pixmap
        lx = pos.x() - px
        ly = pos.y() - py
        
        norm_x = max(0.0, min(1.0, lx / pw))
        norm_y = max(0.0, min(1.0, ly / ph))
        
        self.interactionUpdate.emit(norm_x, norm_y)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = True
            self.interactionStarted.emit()
            self._notify_pos(event.pos())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_dragging:
            self._notify_pos(event.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._is_dragging = False
            self.interactionEnded.emit()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        # 1. 绘制带有圆角的透明底色棋盘格
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 16, 16)
        painter.setClipPath(path)
        
        cell_size = 20
        for y in range(0, self.height(), cell_size):
            for x in range(0, self.width(), cell_size):
                color = QColor(60, 60, 65) if (x // cell_size + y // cell_size) % 2 == 0 else QColor(40, 40, 45)
                painter.fillRect(x, y, cell_size, cell_size, color)

        # 2. 绘制居中的 Pixmap 并应用动画缩放
        pm = self._custom_pixmap
        if pm is None or pm.isNull():
            if getattr(self, '_custom_text', None):
                painter.setPen(QPen(QColor(160, 160, 160)))
                painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self._custom_text)
        else:
            pw = pm.width() * self._anim_scale
            ph = pm.height() * self._anim_scale
            px = (self.width() - pw) / 2.0
            py = (self.height() - ph) / 2.0
            painter.drawPixmap(int(px), int(py), int(pw), int(ph), pm)
            
            # 3. 绘制磁性吸附参考线
            if self._snap_lines:
                painter.setPen(QPen(QColor(0, 255, 255, 180), 1, Qt.PenStyle.DashLine))
                for line in self._snap_lines:
                    axis = line.get('axis')
                    val = line.get('val')
                    if axis == 'v':
                        cx = px + val * pw
                        painter.drawLine(int(cx), int(py), int(cx), int(py + ph))
                    elif axis == 'h':
                        cy = py + val * ph
                        painter.drawLine(int(px), int(cy), int(px + pw), int(cy))

            # 4. 渐变方向线（抗锯齿 + 柔和描边）
            if getattr(self, '_gradient_line', None) and len(self._gradient_line) >= 4:
                gl = self._gradient_line
                x0, y0 = px + gl[0] * pw, py + gl[1] * ph
                x1, y1 = px + gl[2] * pw, py + gl[3] * ph
                p0, p1 = QPointF(x0, y0), QPointF(x1, y1)
                pen = QPen(QColor(0, 255, 255))
                pen.setWidth(3)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawLine(p0, p1)
                for gx, gy in [(gl[0], gl[1]), (gl[2], gl[3])]:
                    cx, cy = px + gx * pw, py + gy * ph
                    painter.setBrush(QColor(0, 255, 255))
                    painter.setPen(QPen(QColor(255, 255, 255, 180), 1, Qt.PenStyle.SolidLine))
                    painter.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))

            # 5. 径向渐变椭圆（抗锯齿 + 柔和描边）
            if getattr(self, '_radial_ellipse', None) and len(self._radial_ellipse) >= 4:
                re = self._radial_ellipse
                cx, cy = px + re[0] * pw, py + re[1] * ph
                ex, ey = px + re[2] * pw, py + re[3] * ph
                rx = abs(ex - cx)
                ry = abs(ey - cy)
                rx, ry = max(rx, 4), max(ry, 4)
                pen = QPen(QColor(0, 255, 255))
                pen.setWidth(3)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QRectF(cx - rx, cy - ry, rx * 2, ry * 2))
                painter.setBrush(QColor(0, 255, 255))
                painter.setPen(QPen(QColor(255, 255, 255, 180), 1, Qt.PenStyle.SolidLine))
                painter.drawEllipse(QRectF(cx - 5, cy - 5, 10, 10))
                painter.drawEllipse(QRectF(ex - 5, ey - 5, 10, 10))

            # 6. 噪点强度指示条（上下拖动时显示）
            if getattr(self, '_noise_indicator', None) is not None:
                val = max(0, min(100, self._noise_indicator)) / 100.0
                bar_w = 8
                bar_x = px + pw - bar_w - 12
                fill_h = int(ph * val)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(0, 0, 0, 120))
                painter.drawRoundedRect(int(bar_x), int(py), bar_w, int(ph), 4, 4)
                painter.setBrush(QColor(0, 255, 255, 200))
                painter.drawRoundedRect(int(bar_x), int(py + ph - fill_h), bar_w, max(2, fill_h), 4, 4)

            # 7. 移动端安全区蒙版叠层
            if self._show_safe_zone and pw > 0 and ph > 0:
                painter.setPen(Qt.PenStyle.NoPen)
                for _label, x0, y0, x1, y1 in SAFE_ZONE_OVERLAYS:
                    rx = px + x0 * pw
                    ry = py + y0 * ph
                    rw = (x1 - x0) * pw
                    rh = (y1 - y0) * ph
                    painter.fillRect(int(rx), int(ry), max(1, int(rw)), max(1, int(rh)),
                                    QColor(0, 0, 0, 140))


# --- 相册库对话框 ---
THUMB_SIZE = 140

class GalleryDialog(QDialog):
    """用户保存与生成的壁纸相册库，支持查看、删除、设为壁纸。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("相册库")
        self.setMinimumSize(720, 480)
        self.setStyleSheet("""
            QDialog { background: #1E1E23; }
            QLabel { color: #E0E0E0; }
            QPushButton {
                background: rgba(50, 50, 55, 0.9);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 8px;
                padding: 6px 12px;
                color: #E0E0E0;
            }
            QPushButton:hover { background: rgba(70, 70, 75, 0.9); border-color: rgba(255,255,255,0.15); }
            QPushButton#btnDelete { color: #E74C3C; }
            QPushButton#btnSetWall { background: #0078D4; border: none; }
        """)
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("已保存的壁纸（output 目录）"))
        top_row.addStretch()
        self.btn_open_folder = QPushButton("📁 打开文件夹")
        self.btn_open_folder.clicked.connect(self._open_folder)
        self.btn_refresh = QPushButton("🔄 刷新")
        self.btn_refresh.clicked.connect(self._refresh)
        top_row.addWidget(self.btn_open_folder)
        top_row.addWidget(self.btn_refresh)
        layout.addLayout(top_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setStyleSheet("background: transparent; border: none;")
        self.grid_widget = QWidget()
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(12)
        self.scroll.setWidget(self.grid_widget)
        layout.addWidget(self.scroll)

        self._refresh()

    def _get_image_files(self):
        out_dir = get_output_dir()
        if not os.path.isdir(out_dir):
            return []
        files = []
        for f in os.listdir(out_dir):
            if f.lower().endswith((".jpg", ".jpeg", ".png")):
                path = os.path.join(out_dir, f)
                if os.path.isfile(path):
                    files.append(path)
        return sorted(files, key=lambda p: os.path.getmtime(p), reverse=True)

    def _make_thumbnail(self, path):
        try:
            img = Image.open(path).convert("RGB")
            img.thumbnail((THUMB_SIZE, THUMB_SIZE), Image.Resampling.LANCZOS)
            data = img.tobytes("raw", "RGB")
            qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format.Format_RGB888)
            return QPixmap.fromImage(qimg)
        except Exception:
            return QPixmap(THUMB_SIZE, THUMB_SIZE)

    def _refresh(self):
        for i in reversed(range(self.grid_layout.count())):
            w = self.grid_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
        files = self._get_image_files()
        cell_w = THUMB_SIZE + 24
        cols = max(1, max(self.scroll.width(), 400) // cell_w)
        if not files:
            empty = QLabel("暂无记录\n\n快去制作第一张壁纸吧！\n\n保存图片或应用壁纸后，图片会出现在这里。")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setStyleSheet("color: #808080; font-size: 14px; padding: 40px;")
            self.grid_layout.addWidget(empty, 0, 0)
        else:
            for idx, path in enumerate(files):
                row, col = idx // cols, idx % cols
                card = self._make_card(path)
                self.grid_layout.addWidget(card, row, col)

    def _make_card(self, path):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                background: rgba(40, 40, 45, 0.9);
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.06);
            }
            QFrame:hover { border-color: rgba(255,255,255,0.12); }
        """)
        frame.setFixedSize(THUMB_SIZE + 24, THUMB_SIZE + 80)
        card_layout = QVBoxLayout(frame)
        card_layout.setSpacing(6)
        card_layout.setContentsMargins(8, 8, 8, 8)

        thumb = QLabel()
        thumb.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb.setStyleSheet("background: rgba(0,0,0,0.3); border-radius: 8px;")
        pix = self._make_thumbnail(path)
        thumb.setPixmap(pix)
        card_layout.addWidget(thumb, alignment=Qt.AlignmentFlag.AlignCenter)

        name = os.path.basename(path)
        if len(name) > 18:
            name = name[:15] + "..."
        name_label = QLabel(name)
        name_label.setStyleSheet("font-size: 11px; color: #A0A0A0;")
        name_label.setWordWrap(True)
        name_label.setMaximumWidth(THUMB_SIZE + 8)
        card_layout.addWidget(name_label, alignment=Qt.AlignmentFlag.AlignCenter)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)
        btn_set = QPushButton("设为壁纸")
        btn_set.setObjectName("btnSetWall")
        btn_set.setFixedHeight(28)
        btn_set.clicked.connect(lambda checked, p=path: self._set_wallpaper(p))
        btn_del = QPushButton("删除")
        btn_del.setObjectName("btnDelete")
        btn_del.setFixedHeight(28)
        btn_del.clicked.connect(lambda checked, p=path: self._delete(p))
        btn_row.addWidget(btn_set)
        btn_row.addWidget(btn_del)
        card_layout.addLayout(btn_row)
        return frame

    def _set_wallpaper(self, path):
        try:
            ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
            QMessageBox.information(self, "成功", "壁纸已设置")
        except Exception as e:
            QMessageBox.warning(self, "失败", "设置壁纸失败：%s" % str(e))

    def _delete(self, path):
        reply = QMessageBox.question(
            self, "确认删除",
            "确定要删除「%s」吗？" % os.path.basename(path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(path)
                self._refresh()
            except Exception as e:
                QMessageBox.warning(self, "删除失败", str(e))

    def _open_folder(self):
        out_dir = get_output_dir()
        if sys.platform == "win32":
            os.startfile(out_dir)
        elif sys.platform == "darwin":
            subprocess.run(["open", out_dir])
        else:
            subprocess.run(["xdg-open", out_dir])

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(50, self._refresh)


# --- 主窗口 ---
class WallpaperUltra(QWidget):
    def __init__(self):
        super().__init__()
        self.is_release_build = bool(getattr(sys, "frozen", False))
        self.font_dict = {"默认字体": "C:/Windows/Fonts/msyhbd.ttc"}
        self.font_cache = {}
        self.font_cache_lock = threading.Lock()
        self.text_metrics_cache = {}
        self.text_metrics_lock = threading.Lock()
        self.bg_image_cache = {}
        self.bg_image_cache_lock = threading.Lock()
        self.bg_gradient_cache = {}
        self.bg_gradient_cache_lock = threading.Lock()
        self._gradient_masks = {}
        self.edit_target = "text"
        self.text_color = QColor("#212122")
        self.layout_mode = "自由排列"
        self.bg_color = QColor("#F7F7F8")
        self.bg_color2 = QColor("#EDEDF0")
        self.bg_gradient_mode = "纯色"
        self.bg_gradient_direction = "上->下"
        self.gradient_line = [0.5, 0.0, 0.5, 1.0]  # [start_x, start_y, end_x, end_y] 归一化
        self.radial_radius = 50  # 0-100，中心区域大小，100 时半径最大(约 200% 画布)
        self.radial_ellipse = [0.5, 0.5, 0.79, 0.79]  # 圆形，对应 radius=50
        self.bg_image_path = None
        self.bg_image_opacity = 1.0
        self.enable_noise = False
        self.noise_intensity = 40  # 0-100
        self.user_color_presets = {}
        self.text_pos = [0.5, 0.5]
        self.preview_profile = "平衡"
        self.export_high_quality = True
        self.preview_pool = QThreadPool.globalInstance()
        self.worker_pool = QThreadPool()
        self.worker_pool.setMaxThreadCount(1)
        
        self._last_state_hash = 0
        self._gradient_drag_start = None  # 自定义渐变时，拖动起点 [x,y]
        self.preview_running = False
        self.preview_queued = None
        self.preview_latest_req_id = 0
        self.preview_req_meta = {}
        self.preview_interacting = False
        self._last_resize_fast_ts = 0.0
        self.wallpaper_applying = False
        self.history = []
        self.future = []
        self._applying_state = False
        self.label_perf = None
        # Material You 动态主题：从背景图主色衍生，无图时用 Fallback
        self._theme_colors = derive_theme_colors(THEME_FALLBACK_HEX)
        self._load_user_color_presets()

        self.initUI()

        QTimer.singleShot(1000, self.async_load_fonts)

    def get_cached_font(self, font_path, size):
        key = (font_path, size)
        with self.font_cache_lock:
            if key not in self.font_cache:
                try:
                    self.font_cache[key] = ImageFont.truetype(font_path, max(5, size))
                except Exception:
                    self.font_cache[key] = ImageFont.truetype(
                        "C:/Windows/Fonts/msyhbd.ttc", max(5, size)
                    )
            return self.font_cache[key]

    def get_cached_bg_image(self, image_path):
        if not image_path:
            return None
        with self.bg_image_cache_lock:
            cached = self.bg_image_cache.get(image_path)
        if cached is not None:
            return cached.copy()
        try:
            img = Image.open(image_path).convert("RGB")
        except Exception:
            return None
        with self.bg_image_cache_lock:
            if len(self.bg_image_cache) > 24:
                self.bg_image_cache.clear()
            self.bg_image_cache[image_path] = img
        return img.copy()

    def _get_presets_path(self):
        if getattr(sys, "frozen", False):
            base = os.path.dirname(sys.executable)
            return os.path.join(base, "user_color_presets.json")
        return os.path.join(_PROJECT_ROOT or _SCRIPT_DIR, "config", "user_color_presets.json")

    def _load_user_color_presets(self):
        path = self._get_presets_path()
        if not os.path.exists(path):
            self.user_color_presets = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                presets = {}
                for name, cfg in data.items():
                    if isinstance(name, str) and isinstance(cfg, dict):
                        tc = cfg.get("text_color")
                        bg = cfg.get("bg_color")
                        if isinstance(tc, str) and isinstance(bg, str):
                            bg2 = cfg.get("bg_color2", bg)
                            gm = cfg.get("gradient_mode", "纯色")
                            gd = cfg.get("gradient_direction", "上->下")
                            if not isinstance(bg2, str):
                                bg2 = bg
                            if gm not in ("纯色", "线性渐变", "径向渐变"):
                                gm = "纯色"
                            if gd not in ("上->下", "下->上", "左->右", "右->左"):
                                gd = "上->下"
                            presets[name] = {
                                "text_color": tc,
                                "bg_color": bg,
                                "bg_color2": bg2,
                                "gradient_mode": gm,
                                "gradient_direction": gd,
                            }
                self.user_color_presets = presets
            else:
                self.user_color_presets = {}
        except Exception:
            self.user_color_presets = {}

    def _save_user_color_presets(self):
        path = self._get_presets_path()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.user_color_presets, f, ensure_ascii=False, indent=2)

    def async_load_fonts(self):
        try:
            font_dir = "C:/Windows/Fonts"
            for file in os.listdir(font_dir):
                if file.lower().endswith((".ttc", ".ttf")):
                    name = file.split(".")[0]
                    self.font_dict[name] = os.path.join(font_dir, file)
            self.combo_font.clear()
            self.combo_font.addItems(sorted(self.font_dict.keys()))
            if "msyhbd" in self.font_dict:
                self.combo_font.setCurrentText("msyhbd")
        except Exception as e:
            print(f"字体加载失败: {e}")
        self.update_preview()

    def initUI(self):
        self.setWindowTitle("极简壁纸DIY")
        self.setMinimumSize(1100, 800)
        self.setObjectName("mainWindow")
        self.setStyleSheet(
            "#mainWindow { background: #0D0D0F; } "
            "QWidget { color: #E0E0E0; font-family: 'Segoe UI'; }"
        )

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 左侧面板：Flex 纵向布局，上方可滚动 + 底部操作区吸底固定
        sidebar_container = QWidget()
        sidebar_container.setMinimumWidth(300)
        sidebar_container.setFixedWidth(318)
        sidebar_container.setStyleSheet("""
            QWidget#sidebar {
                background: rgba(30, 30, 35, 0.75);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        sidebar_container.setObjectName("sidebar")
        sidebar_main = QVBoxLayout(sidebar_container)
        sidebar_main.setSpacing(0)
        sidebar_main.setContentsMargins(0, 0, 0, 0)

        # 可滚动区域：单列排布，无 Tab 分页
        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(0)

        def _divider():
            f = QFrame()
            f.setFrameShape(QFrame.Shape.HLine)
            f.setStyleSheet("background: rgba(255,255,255,0.06); max-height: 1px;")
            f.setFixedHeight(1)
            return f

        # 单列排布：文字 + 背景，控件组间距统一 10px
        scroll_panel = QWidget()
        scroll_panel.setStyleSheet("background: transparent;")
        lt = QVBoxLayout(scroll_panel)
        lt.setSpacing(10)
        lt.setContentsMargins(20, 16, 20, 20)
        lt.setAlignment(Qt.AlignmentFlag.AlignTop)
        text_row = QHBoxLayout()
        text_row.setSpacing(8)
        self.text_input = QPlainTextEdit("INFINITE PROGRESS")
        self.text_input.setMinimumHeight(40)
        self.text_input.setMaximumHeight(120)
        self.text_input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.text_input.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.text_input.setStyleSheet(
            "background: rgba(50, 50, 55, 0.9); border-radius: 8px; "
            "padding: 10px; border: 1px solid rgba(255,255,255,0.06);"
        )
        self.text_input.textChanged.connect(self.on_text_input_changed)
        self.text_input.textChanged.connect(self._update_text_input_height)
        text_row.addWidget(self.text_input, 1)
        self.btn_hitokoto = QPushButton("获取灵感")
        self.btn_hitokoto.setToolTip("从一言 API 获取随机文案并填入输入框，点击即可替换当前文案")
        self.btn_hitokoto.setStyleSheet("""
            QPushButton {
                background: rgba(50, 50, 55, 0.9); padding: 8px 12px;
                border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);
            }
            QPushButton:hover { background: rgba(70, 70, 75, 0.9); border: 1px solid rgba(255,255,255,0.15); }
        """)
        self.btn_hitokoto.clicked.connect(self.on_fetch_hitokoto)
        text_row.addWidget(self.btn_hitokoto, alignment=Qt.AlignmentFlag.AlignBottom)
        lt.addLayout(text_row)
        self._update_text_input_height()

        arrow_path = get_arrow_path().replace("\\", "/")
        combo_style = """
            QComboBox {
                background: rgba(50, 50, 55, 0.95);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 10px 12px;
                padding-right: 32px;
                padding-left: 12px;
                min-height: 20px;
                color: #E0E0E0;
            }
            QComboBox:hover { border-color: rgba(255,255,255,0.15); }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: right center;
                right: 4px;
                width: 24px;
                border: none;
                background: transparent;
                border-radius: 6px;
            }
            QComboBox::down-arrow {
                image: url("%s");
                width: 12px;
                height: 12px;
            }
        """ % arrow_path
        combo_style += """
            QComboBox QAbstractItemView {
                background: rgba(45, 45, 50, 0.98);
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px;
                padding: 6px;
                selection-background-color: #0078D4;
                selection-color: white;
                outline: none;
            }
            QComboBox QAbstractItemView::item {
                min-height: 28px;
                padding: 4px 10px;
                border-radius: 6px;
            }
        """
        lt.addWidget(QLabel("预设文案:"))
        self.combo_preset_text = NoWheelComboBox()
        self.combo_preset_text.setToolTip("选择预设后自动填入上方输入框；手动编辑时自动切换为「自定义」")
        self.combo_preset_text.addItems(PRESET_TEXTS)
        self.combo_preset_text.setCurrentText("INFINITE PROGRESS")
        self.combo_preset_text.setStyleSheet(combo_style)
        self.combo_preset_text.currentTextChanged.connect(self._on_preset_text_changed)
        lt.addWidget(self.combo_preset_text)

        lt.addWidget(QLabel("字体:"))
        self.combo_font = NoWheelComboBox()
        self.combo_font.addItem("默认字体")
        self.combo_font.setStyleSheet(combo_style)
        self.combo_font.currentTextChanged.connect(self.on_font_changed)
        lt.addWidget(self.combo_font)

        self.label_font_hint = QLabel("")
        self.label_font_hint.setStyleSheet(
            "color: #E67E22; font-size: 11px; padding: 2px 0;"
        )
        self.label_font_hint.setWordWrap(True)
        lt.addWidget(self.label_font_hint)

        lt.addWidget(_divider())
        lt.addSpacing(2)

        size_row = QHBoxLayout()
        size_row.setSpacing(8)
        self.label_font_size = QLabel("字号: 100 px")
        self.label_font_size.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        self.label_font_size.setMinimumWidth(72)
        size_row.addWidget(self.label_font_size)
        self.slider_size = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(20, 600)
        self.slider_size.setValue(100)
        self.slider_size.valueChanged.connect(self.on_font_size_changed)
        self.slider_size.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_size.sliderReleased.connect(self.end_preview_interaction)
        self.slider_size.sliderReleased.connect(self._push_history)
        size_row.addWidget(self.slider_size, 1)
        lt.addLayout(size_row)

        letter_spacing_row = QHBoxLayout()
        letter_spacing_row.setSpacing(8)
        self.label_letter_spacing = QLabel("字间距: 0")
        self.label_letter_spacing.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        self.label_letter_spacing.setMinimumWidth(72)
        letter_spacing_row.addWidget(self.label_letter_spacing)
        self.slider_letter_spacing = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_letter_spacing.setRange(-20, 80)
        self.slider_letter_spacing.setValue(0)
        self.slider_letter_spacing.valueChanged.connect(self.on_letter_spacing_changed)
        self.slider_letter_spacing.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_letter_spacing.sliderReleased.connect(self.end_preview_interaction)
        self.slider_letter_spacing.sliderReleased.connect(self._push_history)
        letter_spacing_row.addWidget(self.slider_letter_spacing, 1)
        lt.addLayout(letter_spacing_row)

        lt.addWidget(_divider())
        lt.addSpacing(2)

        lt.addWidget(QLabel("排版模式:"))
        self.combo_layout_mode = NoWheelComboBox()
        self.combo_layout_mode.setToolTip(
            "自由排列：单行居中；主副标题：首行大、次行小；英文底纹+中文小字：英文作背景、中文叠加"
        )
        self.combo_layout_mode.addItems(["自由排列", "主副标题", "英文底纹+中文小字"])
        self.combo_layout_mode.setCurrentText(self.layout_mode)
        self.combo_layout_mode.setStyleSheet(combo_style)
        self.combo_layout_mode.currentTextChanged.connect(self.on_layout_mode_changed)
        lt.addWidget(self.combo_layout_mode)

        self.check_safe_zone = QCheckBox("显示移动端安全区蒙版")
        self.check_safe_zone.setToolTip("在预览区叠层显示 iPhone/Android 刘海、挖孔等遮挡区域")
        self.check_safe_zone.stateChanged.connect(self._on_safe_zone_toggled)
        self.check_safe_zone.setChecked(False)
        self.check_safe_zone.setVisible(False)  # 功能暂关闭
        lt.addWidget(self.check_safe_zone)

        # 文字设计: 字体颜色（单行内联取色器）
        lt.addWidget(_divider())
        lt.addSpacing(2)
        self._inline_text_color = InlineColorPickerRow(
            "字体颜色",
            lambda: self.text_color,
            lambda row: self._open_color_picker_at(row, "text"),
            self
        )
        lt.addWidget(self._inline_text_color)

        self._color_slot_text = QWidget()
        self._color_slot_text.setStyleSheet("background: transparent;")
        self._color_slot_text_layout = QVBoxLayout(self._color_slot_text)
        self._color_slot_text_layout.setContentsMargins(0, 0, 0, 0)
        self._color_slot_text.setFixedHeight(0)  # 仅用于承载 color_swatch，不占空间
        lt.addWidget(self._color_slot_text)

        # 文字设计：高级特效折叠面板（阴影、叠影、斜体）
        self._adv_text = CollapsibleAdvancedBox("✨ 高级特效")
        self.label_shadow_offset = QLabel("阴影偏移量: 0")
        self.label_shadow_offset.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        self._adv_text.addWidget(self.label_shadow_offset)
        self.slider_shadow_offset = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_shadow_offset.setRange(0, 200)
        self.slider_shadow_offset.valueChanged.connect(self.on_shadow_offset_changed)
        self.slider_shadow_offset.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_shadow_offset.sliderReleased.connect(self.end_preview_interaction)
        self.slider_shadow_offset.sliderReleased.connect(self._push_history)
        self.slider_shadow_offset.blockSignals(True)
        self.slider_shadow_offset.setValue(0)
        self.slider_shadow_offset.blockSignals(False)
        self._adv_text.addWidget(self.slider_shadow_offset)

        self.check_stack = QCheckBox("启用叠影效果")
        self.check_stack.setChecked(True)
        self.check_stack.stateChanged.connect(self.on_stack_toggled)
        self._adv_text.addWidget(self.check_stack)

        self.check_italic = QCheckBox("模拟斜体")
        self.check_italic.stateChanged.connect(self.on_italic_toggled)
        self._adv_text.addWidget(self.check_italic)

        lt.addWidget(self._adv_text)

        lt.addWidget(_divider())
        lt.addSpacing(2)
        lt.addWidget(QLabel("壁纸比例:"))
        self.combo_aspect = NoWheelComboBox()
        self.combo_aspect.addItems(list(ASPECT_RATIOS.keys()))
        self.combo_aspect.setCurrentText("16:9")
        self.combo_aspect.setStyleSheet(combo_style)
        self.combo_aspect.currentTextChanged.connect(self.on_aspect_changed)
        lt.addWidget(self.combo_aspect)

        lt.addWidget(QLabel("预览质量:"))
        self.combo_preview_quality = NoWheelComboBox()
        self.combo_preview_quality.setToolTip(
            "速度优先：快速预览；平衡：质量与速度折中；所见即所得：预览最接近导出效果"
        )
        self.combo_preview_quality.addItems(list(PREVIEW_PROFILES.keys()))
        self.combo_preview_quality.setCurrentText(self.preview_profile)
        self.combo_preview_quality.setStyleSheet(combo_style)
        self.combo_preview_quality.currentTextChanged.connect(self.on_preview_quality_changed)
        lt.addWidget(self.combo_preview_quality)

        lt.addWidget(QLabel("背景模式:"))
        self.combo_bg_gradient = NoWheelComboBox()
        self.combo_bg_gradient.addItems(["纯色", "线性渐变", "径向渐变"])
        self.combo_bg_gradient.setCurrentText(self.bg_gradient_mode)
        self.combo_bg_gradient.setStyleSheet(combo_style)
        self.combo_bg_gradient.currentTextChanged.connect(self.on_bg_gradient_mode_changed)
        lt.addWidget(self.combo_bg_gradient)

        self.label_linear_direction = QLabel("线性渐变方向:")
        lt.addWidget(self.label_linear_direction)
        self._gradient_direction_btns = {}
        self._gradient_direction_group = QButtonGroup(self)
        _dirs = [
            ("上->下", "↓", "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #707070,stop:1 #3a3a3a)"),
            ("下->上", "↑", "qlineargradient(x1:0,y1:1,x2:0,y2:0,stop:0 #707070,stop:1 #3a3a3a)"),
            ("左->右", "→", "qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #3a3a3a,stop:1 #707070)"),
            ("右->左", "←", "qlineargradient(x1:1,y1:0,x2:0,y2:0,stop:0 #3a3a3a,stop:1 #707070)"),
        ]
        _btn_row = QHBoxLayout()
        _btn_base = (
            "QPushButton { padding: 10px 14px; border-radius: 8px; font-size: 18px; font-weight: bold; "
            "border: 2px solid rgba(255,255,255,0.1); } "
            "QPushButton:hover { border-color: rgba(255,255,255,0.2); } "
            "QPushButton:checked { border-color: rgba(255,255,255,0.35); background: rgba(255,255,255,0.08); } "
        )
        for direction, arrow, grad in _dirs:
            btn = QPushButton(arrow)
            btn.setCheckable(True)
            btn.setProperty("direction", direction)
            btn.setStyleSheet(_btn_base + "QPushButton { background: %s; }" % grad)
            btn.setToolTip(direction)
            btn.clicked.connect(lambda checked, d=direction: self._on_gradient_direction_clicked(d))
            self._gradient_direction_btns[direction] = btn
            self._gradient_direction_group.addButton(btn)
            _btn_row.addWidget(btn)
        self._btn_gradient_custom = QPushButton("自定义")
        self._btn_gradient_custom.setCheckable(True)
        self._btn_gradient_custom.setToolTip("在预览区拖动以调整渐变方向")
        self._btn_gradient_custom.setStyleSheet(
            _btn_base + "QPushButton { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #505050,stop:1 #303030); }"
        )
        self._btn_gradient_custom.clicked.connect(lambda: self._on_gradient_direction_clicked("自定义"))
        self._gradient_direction_btns["自定义"] = self._btn_gradient_custom
        self._gradient_direction_group.addButton(self._btn_gradient_custom)
        _btn_row.addWidget(self._btn_gradient_custom)
        _btn_row.addStretch()
        lt.addLayout(_btn_row)
        self.label_radial = QLabel("径向渐变:")
        lt.addWidget(self.label_radial)
        self.label_radial_radius = QLabel("中心区域大小: 50%")
        self.label_radial_radius.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        lt.addWidget(self.label_radial_radius)
        self.slider_radial_radius = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_radial_radius.setRange(0, 100)
        self.slider_radial_radius.setValue(50)
        self.slider_radial_radius.valueChanged.connect(self.on_radial_radius_changed)
        self.slider_radial_radius.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_radial_radius.sliderReleased.connect(self.end_preview_interaction)
        self.slider_radial_radius.sliderReleased.connect(self._push_history)
        lt.addWidget(self.slider_radial_radius)

        lt.addWidget(_divider())
        lt.addSpacing(2)
        self._inline_bg_color = InlineColorPickerRow(
            "背景颜色",
            lambda: self.bg_color,
            lambda row: self._open_color_picker_at(row, "bg"),
            self
        )
        self._inline_bg_color2 = InlineColorPickerRow(
            "背景副色",
            lambda: self.bg_color2,
            lambda row: self._open_color_picker_at(row, "bg2"),
            self
        )
        lt.addWidget(self._inline_bg_color)
        lt.addWidget(self._inline_bg_color2)

        self.color_swatch = ColorSwatchWidget()
        self.color_swatch.setFixedHeight(0)
        self.color_swatch.setVisible(False)  # 仅用于 Popover，由 InlineColorPickerRow 触发
        self.color_swatch.colorChanged.connect(self.handle_color_change)
        self.color_swatch.interactionChanged.connect(self.on_picker_interaction_changed)
        self.color_swatch.hex_input.editingFinished.connect(self._push_history)
        self._color_slot_text_layout.addWidget(self.color_swatch)  # 初始在文字设计 Tab
        self.input_color_code = self.color_swatch.hex_input

        self.switch_target("text")
        self._update_color_code_input()

        # 配色预设相关控件（已从 UI 移除，保留隐藏对象以兼容 _mark_custom_preset、分享/恢复状态等）
        self.combo_preset = NoWheelComboBox()
        self.combo_preset.addItem("自定义")
        self.combo_preset.addItems(list(BUILTIN_COLOR_PRESETS.keys()))
        for name in sorted(self.user_color_presets.keys()):
            self.combo_preset.addItem(name)
        self.combo_preset.setStyleSheet(combo_style)
        self.combo_preset.currentTextChanged.connect(self.on_style_preset_changed)
        preset_view = self.combo_preset.view()
        preset_view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        preset_view.customContextMenuRequested.connect(self.on_preset_context_menu)
        self._preset_viewport = preset_view.viewport()
        self._preset_viewport.installEventFilter(self)
        self.combo_preset.setVisible(False)
        self.combo_preset.setFixedHeight(0)
        lt.addWidget(self.combo_preset)
        self.btn_save_preset = QPushButton("保存当前配色")
        self.btn_save_preset.setVisible(False)
        self.input_preset_name = QLineEdit()
        self.input_preset_name.setVisible(False)
        self.btn_preset_ok = QPushButton("保存")
        self.btn_preset_ok.setVisible(False)
        self.btn_preset_cancel = QPushButton("取消")
        self.btn_preset_cancel.setVisible(False)
        self.btn_save_preset.clicked.connect(self.on_save_color_preset)
        self.btn_preset_ok.clicked.connect(self.on_save_color_preset_confirm)
        self.btn_preset_cancel.clicked.connect(self.on_save_color_preset_cancel)
        self.input_preset_name.returnPressed.connect(self.on_save_color_preset_confirm)
        self.label_preset_feedback = QLabel("")
        self.label_preset_feedback.setVisible(False)

        lt.addWidget(_divider())
        lt.addSpacing(2)
        _sec_btn = (
            "QPushButton { background: rgba(50,50,55,0.9); padding: 8px; "
            "border-radius: 6px; border: 1px solid rgba(255,255,255,0.06); } "
            "QPushButton:hover { background: rgba(70, 70, 75, 0.9); border-color: rgba(0,120,212,0.4); }"
        )
        bg_btn_row = QHBoxLayout()
        self.btn_pick_bg_image = QPushButton("📁 导入背景图")
        self.btn_clear_bg_image = QPushButton("✖ 清除图层")
        for btn in (self.btn_pick_bg_image, self.btn_clear_bg_image):
            btn.setStyleSheet(_sec_btn)
        self.btn_pick_bg_image.clicked.connect(self.on_pick_bg_image)
        self.btn_clear_bg_image.clicked.connect(self.on_clear_bg_image)
        bg_btn_row.addWidget(self.btn_pick_bg_image)
        bg_btn_row.addWidget(self.btn_clear_bg_image)
        lt.addLayout(bg_btn_row)

        self.btn_extract_color = QPushButton("💧 提取背景主色")
        self.btn_extract_color.setToolTip("从已导入的背景图中自动提取主色，并应用于文字或背景颜色")
        self.btn_extract_color.setStyleSheet(_sec_btn)
        self.btn_extract_color.clicked.connect(self.on_extract_bg_color)
        lt.addWidget(self.btn_extract_color)

        self.label_bg_image_path = QLabel("当前背景图: 未选择")
        self.label_bg_image_path.setWordWrap(True)
        self.label_bg_image_path.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        lt.addWidget(self.label_bg_image_path)

        self.label_bg_opacity = QLabel("背景图透明度: 100%")
        self.label_bg_opacity.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        lt.addWidget(self.label_bg_opacity)
        self.slider_bg_opacity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_bg_opacity.setRange(0, 100)
        self.slider_bg_opacity.setValue(100)
        self.slider_bg_opacity.valueChanged.connect(self.on_bg_opacity_changed)
        self.slider_bg_opacity.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_bg_opacity.sliderReleased.connect(self.end_preview_interaction)
        self.slider_bg_opacity.sliderReleased.connect(self._push_history)
        lt.addWidget(self.slider_bg_opacity)

        # 高级特效折叠面板（毛玻璃、暗角、噪点）
        self._adv_bg = CollapsibleAdvancedBox("✨ 高级特效")
        self.label_bg_blur = QLabel("背景图毛玻璃(Blur): 0")
        self.label_bg_blur.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        self._adv_bg.addWidget(self.label_bg_blur)
        self.slider_bg_blur = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_bg_blur.setRange(0, 100)
        self.slider_bg_blur.setValue(0)
        self.slider_bg_blur.valueChanged.connect(self.on_bg_blur_changed)
        self.slider_bg_blur.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_bg_blur.sliderReleased.connect(self.end_preview_interaction)
        self.slider_bg_blur.sliderReleased.connect(self._push_history)
        self._adv_bg.addWidget(self.slider_bg_blur)

        self.label_bg_vignette = QLabel("暗角遮罩(Vignette): 0")
        self.label_bg_vignette.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        self._adv_bg.addWidget(self.label_bg_vignette)
        self.slider_bg_vignette = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_bg_vignette.setRange(0, 100)
        self.slider_bg_vignette.setValue(0)
        self.slider_bg_vignette.valueChanged.connect(self.on_bg_vignette_changed)
        self.slider_bg_vignette.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_bg_vignette.sliderReleased.connect(self.end_preview_interaction)
        self.slider_bg_vignette.sliderReleased.connect(self._push_history)
        self._adv_bg.addWidget(self.slider_bg_vignette)

        self.check_noise = QCheckBox("高级质感: 拍立得噪点 (Noise)")
        self.check_noise.stateChanged.connect(self.on_noise_toggled)
        self._adv_bg.addWidget(self.check_noise)
        self.label_noise_intensity = QLabel("噪点强度: 40")
        self.label_noise_intensity.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        self._adv_bg.addWidget(self.label_noise_intensity)
        self.slider_noise_intensity = NoWheelSlider(Qt.Orientation.Horizontal)
        self.slider_noise_intensity.setRange(0, 100)
        self.slider_noise_intensity.setValue(40)
        self.slider_noise_intensity.valueChanged.connect(self.on_noise_intensity_changed)
        self.slider_noise_intensity.sliderPressed.connect(self.begin_preview_interaction)
        self.slider_noise_intensity.sliderReleased.connect(self.end_preview_interaction)
        self.slider_noise_intensity.sliderReleased.connect(self._push_history)
        self._adv_bg.addWidget(self.slider_noise_intensity)

        lt.addWidget(self._adv_bg)

        self.check_export_hq = QCheckBox("导出高质量抗锯齿")
        self.check_export_hq.setChecked(True)
        self.check_export_hq.setVisible(False)
        self.export_high_quality = True

        self._update_bg_image_hint()

        scroll_layout.addWidget(scroll_panel)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("background: transparent; border: none;")
        scroll_area.setWidget(scroll_content)
        self._sidebar_scroll_area = scroll_area
        sidebar_main.addWidget(scroll_area, 1)

        # 不再在滚动区内 addStretch，避免内容被撑满视口导致滚动条跳动、显示不准

        # 底部操作区：吸底固定，不随滚动
        bottom_actions = QWidget()
        bottom_actions.setStyleSheet("background: transparent;")
        bottom_layout = QVBoxLayout(bottom_actions)
        bottom_layout.setSpacing(10)
        bottom_layout.setContentsMargins(20, 10, 20, 16)

        self.btn_save = QPushButton("保存图片")
        self.btn_save.setStyleSheet(
            "background: rgba(50, 50, 55, 0.9); height: 36px; border-radius: 8px; "
            "border: 1px solid rgba(255,255,255,0.08); font-size: 13px;"
        )
        self.btn_save.clicked.connect(self.save_image)
        bottom_layout.addWidget(self.btn_save)

        self.btn_gallery = QPushButton("📷 相册库")
        self.btn_gallery.setStyleSheet(
            "background: rgba(50, 50, 55, 0.9); height: 36px; border-radius: 8px; "
            "border: 1px solid rgba(255,255,255,0.08); font-size: 13px;"
        )
        self.btn_gallery.clicked.connect(self.show_gallery)
        bottom_layout.addWidget(self.btn_gallery)

        self.btn_apply = QPushButton("一键应用桌面壁纸")
        # 主按钮样式由 _refresh_theme_styles 动态注入主题色
        self.btn_apply.clicked.connect(self.apply_wallpaper)
        bottom_layout.addWidget(self.btn_apply)

        sidebar_main.addWidget(bottom_actions)

        # 全局 Slider 样式由 _refresh_theme_styles 动态注入主题色
        self._refresh_theme_styles()

        main_layout.addWidget(sidebar_container)

        # 预览区 + 右上角悬浮撤销/重做（半透明背景，保证可见性）
        preview_container = QWidget()
        preview_container.setStyleSheet("background: transparent;")
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setSpacing(4)
        preview_layout.setContentsMargins(0, 0, 0, 0)

        undo_bar = QFrame()
        undo_bar.setToolTip("画布操作：撤销 / 重做")
        undo_bar.setStyleSheet(
            "QFrame { background: rgba(0, 0, 0, 0.25); border-radius: 8px; "
            "border: 1px solid rgba(255,255,255,0.06); }"
        )
        undo_layout = QHBoxLayout(undo_bar)
        undo_layout.setContentsMargins(10, 6, 10, 6)
        undo_layout.setSpacing(8)
        undo_layout.addStretch()
        self.btn_undo = QPushButton("↶ 撤销")
        self.btn_redo = QPushButton("↷ 重做")
        for btn in (self.btn_undo, self.btn_redo):
            btn.setStyleSheet(
                "background: rgba(40, 40, 45, 0.9); height: 28px; min-width: 64px; "
                "border-radius: 6px; border: 1px solid rgba(255,255,255,0.1); color: #E0E0E0;"
            )
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_undo.clicked.connect(self.on_undo)
        self.btn_redo.clicked.connect(self.on_redo)
        undo_layout.addWidget(self.btn_undo)
        undo_layout.addWidget(self.btn_redo)

        preview_layout.addWidget(undo_bar, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        self.preview_area = PreviewLabel()
        self.preview_area.setText("正在初始化预览...")
        self.preview_area.interactionStarted.connect(self.begin_preview_interaction)
        self.preview_area.setShowSafeZone(False)
        self.preview_area.interactionEnded.connect(self.on_preview_area_interaction_ended)
        self.preview_area.interactionUpdate.connect(self.on_preview_area_update)
        preview_layout.addWidget(self.preview_area, 1)

        main_layout.addWidget(preview_container, 1)
        self._update_gradient_edit_ui()
        self._update_noise_edit_ui()
        self._push_history()

    def _has_cjk(self, text):
        """检测文本是否包含中日韩字符"""
        for ch in text:
            cp = ord(ch)
            if (0x4E00 <= cp <= 0x9FFF or  # CJK 统一汉字
                0x3400 <= cp <= 0x4DBF or  # CJK 扩展 A
                0x3000 <= cp <= 0x303F or  # CJK 符号
                0x3040 <= cp <= 0x30FF):   # 平假名、片假名
                return True
        return False

    def _font_supports_cjk(self, font_name):
        """判断字体是否可能支持中文"""
        cjk_patterns = ("msyh", "simsun", "simhei", "dengxian", "fangsong",
                        "kaiti", "sourcehan", "notosanscjk", "pingfang", "heiti",
                        "stsong", "stkaiti", "stfangsong", "stzhongsong", "stxihei",
                        "weiruanyahei", "microsoft yahei", "宋体", "黑体", "楷体",
                        "仿宋", "微软雅黑", "苹方", "思源")
        fn = font_name.lower()
        return any(p in fn for p in cjk_patterns)

    def _use_fallback_font(self, font_name):
        patterns = ("wingding", "webding", "symbol", "marlett", "segmd", "segmdl2")
        return any(p in font_name.lower() for p in patterns)

    def _need_cjk_fallback(self, font_name, text):
        """当文本含中文且字体不支持中文时需回退"""
        return text and self._has_cjk(text) and not self._font_supports_cjk(font_name)

    def _get_text_input_value(self):
        return self.text_input.toPlainText()

    def _update_text_input_height(self):
        """根据实际行数调整输入框高度，无后续文字时不显示空行"""
        text = self.text_input.toPlainText()
        lines = text.rstrip("\n").split("\n") if text.strip() else [""]
        line_count = max(1, len(lines))
        h = min(120, max(40, line_count * 26 + 16))
        self.text_input.setFixedHeight(h)

    def _on_preset_text_changed(self, text):
        """预设文案下拉：选择后填入文案输入框"""
        if text == "自定义":
            return
        self._mark_custom_preset()
        self.text_input.blockSignals(True)
        self.text_input.setPlainText(text)
        self.text_input.blockSignals(False)
        self._update_text_input_height()
        self.update_font_hint()
        self.update_preview()
        self._push_history()

    def on_text_input_changed(self):
        if self._applying_state:
            return
        self._mark_custom_preset()
        # 手动编辑时，若与预设不符则切到「自定义」
        current = self.text_input.toPlainText()
        if self.combo_preset_text.currentText() != "自定义" and current not in PRESET_TEXTS:
            self.combo_preset_text.blockSignals(True)
            self.combo_preset_text.setCurrentText("自定义")
            self.combo_preset_text.blockSignals(False)
        self.update_font_hint()
        self.update_preview()

    def update_font_hint(self):
        font_name = self.combo_font.currentText()
        text = self._get_text_input_value()
        symbol_fonts = ("wingding", "webding", "symbol", "marlett", "segmd", "segmdl2")
        is_symbol = any(s in font_name.lower() for s in symbol_fonts)
        need_cjk = self._need_cjk_fallback(font_name, text)
        if is_symbol:
            self.label_font_hint.setText("提示：符号字体可能无法正常显示文字")
        elif need_cjk:
            self.label_font_hint.setText("提示：该字体不支持中文，已自动切换为微软雅黑")
        else:
            self.label_font_hint.setText("")

    def on_font_changed(self, font_name):
        self._mark_custom_preset()
        self.update_font_hint()
        self.update_preview()
        self._push_history()

    def on_font_size_changed(self, value):
        self._mark_custom_preset()
        self.label_font_size.setText("字号: %d px" % value)
        self.update_preview()

    def on_letter_spacing_changed(self, value):
        self._mark_custom_preset()
        self.label_letter_spacing.setText("字间距: %d" % value)
        self.update_preview()

    def on_aspect_changed(self, text):
        self.update_preview()
        self._push_history()

    def on_preview_quality_changed(self, text):
        self.preview_profile = text
        self.update_preview()
        self._push_history()

    def on_export_quality_changed(self, state):
        self.export_high_quality = bool(state)
        self._push_history()

    def _update_bg_image_hint(self):
        if self.bg_image_path:
            self.label_bg_image_path.setText("当前背景图: %s" % self.bg_image_path)
        else:
            self.label_bg_image_path.setText("当前背景图: 未选择")
        self.label_bg_opacity.setText("背景图透明度: %d%%" % int(self.bg_image_opacity * 100))

    def on_pick_bg_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择背景图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not file_path:
            return
        try:
            img = Image.open(file_path).convert("RGB")
            img.load()
        except Exception as e:
            QMessageBox.warning(
                self,
                "导入背景图失败",
                "无法加载该图片，可能格式不支持或文件已损坏。\n\n"
                "支持格式：PNG、JPG、JPEG、BMP、WEBP\n\n"
                "错误详情：%s" % str(e)
            )
            return
        self._mark_custom_preset()
        self.bg_image_path = file_path
        self._update_bg_image_hint()
        # Material You：从新导入的背景图提取主色，动态应用为侧边栏主题
        hex_color = extract_dominant_color(file_path)
        self._apply_dynamic_theme(hex_color)
        self.update_preview()
        self._push_history()

    def on_clear_bg_image(self):
        if not self.bg_image_path:
            return
        self._mark_custom_preset()
        self.bg_image_path = None
        self._update_bg_image_hint()
        # Material You：清除背景图时恢复默认 Fallback 主题
        self._apply_dynamic_theme(THEME_FALLBACK_HEX)
        self.update_preview()
        self._push_history()

    def on_bg_opacity_changed(self, value):
        self._mark_custom_preset()
        self.bg_image_opacity = max(0.0, min(1.0, value / 100.0))
        self.label_bg_opacity.setText("背景图透明度: %d%%" % value)
        self.update_preview()

    def on_bg_gradient_mode_changed(self, text):
        if self._applying_state:
            return
        self._mark_custom_preset()
        self.bg_gradient_mode = text
        self._update_gradient_edit_ui()
        self.update_preview()
        self._push_history()

    def _normalize_gradient_direction(self, d):
        """旧数据可能含 左上->右下，映射到四方向；自定义保留"""
        if d in ("上->下", "下->上", "左->右", "右->左", "自定义"):
            return d
        if d in ("左上->右下", "右上->左下", "左下->右上", "右下->左上"):
            return "自定义"  # 对角方向归为自定义，保留 gradient_line
        return "上->下"

    def on_bg_gradient_direction_changed(self, text):
        if self._applying_state:
            return
        self._mark_custom_preset()
        self.bg_gradient_direction = self._normalize_gradient_direction(text)
        self.gradient_line = self._direction_to_gradient_line(self.bg_gradient_direction)
        self._update_gradient_edit_ui()
        self.update_preview()
        self._push_history()

    def _refresh_theme_styles(self):
        """根据当前 _theme_colors 刷新 Tab、主按钮、Slider 的主题色（Material You 动态主题）"""
        c = self._theme_colors
        if c is None:
            c = derive_theme_colors(THEME_FALLBACK_HEX)
            self._theme_colors = c
        primary = c.get("primary") or THEME_FALLBACK_HEX
        primary_hover = c.get("primary_hover") or THEME_FALLBACK_HEX
        primary = str(primary) if primary else THEME_FALLBACK_HEX
        primary_hover = str(primary_hover) if primary_hover else THEME_FALLBACK_HEX
        # 一键应用按钮使用主题主色（仅当已创建时刷新）
        if hasattr(self, "btn_apply") and self.btn_apply is not None:
            btn_style = (
                "background: %s; height: 48px; border-radius: 10px; "
                "font-weight: bold; font-size: 14px; border: none; "
                "QPushButton:hover { background: %s; }"
            ) % (primary, primary_hover)
            self.btn_apply.setStyleSheet(btn_style)
        # 全局 Slider 激活轨道与推钮使用主题色
        base = "#mainWindow { background: #0D0D0F; } QWidget { color: #E0E0E0; font-family: 'Segoe UI'; }"
        slider = """
            QSlider::groove:horizontal {
                border-radius: 4px;
                height: 6px;
                background: rgba(255, 255, 255, 0.1);
            }
            QSlider::sub-page:horizontal {
                background: %s;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #FFFFFF;
                border: 2px solid %s;
                width: 14px;
                height: 14px;
                margin: -4px 0;
                border-radius: 7px;
            }
            QSlider::handle:horizontal:hover {
                background: #EAEAEA;
            }
        """ % (primary, primary)
        self.setStyleSheet(base + " " + slider)

    def _apply_dynamic_theme(self, primary_hex):
        """Material You：从主色衍生主题并刷新 UI"""
        self._theme_colors = derive_theme_colors(primary_hex)
        self._refresh_theme_styles()

    def _jump_to_linear_gradient(self):
        """快速入口：切换到线性渐变"""
        if self.combo_bg_gradient.currentText() != "线性渐变":
            self._mark_custom_preset()
            self.bg_gradient_mode = "线性渐变"
            self.combo_bg_gradient.blockSignals(True)
            self.combo_bg_gradient.setCurrentText("线性渐变")
            self.combo_bg_gradient.blockSignals(False)
            self._update_gradient_edit_ui()
            self.update_preview()
            self._push_history()

    def _open_color_picker_at(self, inline_row, target):
        """点击内联取色器时：切换编辑目标并在触发器位置弹出取色器"""
        self.switch_target(target)
        self.color_swatch.set_color_externally(
            self.text_color if target == "text" else (self.bg_color if target == "bg" else self.bg_color2)
        )
        self.color_swatch.show_picker_at(inline_row.trigger)

    def _update_gradient_edit_ui(self):
        is_linear = self.bg_gradient_mode == "线性渐变"
        is_radial = self.bg_gradient_mode == "径向渐变"
        is_gradient = is_linear or is_radial
        show_linear = is_linear
        show_radial = is_radial
        self.label_linear_direction.setVisible(show_linear)
        for btn in self._gradient_direction_btns.values():
            btn.setVisible(show_linear)
        self.label_radial.setVisible(show_radial)
        self.label_radial_radius.setVisible(show_radial)
        self.slider_radial_radius.setVisible(show_radial)
        if show_linear and self.bg_gradient_direction == "自定义":
            self.preview_area.setGradientLine(self.gradient_line)
        else:
            self.preview_area.setGradientLine(None)
        self.preview_area.setRadialEllipse(None)
        if show_linear:
            self._sync_gradient_direction_buttons()
        # 纯色时只显示背景颜色，渐变时显示主色+副色两行
        self._inline_bg_color.setVisible(not is_gradient)
        self._inline_bg_color2.setVisible(is_gradient)

    def _slider_to_radial_r(self, slider_val):
        """滑块 0-100 -> 实际半径 r，中间段(25-75)拉长，两端压缩"""
        v = max(0, min(100, slider_val)) / 100.0
        if v < 0.25:
            return 0.08 + (v / 0.25) * 0.17
        if v < 0.75:
            return 0.25 + ((v - 0.25) / 0.5) * 0.6
        return 0.85 + ((v - 0.75) / 0.25) * 0.35

    def _radial_r_to_slider(self, r):
        """实际半径 r -> 滑块 0-100"""
        r = max(0.08, min(1.2, r))
        if r <= 0.25:
            return int((r - 0.08) / 0.17 * 25)
        if r <= 0.85:
            return int(25 + (r - 0.25) / 0.6 * 50)
        return int(75 + (r - 0.85) / 0.35 * 25)

    def _radial_radius_to_ellipse(self, radius):
        """radius 0-100（滑块值）-> [cx,cy,ex,ey] 中心固定，圆形 rx=ry"""
        r = self._slider_to_radial_r(radius)
        return [0.5, 0.5, 0.5 + r, 0.5 + r]

    def _radial_ellipse_to_radius(self, ellipse):
        """从 radial_ellipse 反推滑块值 0-100"""
        if not ellipse or len(ellipse) < 4:
            return 50
        dx = ellipse[2] - ellipse[0]
        dy = ellipse[3] - ellipse[1]
        r = math.sqrt(dx * dx + dy * dy)
        return max(0, min(100, self._radial_r_to_slider(r)))

    def on_radial_radius_changed(self, value):
        self._mark_custom_preset()
        self.radial_radius = value
        self.radial_ellipse = self._radial_radius_to_ellipse(value)
        self.label_radial_radius.setText("中心区域大小: %d%%" % value)
        self.update_preview()

    def _on_gradient_direction_clicked(self, direction):
        self._mark_custom_preset()
        self.bg_gradient_direction = direction
        if direction != "自定义":
            self.gradient_line = self._direction_to_gradient_line(direction)
        # 自定义时保留当前 gradient_line，供预览区拖动编辑
        self._sync_gradient_direction_buttons()
        self._update_gradient_edit_ui()
        self.update_preview()
        self._push_history()

    def _direction_to_gradient_line(self, direction):
        """将方向映射为 gradient_line [sx,sy,ex,ey] 归一化"""
        if direction == "上->下":
            return [0.5, 0.0, 0.5, 1.0]
        if direction == "下->上":
            return [0.5, 1.0, 0.5, 0.0]
        if direction == "左->右":
            return [0.0, 0.5, 1.0, 0.5]
        if direction == "右->左":
            return [1.0, 0.5, 0.0, 0.5]
        if direction in ("左上->右下", "右下->左上"):
            return [0.0, 0.0, 1.0, 1.0]
        if direction in ("右上->左下", "左下->右上"):
            return [1.0, 0.0, 0.0, 1.0]
        return [0.5, 0.0, 0.5, 1.0]

    def _sync_gradient_direction_buttons(self):
        btn = self._gradient_direction_btns.get(self.bg_gradient_direction)
        if btn:
            btn.setChecked(True)
        else:
            for b in self._gradient_direction_btns.values():
                b.setChecked(False)

    def _is_editing_gradient(self):
        """是否处于自定义渐变方向编辑模式（在预览区拖动）"""
        return (self.bg_gradient_mode == "线性渐变" and
                self.bg_gradient_direction == "自定义")

    def on_bg_blur_changed(self, value):
        self._mark_custom_preset()
        self.label_bg_blur.setText("背景图毛玻璃(Blur): %d" % value)
        self.update_preview()

    def on_bg_vignette_changed(self, value):
        self._mark_custom_preset()
        self.label_bg_vignette.setText("暗角遮罩(Vignette): %d" % value)
        self.update_preview()

    def on_preview_area_update(self, norm_x, norm_y):
        self._mark_custom_preset()

        # 自定义渐变方向：在预览区拖动设置渐变线（起点->终点）
        if self._is_editing_gradient():
            if self._gradient_drag_start is None:
                self._gradient_drag_start = [norm_x, norm_y]
            self.gradient_line = [
                self._gradient_drag_start[0], self._gradient_drag_start[1],
                norm_x, norm_y
            ]
            self.preview_area.setGradientLine(self.gradient_line)
            self.update_preview()
            return

        # 文字位置：吸附逻辑
        snap_points = [0.333, 0.5, 0.666]
        snap_threshold = 0.03
        snapped_x = norm_x
        snapped_y = norm_y
        snap_lines = []
        for sp in snap_points:
            if abs(norm_x - sp) < snap_threshold:
                snapped_x = sp
                snap_lines.append({'axis': 'v', 'val': sp})
            if abs(norm_y - sp) < snap_threshold:
                snapped_y = sp
                snap_lines.append({'axis': 'h', 'val': sp})
        self.preview_area.setSnapLines(snap_lines)
        self.text_pos = [snapped_x, snapped_y]
        self.update_preview()

    def on_preview_area_interaction_ended(self):
        if self._gradient_drag_start is not None:
            self._push_history()  # 自定义渐变拖动结束后记录历史
        self._gradient_drag_start = None
        self.preview_area.setSnapLines([])
        self.end_preview_interaction()

    def on_layout_mode_changed(self, text):
        self._mark_custom_preset()
        self.layout_mode = text
        self.update_preview()
        self._push_history()

    def _on_safe_zone_toggled(self, state):
        self.preview_area.setShowSafeZone(bool(state))

    def on_fetch_hitokoto(self):
        self.btn_hitokoto.setEnabled(False)
        self.btn_hitokoto.setText("拉取中...")
        self.btn_hitokoto.setToolTip("正在从一言 API 获取随机文案...")
        def fetch(_):
            req = urllib.request.Request("https://v1.hitokoto.cn/")
            req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode('utf-8'))
                return f"{data['hitokoto']}\n—— {data.get('from', '佚名')}"
        task = WorkerTask(fetch, None)
        task.signals.finished.connect(self._on_hitokoto_finished)
        task.signals.error.connect(self._on_hitokoto_error)
        self.worker_pool.start(task)

    def _on_hitokoto_finished(self, text):
        self.text_input.setPlainText(text)
        self.btn_hitokoto.setEnabled(True)
        self.btn_hitokoto.setText("获取灵感")
        self.btn_hitokoto.setToolTip("从一言 API 获取随机文案并填入输入框，点击即可替换当前文案")

    def _on_hitokoto_error(self, err):
        self.btn_hitokoto.setEnabled(True)
        self.btn_hitokoto.setText("重试")
        self.btn_hitokoto.setToolTip("网络超时或服务不可用，点击重试获取随机文案")
        print("Hitokoto Error:", err)

    def on_extract_bg_color(self):
        if not self.bg_image_path:
            return
        img = self.get_cached_bg_image(self.bg_image_path)
        if img is None:
            return
        # Extract prominent color via 1x1 resize
        avg_img = img.resize((1, 1), Image.Resampling.LANCZOS)
        r, g, b = avg_img.getpixel((0, 0))
        # Determine lightness and pick contrasting color
        lightness = 0.2126 * r + 0.7152 * g + 0.0722 * b
        if lightness > 128:
            # BG is light, suggest dark color
            target_rgb = (max(0, r - 120), max(0, g - 120), max(0, b - 120))
        else:
            # BG is dark, suggest light color
            target_rgb = (min(255, r + 120), min(255, g + 120), min(255, b + 120))
            
        self._mark_custom_preset()
        new_color = QColor(target_rgb[0], target_rgb[1], target_rgb[2])
        self.text_color = new_color
        if self.edit_target == "text":
            self.color_swatch.set_color_externally(new_color)
        self.update_preview()
        self._push_history()

    def on_run_benchmark(self):
        if self.label_perf is None:
            return
        result = self.run_preview_regression()
        self.label_perf.setText(
            "回测(ms): F640=%s F960=%s F960S=%s HQ960=%s HQ960S=%s EX1080=%s" % (
                result["fast_640x360"], result["fast_960x540"],
                result["fast_960x540_shadow"], result["hq_960x540"],
                result["hq_960x540_shadow"], result["export_1920x1080"]
            )
        )

    def on_style_preset_changed(self, name):
        if self._applying_state:
            return
        if name == "自定义":
            return
        if name in BUILTIN_COLOR_PRESETS:
            cfg = BUILTIN_COLOR_PRESETS[name]
            self.bg_color = QColor(cfg["bg_color"])
            self.bg_color2 = QColor(cfg.get("bg_color2", cfg["bg_color"]))
            self.bg_gradient_mode = cfg.get("gradient_mode", "纯色")
            orig_gd = cfg.get("gradient_direction", "上->下")
            self.bg_gradient_direction = self._normalize_gradient_direction(orig_gd)
            self.gradient_line = self._direction_to_gradient_line(orig_gd)
            self.radial_ellipse = list(cfg.get("radial_ellipse", [0.5, 0.5, 0.88, 0.88]))
            self.radial_radius = self._radial_ellipse_to_radius(self.radial_ellipse)
            self.radial_ellipse = self._radial_radius_to_ellipse(self.radial_radius)
            self.text_color = QColor(cfg["text_color"])
            if "stack" in cfg:
                self.check_stack.setChecked(bool(cfg["stack"]))
            if "shadow" in cfg:
                self.slider_shadow_offset.setValue(int(cfg["shadow"]))
        elif name in self.user_color_presets:
            cfg = self.user_color_presets[name]
            self.bg_color = QColor(cfg["bg_color"])
            self.bg_color2 = QColor(cfg.get("bg_color2", cfg["bg_color"]))
            self.bg_gradient_mode = cfg.get("gradient_mode", "纯色")
            orig_gd = cfg.get("gradient_direction", "上->下")
            self.bg_gradient_direction = self._normalize_gradient_direction(orig_gd)
            self.gradient_line = self._direction_to_gradient_line(orig_gd)
            self.radial_ellipse = list(cfg.get("radial_ellipse", [0.5, 0.5, 0.88, 0.88]))
            self.radial_radius = self._radial_ellipse_to_radius(self.radial_ellipse)
            self.radial_ellipse = self._radial_radius_to_ellipse(self.radial_radius)
            self.noise_intensity = max(0, min(100, cfg.get("noise_intensity", 40)))
            self.slider_noise_intensity.blockSignals(True)
            self.slider_noise_intensity.setValue(self.noise_intensity)
            self.slider_noise_intensity.blockSignals(False)
            self.label_noise_intensity.setText("噪点强度: %d" % self.noise_intensity)
            self.text_color = QColor(cfg["text_color"])
        self.combo_bg_gradient.blockSignals(True)
        self.combo_bg_gradient.setCurrentText(self.bg_gradient_mode)
        self.combo_bg_gradient.blockSignals(False)
        self.radial_radius = self._radial_ellipse_to_radius(self.radial_ellipse)
        self.slider_radial_radius.blockSignals(True)
        self.slider_radial_radius.setValue(self.radial_radius)
        self.slider_radial_radius.blockSignals(False)
        self.label_radial_radius.setText("中心区域大小: %d%%" % self.radial_radius)
        self._sync_gradient_direction_buttons()
        self._update_gradient_edit_ui()
        self.switch_target(self.edit_target)
        self.update_preview()
        self._push_history()

    def on_save_color_preset(self):
        self.label_preset_feedback.setText("")
        self.input_preset_name.clear()
        self.btn_save_preset.hide()
        self.input_preset_name.show()
        self.btn_preset_ok.show()
        self.btn_preset_cancel.show()
        self.input_preset_name.setFocus()

    def on_save_color_preset_cancel(self):
        self.input_preset_name.clear()
        self.input_preset_name.hide()
        self.btn_preset_ok.hide()
        self.btn_preset_cancel.hide()
        self.btn_save_preset.show()
        self.label_preset_feedback.setText("")

    def _validate_preset_name(self, name):
        name = name.strip()
        if not name:
            return False, "名称不能为空。"
        if (name == "自定义" or
                name in BUILTIN_COLOR_PRESETS or
                name in self.user_color_presets):
            return False, "名称重复，请使用其他名称。"
        return True, name

    def on_save_color_preset_confirm(self):
        ok, payload = self._validate_preset_name(self.input_preset_name.text())
        if not ok:
            self.label_preset_feedback.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.label_preset_feedback.setText(payload)
            return
        name = payload
        self.user_color_presets[name] = {
            "text_color": self.text_color.name(),
            "bg_color": self.bg_color.name(),
            "bg_color2": self.bg_color2.name(),
            "gradient_mode": self.bg_gradient_mode,
            "gradient_direction": self.bg_gradient_direction,
            "gradient_line": list(self.gradient_line),
            "radial_ellipse": list(self.radial_ellipse),
            "noise_intensity": self.noise_intensity,
        }
        try:
            self._save_user_color_presets()
        except Exception as e:
            self.user_color_presets.pop(name, None)
            self.label_preset_feedback.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.label_preset_feedback.setText("写入失败：%s" % e)
            return
        self.combo_preset.addItem(name)
        self.combo_preset.setCurrentText(name)
        self.input_preset_name.hide()
        self.btn_preset_ok.hide()
        self.btn_preset_cancel.hide()
        self.btn_save_preset.show()
        self.label_preset_feedback.setStyleSheet("color: #2ECC71; font-size: 11px;")
        self.label_preset_feedback.setText("已保存配色：%s" % name)
        self._push_history()

    def eventFilter(self, obj, event):
        """阻止配色预设下拉在右键时收起，以便显示上下文菜单"""
        if obj is self._preset_viewport and event.type() == QEvent.Type.MouseButtonRelease:
            if isinstance(event, QMouseEvent) and event.button() == Qt.MouseButton.RightButton:
                return True  # 拦截右键释放，防止下拉关闭
        return False

    def on_preset_context_menu(self, pos):
        view = self.combo_preset.view()
        index = view.indexAt(pos)
        if not index.isValid():
            return
        name = index.data()
        if name not in self.user_color_presets:
            return
        menu = QMenu(self)
        action_delete = menu.addAction("删除配色")
        selected = menu.exec(view.mapToGlobal(pos))
        if selected == action_delete:
            self.delete_user_preset(name)

    def delete_user_preset(self, name):
        if name not in self.user_color_presets:
            return
        self.user_color_presets.pop(name, None)
        try:
            self._save_user_color_presets()
        except Exception as e:
            self.label_preset_feedback.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.label_preset_feedback.setText("删除失败：%s" % e)
            return
        idx = self.combo_preset.findText(name)
        if idx >= 0:
            self.combo_preset.removeItem(idx)
        self.combo_preset.setCurrentText("自定义")
        self.label_preset_feedback.setStyleSheet("color: #A0A0A0; font-size: 11px;")
        self.label_preset_feedback.setText("已删除配色：%s" % name)

    def _preset_to_shareable_dict(self, name, cfg):
        """标准化预设为可分享的 dict，仅包含配色字段。"""
        return {
            "text_color": cfg.get("text_color", "#212122"),
            "bg_color": cfg.get("bg_color", "#F7F7F8"),
            "bg_color2": cfg.get("bg_color2", cfg.get("bg_color", "#F7F7F8")),
            "gradient_mode": cfg.get("gradient_mode", "纯色"),
            "gradient_direction": cfg.get("gradient_direction", "上->下"),
            "gradient_line": cfg.get("gradient_line", [0.5, 0.0, 0.5, 1.0]),
            "radial_ellipse": cfg.get("radial_ellipse", [0.5, 0.5, 0.88, 0.88]),
        }

    def on_copy_share_code(self):
        """将当前配色编码为 Base64 分享码并复制到剪贴板。"""
        name = self.combo_preset.currentText()
        if name in BUILTIN_COLOR_PRESETS:
            cfg = BUILTIN_COLOR_PRESETS[name]
        elif name in self.user_color_presets:
            cfg = self.user_color_presets[name]
        else:
            cfg = self._preset_to_shareable_dict("自定义", {
                "text_color": self.text_color.name(),
                "bg_color": self.bg_color.name(),
                "bg_color2": self.bg_color2.name(),
                "gradient_mode": self.bg_gradient_mode,
                "gradient_direction": self.bg_gradient_direction,
                "gradient_line": list(self.gradient_line),
                "radial_ellipse": list(self.radial_ellipse),
            })
        payload = {name if name != "自定义" else "当前配色": cfg}
        try:
            raw = json.dumps(payload, ensure_ascii=False)
            code = base64.b64encode(raw.encode("utf-8")).decode("ascii")
            QApplication.clipboard().setText(code)
            self.label_preset_feedback.setStyleSheet("color: #2ECC71; font-size: 11px;")
            self.label_preset_feedback.setText("分享码已复制到剪贴板")
        except Exception as e:
            self.label_preset_feedback.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.label_preset_feedback.setText("复制失败：%s" % e)

    def on_paste_share_code(self):
        """从剪贴板或输入框解析分享码，合并到用户配色。"""
        code, ok = QInputDialog.getText(
            self, "粘贴分享码", "请粘贴分享码（或留空使用剪贴板内容）：",
            QLineEdit.EchoMode.Normal, ""
        )
        if not ok:
            return
        if not code.strip():
            code = QApplication.clipboard().text()
        code = code.strip()
        if not code:
            self.label_preset_feedback.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.label_preset_feedback.setText("分享码为空")
            return
        try:
            raw = base64.b64decode(code.encode("ascii")).decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("无效格式")
            merged = 0
            for pname, pcfg in data.items():
                if not isinstance(pname, str) or not isinstance(pcfg, dict):
                    continue
                tc = pcfg.get("text_color")
                bg = pcfg.get("bg_color")
                if not isinstance(tc, str) or not isinstance(bg, str):
                    continue
                self.user_color_presets[pname] = self._preset_to_shareable_dict(pname, pcfg)
                merged += 1
            if merged == 0:
                self.label_preset_feedback.setStyleSheet("color: #E74C3C; font-size: 11px;")
                self.label_preset_feedback.setText("未解析到有效配色")
                return
            self._save_user_color_presets()
            self._refresh_preset_combo()
            self.label_preset_feedback.setStyleSheet("color: #2ECC71; font-size: 11px;")
            self.label_preset_feedback.setText("已导入 %d 个配色" % merged)
        except Exception as e:
            self.label_preset_feedback.setStyleSheet("color: #E74C3C; font-size: 11px;")
            self.label_preset_feedback.setText("解析失败：%s" % str(e)[:50])

    def _refresh_preset_combo(self):
        """刷新预设下拉框中的用户配色项。"""
        current = self.combo_preset.currentText()
        self.combo_preset.clear()
        self.combo_preset.addItem("自定义")
        self.combo_preset.addItems(list(BUILTIN_COLOR_PRESETS.keys()))
        for name in sorted(self.user_color_presets.keys()):
            self.combo_preset.addItem(name)
        idx = self.combo_preset.findText(current)
        if idx >= 0:
            self.combo_preset.setCurrentIndex(idx)

    def _mark_custom_preset(self):
        if self._applying_state:
            return
        if self.combo_preset.currentText() != "自定义":
            self.combo_preset.blockSignals(True)
            self.combo_preset.setCurrentText("自定义")
            self.combo_preset.blockSignals(False)

    def on_shadow_offset_changed(self, value):
        self._mark_custom_preset()
        self.label_shadow_offset.setText("阴影偏移量: %.2f" % (value / 100.0))
        self.update_preview()

    def on_stack_toggled(self, state):
        self._mark_custom_preset()
        self.update_preview()
        self._push_history()

    def on_italic_toggled(self, state):
        self._mark_custom_preset()
        self.update_preview()
        self._push_history()

    def on_noise_toggled(self, state):
        self._mark_custom_preset()
        self.enable_noise = bool(state)
        self._update_noise_edit_ui()
        self.update_preview()
        self._push_history()

    def on_noise_intensity_changed(self, value):
        self._mark_custom_preset()
        self.noise_intensity = value
        self.label_noise_intensity.setText("噪点强度: %d" % value)
        self.update_preview()

    def _update_noise_edit_ui(self):
        show = self.enable_noise
        self.label_noise_intensity.setVisible(show)
        self.slider_noise_intensity.setVisible(show)

    def switch_target(self, target):
        self.edit_target = target
        if target == "text":
            color = self.text_color
        elif target == "bg":
            color = self.bg_color
        else:
            color = self.bg_color2
        self.color_swatch.set_color_externally(color)
        self._update_color_code_input()

    def _update_color_code_input(self):
        """同步当前色号到色块和 Hex 输入框"""
        if self.input_color_code.hasFocus():
            return
        if self.edit_target == "text":
            c = self.text_color
        elif self.edit_target == "bg":
            c = self.bg_color
        else:
            c = self.bg_color2
        self.color_swatch.set_color_externally(c)

    def _on_color_code_edited(self):
        """用户输入色号后应用（由 ColorSwatchWidget 内部处理，此处保留兼容）"""
        raw = self.input_color_code.text().strip()
        if not raw:
            self._update_color_code_input()
            return
        if not raw.startswith("#"):
            raw = "#" + raw
        c = QColor(raw)
        if not c.isValid():
            self._update_color_code_input()
            return
        self._mark_custom_preset()
        if self.edit_target == "text":
            self.text_color = c
        elif self.edit_target == "bg":
            self.bg_color = c
        else:
            self.bg_color2 = c
        self.color_swatch.set_color_externally(c)
        self.update_preview()
        self._push_history()

    def handle_color_change(self, color):
        self._mark_custom_preset()
        if self.edit_target == "text":
            self.text_color = color
        elif self.edit_target == "bg":
            self.bg_color = color
        else:
            self.bg_color2 = color
        self._update_color_code_input()
        self._inline_text_color.refresh()
        self._inline_bg_color.refresh()
        self._inline_bg_color2.refresh()
        self.update_preview()

    def begin_preview_interaction(self):
        if not self.preview_interacting:
            self.preview_interacting = True
            self.update_preview()

    def end_preview_interaction(self):
        if self.preview_interacting:
            self.preview_interacting = False
            self.update_preview()
            self._push_history()

    def on_picker_interaction_changed(self, interacting):
        if interacting:
            self.begin_preview_interaction()
        else:
            self.end_preview_interaction()
            self._push_history()

    def _process_dynamic_variables(self, text):
        if not text:
            return text
        now = datetime.now()
        text = text.replace("[TIME]", now.strftime("%H:%M"))
        text = text.replace("[DATE]", now.strftime("%Y-%m-%d"))
        
        def countdown_replacer(match):
            target_date_str = match.group(1)
            try:
                target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
                delta = (target_date - now).days
                return str(max(0, delta))
            except Exception:
                return match.group(0)
                
        text = re.sub(r'\[COUNTDOWN:(\d{4}-\d{2}-\d{2})\]', countdown_replacer, text)
        return text

    def _build_render_state(self):
        font_name = self.combo_font.currentText()
        font_path = self.font_dict.get(font_name, "C:/Windows/Fonts/msyhbd.ttc")
        text = self._get_text_input_value()
        processed_text = self._process_dynamic_variables(text)
        use_fallback = bool(processed_text and (
            self._use_fallback_font(font_name) or self._need_cjk_fallback(font_name, processed_text)
        ))
        return {
            "bg_rgb": (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue()),
            "bg2_rgb": (self.bg_color2.red(), self.bg_color2.green(), self.bg_color2.blue()),
            "bg_gradient_mode": self.bg_gradient_mode,
            "bg_gradient_direction": self.bg_gradient_direction,
            "gradient_line": list(self.gradient_line),
            "radial_ellipse": list(self.radial_ellipse),
            "bg_image_path": self.bg_image_path,
            "bg_image_opacity": self.bg_image_opacity,
            "bg_blur_value": self.slider_bg_blur.value(),
            "bg_vignette_value": self.slider_bg_vignette.value(),
            "text_rgb": (self.text_color.red(), self.text_color.green(), self.text_color.blue()),
            "font_path": font_path,
            "use_fallback": use_fallback,
            "text": processed_text,
            "size_value": self.slider_size.value(),
            "letter_spacing_value": self.slider_letter_spacing.value(),
            "shadow_offset_value": self.slider_shadow_offset.value(),
            "stack_enabled": self.check_stack.isChecked(),
            "italic_enabled": self.check_italic.isChecked(),
            "noise_enabled": self.check_noise.isChecked(),
            "noise_intensity": self.noise_intensity,
            "layout_mode": self.combo_layout_mode.currentText(),
            "text_pos": list(self.text_pos),
            "preview_profile": self.preview_profile,
            "export_high_quality": self.export_high_quality,
        }

    def _capture_ui_state(self):
        return {
            "text": self._get_text_input_value(),
            "font": self.combo_font.currentText(),
            "size": self.slider_size.value(),
            "letter": self.slider_letter_spacing.value(),
            "aspect": self.combo_aspect.currentText(),
            "stack": self.check_stack.isChecked(),
            "shadow": self.slider_shadow_offset.value(),
            "italic": self.check_italic.isChecked(),
            "text_color": self.text_color.name(),
            "bg_color": self.bg_color.name(),
            "bg_color2": self.bg_color2.name(),
            "bg_gradient_mode": self.combo_bg_gradient.currentText(),
            "bg_gradient_direction": self.bg_gradient_direction,
            "gradient_line": list(self.gradient_line),
            "radial_ellipse": list(self.radial_ellipse),
            "bg_image_path": self.bg_image_path,
            "bg_image_opacity": self.slider_bg_opacity.value(),
            "bg_blur": self.slider_bg_blur.value(),
            "bg_vignette": self.slider_bg_vignette.value(),
            "target": self.edit_target,
            "preset": self.combo_preset.currentText(),
            "profile": self.combo_preview_quality.currentText(),
            "export_hq": self.check_export_hq.isChecked(),
            "noise": self.check_noise.isChecked(),
            "noise_intensity": self.noise_intensity,
            "text_pos": list(self.text_pos),
            "layout_mode": self.combo_layout_mode.currentText(),
        }

    def _apply_ui_state(self, state):
        self._applying_state = True
        try:
            self.text_input.setPlainText(state["text"])
            t = state["text"]
            if t in PRESET_TEXTS:
                self.combo_preset_text.blockSignals(True)
                self.combo_preset_text.setCurrentText(t)
                self.combo_preset_text.blockSignals(False)
            else:
                self.combo_preset_text.blockSignals(True)
                self.combo_preset_text.setCurrentText("自定义")
                self.combo_preset_text.blockSignals(False)
            self.combo_font.setCurrentText(state["font"])
            self.slider_size.setValue(state["size"])
            self.slider_letter_spacing.setValue(state["letter"])
            self.combo_aspect.setCurrentText(state["aspect"])
            self.check_stack.setChecked(state["stack"])
            self.slider_shadow_offset.setValue(state["shadow"])
            self.check_italic.setChecked(state["italic"])
            self.text_color = QColor(state["text_color"])
            self.bg_color = QColor(state["bg_color"])
            self.bg_color2 = QColor(state.get("bg_color2", state["bg_color"]))
            self.bg_gradient_mode = state.get("bg_gradient_mode", "纯色")
            orig_gd = state.get("bg_gradient_direction", "上->下")
            self.bg_gradient_direction = self._normalize_gradient_direction(orig_gd)
            self.gradient_line = list(state.get("gradient_line", self._direction_to_gradient_line(orig_gd)))
            self.radial_ellipse = list(state.get("radial_ellipse", [0.5, 0.5, 0.88, 0.88]))
            self.radial_radius = self._radial_ellipse_to_radius(self.radial_ellipse)
            self.radial_ellipse = self._radial_radius_to_ellipse(self.radial_radius)
            self.slider_radial_radius.blockSignals(True)
            self.slider_radial_radius.setValue(self.radial_radius)
            self.slider_radial_radius.blockSignals(False)
            self.label_radial_radius.setText("中心区域大小: %d%%" % self.radial_radius)
            self.combo_bg_gradient.blockSignals(True)
            self.combo_bg_gradient.setCurrentText(self.bg_gradient_mode)
            self.combo_bg_gradient.blockSignals(False)
            self._sync_gradient_direction_buttons()
            self._update_gradient_edit_ui()
            self._update_noise_edit_ui()
            self.bg_image_path = state.get("bg_image_path")
            self.slider_bg_opacity.setValue(state.get("bg_image_opacity", 100))
            self.bg_image_opacity = max(0.0, min(1.0, self.slider_bg_opacity.value() / 100.0))
            self.slider_bg_blur.setValue(state.get("bg_blur", 0))
            self.slider_bg_vignette.setValue(state.get("bg_vignette", 0))
            self.text_pos = list(state.get("text_pos", [0.5, 0.5]))
            self._update_bg_image_hint()
            self.combo_preset.setCurrentText(state["preset"])
            self.combo_preview_quality.setCurrentText(state["profile"])
            self.check_export_hq.setChecked(state["export_hq"])
            self.check_noise.setChecked(state.get("noise", False))
            self.noise_intensity = max(0, min(100, state.get("noise_intensity", 40)))
            self.slider_noise_intensity.blockSignals(True)
            self.slider_noise_intensity.setValue(self.noise_intensity)
            self.slider_noise_intensity.blockSignals(False)
            self.label_noise_intensity.setText("噪点强度: %d" % self.noise_intensity)
            self.combo_layout_mode.setCurrentText(state.get("layout_mode", "自由排列"))
            self.switch_target(state["target"])
            self.update_font_hint()
        finally:
            self._applying_state = False
        self.update_preview()

    def _push_history(self):
        if self._applying_state:
            return
        current = self._capture_ui_state()
        if self.history and self.history[-1] == current:
            return
        self.history.append(current)
        if len(self.history) > 100:
            self.history = self.history[-100:]
        self.future.clear()

    def on_undo(self):
        if len(self.history) <= 1:
            return
        current = self.history.pop()
        self.future.append(current)
        self._apply_ui_state(self.history[-1])

    def on_redo(self):
        if not self.future:
            return
        target = self.future.pop()
        self.history.append(target)
        self._apply_ui_state(target)

    def _get_quality_settings(self, w, h, is_preview, state, fast_preview):
        pixels = w * h
        if is_preview:
            if fast_preview:
                return 1, 6, True
            profile = PREVIEW_PROFILES.get(state.get("preview_profile", "平衡"), PREVIEW_PROFILES["平衡"])
            small = pixels < 600000
            ss = profile["ss_small"] if small else profile["ss_large"]
            steps = profile["steps_small"] if small else profile["steps_large"]
            return ss, steps, True

        if state.get("export_high_quality", True):
            ss = 4 if pixels <= 2073600 else (3 if pixels <= 3686400 else 2)
            return ss, 12, True
        ss = 2 if pixels <= 3686400 else 1
        return ss, 8, True

    def _adaptive_shadow_steps(self, base_steps, shadow_offset, is_preview, fast_preview):
        # 极小偏移会在大字号时造成肉眼可见叠字，直接关闭叠影
        if shadow_offset <= 0.35:
            return 0
        if not is_preview:
            return base_steps
        # 交互期偏移越大，步数越少，保持深度感同时降低重绘成本
        target_depth = 12.0 if fast_preview else 14.0
        steps = int(round(target_depth / max(0.12, shadow_offset)))
        min_steps = 3 if fast_preview else 4
        return max(min_steps, min(base_steps, steps))

    def _blend_background_image(self, base_img, image_path, opacity, is_preview):
        if not image_path or opacity <= 0:
            return base_img
        src = self.get_cached_bg_image(image_path)
        if src is None:
            return base_img
        w, h = base_img.size
        sw, sh = src.size
        if sw <= 0 or sh <= 0 or w <= 0 or h <= 0:
            return base_img
        scale = max(w / sw, h / sh)
        nw = max(1, int(sw * scale))
        nh = max(1, int(sh * scale))
        resample = Image.Resampling.BILINEAR if is_preview else Image.Resampling.LANCZOS
        fitted = src.resize((nw, nh), resample)
        left = max(0, (nw - w) // 2)
        top = max(0, (nh - h) // 2)
        fitted = fitted.crop((left, top, left + w, top + h)).convert("RGB")
        if opacity >= 0.999:
            return fitted
        try:
            return Image.blend(base_img, fitted, float(opacity))
        except Exception:
            return base_img

    def _get_cached_gradient_mask(self, mode, direction, gradient_line=None, radial_ellipse=None):
        key = (mode, direction, tuple(gradient_line) if gradient_line else None,
               tuple(radial_ellipse) if radial_ellipse else None)
        if key in self._gradient_masks:
            return self._gradient_masks[key]
            
        mask = Image.new("L", (256, 256))
        draw = ImageDraw.Draw(mask)
        
        if mode == "线性渐变":
            if direction == "自定义" and gradient_line and len(gradient_line) >= 4:
                sx, sy = gradient_line[0] * 255, gradient_line[1] * 255
                ex, ey = gradient_line[2] * 255, gradient_line[3] * 255
                dx, dy = ex - sx, ey - sy
                length_sq = dx * dx + dy * dy
                if length_sq < 1e-6:
                    length_sq = 1.0
                for y in range(256):
                    for x in range(256):
                        px, py = x - sx, y - sy
                        t = (px * dx + py * dy) / length_sq
                        t = max(0.0, min(1.0, t))
                        mask.putpixel((x, y), int(t * 255))
            elif direction == "下->上":
                for y in range(256):
                    draw.line((0, y, 256, y), fill=int(255 - y))
            elif direction == "左->右":
                for x in range(256):
                    draw.line((x, 0, x, 256), fill=int(x))
            elif direction == "右->左":
                for x in range(256):
                    draw.line((x, 0, x, 256), fill=int(255 - x))
            else:  # 上->下（默认）
                for y in range(256):
                    draw.line((0, y, 256, y), fill=int(y))
        else:  # 径向渐变，椭圆中心+边缘点，smoothstep 柔化边缘过渡
            def _smoothstep(t):
                t = max(0.0, min(1.0, t))
                return t * t * (3.0 - 2.0 * t)

            if radial_ellipse and len(radial_ellipse) >= 4:
                cx, cy = radial_ellipse[0] * 255, radial_ellipse[1] * 255
                ex, ey = radial_ellipse[2] * 255, radial_ellipse[3] * 255
                rx = max(1.0, abs(ex - cx))
                ry = max(1.0, abs(ey - cy))
                for y in range(256):
                    for x in range(256):
                        dx_n = (x - cx) / rx
                        dy_n = (y - cy) / ry
                        t_raw = math.sqrt(dx_n * dx_n + dy_n * dy_n)
                        t_raw = min(1.0, t_raw)
                        t = _smoothstep(t_raw)
                        mask.putpixel((x, y), int(t * 255))
            else:
                cx, cy = 127.5, 127.5
                max_r = math.sqrt(cx*cx + cy*cy)
                for y in range(256):
                    for x in range(256):
                        d = math.sqrt((x - cx)**2 + (y - cy)**2)
                        t_raw = min(1.0, d / max_r)
                        t = _smoothstep(t_raw)
                        mask.putpixel((x, y), int(t * 255))
                    
        self._gradient_masks[key] = mask
        return mask

    def _build_gradient_background(self, w, h, bg_rgb, bg2_rgb, mode, direction, gradient_line=None, radial_ellipse=None):
        if mode == "纯色":
            return Image.new("RGB", (w, h), bg_rgb)
            
        base_img = Image.new("RGB", (w, h), bg_rgb)
        secondary_img = Image.new("RGB", (w, h), bg2_rgb)
        
        mask = self._get_cached_gradient_mask(mode, direction, gradient_line, radial_ellipse)
        if mode == "径向渐变":
            mask = mask.filter(ImageFilter.GaussianBlur(radius=1.2))
        scaled_mask = mask.resize((w, h), Image.Resampling.BILINEAR)
        
        return Image.composite(secondary_img, base_img, scaled_mask)

    def _get_text_metrics(self, draw, font_path, font_size, text, letter_spacing):
        key = (font_path, font_size, text, letter_spacing)
        with self.text_metrics_lock:
            cached = self.text_metrics_cache.get(key)
        if cached is not None:
            return cached

        font = self.get_cached_font(font_path, max(5, font_size))
        char_widths = []
        for ch in text:
            cb = draw.textbbox((0, 0), ch, font=font)
            char_widths.append(cb[2] - cb[0])
        tb = draw.textbbox((0, 0), text, font=font)
        if letter_spacing == 0:
            total_w = tb[2] - tb[0]
        else:
            total_w = sum(char_widths) + letter_spacing * (len(text) - 1)
        metrics = {
            "bbox": tb,
            "char_widths": char_widths,
            "total_w": total_w,
        }
        with self.text_metrics_lock:
            if len(self.text_metrics_cache) > 400:
                self.text_metrics_cache.clear()
            self.text_metrics_cache[key] = metrics
        return metrics

    def _render_image_from_state(self, w, h, is_preview, state, fast_preview=False):
        bg_rgb = state["bg_rgb"]
        bg2_rgb = state.get("bg2_rgb", bg_rgb)
        bg_gradient_mode = state.get("bg_gradient_mode", "纯色")
        bg_gradient_direction = state.get("bg_gradient_direction", "上->下")
        gradient_line = state.get("gradient_line", [0.5, 0.0, 0.5, 1.0])
        radial_ellipse = state.get("radial_ellipse", [0.5, 0.5, 0.88, 0.88])
        img = self._build_gradient_background(
            w, h, bg_rgb, bg2_rgb, bg_gradient_mode, bg_gradient_direction,
            gradient_line, radial_ellipse
        )
        orig_bg = self._blend_background_image(
            img,
            state.get("bg_image_path"),
            float(state.get("bg_image_opacity", 0.0)),
            is_preview
        )
        
        bg_blur = state.get("bg_blur_value", 0)
        if bg_blur > 0:
            scale_f = max(1.0, w / 960.0) if not is_preview else 1.0
            radius = (bg_blur / 100.0) * 40 * scale_f
            try:
                img = orig_bg.filter(ImageFilter.GaussianBlur(radius=radius))
            except Exception:
                img = orig_bg
        else:
            img = orig_bg
            
        bg_vignette = state.get("bg_vignette_value", 0)
        if bg_vignette > 0:
            v_alpha = int((bg_vignette / 100.0) * 230)
            vig_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            vig_draw = ImageDraw.Draw(vig_img)
            cx, cy = w / 2, h / 2
            max_r = math.sqrt(cx*cx + cy*cy)
            # Create a simple radial gradient mask for vignette
            # To optimize, we draw concentric circles
            steps = 40 if is_preview else 100
            for i in range(steps):
                r = max_r * (1.0 - i/steps)
                alpha = int(max(0, min(v_alpha, (1.0 - i/steps)**2 * v_alpha)))
                vig_draw.ellipse(
                    (cx - r, cy - r, cx + r, cy + r),
                    fill=(0, 0, 0, alpha)
                )
            # Ensure outer corners are dark
            final_vig = Image.new("RGBA", (w, h), (0, 0, 0, v_alpha))
            final_vig.alpha_composite(vig_img)
            img = img.convert("RGBA")
            img.alpha_composite(final_vig)
            img = img.convert("RGB")
            
        ss, shadow_steps, shadow_blur = self._get_quality_settings(w, h, is_preview, state, fast_preview)
        tw, th = w * ss, h * ss
        # 扩大 text_layer 避免长文本/大字号被裁剪（padding 容纳溢出与阴影）
        shadow_offset = state["shadow_offset_value"] / 100.00 * ss
        shadow_steps_calc = self._adaptive_shadow_steps(shadow_steps, shadow_offset, is_preview, fast_preview)
        pad = int(max(tw, th) * 0.6) + int(max(0, shadow_offset * shadow_steps_calc)) + 400
        tw_full, th_full = tw + 2 * pad, th + 2 * pad
        text_layer = Image.new("RGBA", (tw_full, th_full), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)
        draw.fontmode = "L"

        scale = w / 1920
        fs = int(state["size_value"] * (scale if is_preview else 1.0)) * ss
        font_path = state["font_path"]
        if state["use_fallback"]:
            font_path = "C:/Windows/Fonts/msyhbd.ttc"
        font_size = max(5, fs)
        font = self.get_cached_font(font_path, font_size)

        text = state["text"]
        tc = state["text_rgb"]
        letter_spacing = state["letter_spacing_value"] * ss

        shadow_offset = state["shadow_offset_value"] / 100.00 * ss
        shadow_steps = self._adaptive_shadow_steps(shadow_steps, shadow_offset, is_preview, fast_preview)
        shadow_rgb = (max(0, int(tc[0] * 0.2)), max(0, int(tc[1] * 0.2)),
                      max(0, int(tc[2] * 0.2)))
        effective_stack = state["stack_enabled"] and shadow_steps > 0

        def draw_shadow_only(draw_obj, cx, cy, draw_fn):
            for i in range(shadow_steps, 0, -1):
                off = i * shadow_offset
                draw_fn(draw_obj, cx + off, cy + off,
                        (shadow_rgb[0], shadow_rgb[1], shadow_rgb[2], 255))

        def draw_main_only(draw_obj, cx, cy, draw_fn):
            draw_fn(draw_obj, cx, cy, (tc[0], tc[1], tc[2], 255))

        if text:
            layout_mode = state.get("layout_mode", "自由排列")
            text_pos = state["text_pos"]
            
            if layout_mode == "主副标题" and "\n" in text:
                parts = text.split("\n", 1)
                title = parts[0]
                subtitle = parts[1]
                
                title_font = font
                subtitle_font_size = max(5, int(font_size * 0.35))
                subtitle_font = self.get_cached_font(font_path, subtitle_font_size)
                
                title_metrics = self._get_text_metrics(draw, font_path, font_size, title, letter_spacing)
                subtitle_metrics = self._get_text_metrics(draw, font_path, subtitle_font_size, subtitle, letter_spacing * 0.5)
                
                block_w = max(title_metrics["total_w"], subtitle_metrics["total_w"])
                gap = int(font_size * 0.3)
                block_h = (title_metrics["bbox"][3] - title_metrics["bbox"][1]) + gap + (subtitle_metrics["bbox"][3] - subtitle_metrics["bbox"][1])
                
                cx = tw * text_pos[0] + pad
                cy = th * text_pos[1] + pad
                
                title_y = cy - block_h / 2
                subtitle_y = title_y + (title_metrics["bbox"][3] - title_metrics["bbox"][1]) + gap
                
                def grouped_draw(draw_obj, px, py, fill):
                    tcw = title_metrics.get("char_widths")
                    if not tcw or len(tcw) != len(title):
                        tcw = [title_metrics["total_w"] / max(1, len(title))] * len(title)
                    scw = subtitle_metrics.get("char_widths")
                    if not scw or len(scw) != len(subtitle):
                        scw = [subtitle_metrics["total_w"] / max(1, len(subtitle))] * len(subtitle)
                    tx = px - title_metrics["total_w"] / 2
                    for j, ch in enumerate(title):
                        draw_obj.text((tx, py - block_h / 2), ch, font=title_font, fill=fill)
                        tx += tcw[j] + letter_spacing
                    sx = px - subtitle_metrics["total_w"] / 2
                    for j, ch in enumerate(subtitle):
                        draw_obj.text((sx, py - block_h / 2 + (title_metrics["bbox"][3] - title_metrics["bbox"][1]) + gap), ch, font=subtitle_font, fill=fill)
                        sx += scw[j] + letter_spacing * 0.5

                if effective_stack:
                    shadow_layer = Image.new("RGBA", (tw_full, th_full), (0, 0, 0, 0))
                    shadow_draw = ImageDraw.Draw(shadow_layer)
                    shadow_draw.fontmode = "L"
                    draw_shadow_only(shadow_draw, cx, cy, grouped_draw)
                    if shadow_blur:
                        blur_r = 1 if (is_preview and ss == 1) else max(2, ss)
                        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_r))
                    text_layer.paste(shadow_layer, (0, 0), shadow_layer)
                    draw = ImageDraw.Draw(text_layer)
                    draw.fontmode = "L"
                draw_main_only(draw, cx, cy, grouped_draw)

            elif layout_mode == "英文底纹+中文小字" and "\n" in text:
                parts = text.split("\n", 1)
                bg_text = parts[0]
                fg_text = parts[1]
                
                bg_font_size = max(5, int(font_size * 2.5))
                bg_font = self.get_cached_font("C:/Windows/Fonts/impact.ttf", bg_font_size) # Impact for background
                fg_font = font
                
                bg_metrics = self._get_text_metrics(draw, "C:/Windows/Fonts/impact.ttf", bg_font_size, bg_text, letter_spacing * 1.5)
                fg_metrics = self._get_text_metrics(draw, font_path, font_size, fg_text, letter_spacing)
                
                cx = tw * text_pos[0] + pad
                cy = th * text_pos[1] + pad
                
                def bg_draw(draw_obj, px, py, fill):
                    bcw = bg_metrics.get("char_widths")
                    if not bcw or len(bcw) != len(bg_text):
                        bcw = [bg_metrics["total_w"] / max(1, len(bg_text))] * len(bg_text)
                    bx = px - bg_metrics["total_w"] / 2
                    bg_fill = (fill[0], fill[1], fill[2], 25) # low opacity for background
                    for j, ch in enumerate(bg_text):
                        draw_obj.text((bx, py - (bg_metrics["bbox"][3] - bg_metrics["bbox"][1])/2), ch, font=bg_font, fill=bg_fill)
                        bx += bcw[j] + letter_spacing * 1.5

                def fg_draw(draw_obj, px, py, fill):
                    fcw = fg_metrics.get("char_widths")
                    if not fcw or len(fcw) != len(fg_text):
                        fcw = [fg_metrics["total_w"] / max(1, len(fg_text))] * len(fg_text)
                    fx = px - fg_metrics["total_w"] / 2
                    for j, ch in enumerate(fg_text):
                        draw_obj.text((fx, py - (fg_metrics["bbox"][3] - fg_metrics["bbox"][1])/2), ch, font=fg_font, fill=fill)
                        fx += fcw[j] + letter_spacing

                if effective_stack:
                    shadow_layer = Image.new("RGBA", (tw_full, th_full), (0, 0, 0, 0))
                    shadow_draw = ImageDraw.Draw(shadow_layer)
                    shadow_draw.fontmode = "L"
                    draw_shadow_only(shadow_draw, cx, cy, fg_draw)
                    if shadow_blur:
                        blur_r = 1 if (is_preview and ss == 1) else max(2, ss)
                        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_r))
                    text_layer.paste(shadow_layer, (0, 0), shadow_layer)
                    draw = ImageDraw.Draw(text_layer)
                    draw.fontmode = "L"
                
                bg_draw(draw, cx, cy, (tc[0],tc[1],tc[2],255))
                draw_main_only(draw, cx, cy, fg_draw)
            
            else:
                line_gap = max(2, int(font_size * 0.22))
                if letter_spacing == 0:
                    is_multiline = "\n" in text
                    if is_multiline:
                        bbox = draw.multiline_textbbox(
                            (0, 0), text, font=font, spacing=line_gap, align="center"
                        )
                    else:
                        metrics = self._get_text_metrics(draw, font_path, font_size, text, 0)
                        bbox = metrics["bbox"]
                    cx = (bbox[0] + bbox[2]) / 2
                    cy = (bbox[1] + bbox[3]) / 2
                    x = tw * text_pos[0] - cx + pad
                    y = th * text_pos[1] - cy + pad

                    def simple_draw(draw_obj, px, py, fill):
                        if is_multiline:
                            draw_obj.multiline_text(
                                (px, py), text, font=font, fill=fill,
                                spacing=line_gap, align="center"
                            )
                        else:
                            draw_obj.text((px, py), text, font=font, fill=fill)

                    if effective_stack:
                        shadow_layer = Image.new("RGBA", (tw_full, th_full), (0, 0, 0, 0))
                        shadow_draw = ImageDraw.Draw(shadow_layer)
                        shadow_draw.fontmode = "L"
                        draw_shadow_only(shadow_draw, x, y, simple_draw)
                        if shadow_blur:
                            blur_r = 1 if (is_preview and ss == 1) else max(2, ss)
                            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_r))
                        text_layer.paste(shadow_layer, (0, 0), shadow_layer)
                        draw = ImageDraw.Draw(text_layer)
                        draw.fontmode = "L"
                    draw_main_only(draw, x, y, simple_draw)
                else:
                    if "\n" in text:
                        lines = text.split("\n")
                        ref_bbox = draw.textbbox((0, 0), "Ag", font=font)
                        line_h = max(1, ref_bbox[3] - ref_bbox[1])
                        lines_info = []
                        block_w = 0
                        block_h = 0
                        for idx, line in enumerate(lines):
                            char_widths = []
                            for ch in line:
                                cb = draw.textbbox((0, 0), ch, font=font)
                                char_widths.append(cb[2] - cb[0])
                            if char_widths:
                                line_w = sum(char_widths) + letter_spacing * (len(char_widths) - 1)
                            else:
                                line_w = 0
                            lines_info.append((line, char_widths, line_w))
                            block_w = max(block_w, line_w)
                            block_h += line_h
                            if idx < len(lines) - 1:
                                block_h += line_gap
                        x = tw * text_pos[0] - block_w / 2 + pad
                        y = th * text_pos[1] - block_h / 2 + pad

                        def char_draw(draw_obj, px, py, fill):
                            cy = py
                            for line, cws, line_w in lines_info:
                                cx = px + (block_w - line_w) / 2
                                for j, ch in enumerate(line):
                                    draw_obj.text((cx, cy), ch, font=font, fill=fill)
                                    cx += cws[j] + letter_spacing
                                cy += line_h + line_gap
                    else:
                        metrics = self._get_text_metrics(draw, font_path, font_size, text, letter_spacing)
                        char_widths = metrics["char_widths"]
                        total_w = metrics["total_w"]
                        bbox = metrics["bbox"]
                        cy = (bbox[1] + bbox[3]) / 2
                        x = tw * text_pos[0] - total_w / 2 + pad
                        y = th * text_pos[1] - cy + pad

                        def char_draw(draw_obj, px, py, fill):
                            for j, ch in enumerate(text):
                                draw_obj.text((px, py), ch, font=font, fill=fill)
                                px += char_widths[j] + letter_spacing

                    if effective_stack:
                        shadow_layer = Image.new("RGBA", (tw_full, th_full), (0, 0, 0, 0))
                        shadow_draw = ImageDraw.Draw(shadow_layer)
                        shadow_draw.fontmode = "L"
                        draw_shadow_only(shadow_draw, x, y, char_draw)
                        if shadow_blur:
                            blur_r = 1 if (is_preview and ss == 1) else max(2, ss)
                            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=blur_r))
                        text_layer.paste(shadow_layer, (0, 0), shadow_layer)
                        draw = ImageDraw.Draw(text_layer)
                        draw.fontmode = "L"
                    draw_main_only(draw, x, y, char_draw)

        # 裁剪回可见区域，去除 padding
        text_layer = text_layer.crop((pad, pad, pad + tw, pad + th))

        if state["italic_enabled"]:
            tx = -0.075 * th
            try:
                sheared = text_layer.transform(
                    text_layer.size, Image.Transform.AFFINE,
                    (1, 0.15, tx, 0, 1, 0),
                    resample=Image.Resampling.BICUBIC
                )
                text_layer = sheared
            except Exception:
                pass

        if state.get("noise_enabled", False):
            # Generate uniform noise and overlay lightly
            import random
            noise_intensity = max(0, min(100, state.get("noise_intensity", 40)))
            max_alpha = int(0.6 * noise_intensity)  # 0-100 -> 0-60
            noise_img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            noise_draw = ImageDraw.Draw(noise_img)
            # Procedural noise optimization: block stamp to save time
            block_size = 120 if is_preview else 240
            noise_block = Image.new("RGBA", (block_size, block_size), (0, 0, 0, 0))
            block_pixels = noise_block.load()
            for i in range(block_size):
                for j in range(block_size):
                    val = random.randint(0, 255)
                    alpha = random.randint(0, max_alpha) if max_alpha > 0 else 0
                    block_pixels[i, j] = (val, val, val, alpha)
            
            for y_off in range(0, h, block_size):
                for x_off in range(0, w, block_size):
                    noise_img.paste(noise_block, (x_off, y_off))
                    
            text_layer_resized = text_layer.resize((w, h), Image.Resampling.BILINEAR if is_preview else Image.Resampling.LANCZOS) if ss > 1 else text_layer
            img.paste(text_layer_resized, (0, 0), text_layer_resized)
            img = img.convert("RGBA")
            img.alpha_composite(noise_img)
            img = img.convert("RGB")
        else:
            if ss > 1:
                resample = Image.Resampling.BILINEAR if is_preview else Image.Resampling.LANCZOS
                text_layer = text_layer.resize((w, h), resample)
            img.paste(text_layer, (0, 0), text_layer)
            
        return img

    def generate_img(self, w, h, is_preview=True):
        try:
            state = self._build_render_state()
            return self._render_image_from_state(w, h, is_preview, state)
        except Exception as e:
            print("渲染图片出错:", e)
            return Image.new("RGB", (w, h), (0, 0, 0))

    def _render_preview_canvas_bytes(self, payload):
        display_w = payload["display_w"]
        display_h = payload["display_h"]
        fit_w = payload["fit_w"]
        fit_h = payload["fit_h"]
        state = payload["state"]
        fast_preview = payload.get("fast_preview", False)
        img = self._render_image_from_state(fit_w, fit_h, True, state, fast_preview)
        canvas = Image.new("RGB", (display_w, display_h), (0xD1, 0xD1, 0xD6))
        paste_x = (display_w - fit_w) // 2
        paste_y = (display_h - fit_h) // 2
        canvas.paste(img, (paste_x, paste_y))
        return display_w, display_h, canvas.tobytes("raw", "RGB")

    def _start_next_preview_task(self):
        if self.preview_running or self.preview_queued is None:
            return
        req_id, payload = self.preview_queued
        self.preview_queued = None
        self.preview_running = True
        task = PreviewRenderTask(req_id, payload, self._render_preview_canvas_bytes)
        task.signals.finished.connect(self._on_preview_task_finished)
        task.signals.error.connect(self._on_preview_task_error)
        self.preview_pool.start(task)

    def _on_preview_task_finished(self, req_id, w, h, data):
        self.preview_running = False
        if req_id == self.preview_latest_req_id:
            meta = self.preview_req_meta.pop(req_id, None)
            animate = meta.get("animate", False) if meta else False
            self._set_preview_from_bytes(w, h, data, animate=animate)
            if meta:
                elapsed_ms = (time.perf_counter() - meta["t0"]) * 1000.0
                self._update_perf_label(elapsed_ms, meta["fast"], meta["fit_w"], meta["fit_h"])
        self._start_next_preview_task()

    def _on_preview_task_error(self, req_id, message):
        self.preview_running = False
        self.preview_req_meta.pop(req_id, None)
        print("预览渲染出错:", message)
        self._start_next_preview_task()

    def _compute_preview_geometry(self):
        display_w = self.preview_area.width()
        display_h = self.preview_area.height()
        if display_w < 50 or display_h < 30:
            display_w = max(400, self.width() - 350)
            display_h = max(300, self.height() - 50)
        img_w, img_h = self._get_wallpaper_size()
        scale = min(display_w / img_w, display_h / img_h)
        fit_w = max(320, int(img_w * scale))
        fit_h = max(180, int(img_h * scale))
        return display_w, display_h, fit_w, fit_h

    def _set_preview_from_bytes(self, w, h, data, animate=True):
        qimg = QImage(data, w, h, w * 3, QImage.Format.Format_RGB888).copy()
        self.preview_area.setPixmapAnimated(QPixmap.fromImage(qimg), animate=animate)

    def _set_runtime_status(self, text):
        if self.label_perf is not None:
            self.label_perf.setText(text)

    def _update_perf_label(self, elapsed_ms, fast_preview, fit_w, fit_h):
        mode = "快速预览" if fast_preview else "高质量预览"
        self._set_runtime_status(
            "预览耗时: %.1f ms | 模式: %s | 分辨率: %dx%d" %
            (elapsed_ms, mode, fit_w, fit_h)
        )

    def _render_fast_preview_sync(self):
        display_w, display_h, fit_w, fit_h = self._compute_preview_geometry()
        if fit_w < 1 or fit_h < 1:
            return
        payload = {
            "display_w": display_w,
            "display_h": display_h,
            "fit_w": fit_w,
            "fit_h": fit_h,
            "state": self._build_render_state(),
            "fast_preview": True,
        }
        try:
            t0 = time.perf_counter()
            w, h, data = self._render_preview_canvas_bytes(payload)
            self._set_preview_from_bytes(w, h, data, animate=False)
            self._update_perf_label((time.perf_counter() - t0) * 1000.0, True, fit_w, fit_h)
        except Exception as e:
            print("快速预览渲染出错:", e)

    def run_preview_regression(self):
        """简单回测：输出预览渲染耗时，便于对比优化前后。"""
        state = self._build_render_state()
        shadow_state = dict(state)
        shadow_state["stack_enabled"] = True
        shadow_state["shadow_offset_value"] = max(60, state["shadow_offset_value"])
        cases = [
            ("fast_640x360", 640, 360, True, True, state),
            ("fast_960x540", 960, 540, True, True, state),
            ("fast_960x540_shadow", 960, 540, True, True, shadow_state),
            ("hq_960x540", 960, 540, True, False, state),
            ("hq_960x540_shadow", 960, 540, True, False, shadow_state),
            ("export_1920x1080", 1920, 1080, False, False, state),
        ]
        results = {}
        for name, w, h, is_preview, fast_preview, case_state in cases:
            runs = 3
            total_ms = 0.0
            for _ in range(runs):
                t0 = time.perf_counter()
                self._render_image_from_state(w, h, is_preview, case_state, fast_preview)
                total_ms += (time.perf_counter() - t0) * 1000.0
            results[name] = round(total_ms / runs, 2)
        print("Preview regression(ms):", results)
        return results

    def _get_wallpaper_filename(self, ext=".jpg"):
        text = self._get_text_input_value().strip()
        safe = "".join(c if c not in '\\/:*?"<>|' else "_" for c in text)
        safe = safe.replace("\n", "_")
        safe = safe.replace(" ", "_") or "wallpaper"
        date_str = datetime.now().strftime("%y%m%d")
        return "wallpaper_%s_%s%s" % (safe, date_str, ext)

    def _get_wallpaper_size(self):
        val = ASPECT_RATIOS.get(self.combo_aspect.currentText(), (16, 9))
        if val is None:
            try:
                user32 = ctypes.windll.user32
                return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            except Exception:
                return 1920, 1080
        rw, rh = val
        base = 1920
        if rw >= rh:
            return base, int(base * rh / rw)
        return int(base * rw / rh), base

    def update_preview(self):
        display_w, display_h, fit_w, fit_h = self._compute_preview_geometry()
        if fit_w < 1 or fit_h < 1:
            return
            
        state = self._build_render_state()
        animate = False
        
        payload = {
            "display_w": display_w,
            "display_h": display_h,
            "fit_w": fit_w,
            "fit_h": fit_h,
            "state": state,
            "fast_preview": self.preview_interacting,
        }
        self.preview_latest_req_id += 1
        req_id = self.preview_latest_req_id
        self.preview_req_meta[req_id] = {
            "t0": time.perf_counter(),
            "fast": self.preview_interacting,
            "fit_w": fit_w,
            "fit_h": fit_h,
            "animate": animate
        }
        if len(self.preview_req_meta) > 30:
            keep = self.preview_req_meta.get(req_id)
            self.preview_req_meta.clear()
            if keep is not None:
                self.preview_req_meta[req_id] = keep
        self.preview_queued = (req_id, payload)
        self._start_next_preview_task()

    def get_output_size(self):
        val = ASPECT_RATIOS.get(self.combo_aspect.currentText())
        if val is None:
            try:
                user32 = ctypes.windll.user32
                return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
            except Exception:
                return 1920, 1080
        rw, rh = val
        base = 1920
        if rw >= rh:
            return base, int(base * rh / rw)
        return int(base * rw / rh), base

    def show_gallery(self):
        dlg = GalleryDialog(self)
        dlg.exec()

    def save_image(self):
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
        except Exception:
            w, h = 1920, 1080
        final = self.generate_img(w, h, is_preview=False)
        default_path = os.path.join(get_output_dir(), self._get_wallpaper_filename())
        path, _ = QFileDialog.getSaveFileName(
            self, "保存图片", default_path,
            "JPEG 图片 (*.jpg *.jpeg);;PNG 图片 (*.png);;所有文件 (*)"
        )
        if path:
            try:
                if path.lower().endswith(".png"):
                    final.save(path)
                else:
                    final.save(path, quality=95, subsampling=0, progressive=True)
                print("图片已保存:", path)
            except OSError as e:
                err_msg = str(e).lower()
                if "no space" in err_msg or "disk" in err_msg:
                    hint = "请清理磁盘空间后重试，或选择其他保存位置。"
                elif "permission" in err_msg or "access" in err_msg:
                    hint = "请检查是否有写入权限，或尝试保存到其他目录（如桌面）。"
                else:
                    hint = "请尝试保存到其他目录或更换文件名。"
                QMessageBox.warning(
                    self, "保存失败",
                    "无法保存图片。\n\n%s\n\n%s" % (hint, str(e))
                )
            except Exception as e:
                QMessageBox.warning(
                    self, "保存失败",
                    "保存时发生错误：%s\n\n请尝试更换保存位置或文件名。" % str(e)
                )

    def _render_and_save_wallpaper(self, payload):
        w = payload["w"]
        h = payload["h"]
        out_dir = get_output_dir()
        path = os.path.join(out_dir, self._get_wallpaper_filename(ext=".png"))
        final = self._render_image_from_state(w, h, False, payload["state"], False)
        final.save(path)
        return {"path": path, "w": w, "h": h}

    def _on_apply_wallpaper_finished(self, result):
        self.wallpaper_applying = False
        self.btn_apply.setEnabled(True)
        self.btn_apply.setText("一键应用桌面壁纸")
        path = result["path"]
        w = result["w"]
        h = result["h"]
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        print("壁纸已成功设置:", path, "(%d x %d)" % (w, h))
        self._set_runtime_status("预览耗时: -- ms | 壁纸应用完成")

    def _on_apply_wallpaper_error(self, message):
        self.wallpaper_applying = False
        self.btn_apply.setEnabled(True)
        self.btn_apply.setText("一键应用桌面壁纸")
        print("应用壁纸失败:", message)
        self._set_runtime_status("预览耗时: -- ms | 壁纸应用失败")
        QMessageBox.warning(
            self, "应用壁纸失败",
            "%s\n\n可能原因：系统权限限制、路径不可写等。请尝试先「保存图片」到本地，再手动设为壁纸。" % message
        )

    def apply_wallpaper(self):
        if self.wallpaper_applying:
            return
        try:
            user32 = ctypes.windll.user32
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
        except Exception:
            w, h = 1920, 1080
        self.wallpaper_applying = True
        self.btn_apply.setEnabled(False)
        self.btn_apply.setText("应用中...")
        self._set_runtime_status("预览耗时: -- ms | 正在渲染壁纸...")
        payload = {"w": w, "h": h, "state": self._build_render_state()}
        task = WorkerTask(self._render_and_save_wallpaper, payload)
        task.signals.finished.connect(self._on_apply_wallpaper_finished)
        task.signals.error.connect(self._on_apply_wallpaper_error)
        self.worker_pool.start(task)

    def showEvent(self, event):
        QTimer.singleShot(50, self.update_preview)
        super().showEvent(event)

    def resizeEvent(self, event):
        now = time.perf_counter()
        if now - self._last_resize_fast_ts >= 0.016:
            self._last_resize_fast_ts = now
            self._render_fast_preview_sync()
        self.update_preview()
        super().resizeEvent(event)


if __name__ == "__main__":
    try:
        screenshot_mode = "--screenshot" in sys.argv or "-s" in sys.argv
        app = QApplication(sys.argv)
        win = WallpaperUltra()

        if screenshot_mode:
            # Agent 自动化截图模式：启动后截取主窗口并保存，便于 AI 直接获取当前 UI 状态
            win.setWindowTitle("中国壁纸DIY")
            win.resize(1280, 800)
            win.show()
            out_path = get_agent_screenshot_path()

            def _capture_and_quit():
                try:
                    pix = win.grab()
                    if not pix.isNull():
                        pix.save(out_path)
                        print("Agent UI 截图已保存:", out_path)
                    else:
                        print("截图失败: grab() 返回空")
                except Exception as ex:
                    print("截图异常:", ex)
                app.quit()

            QTimer.singleShot(800, _capture_and_quit)
            sys.exit(app.exec())
        else:
            win.show()
            sys.exit(app.exec())
    except Exception as e:
        print("发生重大错误:")
        traceback.print_exc()
