# P3 结构化重构计划

main.py 已超过 2400 行，建议拆分为以下模块以降低回归成本。

## 目标结构

```
WallpaperDIY/
├── main.py          # 入口 + 主窗口组装（精简至 ~200 行）
├── state.py         # 状态定义、序列化、历史
├── renderer.py      # PIL 渲染管线
├── ui_panel.py      # UI 组件（ColorWheelPicker, CollapsibleBox, PreviewLabel 等）
└── constants.py     # 常量（ASPECT_RATIOS, PREVIEW_PROFILES, BUILTIN_COLOR_PRESETS 等）
```

## 拆分策略

### 1. constants.py
- `OUTPUT_DIR`, `ASPECT_RATIOS`, `PREVIEW_PROFILES`, `BUILTIN_COLOR_PRESETS`
- `SAFE_ZONE_OVERLAYS`
- 无依赖，可独立测试

### 2. state.py
- `_build_render_state()` 逻辑
- `_capture_ui_state()` / `_apply_ui_state()` 的序列化格式
- 历史栈 `history`, `future`, `_push_history`, `on_undo`, `on_redo`
- 依赖：需接收 UI 控件引用或通过回调获取值

### 3. renderer.py
- `_build_gradient_background`, `_get_cached_gradient_mask`
- `_blend_background_image`
- `_get_text_metrics`, `_adaptive_shadow_steps`, `_get_quality_settings`
- `_render_image_from_state`（核心渲染）
- `PreviewRenderTask`, `WorkerTask` 等可保留在 main 或移入 renderer
- 依赖：font_cache, bg_image_cache, _gradient_masks 等需注入或作为 Renderer 类成员

### 4. ui_panel.py
- `ColorWheelPicker`
- `CollapsibleBox`
- `PreviewLabel`（含 SAFE_ZONE_OVERLAYS 绘制）
- 纯 UI 组件，无业务逻辑

### 5. main.py（精简后）
- `get_output_dir`, `get_arrow_path`
- `WallpaperUltra` 主窗口：组装 ui_panel、state、renderer
- 事件绑定、initUI 布局
- 入口 `if __name__ == "__main__"`

## 迁移步骤建议

1. **先抽 constants.py**：无风险，立即执行
2. **再抽 ui_panel.py**：ColorWheelPicker、CollapsibleBox、PreviewLabel 独立
3. **抽 renderer.py**：创建 `WallpaperRenderer` 类，接收 state dict，返回 PIL Image
4. **抽 state.py**：将 state 相关逻辑封装，WallpaperUltra 持有 StateManager
5. **每步后跑 `pytest tests/`** 确保无回归

## 依赖关系

```
main.py
  ├── constants.py
  ├── ui_panel.py
  ├── state.py (可选，也可保留在 main)
  └── renderer.py
```

## 测试适配

- `tests/test_render.py`：改为 `from renderer import WallpaperRenderer` 或保持从 main 导入
- 若 renderer 独立，可增加 `tests/test_renderer.py` 纯单元测试
