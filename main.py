import sys
import os
import ctypes
import math
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QLineEdit, QPushButton, QLabel, QComboBox, QSlider, QFrame, 
                             QFileDialog, QCheckBox)
from PyQt6.QtGui import QPixmap, QImage, QColor, QPainter, QConicalGradient, QLinearGradient, QBrush, QPen
from PyQt6.QtCore import Qt, QPoint, QPointF, pyqtSignal, QSize
import matplotlib.font_manager as fm

# --- 自定义直观调色圆盘组件 ---
class ColorWheelPicker(QWidget):
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(220, 220)
        self.hue = 0.0        # 0.0 - 1.0
        self.sat = 1.0        # 0.0 - 1.0
        self.val = 1.0        # 0.0 - 1.0
        self.current_color = QColor.fromHsvF(self.hue, self.sat, self.val)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        center = rect.center()
        
        # --- 核心修改点：定义一个浮点类型的中心点 ---
        center_f = QPointF(center) 
        
        radius = min(rect.width(), rect.height()) // 2 - 10

        # 1. 绘制色相环
        inner_radius = radius - 20
        
        # --- 修改点：这里传入 center_f 和 0.0 (浮点数) ---
        gradient = QConicalGradient(center_f, 0.0) 
        
        for i in range(361):
            gradient.setColorAt(i / 360.0, QColor.fromHsv(360 - i, 255, 255))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # --- 修改点：drawEllipse 也建议使用 center_f ---
        painter.drawEllipse(center_f, float(radius), float(radius))
        
        # 镂空中心
        painter.setBrush(QBrush(QColor("#121212")))
        painter.drawEllipse(center_f, float(inner_radius), float(inner_radius))

        # 2. 绘制中间的饱和度/明度方块 (Inner Square)
        box_size = int(inner_radius * math.sqrt(2) * 0.8)
        box_rect = QPoint(center.x() - box_size // 2, center.y() - box_size // 2)
        
        # 方块背景：从白到当前色相的水平渐变
        h_grad = QLinearGradient(box_rect.x(), 0, box_rect.x() + box_size, 0)
        h_grad.setColorAt(0, Qt.GlobalColor.white)
        h_grad.setColorAt(1, QColor.fromHsvF(self.hue, 1.0, 1.0))
        painter.fillRect(box_rect.x(), box_rect.y(), box_size, box_size, h_grad)
        
        # 方块叠加：从透明到黑色的垂直渐变
        v_grad = QLinearGradient(0, box_rect.y(), 0, box_rect.y() + box_size)
        v_grad.setColorAt(0, QColor(0, 0, 0, 0))
        v_grad.setColorAt(1, Qt.GlobalColor.black)
        painter.fillRect(box_rect.x(), box_rect.y(), box_size, box_size, v_grad)

        # 3. 绘制选择器标线 (Selector handles)
        # 色环上的位置
        angle = (1.0 - self.hue) * 2 * math.pi
        hx = center.x() + (radius - 10) * math.cos(angle)
        hy = center.y() + (radius - 10) * math.sin(angle)
        painter.setPen(QPen(Qt.GlobalColor.white, 2))
        painter.drawEllipse(QPoint(int(hx), int(hy)), 5, 5)

        # 方块内的位置
        sx = box_rect.x() + self.sat * box_size
        sy = box_rect.y() + (1.0 - self.val) * box_size
        painter.drawEllipse(QPoint(int(sx), int(sy)), 4, 4)

    def mouseMoveEvent(self, event):
        self.handle_mouse(event.pos())

    def mousePressEvent(self, event):
        self.handle_mouse(event.pos())

    def handle_mouse(self, pos):
        center = self.rect().center()
        dx, dy = pos.x() - center.x(), pos.y() - center.y()
        dist = math.sqrt(dx*dx + dy*dy)
        radius = self.width() // 2 - 10
        inner_radius = radius - 20

        # 点击了圆环
        if inner_radius - 5 <= dist <= radius + 5:
            angle = math.atan2(dy, dx)
            self.hue = 1.0 - ((angle if angle >= 0 else (angle + 2 * math.pi)) / (2 * math.pi))
        
        # 点击了内部方块
        box_size = int(inner_radius * math.sqrt(2) * 0.8)
        bx, by = center.x() - box_size // 2, center.y() - box_size // 2
        if bx <= pos.x() <= bx + box_size and by <= pos.y() <= by + box_size:
            self.sat = (pos.x() - bx) / box_size
            self.val = 1.0 - (pos.y() - by) / box_size

        self.current_color = QColor.fromHsvF(self.hue, self.sat, self.val)
        self.colorChanged.emit(self.current_color)
        self.update()

# --- 主程序窗口 ---
class WallpaperProMax(QWidget):
    def __init__(self):
        super().__init__()
        self.font_dict = {}
        self.init_font_map()
        
        # 初始状态
        self.text_pos = [0.5, 0.5]
        self.text_color = QColor(100, 255, 218) # 默认极客绿
        self.is_dragging = False

        self.initUI()
        self.update_preview()

    def init_font_map(self):
        fonts = fm.findSystemFonts()
        for f in fonts:
            try:
                name = fm.FontProperties(fname=f).get_name()
                if name not in self.font_dict: self.font_dict[name] = f
            except: continue

    def initUI(self):
        self.setWindowTitle('极简壁纸设计器 Pro - 调色圆盘版')
        self.setMinimumSize(1200, 850)
        self.setStyleSheet("background-color: #121212; color: #eee; font-family: 'Segoe UI';")

        main_layout = QHBoxLayout(self)

        # --- 左侧：设计控制面板 ---
        sidebar = QVBoxLayout()
        sidebar.setContentsMargins(15, 15, 15, 15)
        sidebar.setSpacing(12)
        
        # 内容
        sidebar.addWidget(QLabel("文字内容:"))
        self.text_input = QLineEdit("FOCUS")
        self.text_input.textChanged.connect(self.update_preview)
        self.text_input.setStyleSheet("font-size: 16px; padding: 8px; background: #222; border: 1px solid #333; border-radius: 4px;")
        sidebar.addWidget(self.text_input)

        # 字体选择
        sidebar.addWidget(QLabel("字体选择:"))
        self.combo_font = QComboBox()
        self.combo_font.addItems(sorted(self.font_dict.keys()))
        self.combo_font.setCurrentText("Microsoft YaHei UI")
        self.combo_font.currentTextChanged.connect(self.update_preview)
        sidebar.addWidget(self.combo_font)

        # 字号
        sidebar.addWidget(QLabel("字号调节:"))
        self.slider_size = QSlider(Qt.Orientation.Horizontal)
        self.slider_size.setRange(20, 600)
        self.slider_size.setValue(180)
        self.slider_size.valueChanged.connect(self.update_preview)
        sidebar.addWidget(self.slider_size)

        # --- 重点：调色圆盘 ---
        sidebar.addSpacing(10)
        sidebar.addWidget(QLabel("文字颜色 (直观调色圆盘):"))
        self.color_picker = ColorWheelPicker()
        self.color_picker.colorChanged.connect(self.set_color_realtime)
        sidebar.addWidget(self.color_picker, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.hex_label = QLabel("#64FFDA")
        self.hex_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar.addWidget(self.hex_label)

        # 样式选择
        self.check_shadow = QCheckBox("启用叠影阴影")
        self.check_shadow.setChecked(True)
        self.check_shadow.stateChanged.connect(self.update_preview)
        sidebar.addWidget(self.check_shadow)

        sidebar.addStretch()

        # 导出与应用
        sidebar.addWidget(QLabel("多端导出:"))
        btns = QHBoxLayout()
        btn_pc = QPushButton("PC (4K)")
        btn_pc.clicked.connect(lambda: self.export_wallpaper(3840, 2160))
        btn_phone = QPushButton("手机 (竖屏)")
        btn_phone.clicked.connect(lambda: self.export_wallpaper(1080, 1920))
        btns.addWidget(btn_pc); btns.addWidget(btn_phone)
        sidebar.addLayout(btns)

        self.btn_apply = QPushButton("一键应用到桌面")
        self.btn_apply.clicked.connect(self.apply_to_desktop)
        self.btn_apply.setStyleSheet("background: #0078d4; font-weight: bold; padding: 12px; border-radius: 5px;")
        sidebar.addWidget(self.btn_apply)

        main_layout.addLayout(sidebar, 1)

        # --- 右侧：画布预览 (支持拖拽) ---
        self.preview_area = QLabel()
        self.preview_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_area.setStyleSheet("background: #000; border: 1px solid #333; border-radius: 8px;")
        self.preview_area.setMouseTracking(True)
        main_layout.addWidget(self.preview_area, 3)

    # --- 逻辑处理 ---
    def set_color_realtime(self, color):
        self.text_color = color
        self.hex_label.setText(color.name().upper())
        self.update_preview()

    def mousePressEvent(self, event):
        if self.preview_area.geometry().contains(event.pos()):
            self.is_dragging = True
            self.update_pos(event.pos())

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.update_pos(event.pos())

    def update_pos(self, pos):
        local_pos = self.preview_area.mapFromParent(pos)
        rel_x = local_pos.x() / self.preview_area.width()
        rel_y = local_pos.y() / self.preview_area.height()
        self.text_pos = [max(0, min(1, rel_x)), max(0, min(1, rel_y))]
        self.update_preview()

    def mouseReleaseEvent(self, event):
        self.is_dragging = False

    def generate_image(self, width, height):
        img = Image.new('RGB', (width, height), (18, 18, 18)) # 深色背景
        draw = ImageDraw.Draw(img)
        
        font_path = self.font_dict.get(self.combo_font.currentText(), "C:/Windows/Fonts/msyh.ttc")
        font = ImageFont.truetype(font_path, self.slider_size.value())
        
        text = self.text_input.text()
        tc = (self.text_color.red(), self.text_color.green(), self.text_color.blue())
        
        bbox = draw.textbbox((0, 0), text, font=font)
        tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
        x = width * self.text_pos[0] - tw/2
        y = height * self.text_pos[1] - th/2

        if self.check_shadow.isChecked():
            # 绘制阴影层
            draw.text((x+10, y+10), text, font=font, fill=(tc[0]//4, tc[1]//4, tc[2]//4))
        
        draw.text((x, y), text, font=font, fill=tc)
        return img

    def update_preview(self):
        img = self.generate_image(1280, 720)
        data = img.tobytes("raw", "RGB")
        qimg = QImage(data, 1280, 720, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg)
        self.preview_area.setPixmap(pixmap.scaled(self.preview_area.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def apply_to_desktop(self):
        user32 = ctypes.windll.user32
        w, h = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        final = self.generate_image(w, h)
        path = os.path.abspath("temp_wallpaper.jpg")
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