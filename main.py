import sys
import os
import ctypes
import math
import traceback
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLineEdit, QPushButton, QLabel, QComboBox, QSlider, 
                             QFrame, QCheckBox, QScrollArea)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPainter, QConicalGradient, QLinearGradient, QBrush, QPen
from PyQt6.QtCore import Qt, QPointF, pyqtSignal, QTimer

# --- 现代调色盘组件 ---
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

    def set_color_externally(self, color: QColor):
        """外部切换目标时，精准还原圆盘位置"""
        h = color.hueF()
        self.hue = h if h >= 0 else 0
        self.sat = color.saturationF()
        self.val = color.valueF()
        self.update_color()
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        center = QPointF(rect.center())
        radius = rect.width() / 2 - 12
        inner_radius = radius - 18

        # 1. 绘制色相环 (对齐起始点：3点钟方向为红色，逆时针旋转)
        grad = QConicalGradient(center, 0.0) 
        for i in range(361):
            # HSV 的 0-1 映射到圆周的 0-1，顺着渐变方向
            grad.setColorAt(i / 360.0, QColor.fromHsvF(i / 360.0, 1.0, 1.0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, radius, radius)
        
        # 镂空中心
        painter.setBrush(QBrush(QColor("#1A1A1A")))
        painter.drawEllipse(center, inner_radius, inner_radius)

        # 2. 绘制中间 S/V 方块
        box_size = int(inner_radius * 1.2)
        bx, by = center.x() - box_size/2, center.y() - box_size/2
        
        # 方块底色严格跟随 Hue
        h_grad = QLinearGradient(bx, 0, bx + box_size, 0)
        h_grad.setColorAt(0, Qt.GlobalColor.white)
        h_grad.setColorAt(1, QColor.fromHsvF(self.hue, 1.0, 1.0))
        painter.fillRect(int(bx), int(by), box_size, box_size, h_grad)
        
        v_grad = QLinearGradient(0, by, 0, by + box_size)
        v_grad.setColorAt(0, QColor(0, 0, 0, 0))
        v_grad.setColorAt(1, Qt.GlobalColor.black)
        painter.fillRect(int(bx), int(by), box_size, box_size, v_grad)

        # 3. 绘制手柄
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        
        # 计算圆环指示器位置：使用 -self.hue 是因为三角函数默认顺时针，需转为逆时针
        angle_rad = self.hue * 2 * math.pi
        hx = center.x() + (radius - 9) * math.cos(angle_rad)
        hy = center.y() - (radius - 9) * math.sin(angle_rad) # 取负号实现逆时针映射
        painter.drawEllipse(QPointF(hx, hy), 6, 6)

        # 方块指示器
        sx = bx + self.sat * box_size
        sy = by + (1.0 - self.val) * box_size
        painter.setPen(QPen(Qt.GlobalColor.black if self.val > 0.5 else Qt.GlobalColor.white, 2))
        painter.drawEllipse(QPointF(sx, sy), 5, 5)

    def handle_mouse(self, pos):
        center = QPointF(self.rect().center())
        dx, dy = pos.x() - center.x(), pos.y() - center.y()
        dist = math.sqrt(dx*dx + dy*dy)
        
        if dist > (self.width()/2 - 35): 
            # 核心修正：使用 -dy 将屏幕坐标(Y向下)转为标准坐标(Y向上)
            # 这样 atan2 的 0 到 2pi 刚好对应逆时针旋转，与色相环完美重合
            angle = math.atan2(-dy, dx) 
            if angle < 0: angle += 2 * math.pi
            self.hue = angle / (2 * math.pi)
        else:
            inner_r = self.width()/2 - 30
            box_s = int(inner_r * 1.2)
            bx, by = center.x() - box_s/2, center.y() - box_s/2
            self.sat = max(0.0, min(1.0, (pos.x() - bx) / box_s))
            self.val = max(0.0, min(1.0, 1.0 - (pos.y() - by) / box_s))

        self.update_color()
        self.colorChanged.emit(self.current_color)
        self.update()

    def mousePressEvent(self, event): self.handle_mouse(event.pos())
    def mouseMoveEvent(self, event): self.handle_mouse(event.pos())
# --- 主窗口 ---
class WallpaperUltra(QWidget):
    def __init__(self):
        super().__init__()
        print("1. 正在初始化界面组件...")
        self.font_dict = {"默认字体": "C:/Windows/Fonts/msyhbd.ttc"}
        self.edit_target = "text" 
        self.text_color = QColor("#64FFDA")
        self.bg_color = QColor("#0A0A0A")
        self.text_pos = [0.5, 0.5]
        
        self.initUI()
        print("2. 界面显示完成。")
        
        # 延迟 1 秒加载字体，防止启动假死
        QTimer.singleShot(1000, self.async_load_fonts)

    def async_load_fonts(self):
        print("3. 正在加载系统字体...")
        try:
            # 采用手动遍历 Windows 目录的方式，比 matplotlib 快得多
            font_dir = "C:/Windows/Fonts"
            for file in os.listdir(font_dir):
                if file.lower().endswith((".ttc", ".ttf")):
                    # 简单截取文件名作为显示
                    name = file.split(".")[0]
                    self.font_dict[name] = os.path.join(font_dir, file)
            self.combo_font.clear()
            self.combo_font.addItems(sorted(self.font_dict.keys()))
            if "msyhbd" in self.font_dict: self.combo_font.setCurrentText("msyhbd")
            print(f"4. 字体加载完成，共计 {len(self.font_dict)} 个。")
        except Exception as e:
            print(f"字体加载失败: {e}")
        self.update_preview()

    def initUI(self):
        self.setWindowTitle('极简壁纸 Ultra Pro - 最终版')
        self.setMinimumSize(1100, 800)
        self.setStyleSheet("background-color: #121212; color: #E0E0E0; font-family: 'Segoe UI';")

        main_layout = QHBoxLayout(self)
        sidebar_w = QWidget()
        sidebar_w.setFixedWidth(280)
        sidebar = QVBoxLayout(sidebar_w)
        
        sidebar.addWidget(QLabel("1. 内容设计"))
        self.text_input = QLineEdit("INFINITE PROGRESS")
        self.text_input.textChanged.connect(self.update_preview)
        sidebar.addWidget(self.text_input)
        
        self.combo_font = QComboBox()
        self.combo_font.addItem("默认字体")
        self.combo_font.currentTextChanged.connect(self.update_preview)
        sidebar.addWidget(self.combo_font)
        
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(20, 600)
        self.slider_size.setValue(180)
        self.slider_size.valueChanged.connect(self.update_preview)
        sidebar.addWidget(QLabel("字号调节:"))
        sidebar.addWidget(self.slider_size)

        sidebar.addWidget(QFrame(frameShape=QFrame.Shape.HLine, styleSheet="background:#333; margin:10px 0;"))

        # 颜色切换按钮
        sidebar.addWidget(QLabel("2. 视觉色彩"))
        btn_layout = QHBoxLayout()
        self.btn_edit_text = QPushButton("字体颜色")
        self.btn_edit_text.setCheckable(True)
        self.btn_edit_text.setChecked(True)
        self.btn_edit_text.setStyleSheet("QPushButton { background: #222; padding: 8px; border-radius: 4px; } QPushButton:checked { background: #0078D4; }")
        self.btn_edit_text.clicked.connect(lambda: self.switch_target("text"))
        
        self.btn_edit_bg = QPushButton("背景颜色")
        self.btn_edit_bg.setCheckable(True)
        self.btn_edit_bg.setStyleSheet("QPushButton { background: #222; padding: 8px; border-radius: 4px; } QPushButton:checked { background: #0078D4; }")
        self.btn_edit_bg.clicked.connect(lambda: self.switch_target("bg"))
        
        btn_layout.addWidget(self.btn_edit_text); btn_layout.addWidget(self.btn_edit_bg)
        sidebar.addLayout(btn_layout)

        self.color_picker = ColorWheelPicker()
        self.color_picker.colorChanged.connect(self.handle_color_change)
        sidebar.addWidget(self.color_picker, alignment=Qt.AlignmentFlag.AlignCenter)

        sidebar.addWidget(QFrame(frameShape=QFrame.Shape.HLine, styleSheet="background:#333; margin:10px 0;"))

        sidebar.addWidget(QLabel("3. 艺术样式"))
        self.check_stack = QCheckBox("启用叠影效果")
        self.check_stack.setChecked(True)
        self.check_stack.stateChanged.connect(self.update_preview)
        sidebar.addWidget(self.check_stack)
        
        self.check_italic = QCheckBox("模拟斜体 (修复边缘)")
        self.check_italic.stateChanged.connect(self.update_preview)
        sidebar.addWidget(self.check_italic)

        sidebar.addStretch()
        self.btn_apply = QPushButton("一键应用桌面壁纸")
        self.btn_apply.setStyleSheet("background:#0078D4; height:45px; border-radius:5px; font-weight:bold;")
        self.btn_apply.clicked.connect(self.apply_wallpaper)
        sidebar.addWidget(self.btn_apply)
        
        main_layout.addWidget(sidebar_w)

        self.preview_area = QLabel("正在初始化预览...")
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setStyleSheet("background: #000; border-radius: 12px;")
        main_layout.addWidget(self.preview_area, 1)

    def switch_target(self, target):
        self.edit_target = target
        self.btn_edit_text.setChecked(target == "text")
        self.btn_edit_bg.setChecked(target == "bg")
        color = self.text_color if target == "text" else self.bg_color
        self.color_picker.set_color_externally(color)

    def handle_color_change(self, color):
        if self.edit_target == "text": self.text_color = color
        else: self.bg_color = color
        self.update_preview()

    def generate_img(self, w, h, is_preview=True):
        try:
            bg_rgb = (self.bg_color.red(), self.bg_color.green(), self.bg_color.blue())
            img = Image.new('RGB', (w, h), bg_rgb)
            text_layer = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            draw = ImageDraw.Draw(text_layer)
            
            font_path = self.font_dict.get(self.combo_font.currentText(), "C:/Windows/Fonts/msyhbd.ttc")
            scale = w / 1920
            fs = int(self.slider_size.value() * (scale if is_preview else 1.0))
            font = ImageFont.truetype(font_path, max(5, fs))
            
            text = self.text_input.text()
            tc = (self.text_color.red(), self.text_color.green(), self.text_color.blue())
            
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
            x, y = w*self.text_pos[0]-tw/2, h*self.text_pos[1]-th/2

            if self.check_stack.isChecked():
                for i in range(8, 0, -1):
                    off = i * (fs // 40)
                    draw.text((x + off, y + off), text, font=font, fill=(tc[0]//4, tc[1]//4, tc[2]//4, 255))
            draw.text((x, y), text, font=font, fill=(tc[0], tc[1], tc[2], 255))

            if self.check_italic.isChecked():
                text_layer = text_layer.transform(text_layer.size, Image.Transform.AFFINE, (1, -0.2, 0, 0, 1, 0))

            img.paste(text_layer, (0, 0), text_layer)
            return img
        except Exception as e:
            print(f"渲染图片出错: {e}")
            return Image.new('RGB', (w, h), (0,0,0))

    def update_preview(self):
        pw, ph = self.preview_area.width(), self.preview_area.height()
        if pw < 50: return
        img = self.generate_img(pw, ph, is_preview=True)
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGB888)
        self.preview_area.setPixmap(QPixmap.fromImage(qimg))

    def apply_wallpaper(self):
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        final = self.generate_img(w, h, is_preview=False)
        path = os.path.abspath("wallpaper_final.jpg")
        final.save(path, quality=100)
        ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
        print(f"壁纸已成功设置: {path}")

    def resizeEvent(self, event):
        self.update_preview()
        super().resizeEvent(event)

if __name__ == '__main__':
    try:
        app = QApplication(sys.argv)
        win = WallpaperUltra()
        win.show()
        print("5. 程序进入事件循环，请检查是否有窗口弹出。")
        sys.exit(app.exec())
    except Exception as e:
        print("发生重大错误:")
        traceback.print_exc()