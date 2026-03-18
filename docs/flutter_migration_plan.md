# WallpaperDIY `main.py` -> Flutter Migration Plan

## Goal and Constraints
- Keep existing Python app (`main.py`) untouched during migration.
- Build a parallel Flutter app in `flutter_app` with incremental feature parity.
- After each milestone, run regression checks (`flutter analyze` + `flutter test`) and record results.

## Class/Function Mapping (Python -> Flutter)

| Python (`main.py`) | Flutter target | Notes |
| --- | --- | --- |
| `WallpaperUltra` | `WallpaperPage` + `WallpaperController` | UI layer and state management split |
| `ColorWheelPicker` | `ColorPickerPanel` (slider-based MVP now, wheel later) | First landing with HSV sliders for stable interaction |
| `SectionGroup` | `Card` + reusable panel widgets | Material card sections |
| `PreviewRenderTask` / `PreviewRenderSignals` | `compute()`/isolate-ready render pipeline (phase 2) | Phase 1 keeps painter on UI isolate |
| `WorkerTask` / `WorkerSignals` | async service calls + `Future`/`ValueNotifier` | For export/apply actions |
| `get_output_dir()` | `OutputPathResolver` service | Platform-specific path policy |
| `get_arrow_path()` | pure Flutter `DropdownButton` icon | No generated arrow file needed |
| `_build_render_state()` | `WallpaperState` immutable model | Single source of truth |
| `_capture_ui_state()` / `_apply_ui_state()` | `undo/redo stacks` in controller | Time-travel state |
| `_push_history()` / `on_undo()` / `on_redo()` | `WallpaperController.undo/redo` | API parity |
| `_load_user_color_presets()` / `_save_user_color_presets()` | `PresetStore` | JSON file persistence |
| `on_save_color_preset*` / `delete_user_preset` | inline preset editor in sidebar | Same UX direction |
| `_get_quality_settings()` / `_adaptive_shadow_steps()` | `RenderQualityPolicy` | Fast during interaction, HQ after release |
| `_render_image_from_state()` / `generate_img()` | `PreviewPainter` + export renderer (phase 2) | Canvas text + shadow + spacing |
| `run_preview_regression()` | `controller/perf tests` | Automated baseline checks |
| `save_image()` | export service | PNG/JPG options |
| `apply_wallpaper()` | platform channel (`MethodChannel`) | Implement per platform progressively |

## Milestones

### M1 - Foundation and Architecture
- [x] Create Flutter project scaffold (`flutter_app`).
- [x] Establish folders: `domain/application/infrastructure/presentation`.
- [x] Add immutable state model and typed presets.
- [x] Add controller with state mutation and undo/redo.
- Regression:
  - `flutter analyze` passes.
  - `flutter test` passes for controller unit tests.

### M2 - MVP UI and Preview
- [x] Build `WallpaperPage` with:
  - text input (multiline),
  - color controls (text/bg),
  - basic typography controls (size, letter spacing, italic),
  - aspect ratio and shadow controls,
  - preset save/load/delete.
- [x] Implement `CustomPainter` preview with fast interactive updates.
- Regression:
  - `flutter test` includes widget smoke test.
  - Manual interaction has no frame-stall during slider drag (sanity).

### M3 - Persistence and Regression Harness
- [x] Persist user presets via JSON.
- [x] Add automated regression checks for:
  - undo/redo behavior,
  - preset name conflict validation,
  - quality policy state transitions.
- Regression:
  - `flutter analyze` + `flutter test` all green.

### M4 - Platform Integration
- [x] Export high-quality image service (PNG + JPG).
- [x] Apply wallpaper through platform channels (stub + fallback):
  - Windows first,
  - then Android/iOS/macOS.
- [x] Isolate-based export pipeline for non-blocking HQ encode stage.
- Regression:
  - [x] render byte generation test for exporter,
  - [x] platform channel mock test for method invocation,
  - [x] isolate pipeline tests (PNG passthrough + JPG encode),
  - [x] JPG file export test.

## Current Execution Log

### 2026-03-15
- Created migration project in `flutter_app` (offline-safe mode).
- Completed M1-M3 implementation in this round.
- Regression result (M1): `flutter analyze` -> pass.
- Regression result (M2): widget smoke test (`preview painter smoke test`) -> pass.
- Regression result (M3): controller tests (undo/redo, duplicate preset, quality transition, preset apply) -> pass.
- Final verification:
  - `flutter analyze` -> **No issues found**.
  - `flutter test` -> **All tests passed (8/8)**.
- `main.py` remained unchanged as required.
- M4 execution updates:
  - Added `ExportService` (PNG render/export path in `output`).
  - Upgraded `ExportService` to support `ExportEncodeOptions` and JPG export.
  - Replaced Windows PowerShell JPG conversion with pure-Dart JPEG encoding (`image` library) in isolate pipeline.
  - Added `IsolateRenderPipeline` (`compute`) for background encode stage.
  - Added `WallpaperChannelService` iOS flow:
    - save generated image to Photos,
    - return user guidance for setting wallpaper manually (iOS-compliant),
    - open app Settings entry when Photos permission is denied.
  - Added iOS native channel implementation in `ios/Runner/AppDelegate.swift` and Photos permissions in `ios/Runner/Info.plist`.
  - Added UI actions: `Export PNG`, `Export JPG`, `Apply Wallpaper`.
  - Added regression tests for exporter, isolate encode pipeline, and method channel behavior.
  - Added custom background-image layer feature:
    - import local image via Windows native file picker channel (`pickBackgroundImage`),
    - blend image at the bottom layer with adjustable opacity,
    - preserve same rendering behavior in preview and export paths.
  - Final verification after M4 completion:
    - `flutter analyze` -> **No issues found**.
    - `flutter test` -> **All tests passed (12/12)**.
  - Note: due restricted pub access, the pure-Dart image stack is vendored locally via path deps (`third_party_image` + required transitive packages).
