#!/usr/bin/env python3
"""
树莓派全屏图片展示器 - 优化版
修复全屏问题和字体支持
"""

import os
import sys
import random
import time
import argparse
from pathlib import Path
from typing import List, Tuple, Optional, Dict
import json
import threading

# 第三方库
try:
    import pygame
    from pygame.locals import *
    from PIL import Image, ImageFile

    # 启用大文件支持
    ImageFile.LOAD_TRUNCATED_IMAGES = True
except ImportError as e:
    print(f"缺少必要的依赖库: {e}")
    print("请安装: pip install pygame pillow")
    sys.exit(1)


class Config:
    """配置文件类"""

    def __init__(self):
        self.image_folder = "images"  # 默认图片文件夹
        self.interval = 5.0  # 默认切换间隔（秒）
        self.random_order = True  # 默认随机播放
        self.fullscreen = True  # 默认全屏
        self.scale_mode = "fit"  # 缩放模式: fit, fill, stretch
        self.background_color = (0, 0, 0)  # 背景色（黑色）
        self.recursive = True  # 是否包含子文件夹
        self.valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff', '.webp'}
        self.fps = 60  # 帧率
        self.rescan_interval = 30  # 重新扫描文件夹间隔（秒）
        self.show_info = True  # 是否显示信息
        self.auto_restart = True  # 播放完毕后自动重新开始
        self.font_path = None  # 自定义字体路径，None表示使用默认字体
        self.font_size = 36  # 字体大小
        self.small_font_size = 24  # 小字体大小
        self.force_fullscreen = True  # 强制全屏，防止窗口化
        self.fullscreen_mode = "fullscreen"  # fullscreen, borderless, window
        self.screen_width = 0  # 屏幕宽度，0表示自动检测
        self.screen_height = 0  # 屏幕高度，0表示自动检测

    @classmethod
    def load_from_file(cls, config_path: str) -> 'Config':
        """从配置文件加载设置"""
        config = cls()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(config, key):
                            # 特殊处理颜色
                            if key == 'background_color' and isinstance(value, list):
                                setattr(config, key, tuple(value))
                            else:
                                setattr(config, key, value)
                print(f"已加载配置文件: {config_path}")
            except Exception as e:
                print(f"配置文件加载失败，使用默认设置: {e}")
        return config

    def save_to_file(self, config_path: str):
        """保存设置到配置文件"""
        try:
            data = {}
            for key in dir(self):
                if not key.startswith('_') and not callable(getattr(self, key)):
                    value = getattr(self, key)
                    # 特殊处理颜色
                    if key == 'background_color' and isinstance(value, tuple):
                        data[key] = list(value)
                    else:
                        data[key] = value
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            print(f"配置已保存到: {config_path}")
        except Exception as e:
            print(f"保存配置失败: {e}")


class FontManager:
    """字体管理器类"""

    def __init__(self, config: Config):
        self.config = config
        self.fonts: Dict[str, pygame.font.Font] = {}
        self._init_fonts()

    def _init_fonts(self):
        """初始化字体"""
        # 尝试加载自定义字体
        if self.config.font_path and os.path.exists(self.config.font_path):
            try:
                # 主字体
                self.fonts['main'] = pygame.font.Font(self.config.font_path, self.config.font_size)
                # 小字体
                self.fonts['small'] = pygame.font.Font(self.config.font_path, self.config.small_font_size)
                print(f"已加载自定义字体: {self.config.font_path}")
                return
            except Exception as e:
                print(f"加载自定义字体失败: {e}")

        # 回退到系统字体
        print("使用系统默认字体")
        try:
            # 尝试加载常用字体
            font_names = ['arial', 'simhei', 'msyh', 'dejavusans']
            for font_name in font_names:
                try:
                    self.fonts['main'] = pygame.font.SysFont(font_name, self.config.font_size)
                    self.fonts['small'] = pygame.font.SysFont(font_name, self.config.small_font_size)
                    print(f"使用系统字体: {font_name}")
                    return
                except:
                    continue
        except:
            pass

        # 最后回退到pygame默认字体
        print("使用pygame默认字体")
        self.fonts['main'] = pygame.font.Font(None, self.config.font_size)
        self.fonts['small'] = pygame.font.Font(None, self.config.small_font_size)

    def get_font(self, size_type: str = 'main') -> pygame.font.Font:
        """获取指定类型的字体"""
        if size_type in self.fonts:
            return self.fonts[size_type]
        return self.fonts['main']


