#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PySide6 全屏图片播放器
支持多格式、全屏展示、播放控制、配置管理
"""

import sys
import json
import random
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QLabel,
    QWidget,
    QVBoxLayout,
    QMessageBox,
)
from PySide6.QtCore import Qt, QTimer, Signal, QThread, QSize, QPoint
from PySide6.QtGui import (
    QPixmap,
    QImage,
    QKeyEvent,
    QPainter,
    QFont,
    QColor,
    QCursor,
    QPalette,
    QFontDatabase,
)
from PIL import Image


class Config:
    """配置管理类"""

    DEFAULT_CONFIG = {
        "image_folder": "",
        "recursive": True,
        "interval": 5,
        "random": True,
        "fullscreen": True,
        "scale_mode": "fit",  # fit, fill, stretch
        "extensions": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"],
        "rescan_interval": 300,
        "show_info": True,
        "show_clock": True,
        "font_path": None,
        "font_size": 20,
        "info_color": "#FFFFFF",
        "background_color": "#000000",
    }

    def __init__(self, config_file: str = "slideshow_config.json"):
        self.config_file = Path(config_file)
        self.config = self.load()

    def load(self) -> dict:
        """加载配置"""
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    return {**self.DEFAULT_CONFIG, **loaded}
            except Exception as e:
                print(f"配置加载失败: {e},使用默认配置")
        return self.DEFAULT_CONFIG.copy()

    def save(self):
        """保存配置"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"配置保存失败: {e}")

    def get(self, key: str, default=None):
        return self.config.get(key, default)

    def set(self, key: str, value):
        self.config[key] = value
        self.save()


class ImageScanner(QThread):
    """图片扫描线程"""

    scan_complete = Signal(list)

    def __init__(self, folder: str, extensions: List[str], recursive: bool):
        super().__init__()
        self.folder = Path(folder)
        self.extensions = [ext.lower() for ext in extensions]
        self.recursive = recursive

    def run(self):
        """扫描图片文件"""
        images = []
        try:
            if not self.folder.exists():
                self.scan_complete.emit(images)
                return

            pattern = "**/*" if self.recursive else "*"
            for path in self.folder.glob(pattern):
                if path.is_file() and path.suffix.lower() in self.extensions:
                    images.append(str(path))

            self.scan_complete.emit(images)
        except Exception as e:
            print(f"扫描错误: {e}")
            self.scan_complete.emit([])


