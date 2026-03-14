import sys
import os
import ctypes
import random
import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLineEdit, QPushButton, QLabel, QColorDialog, QFontDialog, 
                             QComboBox, QSlider, QFrame)
from PyQt6.QtGui import QPixmap, QImage, QColor
from PyQt6.QtCore import Qt, QTimer

class WallpaperPro(QWidget):
    def __init__(self):
        super().__init__()
        # 初始化配置
        self.bg_mode = "渐变"
        self.style_mode = "斜体叠影"
        self.bg_color_1 = QColor(20, 20, 20)
        self.bg_color_2 = QColor(60, 60, 60)
        self.text_color = QColor(255, 255, 255)
        self.current_font_family = "Microsoft YaHei"
        self.current_font_size = 120
        self.is_italic = True
        
        self.initUI()
        self.update_preview() # 初始渲染

    def initUI(self):
        self.setWindowTitle('极简壁纸 Pro - 实时设计器')
        self.setMinimumSize(1000, 600)
        self.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0; font-family: 'Segoe UI';")

        main_layout = QHBoxLayout()

        # --- 左侧控制面板 ---
        controls = QVBoxLayout()
        controls.setSpacing(15)

        self.text_input = QLineEdit("INFINITE PROGRESS")
        self.text_input.setPlaceholderText("输入文字...")
        self.text_input.textChanged.connect(self.update_preview)
        self.text_input.setStyleSheet("padding:12px; font-size:18px; background:#2d2d2d; border:1px solid #444; border-radius:5px;")
        controls.addWidget(self.text_input)

        # 样式选择
        grid = QGridLayout()
        
        self.combo_style = QComboBox()
        self.combo_style.addItems(["斜体叠影", "极简居中", "巨幕海报"])
        self.combo_style.currentTextChanged.connect(self.update_preview)
        grid.addWidget(QLabel("排版样式:"), 0, 0)
        grid.addWidget(self.combo_style, 0, 1)

        self.combo_bg = QComboBox()
        self.combo_bg.addItems(["渐变", "纯色", "噪点质感"])
        self.combo_bg.currentTextChanged.connect(self.update_preview)
        grid.addWidget(QLabel("背景模式:"), 1, 0)
        grid.addWidget(self.combo_bg, 1, 1)
        controls.addLayout(grid)

        # 颜色控制
        color_layout = QHBoxLayout()
        btn_bg1 = QPushButton("背景色1")
        btn_bg1.clicked.connect(lambda: self.pick_color('bg1'))
        btn_bg2 = QPushButton("背景色2")
        btn_bg2.clicked.connect(lambda: self.pick_color('bg2'))
        btn_txt = QPushButton("文字颜色")
        btn_txt.clicked.connect(lambda: self.pick_color('text'))
        color_layout.addWidget(btn_bg1); color_layout.addWidget(btn_bg2); color_layout.addWidget(btn_txt)
        controls.addLayout(color_layout)

        # 字体控制
        btn_font = QPushButton("选择字体 & 预览")
        btn_font.clicked.connect(self.pick_font)
        controls.addWidget(btn_font)

        # 功能按钮
        btn_quote = QPushButton("获取随机金句")
        btn_quote.clicked.connect(self.get_daily_quote)
        btn_quote.setStyleSheet("background:#444;")
        controls.addWidget(btn_quote)

        controls.addStretch()

        self.btn_apply = QPushButton("一键设为桌面壁纸")
        self.btn_apply.clicked.connect(self.apply_wallpaper)
        self.btn_apply.setStyleSheet("background:#0078d4; font-weight:bold; padding:15px; border-radius:8px;")
        controls.addWidget(self.btn_apply)

        main_layout.addLayout(controls, 1)

        # --- 右侧预览面板 ---
        preview_box = QVBoxLayout()
        self.preview_label = QLabel("正在生成预览...")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setStyleSheet("background:#000; border-radius:10px; border:2px solid #333;")
        preview_box.addWidget(self.preview_label)
        
        self.res_label = QLabel("预览分辨率: 缩放匹配窗口")
        self.res_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_box.addWidget(self.res_label)
        
        main_layout.addLayout(preview_box, 2)

        self.setLayout(main_layout)

    # --- 核心逻辑 ---

    def pick_color(self, target):
        color = QColorDialog.getColor()
        if color.isValid():
            if target == 'bg1': self.bg_color_1 = color
            elif target == 'bg2': self.bg_color_2 = color
            else: self.text_color = color
            self.update_preview()

    def pick_font(self):
        font, ok = QFontDialog.getFont()
        if ok:
            self.current_font_family = font.family()
            self.current_font_size = font.pointSize() * 2
            self.is_italic = font.italic()
            self.update_preview()

    def get_daily_quote(self):
        try:
            # 使用公开的一言API
            resp = requests.get("https://v1.hitokoto.cn/?c=d&c=i", timeout=3)
            if resp.status_code == 200:
                self.text_input.setText(resp.json()['hitokoto'])
        except:
            self.text_input.setText("Stay Hungry, Stay Foolish")

    def create_wallpaper_img(self, width, height):
        # 1. 创建背景
        c1 = (self.bg_color_1.red(), self.bg_color_1.green(), self.bg_color_1.blue())
        c2 = (self.bg_color_2.red(), self.bg_color_2.green(), self.bg_color_2.blue())
        
        img = Image.new('RGB', (width, height), c1)
        draw = ImageDraw.Draw(img)

        if self.combo_bg.currentText() == "渐变":
            for y in range(height):
                r = int(c1[0] + (c2[0] - c1[0]) * (y / height))
                g = int(c1[1] + (c2[1] - c1[1]) * (y / height))
                b = int(c1[2] + (c2[2] - c1[2]) * (y / height))
                draw.line([(0, y), (width, y)], fill=(r, g, b))
        
        if self.combo_bg.currentText() == "噪点质感":
            noise = Image.effect_noise((width, height), 20)
            img = Image.blend(img, noise.convert("RGB"), 0.05)

        # 2. 绘制文字
        text = self.text_input.text()
        try:
            # 注意：Windows字体查找逻辑简化处理，实际可能需要更复杂的路径匹配
            font_path = "C:/Windows/Fonts/msyhbd.ttc" 
            font = ImageFont.truetype(font_path, self.current_font_size)
        except:
            font = ImageFont.load_default()

        # 计算位置
        tc = (self.text_color.red(), self.text_color.green(), self.text_color.blue())
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        
        x, y = (width - tw)/2, (height - th)/2

        style = self.combo_style.currentText()
        if style == "斜体叠影":
            # 绘制底层（阴影/重影）
            shadow_offset = 8
            draw.text((x + shadow_offset, y + shadow_offset), text, font=font, fill=(tc[0]//2, tc[1]//2, tc[2]//2))
            # 绘制顶层
            draw.text((x, y), text, font=font, fill=tc)
        elif style == "极简居中":
            draw.text((x, y), text, font=font, fill=tc)
        elif style == "巨幕海报":
            # 这里的逻辑可以做得更夸张
            draw.text((x, y), text, font=font, fill=tc, stroke_width=2, stroke_fill=(255,255,255))

        return img

    def update_preview(self):
        # 预览图使用较小分辨率以保持流畅
        preview_img = self.create_wallpaper_img(1280, 720)
        
        # 将 Pillow 图片转为 QPixmap 显示
        data = preview_img.tobytes("raw", "RGB")
        qimg = QImage(data, 1280, 720, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        scaled_pixmap = pixmap.scaled(self.preview_label.width()-10, self.preview_label.height()-10, 
                                      Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.preview_label.setPixmap(scaled_pixmap)

    def apply_wallpaper(self):
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        
        final_img = self.create_wallpaper_img(w, h)
        save_path = os.path.abspath("my_wallpaper.jpg")
        final_img.save(save_path, "JPEG", quality=100)
        
        ctypes.windll.user32.SystemParametersInfoW(20, 0, save_path, 3)
        self.btn_apply.setText("设置成功！")
        QTimer.singleShot(2000, lambda: self.btn_apply.setText("一键设为桌面壁纸"))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = WallpaperPro()
    window.show()
    sys.exit(app.exec())