class ImageLoader:
    """图片加载器类，负责管理图片文件列表"""

    def __init__(self, config: Config):
        self.config = config
        self.image_files = []
        self.last_scan_time = 0
        self.lock = threading.Lock()
        self._scan_images()

    def _scan_images(self):
        """扫描图片文件"""
        folder_path = Path(self.config.image_folder)

        if not folder_path.exists():
            print(f"警告: 图片文件夹 '{self.config.image_folder}' 不存在!")
            with self.lock:
                self.image_files = []
            return False

        print(f"正在从 '{self.config.image_folder}' 扫描图片...")

        # 递归查找图片文件
        image_files = []
        try:
            if self.config.recursive:
                for ext in self.config.valid_extensions:
                    # 查找所有扩展名（大小写不敏感）
                    pattern = f"*{ext}"
                    image_files.extend(folder_path.rglob(pattern))
                    # 也查找大写扩展名
                    image_files.extend(folder_path.rglob(pattern.upper()))
            else:
                for ext in self.config.valid_extensions:
                    pattern = f"*{ext}"
                    image_files.extend(folder_path.glob(pattern))
                    image_files.extend(folder_path.glob(pattern.upper()))

            # 去除重复，转换为绝对路径并排序
            image_files = list(set(image_files))
            image_files = sorted([str(f.absolute()) for f in image_files])

            with self.lock:
                self.image_files = image_files
                self.last_scan_time = time.time()

            print(f"找到 {len(image_files)} 张图片")
            return True

        except Exception as e:
            print(f"扫描图片时出错: {e}")
            with self.lock:
                self.image_files = []
            return False

    def get_files(self):
        """获取当前图片文件列表"""
        with self.lock:
            return self.image_files.copy()

    def needs_rescan(self):
        """检查是否需要重新扫描"""
        return time.time() - self.last_scan_time > self.config.rescan_interval

    def rescan_if_needed(self):
        """如果需要则重新扫描"""
        if self.needs_rescan():
            old_count = len(self.get_files())
            success = self._scan_images()
            new_count = len(self.get_files())
            if success and new_count != old_count:
                print(f"重新扫描完成，图片数量变化: {old_count} -> {new_count}")
            return True
        return False

    def shuffle(self):
        """随机打乱图片顺序"""
        with self.lock:
            if self.image_files:
                random.shuffle(self.image_files)
                return True
        return False

    def sort(self):
        """按文件名排序图片"""
        with self.lock:
            if self.image_files:
                self.image_files.sort()
                return True
        return False


class FullscreenManager:
    """全屏管理器类"""

    def __init__(self, config: Config):
        self.config = config
        self.screen = None
        self.display_info = None
        self._init_display()

    def _init_display(self):
        """初始化显示"""
        # 获取显示信息
        pygame.display.init()
        self.display_info = pygame.display.Info()

        # 设置屏幕尺寸
        if self.config.screen_width == 0 or self.config.screen_height == 0:
            self.screen_width = self.display_info.current_w
            self.screen_height = self.display_info.current_h
        else:
            self.screen_width = self.config.screen_width
            self.screen_height = self.config.screen_height

        print(f"屏幕分辨率: {self.screen_width}x{self.screen_height}")

    def create_screen(self):
        """创建屏幕表面"""
        flags = 0

        if self.config.fullscreen:
            if self.config.fullscreen_mode == "borderless":
                # 无边框全屏窗口
                flags = pygame.NOFRAME | pygame.HWSURFACE | pygame.DOUBLEBUF
                self.screen = pygame.display.set_mode(
                    (self.screen_width, self.screen_height), flags
                )
                # 移动窗口到左上角
                os.environ['SDL_VIDEO_WINDOW_POS'] = "0,0"
            else:
                # 真正的全屏模式
                flags = pygame.FULLSCREEN | pygame.HWSURFACE | pygame.DOUBLEBUF
                self.screen = pygame.display.set_mode(
                    (self.screen_width, self.screen_height), flags
                )
        else:
            # 窗口模式
            flags = pygame.RESIZABLE | pygame.HWSURFACE | pygame.DOUBLEBUF
            self.screen = pygame.display.set_mode(
                (1024, 768), flags
            )
            pygame.display.set_caption("图片展示器 (ESC退出, 空格切换, R随机/顺序, F全屏)")

        return self.screen

    def toggle_fullscreen(self):
        """切换全屏模式"""
        self.config.fullscreen = not self.config.fullscreen
        self.create_screen()
        return self.screen


