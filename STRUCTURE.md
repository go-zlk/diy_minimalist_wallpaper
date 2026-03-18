# WallpaperDIY 目录结构说明

```
WallpaperDIY/
├── config/                 # 公共配置
│   ├── requirements-dev.txt
│   └── user_color_presets.json
├── docs/                   # 文档
│   ├── cursor_handover.md
│   ├── REFACTOR_PLAN.md
│   ├── TESTING.md
│   └── flutter_migration_plan.md
├── platforms/
│   ├── desktop/            # Python/PyQt6 桌面版 (Windows)
│   │   ├── main.py
│   │   └── WallpaperUltraPro.spec
│   └── mobile/             # Flutter 移动端 (iOS/Android)
│       └── (原 flutter_app 内容)
├── tests/                  # 自动化测试
├── archive/                # 归档文件（历史/临时）
├── .cursor/
├── pytest.ini
├── README.md
├── LICENSE
├── requirements-dev.txt    # 根目录快捷入口
└── run_desktop.py          # 桌面版入口
```

## 运行方式

- **桌面版**: `python run_desktop.py` 或 `python platforms/desktop/main.py`
- **测试**: `python -m pytest tests/ -v`（从项目根目录）
- **移动端**: `cd platforms/mobile && flutter run`
- **打包**: `cd platforms/desktop && pyinstaller WallpaperUltraPro.spec`
