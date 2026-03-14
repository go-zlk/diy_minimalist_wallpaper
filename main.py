import sys
import os
import ctypes
import math
import traceback
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QPushButton, QLabel, QComboBox, QSlider,
                             QFrame, QCheckBox, QScrollArea)
from PyQt6.QtGui import (QPixmap, QImage, QColor, QPainter, QConicalGradient,
                         QLinearGradient, QBrush, QPen, QPainterPath)
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QTimer, QRectF

# --- 现代调色盘组件（超大圆角 SV + 呼吸感双环手柄）---
class ColorWheelPicker(QWidget):
    colorChanged = pyqtSignal(QColor)

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

        pad = 4
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
        self.handle_mouse(event.pos())

    def mouseMoveEvent(self, event):
        self.handle_mouse(event.pos())


# --- 带标题的分组容器（解决 QGroupBox 重叠问题）---
class SectionGroup(QWidget):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 8)
        layout.setSpacing(6)
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet(
            "font-weight: bold; font-size: 13px; color: #B0B0B0; "
            "margin-bottom: 4px; padding: 0;"
        )
        layout.addWidget(self.title_label)
        self.content_layout = QVBoxLayout()
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(self.content_layout)

    def addWidget(self, widget, stretch=0, alignment=Qt.AlignmentFlag.AlignTop):
        self.content_layout.addWidget(widget, stretch, alignment)

    def addLayout(self, layout):
        self.content_layout.addLayout(layout)