class ImageViewer(QLabel):
    """图片显示组件"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setScaledContents(False)
        self.current_pixmap: Optional[QPixmap] = None
        self.scale_mode = "fit"
        self.info_text = ""
        self.show_info_flag = True
        self.show_clock_flag = True
        self.clock_text = ""
        self.info_font = QFont("Arial", 20)
        self.info_color = QColor("#FFFFFF")

    def set_image(self, image_path: str, scale_mode: str = "fit"):
        """设置并显示图片"""
        self.scale_mode = scale_mode
        try:
            # 使用 Pillow 加载图片以支持更多格式
            pil_image = Image.open(image_path)

            # 转换为 RGB 模式
            if pil_image.mode not in ('RGB', 'RGBA'):
                pil_image = pil_image.convert('RGB')

            # 转换为 QImage
            if pil_image.mode == 'RGBA':
                data = pil_image.tobytes("raw", "RGBA")
                qimage = QImage(
                    data, pil_image.width, pil_image.height, QImage.Format_RGBA8888
                )
            else:
                data = pil_image.tobytes("raw", "RGB")
                qimage = QImage(
                    data, pil_image.width, pil_image.height, QImage.Format_RGB888
                )

            self.current_pixmap = QPixmap.fromImage(qimage)
            self.update_display()
            return True

        except Exception as e:
            print(f"图片加载失败 {image_path}: {e}")
            return False

    def update_display(self):
        """更新显示"""
        if not self.current_pixmap:
            return

        size = self.size()
        if self.scale_mode == "fit":
            # 保持宽高比适应
            scaled = self.current_pixmap.scaled(
                size, Qt.KeepAspectRatio, Qt.SmoothTransformation
            )
        elif self.scale_mode == "fill":
            # 填充(可能裁剪)
            scaled = self.current_pixmap.scaled(
                size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation
            )
        else:  # stretch
            # 拉伸填充
            scaled = self.current_pixmap.scaled(
                size, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )

        self.setPixmap(scaled)

    def resizeEvent(self, event):
        """窗口大小改变时重新缩放"""
        super().resizeEvent(event)
        self.update_display()

    def paintEvent(self, event):
        """绘制事件 - 添加信息显示和时钟"""
        super().paintEvent(event)

        painter = QPainter(self)
        painter.setFont(self.info_font)
        painter.setPen(self.info_color)

        # 绘制左下角信息
        if self.show_info_flag and self.info_text:
            # 计算文字大小
            text_rect = painter.boundingRect(
                0, 0, self.width(), self.height(), 0, self.info_text
            )

            # 设置背景矩形的内边距
            padding = 6
            bg_rect = text_rect.adjusted(-padding, -padding, padding, padding)

            # 将背景矩形定位到左下角
            margin = 20
            bg_rect.moveBottomLeft(self.rect().bottomLeft() + QPoint(margin, -margin))
            text_rect.moveBottomLeft(bg_rect.bottomLeft() + QPoint(padding, -padding))

            # 绘制半透明背景
            painter.setBrush(QColor(0, 0, 0, 120))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bg_rect, 4, 4)

            # 恢复文字颜色和绘制文字
            painter.setPen(self.info_color)
            painter.drawText(text_rect, 0, self.info_text)

        # 绘制右上角时钟
        if self.show_clock_flag and self.clock_text:
            # 根据窗口大小动态调整时钟字体
            clock_font = QFont(self.info_font)
            clock_size = max(24, int(self.width() * 0.025))
            clock_font.setPointSize(clock_size)
            painter.setFont(clock_font)

            # 计算时钟文字大小
            clock_rect = painter.boundingRect(
                0, 0, self.width(), self.height(), 0, self.clock_text
            )

            # 设置背景矩形的内边距
            padding = 8
            bg_rect = clock_rect.adjusted(-padding, -padding, padding, padding)

            # 将背景矩形定位到右上角
            margin = 20
            bg_rect.moveTopRight(self.rect().topRight() + QPoint(-margin, margin))
            clock_rect.moveTopRight(bg_rect.topRight() + QPoint(-padding, padding))

            # 绘制半透明背景
            painter.setBrush(QColor(0, 0, 0, 120))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(bg_rect, 4, 4)

            # 恢复文字颜色和绘制时钟
            painter.setPen(self.info_color)
            painter.drawText(clock_rect, 0, self.clock_text)

        painter.end()

    def set_info(self, text: str):
        """设置信息文本"""
        self.info_text = text
        self.update()

    def set_clock(self, text: str):
        """设置时钟文本"""
        self.clock_text = text
        self.update()


class SlideshowWindow(QMainWindow):
    """主窗口"""

    def __init__(self):
        super().__init__()
        self.config = Config()
        self.images: List[str] = []
        self.current_index = 0
        self.is_random = self.config.get("random", True)

        self.setup_ui()
        self.setup_timers()
        self.start_scan()

    def setup_ui(self):
        """设置UI"""
        self.setWindowTitle("图片播放器")

        # 设置背景色
        bg_color = self.config.get("background_color", "#000000")
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(bg_color))
        self.setPalette(palette)

        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建布局
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # 创建图片显示组件
        self.image_viewer = ImageViewer()
        self.image_viewer.show_info_flag = self.config.get("show_info", True)
        self.image_viewer.show_clock_flag = self.config.get("show_clock", True)

        # 设置字体
        font_path = self.config.get("font_path")
        font_size: int = self.config.get("font_size", 20)
        font_family = loadFont(font_path)
        font_family.setBold(True)
        font_family.setPointSize(font_size)
        self.image_viewer.info_font = font_family

        self.image_viewer.info_color = QColor(self.config.get("info_color", "#FFFFFF"))

        layout.addWidget(self.image_viewer)

        # 设置全屏
        if self.config.get("fullscreen", True):
            self.showFullScreen()
        else:
            self.showMaximized()

        # 隐藏鼠标
        self.setCursor(Qt.BlankCursor)

    def setup_timers(self):
        """设置定时器"""
        # 播放定时器
        self.play_timer = QTimer()
        self.play_timer.timeout.connect(self.next_image)
        interval = self.config.get("interval", 5) * 1000
        self.play_timer.setInterval(interval)

        # 扫描定时器
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.start_scan)
        rescan_interval = self.config.get("rescan_interval", 30) * 1000
        self.scan_timer.setInterval(rescan_interval)
        self.scan_timer.start()

        # 时钟更新定时器
        self.clock_timer = QTimer()
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.setInterval(200)  # 每0.2秒更新
        self.clock_timer.start()

    def update_clock(self):
        """更新时钟显示"""
        now = datetime.now()
        clock_text = now.strftime("%H:%M")  # %H:%M:%S
        self.image_viewer.set_clock(clock_text)

    def start_scan(self):
        """开始扫描图片"""
        folder = self.config.get("image_folder", "images")
        extensions = self.config.get("extensions", [".jpg", ".png"])
        recursive = self.config.get("recursive", True)

        self.scanner = ImageScanner(folder, extensions, recursive)
        self.scanner.scan_complete.connect(self.on_scan_complete)
        self.scanner.start()

    def on_scan_complete(self, images: List[str]):
        """扫描完成回调"""
        if not images:
            info = "未找到图片,等待下次扫描..."
            self.image_viewer.set_info(info)
            print(info)
            self.play_timer.stop()
            return

        # 更新图片列表
        old_count = len(self.images)
        self.images = images

        if self.is_random:
            random.shuffle(self.images)

        print(f"找到 {len(self.images)} 张图片")

        # 如果是首次加载或列表为空,显示第一张
        if old_count == 0:
            self.current_index = 0
            self.show_current_image()
            self.play_timer.start()

    def show_current_image(self):
        """显示当前图片"""
        if not self.images:
            return

        image_path = self.images[self.current_index]
        scale_mode = self.config.get("scale_mode", "fit")

        success = self.image_viewer.set_image(image_path, scale_mode)

        if success:
            _interval = self.config.get("interval")
            # 更新信息显示
            filename = Path(image_path).name
            info = f"{filename} | {self.current_index + 1}/{len(self.images)} | "
            info += f"{'R' if self.is_random else 'O'} | {scale_mode.upper()} | {_interval}s"
            self.image_viewer.set_info(info)
        else:
            # 图片加载失败,跳到下一张
            self.next_image()

    def next_image(self):
        """下一张图片"""
        if not self.images:
            return

        if self.is_random:
            self.current_index = random.randint(0, len(self.images) - 1)
        else:
            self.current_index = (self.current_index + 1) % len(self.images)

        self.show_current_image()

    def prev_image(self):
        """上一张图片"""
        if not self.images:
            return

        if not self.is_random:
            self.current_index = (self.current_index - 1) % len(self.images)

        self.show_current_image()

    def toggle_random(self):
        """切换随机/顺序模式"""
        self.is_random = not self.is_random
        self.config.set("random", self.is_random)

        if self.is_random:
            random.shuffle(self.images)

        self.show_current_image()

    def toggle_fullscreen(self):
        """切换全屏"""
        if self.isFullScreen():
            self.showMaximized()
        else:
            self.showFullScreen()

    def toggle_info(self):
        """切换信息显示"""
        self.image_viewer.show_info_flag = not self.image_viewer.show_info_flag
        self.config.set("show_info", self.image_viewer.show_info_flag)
        self.image_viewer.update()

    def toggle_clock(self):
        """切换时钟显示"""
        self.image_viewer.show_clock_flag = not self.image_viewer.show_clock_flag
        self.config.set("show_clock", self.image_viewer.show_clock_flag)
        self.image_viewer.update()

    def toggle_mouse(self):
        """切换鼠标可见性"""
        if self.cursor().shape() == Qt.BlankCursor:
            self.setCursor(Qt.ArrowCursor)
        else:
            self.setCursor(Qt.BlankCursor)

    def cycle_scale_mode(self):
        """循环切换缩放模式"""
        modes = ["fit", "fill", "stretch"]
        current = self.config.get("scale_mode", "fit")
        current_idx = modes.index(current) if current in modes else 0
        next_mode = modes[(current_idx + 1) % len(modes)]

        self.config.set("scale_mode", next_mode)
        self.image_viewer.scale_mode = next_mode
        self.image_viewer.update_display()
        self.show_current_image()

    def keyPressEvent(self, event: QKeyEvent):
        """键盘事件处理"""
        key = event.key()

        if key == Qt.Key_Escape or key == Qt.Key_Q or key == Qt.Key.Key_X:
            # 退出
            self.close()
        elif key == Qt.Key_Space or key == Qt.Key_Right:
            # 下一张
            self.next_image()
        elif key == Qt.Key_Left:
            # 上一张
            self.prev_image()
        elif key == Qt.Key_R:
            # 切换随机模式
            self.toggle_random()
        elif key == Qt.Key_F:
            # 切换全屏
            self.toggle_fullscreen()
        elif key == Qt.Key_I:
            # 切换信息显示
            self.toggle_info()
        elif key == Qt.Key_C:
            # 切换时钟显示
            self.toggle_clock()
        elif key == Qt.Key_M:
            # 切换鼠标
            self.toggle_mouse()
        elif key == Qt.Key_S:
            # 手动扫描
            self.start_scan()
        elif key == Qt.Key_Z:
            # 循环缩放模式
            self.cycle_scale_mode()
        elif key == Qt.Key_P:
            # 暂停/继续
            if self.play_timer.isActive():
                self.play_timer.stop()
            else:
                self.play_timer.start()

    def closeEvent(self, event):
        """关闭事件"""
        self.play_timer.stop()
        self.scan_timer.stop()
        self.clock_timer.stop()
        if hasattr(self, 'scanner'):
            self.scanner.quit()
            self.scanner.wait()
        event.accept()


def loadFont(path: str | None) -> QFont:
    if path is None:
        return QFont()
    # 尝试加载字体
    font_path = path  # 替换为你的字体路径
    font_id = QFontDatabase.addApplicationFont(font_path)

    if font_id < 0:
        print(f"错误:无法加载字体文件 {font_path}")
        # 可以在这里设置一个备用字体
        font_family = "Arial"
    else:
        # 获取加载字体的家族名称
        font_families = QFontDatabase.applicationFontFamilies(font_id)
        if font_families:
            font_family = font_families[0]
            print(f"字体加载成功: {font_family}")
        else:
            font_family = "Arial"
    return QFont(font_family)


def main():
    """主函数"""
    app = QApplication(sys.argv)

    app.setApplicationName("PySide6 图片播放器")

    # 设置应用样式
    app.setStyle("Fusion")

    window = SlideshowWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