class ImagePlayer:
    """图片播放器类"""

    def __init__(self, config: Config):
        self.config = config
        self.screen = None
        self.clock = None
        self.running = True
        self.current_image_index = 0
        self.image_loader = ImageLoader(config)
        self.current_surface = None
        self.last_change_time = 0
        self.last_rescan_time = 0
        self.font_manager = None
        self.fullscreen_manager = None
        self.info_display_time = 0
        self.fullscreen_check_time = 0

        # 初始化系统
        self._init_system()

        # 加载第一张图片
        self._load_next_image()

    def _init_system(self):
        """初始化系统"""
        pygame.init()

        # 初始化全屏管理器
        self.fullscreen_manager = FullscreenManager(self.config)
        self.screen = self.fullscreen_manager.create_screen()

        self.clock = pygame.time.Clock()

        # 初始化字体管理器
        self.font_manager = FontManager(self.config)

        # 隐藏鼠标（在全屏模式下）
        if self.config.fullscreen:
            pygame.mouse.set_visible(False)

    def _load_image(self, image_path: str) -> Optional[pygame.Surface]:
        """加载并缩放图片以适应屏幕"""
        try:
            # 使用PIL加载图片（支持更多格式）
            pil_image = Image.open(image_path)

            # 如果是GIF，只取第一帧
            if pil_image.format == 'GIF':
                pil_image = pil_image.convert('RGBA')
            else:
                # 转换为RGB模式
                if pil_image.mode == 'RGBA':
                    # 处理透明通道
                    background = Image.new('RGB', pil_image.size, self.config.background_color)
                    background.paste(pil_image, mask=pil_image.split()[3])
                    pil_image = background
                else:
                    pil_image = pil_image.convert('RGB')

            # 转换为Pygame Surface
            mode = pil_image.mode
            size = pil_image.size
            data = pil_image.tobytes()

            pygame_image = pygame.image.fromstring(data, size, mode)

            # 根据缩放模式调整图片大小
            screen_width, screen_height = self.screen.get_size()
            image_width, image_height = pygame_image.get_size()

            if self.config.scale_mode == "stretch":
                # 拉伸填充整个屏幕
                return pygame.transform.scale(pygame_image, (screen_width, screen_height))

            elif self.config.scale_mode == "fill":
                # 填充整个屏幕，保持宽高比，可能裁剪
                scale = max(screen_width / image_width, screen_height / image_height)
                new_width = int(image_width * scale)
                new_height = int(image_height * scale)
                scaled = pygame.transform.scale(pygame_image, (new_width, new_height))

                # 居中裁剪
                x = (new_width - screen_width) // 2
                y = (new_height - screen_height) // 2
                if x < 0 or y < 0:
                    # 如果图片比屏幕小，则居中显示
                    x = max(0, x)
                    y = max(0, y)
                    surface = pygame.Surface((screen_width, screen_height))
                    surface.fill(self.config.background_color)
                    surface.blit(scaled, (x, y))
                    return surface
                return scaled.subsurface((x, y, screen_width, screen_height))

            else:  # "fit" 模式
                # 适应屏幕，保持宽高比，添加黑边
                scale = min(screen_width / image_width, screen_height / image_height)
                new_width = int(image_width * scale)
                new_height = int(image_height * scale)
                scaled = pygame.transform.scale(pygame_image, (new_width, new_height))

                # 创建新的Surface并居中显示
                surface = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
                surface.fill((*self.config.background_color, 255))

                x = (screen_width - new_width) // 2
                y = (screen_height - new_height) // 2
                surface.blit(scaled, (x, y))

                return surface

        except Exception as e:
            print(f"加载图片失败 {image_path}: {e}")
            return None

    def _check_fullscreen_integrity(self):
        """检查全屏完整性，防止意外窗口化"""
        if not self.config.fullscreen or not self.config.force_fullscreen:
            return

        current_time = time.time()
        if current_time - self.fullscreen_check_time > 5.0:  # 每5秒检查一次
            # 检查当前显示模式
            if not pygame.display.get_surface().get_flags() & pygame.FULLSCREEN:
                if self.config.fullscreen_mode == "borderless":
                    print("检测到全屏丢失，正在恢复无边框全屏...")
                else:
                    print("检测到全屏丢失，正在恢复全屏...")
                self.screen = self.fullscreen_manager.create_screen()
                # 重新加载当前图片以适应新屏幕
                if self.current_surface:
                    self._load_next_image()

            self.fullscreen_check_time = current_time

    def _load_next_image(self):
        """加载下一张图片"""
        image_files = self.image_loader.get_files()

        if not image_files:
            print("没有找到图片，等待中...")
            self.current_surface = None
            self.last_change_time = time.time()
            return

        # 确保索引在有效范围内
        if self.current_image_index >= len(image_files):
            self.current_image_index = 0

        image_path = image_files[self.current_image_index]

        try:
            print(f"显示: {Path(image_path).name} ({self.current_image_index + 1}/{len(image_files)})")
            self.current_surface = self._load_image(image_path)

            # 如果加载失败，尝试下一张
            if self.current_surface is None:
                print(f"跳过无法加载的图片: {Path(image_path).name}")
                self.current_image_index = (self.current_image_index + 1) % len(image_files)
                self._load_next_image()
                return

            self.last_change_time = time.time()
            self.info_display_time = time.time() + 3  # 显示信息3秒

        except Exception as e:
            print(f"加载图片出错: {e}")
            self.current_surface = None

    def _next_image(self):
        """切换到下一张图片"""
        image_files = self.image_loader.get_files()

        if not image_files:
            print("没有图片可显示")
            return

        # 移动到下一张图片
        self.current_image_index += 1

        # 如果超过范围，回到第一张
        if self.current_image_index >= len(image_files):
            self.current_image_index = 0
            print("=== 重新开始播放 ===")
            # 如果是随机模式且需要自动重新开始，则重新打乱
            if self.config.random_order and self.config.auto_restart:
                print("重新打乱图片顺序")
                self.image_loader.shuffle()

        self._load_next_image()

    def _prev_image(self):
        """切换到上一张图片"""
        image_files = self.image_loader.get_files()

        if not image_files:
            print("没有图片可显示")
            return

        # 移动到上一张图片
        self.current_image_index -= 1

        # 如果小于0，回到最后一张
        if self.current_image_index < 0:
            self.current_image_index = len(image_files) - 1

        self._load_next_image()

    def _toggle_random_order(self):
        """切换随机/顺序播放模式"""
        self.config.random_order = not self.config.random_order

        image_files = self.image_loader.get_files()
        if image_files:
            if self.config.random_order:
                self.image_loader.shuffle()
                print("切换到随机播放模式")
            else:
                self.image_loader.sort()
                print("切换到顺序播放模式")

            # 重置到第一张
            self.current_image_index = 0
            self._load_next_image()

            # 显示提示信息
            self.info_display_time = time.time() + 3

    def _toggle_fullscreen(self):
        """切换全屏模式"""
        # 切换全屏状态
        self.config.fullscreen = not self.config.fullscreen

        # 重新创建屏幕
        self.screen = self.fullscreen_manager.toggle_fullscreen()

        # 显示/隐藏鼠标
        pygame.mouse.set_visible(not self.config.fullscreen)

        # 重新加载当前图片
        self._load_next_image()

        # 显示提示信息
        self.info_display_time = time.time() + 3
        print(f"切换到{'全屏' if self.config.fullscreen else '窗口'}模式")

    def _show_message(self, message: str, duration: float = 3.0):
        """显示临时消息"""
        if self.font_manager:
            font = self.font_manager.get_font('main')
            text = font.render(message, True, (255, 255, 255))
            text_rect = text.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))

            # 半透明背景
            bg = pygame.Surface((text_rect.width + 40, text_rect.height + 20), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 180))

            self.screen.blit(bg, (text_rect.x - 20, text_rect.y - 10))
            self.screen.blit(text, text_rect)
            pygame.display.flip()

            # 等待指定时间
            wait_start = time.time()
            while time.time() - wait_start < duration:
                for event in pygame.event.get():
                    if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                        return
                pygame.time.wait(10)

    def _show_status_overlay(self):
        """显示状态叠加层"""
        image_files = self.image_loader.get_files()

        if not self.config.show_info:
            return

        # 只在信息显示时间内显示，或者总是显示（如果没有图片）
        if image_files and time.time() > self.info_display_time:
            return

        # 显示当前图片信息
        lines = []

        if image_files:
            current_file = Path(image_files[self.current_image_index]).name
            lines.append(f"{current_file}")
            lines.append(f"图片: {self.current_image_index + 1}/{len(image_files)}")

            if self.config.random_order:
                lines.append("模式: 随机")
            else:
                lines.append("模式: 顺序")

            lines.append(f"间隔: {self.config.interval}秒")
        else:
            lines.append("等待图片中...")
            lines.append(f"文件夹: {self.config.image_folder}")
            lines.append(
                f"下次扫描: {int(self.config.rescan_interval - (time.time() - self.image_loader.last_scan_time))}秒")

        # 渲染文本行
        y_pos = 20
        for line in lines:
            font = self.font_manager.get_font('small')
            text = font.render(line, True, (255, 255, 255))
            text_bg = pygame.Surface((text.get_width() + 20, text.get_height() + 10), pygame.SRCALPHA)
            text_bg.fill((0, 0, 0, 180))
            self.screen.blit(text_bg, (10, y_pos - 5))
            self.screen.blit(text, (20, y_pos))
            y_pos += text.get_height() + 10

        # 显示操作提示（只在Windows或非全屏时显示）
        if sys.platform == 'win32' or not self.config.fullscreen:
            hints = [
                "ESC:退出  空格:下一张  ←/→:上一张/下一张",
                "R:随机/顺序  F:全屏切换  S:重新扫描"
            ]

            y_pos = self.screen.get_height() - 60
            for hint in hints:
                font = self.font_manager.get_font('small')
                text = font.render(hint, True, (200, 200, 200))
                text_bg = pygame.Surface((text.get_width() + 20, text.get_height() + 10), pygame.SRCALPHA)
                text_bg.fill((0, 0, 0, 180))
                self.screen.blit(text_bg, (10, y_pos - 5))
                self.screen.blit(text, (20, y_pos))
                y_pos += text.get_height() + 10

    def _show_no_images_message(self):
        """显示没有图片的消息"""
        if self.font_manager:
            self.screen.fill(self.config.background_color)

            font = self.font_manager.get_font('main')
            small_font = self.font_manager.get_font('small')

            messages = [
                "没有找到图片",
                f"文件夹: {self.config.image_folder}",
                f"支持格式: {', '.join(self.config.valid_extensions)}",
                "程序会定期自动扫描",
                "按ESC退出"
            ]

            y_pos = self.screen.get_height() // 2 - 100
            for msg in messages:
                text = font.render(msg, True, (255, 255, 255))
                rect = text.get_rect(center=(self.screen.get_width() // 2, y_pos))
                self.screen.blit(text, rect)
                y_pos += 50

            # 显示下次扫描时间
            if self.image_loader.last_scan_time > 0:
                next_scan = int(self.config.rescan_interval - (time.time() - self.image_loader.last_scan_time))
                if next_scan > 0:
                    scan_text = f"下次扫描: {next_scan}秒后"
                    text = small_font.render(scan_text, True, (200, 200, 200))
                    rect = text.get_rect(center=(self.screen.get_width() // 2, y_pos + 20))
                    self.screen.blit(text, rect)

    def _handle_events(self):
        """处理事件"""
        for event in pygame.event.get():
            if event.type == QUIT:
                self.running = False
                return
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    self.running = False
                    return
                elif event.key == K_SPACE:
                    self._next_image()
                elif event.key == K_r:
                    self._toggle_random_order()
                elif event.key == K_LEFT:
                    self._prev_image()
                elif event.key == K_RIGHT:
                    self._next_image()
                elif event.key == K_f:
                    self._toggle_fullscreen()
                elif event.key == K_s:
                    print("手动重新扫描图片...")
                    self.image_loader._scan_images()
                    image_files = self.image_loader.get_files()
                    if image_files:
                        self.current_image_index = 0
                        self._load_next_image()
                        self._show_message(f"找到 {len(image_files)} 张图片", 2.0)
                    else:
                        self._show_message("未找到图片", 2.0)
                elif event.key == K_i:
                    self.config.show_info = not self.config.show_info
                    self.info_display_time = time.time() + 3
                elif event.key == K_m:
                    # 切换鼠标可见性
                    current_visible = pygame.mouse.get_visible()
                    pygame.mouse.set_visible(not current_visible)
                    print(f"鼠标{'显示' if not current_visible else '隐藏'}")
            elif event.type == VIDEORESIZE:
                # 如果窗口大小改变，重新加载图片
                if not self.config.fullscreen:
                    self.screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    self._load_next_image()

    def _update(self):
        """更新逻辑"""
        current_time = time.time()

        # 自动切换图片
        if self.current_surface and current_time - self.last_change_time >= self.config.interval:
            self._next_image()

        # 定期重新扫描文件夹
        if current_time - self.last_rescan_time > self.config.rescan_interval:
            if self.image_loader.rescan_if_needed():
                image_files = self.image_loader.get_files()
                if image_files and self.current_image_index >= len(image_files):
                    self.current_image_index = 0
                    self._load_next_image()
            self.last_rescan_time = current_time

        # 检查全屏完整性
        self._check_fullscreen_integrity()

    def _render(self):
        """渲染画面"""
        # 清屏
        self.screen.fill(self.config.background_color)

        # 显示当前图片
        if self.current_surface:
            self.screen.blit(self.current_surface, (0, 0))
        else:
            # 没有图片时显示提示
            image_files = self.image_loader.get_files()
            if not image_files:
                self._show_no_images_message()

        # 显示状态信息
        self._show_status_overlay()

        # 更新显示
        pygame.display.flip()

    def run(self):
        """运行主循环"""
        print("=" * 50)
        print("图片展示器已启动")
        print("按ESC键退出程序")
        print("=" * 50)

        while self.running:
            self._handle_events()
            if not self.running:
                break

            self._update()
            self._render()
            self.clock.tick(self.config.fps)

        print("正在退出程序...")
        pygame.quit()
        sys.exit(0)


def find_system_fonts():
    """查找系统可用字体"""
    print("\n查找系统字体...")

    # 常见字体列表
    common_fonts = [
        # Windows 字体
        "C:/Windows/Fonts/msyh.ttc",  # 微软雅黑
        "C:/Windows/Fonts/simhei.ttf",  # 黑体
        "C:/Windows/Fonts/simsun.ttc",  # 宋体
        "C:/Windows/Fonts/arial.ttf",  # Arial

        # Linux 字体
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",

        # macOS 字体
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    for font_path in common_fonts:
        if os.path.exists(font_path):
            print(f"找到字体: {font_path}")
            return font_path

    print("未找到常用字体，将使用系统默认字体")
    return None


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='树莓派全屏图片展示器 - 优化版')
    parser.add_argument('--folder', '-f', type=str, default=None,
                        help='图片文件夹路径 (默认: 使用配置文件中的设置)')
    parser.add_argument('--interval', '-i', type=float, default=None,
                        help='图片切换间隔（秒）(默认: 使用配置文件中的设置)')
    parser.add_argument('--order', '-o', type=str, choices=['random', 'sequential'], default=None,
                        help='播放顺序: random(随机) 或 sequential(顺序) (默认: 使用配置文件中的设置)')
    parser.add_argument('--scale', '-s', type=str, choices=['fit', 'fill', 'stretch'], default=None,
                        help='图片缩放模式: fit(适应), fill(填充), stretch(拉伸) (默认: 使用配置文件中的设置)')
    parser.add_argument('--no-fullscreen', action='store_true',
                        help='禁用全屏模式（开发时使用）')
    parser.add_argument('--config', '-c', type=str, default='config.json',
                        help='配置文件路径 (默认: config.json)')
    parser.add_argument('--save-config', action='store_true',
                        help='将当前设置保存到配置文件')
    parser.add_argument('--list-fonts', action='store_true',
                        help='查找系统可用字体')
    parser.add_argument('--font', type=str, default=None,
                        help='自定义字体文件路径')
    parser.add_argument('--borderless', action='store_true',
                        help='使用无边框全屏模式')

    args = parser.parse_args()

    # 如果请求列出字体
    if args.list_fonts:
        find_system_fonts()
        return

    # 加载配置
    config = Config.load_from_file(args.config)

    # 应用命令行参数（如果不为None）
    if args.folder is not None:
        config.image_folder = args.folder
    if args.interval is not None:
        config.interval = args.interval
    if args.order is not None:
        config.random_order = (args.order == 'random')
    if args.scale is not None:
        config.scale_mode = args.scale
    if args.font is not None:
        config.font_path = args.font
    if args.no_fullscreen:
        config.fullscreen = False
    if args.borderless:
        config.fullscreen_mode = "borderless"

    # 如果指定保存配置，则保存
    if args.save_config:
        config.save_to_file(args.config)
        print("配置已保存。重新启动程序使配置生效。")
        return

    # 创建并运行播放器
    try:
        player = ImagePlayer(config)
        player.run()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        input("按Enter键退出...")


if __name__ == "__main__":
    main()