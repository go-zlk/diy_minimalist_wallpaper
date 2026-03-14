import sys
import os
import ctypes
import json
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLineEdit, QPushButton, QLabel, QComboBox, QSlider, QFrame, 
                             QFileDialog, QCheckBox)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPainter, QPen
from PyQt6.QtCore import Qt, QPoint, QTimer
import matplotlib.font_manager as fm

class WallpaperProMax(QWidget):
    def __init__(self):
        super().__init__()
        # 1. 初始化字体映射 (完成 A)
        self.font_dict = {}
        self.init_font_map()
        
        # 2. 状态变量 (完成 C: 图层位置信息)
        self.text_pos = [0.5, 0.5]  # 相对坐标 (0-1)，方便适配不同分辨率
        self.bg_color = QColor(20, 20, 20)
        self.text_color = QColor(255, 255, 255)
        self.font_size = 100
        self.is_dragging = False
        self.last_mouse_pos = QPoint()

        self.initUI()
        self.update_preview()

    def init_font_map(self):
        # 获取系统所有可用字体路径
        fonts = fm.findSystemFonts()
        for f in fonts:
            try:
                name = fm.FontProperties(fname=f).get_name()
                if name not in self.font_dict:
                    self.font_dict[name] = f
            except: continue

    def initUI(self):
        self.setWindowTitle('极简壁纸 Pro Max - 设计器')
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("background-color: #121212; color: #eee; font-family: 'Segoe UI';")

        main_layout = QHBoxLayout(self)

        # --- 左侧：控制面板 (实时控制，无弹窗) ---
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(10, 10, 10, 10)
        
        # 文字输入
        self.text_input = QLineEdit("INFINITE PROGRESS")
        self.text_input.textChanged.connect(self.update_preview)
        self.text_input.setStyleSheet("font-size: 18px; padding: 10px; background: #252525; border: none; border-radius: 4px;")
        sidebar.addWidget(QLabel("内容:"))
        sidebar.addWidget(self.text_input)

        # 字体选择 (实时)
        self.combo_font = QComboBox()
        self.combo_font.addItems(sorted(self.font_dict.keys()))
        self.combo_font.setCurrentText("Microsoft YaHei")
        self.combo_font.currentTextChanged.connect(self.update_preview)
        sidebar.addWidget(QLabel("字体:"))
        sidebar.addWidget(self.combo_font)

        # 字号滑动条 (实时)
        sidebar.addWidget(QLabel("字号:"))
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(20, 500)
        self.slider_size.setValue(100)
        self.slider_size.valueChanged.connect(self.update_preview)
        sidebar.addWidget(self.slider_size)

        # 调色盘区域 (RGB 实时滑动条代替复杂弹窗)
        sidebar.addWidget(QLabel("文字颜色 (R/G/B):"))
        self.r_slider = self.create_color_slider(sidebar)
        self.g_slider = self.create_color_slider(sidebar)
        self.b_slider = self.create_color_slider(sidebar)

        # 排版/效果
        self.check_italic = QCheckBox("斜体 (模拟)")
        self.check_italic.stateChanged.connect(self.update_preview)
        self.check_shadow = QCheckBox("启用叠影阴影")
        self.check_shadow.setChecked(True)
        self.check_shadow.stateChanged.connect(self.update_preview)
        sidebar.addWidget(self.check_italic)
        sidebar.addWidget(self.check_shadow)

        sidebar.addStretch()

        # 导出多端尺寸 (完成 D)
        sidebar.addWidget(QLabel("多端一键导出:"))
        export_layout = QGridLayout()
        btn_pc = QPushButton("PC (4K)")
        btn_pc.clicked.connect(lambda: self.export_wallpaper(3840, 2160))
        btn_phone = QPushButton("手机 (竖屏)")
        btn_phone.clicked.connect(lambda: self.export_wallpaper(1080, 1920))
        export_layout.addWidget(btn_pc, 0, 0)
        export_layout.addWidget(btn_phone, 0, 1)
        sidebar.addLayout(export_layout)

        # 设置壁纸
        self.btn_apply = QPushButton("一键应用到桌面")
        self.btn_apply.clicked.connect(self.apply_to_desktop)
        self.btn_apply.setStyleSheet("background: #0078d4; font-weight: bold; padding: 15px; border-radius: 5px;")
        sidebar.addWidget(self.btn_apply)

        main_layout.addLayout(sidebar, 1)

        # --- 右侧：画布预览 (支持拖拽 C) ---
        self.preview_area = QLabel()
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setStyleSheet("background: #000; border: 2px solid #333; border-radius: 8px;")
        self.preview_area.setMouseTracking(True)
        main_layout.addWidget(self.preview_area, 3)

    def create_color_slider(self, layout):
        s = QSlider(Qt.Orientation.Horizontal)
        s.setRange(0, 255)
        s.setValue(255)
        s.valueChanged.connect(self.update_preview)
        layout.addWidget(s)
        return s

    # --- 交互逻辑 (拖拽图层 C) ---
    def mousePressEvent(self, event):
        if self.preview_area.geometry().contains(event.pos()):
            self.is_dragging = True
            self.update_pos(event.pos())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.update_pos(event.pos())

    def mouseReleaseEvent(self, event):
        self.is_dragging = False

    def update_pos(self, pos):
        # 计算相对画布的坐标
        local_pos = self.preview_area.mapFromParent(pos)
        rel_x = local_pos.x() / self.preview_area.width()
        rel_y = local_pos.y() / self.preview_area.height()
        self.text_pos = [max(0, min(1, rel_x)), max(0, min(1, rel_y))]
        self.update_preview()

    # --- 图像渲染逻辑 ---
    def generate_image(self, width, height):
        img = Image.new('RGB', (width, height), (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue()))
        draw = ImageDraw.Draw(img)
        
        # 字体加载 (完成 A)
        font_path = self.font_dict.get(self.combo_font.currentText(), "C:/Windows/Fonts/arial.ttf")
        font = ImageFont.truetype(font_path, self.slider_size.value())
        
        text = self.text_input.text()
        tc = (self.r_slider.value(), self.g_slider.value(), self.b_slider.value())
        
        # 计算坐标
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x = width * self.text_pos[0] - tw/2
        y = height * self.text_pos[1] - th/2

        # 渲染样式
        if self.check_shadow.isChecked():
            draw.text((x+8, y+8), text, font=font, fill=(tc[0]//4, tc[1]//4, tc[2]//4)) # 暗阴影
        
        draw.text((x, y), text, font=font, fill=tc)
        
        return img

    def update_preview(self):
        # 使用缩略图预览以保证丝滑流畅
        img = self.generate_image(1280, 720)
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, 1280, 720, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.preview_area.setPixmap(pixmap.scaled(self.preview_area.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def apply_to_desktop(self):
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        final = self.generate_image(w, h)
        path = os.path.abspath("wallpaper_current.jpg")
        final.save(path, quality=100)
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)

    def export_wallpaper(self, w, h):
        file_path, _ = QFileDialog.getSaveFileName(self, "导出图片", f"wallpaper_{w}x{h}.png", "PNG (*.png);;JPG (*.jpg)")
        if file_path:
            img = self.generate_image(w, h)
            img.save(file_path)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WallpaperProMax()
    window.show()
    sys.exit(app.exec())