# --- 主窗口 ---
class WallpaperUltra(QWidget):
    def __init__(self):
        super().__init__()
        self.font_dict = {"默认字体": "C:/Windows/Fonts/msyhbd.ttc"}
        self.font_cache = {}
        self.edit_target = "text"
        self.text_color = QColor("#64FFDA")
        self.bg_color = QColor("#0A0A0A")
        self.text_pos = [0.5, 0.5]

        self.initUI()

        QTimer.singleShot(1000, self.async_load_fonts)

    def get_cached_font(self, font_path, size):
        key = (font_path, size)
        if key not in self.font_cache:
            try:
                self.font_cache[key] = ImageFont.truetype(font_path, max(5, size))
            except Exception:
                self.font_cache[key] = ImageFont.truetype(
                    "C:/Windows/Fonts/msyhbd.ttc", max(5, size)
                )
        return self.font_cache[key]

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
        self.setWindowTitle("极简壁纸 Ultra Pro - 最终版")
        self.setMinimumSize(1100, 800)
        self.setObjectName("mainWindow")
        self.setStyleSheet(
            "#mainWindow { background: #0D0D0F; } "
            "QWidget { color: #E0E0E0; font-family: 'Segoe UI'; }"
        )

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # 左侧玻璃拟态面板
        sidebar_container = QWidget()
        sidebar_container.setFixedWidth(300)
        sidebar_container.setStyleSheet("""
            QWidget#sidebar {
                background: rgba(30, 30, 35, 0.75);
                border-radius: 16px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }
        """)
        sidebar_container.setObjectName("sidebar")
        sidebar = QVBoxLayout(sidebar_container)
        sidebar.setSpacing(12)
        sidebar.setContentsMargins(20, 20, 20, 20)

        # 1. 内容设计
        sec_content = SectionGroup("1. 内容设计")
        self.text_input = QLineEdit("INFINITE PROGRESS")
        self.text_input.setStyleSheet(
            "background: rgba(50, 50, 55, 0.9); border-radius: 8px; "
            "padding: 10px; border: 1px solid rgba(255,255,255,0.06);"
        )
        self.text_input.textChanged.connect(self.update_preview)
        sec_content.addWidget(self.text_input)

        self.combo_font = QComboBox()
        self.combo_font.addItem("默认字体")
        self.combo_font.setStyleSheet(
            "background: rgba(50, 50, 55, 0.9); border-radius: 8px; "
            "padding: 8px; border: 1px solid rgba(255,255,255,0.06);"
        )
        self.combo_font.currentTextChanged.connect(self.on_font_changed)
        sec_content.addWidget(self.combo_font)

        self.label_font_hint = QLabel("")
        self.label_font_hint.setStyleSheet(
            "color: #E67E22; font-size: 11px; padding: 2px 0;"
        )
        self.label_font_hint.setWordWrap(True)
        sec_content.addWidget(self.label_font_hint)

        size_row = QHBoxLayout()
        self.label_font_size = QLabel("字号: 180 px")
        self.label_font_size.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        size_row.addWidget(self.label_font_size)
        size_row.addStretch()
        sec_content.addLayout(size_row)

        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(20, 600)
        self.slider_size.setValue(180)
        self.slider_size.valueChanged.connect(self.on_font_size_changed)
        sec_content.addWidget(self.slider_size)

        letter_spacing_row = QHBoxLayout()
        self.label_letter_spacing = QLabel("字间距: 0")
        self.label_letter_spacing.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        letter_spacing_row.addWidget(self.label_letter_spacing)
        letter_spacing_row.addStretch()
        sec_content.addLayout(letter_spacing_row)

        self.slider_letter_spacing = QSlider(Qt.Orientation.Horizontal)
        self.slider_letter_spacing.setRange(-20, 80)
        self.slider_letter_spacing.setValue(0)
        self.slider_letter_spacing.valueChanged.connect(self.on_letter_spacing_changed)
        sec_content.addWidget(self.slider_letter_spacing)

        sidebar.addWidget(sec_content)
        sidebar.addWidget(QFrame(frameShape=QFrame.Shape.HLine,
                         styleSheet="background: rgba(255,255,255,0.08); margin: 8px 0;"))

        # 2. 视觉色彩
        sec_color = SectionGroup("2. 视觉色彩")
        btn_layout = QHBoxLayout()
        self.btn_edit_text = QPushButton("字体颜色")
        self.btn_edit_text.setCheckable(True)
        self.btn_edit_text.setChecked(True)
        self.btn_edit_text.setStyleSheet(
            "QPushButton { background: rgba(50,50,55,0.9); padding: 8px; "
            "border-radius: 6px; border: 1px solid rgba(255,255,255,0.06); } "
            "QPushButton:checked { background: #0078D4; border-color: #0078D4; }"
        )
        self.btn_edit_text.clicked.connect(lambda: self.switch_target("text"))

        self.btn_edit_bg = QPushButton("背景颜色")
        self.btn_edit_bg.setCheckable(True)
        self.btn_edit_bg.setStyleSheet(
            "QPushButton { background: rgba(50,50,55,0.9); padding: 8px; "
            "border-radius: 6px; border: 1px solid rgba(255,255,255,0.06); } "
            "QPushButton:checked { background: #0078D4; border-color: #0078D4; }"
        )
        self.btn_edit_bg.clicked.connect(lambda: self.switch_target("bg"))

        btn_layout.addWidget(self.btn_edit_text)
        btn_layout.addWidget(self.btn_edit_bg)
        sec_color.addLayout(btn_layout)

        self.color_picker = ColorWheelPicker()
        self.color_picker.colorChanged.connect(self.handle_color_change)
        sec_color.addWidget(self.color_picker, alignment=Qt.AlignmentFlag.AlignCenter)
        sidebar.addWidget(sec_color)
        sidebar.addWidget(QFrame(frameShape=QFrame.Shape.HLine,
                         styleSheet="background: rgba(255,255,255,0.08); margin: 8px 0;"))

        # 3. 艺术样式
        sec_style = SectionGroup("3. 艺术样式")
        self.check_stack = QCheckBox("启用叠影效果")
        self.check_stack.setChecked(True)
        self.check_stack.stateChanged.connect(self.update_preview)
        sec_style.addWidget(self.check_stack)

        self.label_shadow_offset = QLabel("叠影偏移量: 0")
        self.label_shadow_offset.setStyleSheet("color: #A0A0A0; font-size: 12px;")
        sec_style.addWidget(self.label_shadow_offset)

        self.slider_shadow_offset = QSlider(Qt.Orientation.Horizontal)
        self.slider_shadow_offset.setRange(0, 200)
        self.slider_shadow_offset.valueChanged.connect(self.on_shadow_offset_changed)
        self.slider_shadow_offset.blockSignals(True)
        self.slider_shadow_offset.setValue(0)
        self.slider_shadow_offset.blockSignals(False)
        sec_style.addWidget(self.slider_shadow_offset)

        self.check_italic = QCheckBox("模拟斜体 (修复边缘)")
        self.check_italic.stateChanged.connect(self.update_preview)
        sec_style.addWidget(self.check_italic)

        sidebar.addWidget(sec_style)
        sidebar.addStretch()

        self.btn_apply = QPushButton("一键应用桌面壁纸")
        self.btn_apply.setStyleSheet(
            "background: #0078D4; height: 48px; border-radius: 10px; "
            "font-weight: bold; border: none;"
        )
        self.btn_apply.clicked.connect(self.apply_wallpaper)
        sidebar.addWidget(self.btn_apply)

        main_layout.addWidget(sidebar_container)

        # 右侧预览区（含任务栏模拟）
        self.preview_area = QLabel("正在初始化预览...")
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setStyleSheet(
            "background: #0A0A0A; border-radius: 16px; "
            "border: 1px solid rgba(255,255,255,0.06);"
        )
        self.preview_area.setMinimumSize(400, 300)
        main_layout.addWidget(self.preview_area, 1)

    def on_font_changed(self, font_name):
        symbol_fonts = ("wingding", "webding", "symbol", "marlett")
        is_symbol = any(s in font_name.lower() for s in symbol_fonts)
        if is_symbol:
            self.label_font_hint.setText("提示：符号字体可能无法正常显示文字")
        else:
            self.label_font_hint.setText("")
        self.update_preview()

    def on_font_size_changed(self, value):
        self.label_font_size.setText("字号: %d px" % value)
        self.update_preview()

    def on_letter_spacing_changed(self, value):
        self.label_letter_spacing.setText("字间距: %d" % value)
        self.update_preview()

    def on_shadow_offset_changed(self, value):
        self.label_shadow_offset.setText("叠影偏移量: %d" % (value / 2))
        self.update_preview()

    def switch_target(self, target):
        self.edit_target = target
        self.btn_edit_text.setChecked(target == "text")
        self.btn_edit_bg.setChecked(target == "bg")
        color = self.text_color if target == "text" else self.bg_color
        self.color_picker.set_color_externally(color)

    def handle_color_change(self, color):
        if self.edit_target == "text":
            self.text_color = color
        else:
            self.bg_color = color
        self.update_preview()

    def generate_img(self, w, h, is_preview=True):
        try:
            bg_rgb = (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue())
            img = Image.new("RGB", (w, h), bg_rgb)
            text_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(text_layer)

            font_path = self.font_dict.get(
                self.combo_font.currentText(),
                "C:/Windows/Fonts/msyhbd.ttc"
            )
            scale = w / 1920
            fs = int(self.slider_size.value() * (scale if is_preview else 1.0))
            font = self.get_cached_font(font_path, max(5, fs))

            text = self.text_input.text()
            tc = (self.text_color.red(), self.text_color.green(), self.text_color.blue())
            letter_spacing = self.slider_letter_spacing.value()

            shadow_offset = self.slider_shadow_offset.value() / 100.00
            shadow_steps = 8

            shadow_rgb = (max(0, int(tc[0] * 0.2)), max(0, int(tc[1] * 0.2)),
                          max(0, int(tc[2] * 0.2)))

            def draw_text_with_shadow(cx, cy, draw_fn):
                if self.check_stack.isChecked():
                    for i in range(shadow_steps, 0, -1):
                        off = i * shadow_offset
                        draw_fn(cx + off, cy + off, (shadow_rgb[0], shadow_rgb[1], shadow_rgb[2], 255))
                draw_fn(cx, cy, (tc[0], tc[1], tc[2], 255))

            if not text:
                pass
            elif letter_spacing == 0:
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                x = w * self.text_pos[0] - tw / 2
                y = h * self.text_pos[1] - th / 2

                def simple_draw(px, py, fill):
                    draw.text((px, py), text, font=font, fill=fill)

                draw_text_with_shadow(x, y, simple_draw)
            else:
                char_widths = []
                for ch in text:
                    bbox = draw.textbbox((0, 0), ch, font=font)
                    char_widths.append(bbox[2] - bbox[0])
                total_w = sum(char_widths) + letter_spacing * (len(text) - 1)
                bbox = draw.textbbox((0, 0), text[0], font=font)
                th = bbox[3] - bbox[1]
                x = w * self.text_pos[0] - total_w / 2
                y = h * self.text_pos[1] - th / 2

                def char_draw(px, py, fill):
                    for j, ch in enumerate(text):
                        draw.text((px, py), ch, font=font, fill=fill)
                        px += char_widths[j] + letter_spacing

                draw_text_with_shadow(x, y, char_draw)

            if self.check_italic.isChecked():
                _, th = text_layer.size
                # 向右倾斜，补偿位移使文字中心保持不动
                tx = -0.1 * th
                text_layer = text_layer.transform(
                    text_layer.size, Image.Transform.AFFINE,
                    (1, 0.2, tx, 0, 1, 0),
                    resample=Image.Resampling.LANCZOS
                )

            img.paste(text_layer, (0, 0), text_layer)

            if is_preview:
                img = self.draw_taskbar_overlay(img, w, h)

            return img
        except Exception as e:
            print("渲染图片出错:", e)
            return Image.new("RGB", (w, h), (0, 0, 0))

    def draw_taskbar_overlay(self, img, w, h):
        taskbar_h = max(24, int(h * 0.04))
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        bar_y = h - taskbar_h
        draw.rectangle(
            [0, bar_y, w, h],
            fill=(30, 30, 35, 180),
            outline=(60, 60, 65, 100)
        )
        dot_r = 4
        dot_y = bar_y + taskbar_h // 2
        for i in range(8):
            dot_x = 24 + i * 36
            draw.ellipse(
                [dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r],
                fill=(120, 120, 130, 200)
            )
        img_rgba = img.convert("RGBA")
        img_rgba = Image.alpha_composite(img_rgba, overlay)
        return img_rgba.convert("RGB")

    def update_preview(self):
        pw = self.preview_area.width()
        ph = self.preview_area.height()
        if pw < 50:
            return
        img = self.generate_img(pw, ph, is_preview=True)
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.size[0], img.size[1], img.size[0] * 3,
                      QImage.Format.Format_RGB888)
        self.preview_area.setPixmap(QPixmap.fromImage(qimg))

    def apply_wallpaper(self):
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)
        final = self.generate_img(w, h, is_preview=False)
        path = os.path.abspath("wallpaper_final.jpg")
        final.save(path, quality=100)
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        print("壁纸已成功设置:", path)

    def resizeEvent(self, event):
        self.update_preview()
        super().resizeEvent(event)


if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        win = WallpaperUltra()
        win.show()
        sys.exit(app.exec())
    except Exception as e:
        print("发生重大错误:")
        traceback.print_exc()
