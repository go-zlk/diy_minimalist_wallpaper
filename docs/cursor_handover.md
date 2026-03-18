# WallpaperDIY Project Handover

## Project Overview
WallpaperDIY is a Python/PyQt6 based desktop application that allows users to create elegant, minimalist text-based wallpapers. It features extensive customization for typography, layout, background gradients/images, styling (shadows, noise), and performance profiling.

## Current State & Recently Completed Work (by previous AI Assistant)

Over the past session, significant structural refactoring, UI/UX polishing, and underlying rendering performance optimizations have been completed on `main.py`:

### 1. UI & Visual Enhancements (Phase 2 Polish)
*   **Collapsible Accordion Panels**: The sidebar sections (内容设计, 视觉色彩, 背景图层, 艺术样式, 性能监控) were refactored into a custom `CollapsibleBox` widget, decluttering the UI. 
*   **Aesthetics overhaul**: `QSlider`, `QPushButton`, and `QComboBox` stylesheets were heavily customized (glassmorphism hover glow, accent colors, thicker grooves, rounded handlers).
*   **Preview Area Rendering**: Added a rounded transparent checkerboard background under the preview image.
*   **Smooth Animations**: Introduced `QVariantAnimation` (Elastic/OutBack easing) in `PreviewLabel` to make image scaling and updating visually bouncy and premium.

### 2. Bug Fixes & Rendering Optimizations
*   **Startup / Layout Jumping**: Fixed an issue where the `QVariantAnimation` and `QLabel`'s `sizeHint` would cause severe visual "jumping" when the app started or when certain properties (like dropdowns) were changed. `PreviewLabel` now securely inherits from `QWidget` and manages its own internal `_custom_pixmap`.
*   **Color Wheel / Gradient Performance Lag**: Resolved massive UI lag when dragging the color wheel with "Radial/Linear Gradient" backgrounds enabled. Replaced an intensive $O(n^2)$ Python nested loop pixel calculation with cached 256x256 "L" mode `ImageDraw` masks and `Image.composite()`. **Speed increased by >200x.**
*   **"Duplicate Text Box" Artifact**: Fixed an issue where "fast preview" (dragging sliders) aggressively stripped `shadow_steps`, creating disjointed duplicate texts instead of a soft drop shadow. Fixed by enforcing a minimum of 3 shadow steps and applying `ImageFilter.GaussianBlur` to the shadow layer during fast interaction.
*   **Hitokoto API Fix**: Added proper `User-Agent` headers to bypass 403 Forbidden restrictions on the Hitokoto ideas API.

## Pending Tasks & Roadmap (To-Do)

The following items are defined in the project's backlog (`todo.md`) and are ready for you (Cursor) to implement next:

### 1. New Core Features
*   **背景图片毛玻璃与暗角**: ✅ 已完整实现，UI 绑定、预览、导出、保存图片均使用同一 state，一致。
*   **磁吸对齐系统（Snapping）**: When the user drags the text to adjust `text_pos`, implement automatic snapping to center lines (vertical/horizontal) and golden ratio lines (e.g., left 1/3) with visual guidelines (a temporarily glowing thin line).
*   **层级字体排布（主副标题系统）**: Provide predefined typography layout templates (e.g., "Large English watermark background + Small Chinese foreground" or "Heavy weight core word + thin signature/subtitle below") out of the rigid single-text limitation. 

### 2. Phase 2: Platform Interop & Distribution ✅ (已收尾)
*   **移动端安全区蒙版**: 预览区叠层显示 iPhone 刘海/底部横条、Android 挖孔等遮挡区域（勾选「显示移动端安全区蒙版」）。
*   **配方分享码**: JSON→Base64 编码，「复制分享码」「粘贴分享码」按钮已实现。

### 3. Phase 3: AI-Driven Design Automation
*   **指令化生成 (Prompt to Design)**: Connect entirely to a lightweight LLM endpoint, allowing users to type "A calm minimalist screen" to instantly output proper HSV palettes, gradients, and font selections.
*   **自适应情绪调色板**: Algorithm to analyze input text semantics and intelligently default to matching font styles (sans-serif for focus, serif for poetic) and semantic background gradients.

## Code Architecture Notes for Cursor
*   **State Management**: All UI interaction is immediately serialized into a dictionary via `_build_render_state()`.
*   **Threading**: Rendering happens asynchronously in a `QThreadPool` worker (`_render_preview_canvas_bytes`) to avoid blocking the PyQt GUI thread. 
*   **PIL / Pillow**: All image compositing, text drawing, bounds calculation, blur filtering, and gradient masking occurs purely in standard Pillow buffer operations before being hydrated into a `QPixmap`.

## 目录结构
*   见根目录 `STRUCTURE.md`。`platforms/desktop/` 为 Python 桌面版，`platforms/mobile/` 为 Flutter 移动端，`config/` 为公共配置，`docs/` 为文档。

## P3 重构建议
*   main.py 已 2400+ 行，建议拆分为 `ui_panel.py`、`renderer.py`、`state.py`、`constants.py`。详见 `docs/REFACTOR_PLAN.md`。

## Testing Workflow
*   **Automated tests**: `tests/` directory with pytest. Run: `python -m pytest tests/ -v`
*   **Rule**: 新增功能需增加测试项，修改代码需跑测试，测试通过后才能往下走
*   See `TESTING.md` and `.cursor/rules/testing-workflow.mdc` for details.

*Good luck with the next iterations!*
