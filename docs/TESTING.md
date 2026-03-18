# WallpaperDIY 自动化测试说明

## 快速开始

```bash
pip install -r config/requirements-dev.txt
python -m pytest tests/ -v
```

## 测试覆盖

| 模块 | 文件 | 覆盖内容 |
|------|------|----------|
| 工具函数 | `test_utils.py` | get_output_dir, get_arrow_path, 常量校验 |
| 渲染逻辑 | `test_render.py` | 渐变背景、文字度量、mask 缓存 |
| 动态变量 | `test_dynamic_vars.py` | [TIME]/[DATE]/[COUNTDOWN] 替换、字体回退 |

## 开发规范

- **新增功能**：在对应 `test_*.py` 中增加测试用例
- **修改代码**：修改后运行 `pytest tests/`，通过后再继续
- **CI/提交前**：确保所有测试通过

## 配置

- `pytest.ini`：测试路径、输出格式
- `requirements-dev.txt`：pytest 等开发依赖
