## 🎯 核心优势

### **跨平台支持**

- Windows 和树莓派完全兼容
- Qt 框架原生跨平台支持
- 更好的硬件加速

### **功能**

- ✅ 多格式支持(通过 Pillow)
- ✅ 全屏展示
- ✅ 随机/顺序播放
- ✅ 键盘控制
- ✅ 配置管理
- ✅ 自动扫描
- ✅ 状态显示

## 📦 安装依赖

```bash
# Windows
pip install PySide6 Pillow

# 树莓派 (Raspberry Pi OS)
sudo apt-get install python3-pyside6.qtcore python3-pyside6.qtgui python3-pyside6.qtwidgets
pip install Pillow
```

## ⌨️ 快捷键

| 按键     | 功能          |
| -------- | ------------- |
| ESC / Q  | 退出          |
| 空格 / → | 下一张        |
| ←        | 上一张        |
| R        | 切换随机/顺序 |
| F        | 切换全屏      |
| I        | 显示/隐藏信息 |
| M        | 显示/隐藏鼠标 |
| S        | 手动重新扫描  |
| Z        | 切换缩放模式  |
| P        | 暂停/继续播放 |

## 🔧 配置文件示例

程序会自动生成 `slideshow_config.json`:

```json
{
  "image_folder": "images",
  "recursive": true,
  "interval": 5,
  "random": true,
  "fullscreen": true,
  "scale_mode": "fit",
  "extensions": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".webp"],
  "rescan_interval": 30,
  "show_info": true,
  "font_size": 20,
  "info_color": "#FFFFFF",
  "background_color": "#000000"
}
```

## 🍓 树莓派部署

### 1. 创建服务文件

```bash
sudo nano /etc/systemd/system/slideshow.service
```

```ini
[Unit]
Description=PySide6 Slideshow
After=graphical.target

[Service]
Type=simple
User=pi
Environment=DISPLAY=:0
Environment=QT_QPA_PLATFORM=xcb
WorkingDirectory=/home/pi/slideshow
ExecStart=/usr/bin/python3 /home/pi/slideshow/slideshow.py
Restart=always

[Install]
WantedBy=graphical.target
```

### 2. 启用服务

```bash
sudo systemctl enable slideshow.service
sudo systemctl start slideshow.service
```

### 3. 禁用屏保

```bash
# 编辑 autostart
mkdir -p ~/.config/lxsession/LXDE-pi
nano ~/.config/lxsession/LXDE-pi/autostart

# 添加以下内容
@xset s off
@xset -dpms
@xset s noblank
```

## 📄 许可证

[GPLv3](https://gnu.ac.cn/licenses/gpl-3.0.html)
