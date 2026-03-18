#!/usr/bin/env python3
"""桌面版入口：从项目根目录启动 WallpaperDIY。"""
import sys
import os

# 将 platforms/desktop 加入路径并切换工作目录
_root = os.path.dirname(os.path.abspath(__file__))
_desktop = os.path.join(_root, "platforms", "desktop")
sys.path.insert(0, _desktop)
os.chdir(_desktop)

# 以 __main__ 身份执行 main.py
import runpy
runpy.run_path(os.path.join(_desktop, "main.py"), run_name="__main__")
