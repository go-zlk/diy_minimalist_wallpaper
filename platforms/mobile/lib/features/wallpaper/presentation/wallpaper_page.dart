import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_app/features/wallpaper/application/wallpaper_controller.dart';
import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/export_service.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/isolate_render_pipeline.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/wallpaper_channel_service.dart';
import 'package:flutter_app/features/wallpaper/presentation/preview_painter.dart';

class WallpaperPage extends StatefulWidget {
  const WallpaperPage({super.key, required this.controller});

  final WallpaperController controller;

  @override
  State<WallpaperPage> createState() => _WallpaperPageState();
}

class _WallpaperPageState extends State<WallpaperPage> {
  late final TextEditingController _textController;
  late final TextEditingController _presetNameController;
  final ExportService _exportService = ExportService();
  final WallpaperChannelService _wallpaperChannelService = WallpaperChannelService();
  String? _presetMessage;
  ui.Image? _backgroundImage;
  String? _loadedBackgroundImagePath;

  @override
  void initState() {
    super.initState();
    _textController = TextEditingController(text: widget.controller.state.text);
    _presetNameController = TextEditingController();
    widget.controller.addListener(_onControllerChanged);
    _loadBackgroundImage(widget.controller.state.backgroundImagePath);
  }

  void _onControllerChanged() {
    final value = widget.controller.state.text;
    if (_textController.text != value) {
      _textController.text = value;
    }
    final bgPath = widget.controller.state.backgroundImagePath;
    if (bgPath != _loadedBackgroundImagePath) {
      _loadBackgroundImage(bgPath);
    }
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _textController.dispose();
    _presetNameController.dispose();
    super.dispose();
  }

  Future<void> _loadBackgroundImage(String? path) async {
    _loadedBackgroundImagePath = path;
    if (path == null || path.isEmpty) {
      if (mounted) {
        setState(() {
          _backgroundImage = null;
        });
      }
      return;
    }
    try {
      final bytes = await File(path).readAsBytes();
      final codec = await ui.instantiateImageCodec(bytes);
      final frame = await codec.getNextFrame();
      if (!mounted || _loadedBackgroundImagePath != path) {
        return;
      }
      setState(() {
        _backgroundImage = frame.image;
      });
    } catch (_) {
      if (!mounted || _loadedBackgroundImagePath != path) {
        return;
      }
      setState(() {
        _backgroundImage = null;
      });
    }
  }

  Future<void> _pickBackgroundImage() async {
    final path = await _wallpaperChannelService.pickBackgroundImagePath();
    if (path == null) {
      return;
    }
    widget.controller.updateBackgroundImagePath(path);
  }

  Future<void> _savePreset() async {
    final message = await widget.controller.savePreset(_presetNameController.text);
    setState(() {
      _presetMessage = message ?? 'Preset saved.';
      if (message == null) {
        _presetNameController.clear();
      }
    });
  }

  Future<void> _exportCurrentWallpaper(ExportImageFormat format) async {
    final now = DateTime.now();
    final ext = format == ExportImageFormat.jpg ? 'jpg' : 'png';
    final fileName =
        'wallpaper_flutter_${now.year}${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}_${now.hour.toString().padLeft(2, '0')}${now.minute.toString().padLeft(2, '0')}${now.second.toString().padLeft(2, '0')}.$ext';
    final outputPath =
        '${Directory.current.path}${Platform.pathSeparator}output${Platform.pathSeparator}$fileName';
    final size = Size(
      1920,
      (1920 / widget.controller.state.aspectRatio.value).roundToDouble(),
    );
    try {
      final path = await _exportService.exportImage(
        state: widget.controller.state,
        size: size,
        outputPath: outputPath,
        options: ExportEncodeOptions(
          format: format,
          jpgQuality: 92,
          useIsolate: true,
        ),
      );
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('${ext.toUpperCase()} exported: $path')),
      );
    } catch (e) {
      if (!mounted) {
        return;
      }
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Export failed: $e')),
      );
    }
  }

  Future<void> _applyWallpaper() async {
    final now = DateTime.now();
    final fileName = 'wallpaper_apply_${now.millisecondsSinceEpoch}.png';
    final outputPath =
        '${Directory.current.path}${Platform.pathSeparator}output${Platform.pathSeparator}$fileName';
    final size = Size(
      1920,
      (1920 / widget.controller.state.aspectRatio.value).roundToDouble(),
    );
    final path = await _exportService.exportImage(
      state: widget.controller.state,
      size: size,
      outputPath: outputPath,
      options: const ExportEncodeOptions(
        format: ExportImageFormat.png,
        useIsolate: true,
      ),
    );
    final result = await _wallpaperChannelService.saveToPhotosAndGuide(path);
    if (!mounted) {
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(result.message),
        action: result.needsSettings
            ? SnackBarAction(
                label: 'Open Settings',
                onPressed: () {
                  _wallpaperChannelService.openAppSettings();
                },
              )
            : null,
      ),
    );
    if (result.success && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text(
            'Open Photos, choose image, tap Share -> Use as Wallpaper.',
          ),
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final state = widget.controller.state;
        return Scaffold(
          appBar: AppBar(
            title: const Text('WallpaperDIY Flutter Migration'),
            actions: [
              IconButton(
                onPressed: widget.controller.canUndo ? widget.controller.undo : null,
                icon: const Icon(Icons.undo),
              ),
              IconButton(
                onPressed: widget.controller.canRedo ? widget.controller.redo : null,
                icon: const Icon(Icons.redo),
              ),
              const SizedBox(width: 8),
            ],
          ),
          body: Row(
            children: [
              SizedBox(
                width: 360,
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    spacing: 16,
                    children: [
                      _Section(
                        title: 'Text',
                        child: TextField(
                          controller: _textController,
                          minLines: 3,
                          maxLines: 5,
                          onChanged: widget.controller.updateText,
                          decoration: const InputDecoration(
                            border: OutlineInputBorder(),
                            hintText: 'Enter multiline text...',
                          ),
                        ),
                      ),
                      _Section(
                        title: 'Typography',
                        child: Column(
                          spacing: 8,
                          children: [
                            _LabeledSlider(
                              label: 'Font Size',
                              value: state.fontSize,
                              min: 24,
                              max: 180,
                              onChanged: widget.controller.updateFontSize,
                              onChangeStart: (_) => widget.controller.beginInteraction(),
                              onChangeEnd: (_) => widget.controller.endInteraction(),
                            ),
                            _LabeledSlider(
                              label: 'Letter Spacing',
                              value: state.letterSpacing,
                              min: -2,
                              max: 12,
                              onChanged: widget.controller.updateLetterSpacing,
                              onChangeStart: (_) => widget.controller.beginInteraction(),
                              onChangeEnd: (_) => widget.controller.endInteraction(),
                            ),
                            SwitchListTile(
                              title: const Text('Italic'),
                              value: state.italic,
                              onChanged: widget.controller.updateItalic,
                              dense: true,
                              contentPadding: EdgeInsets.zero,
                            ),
                          ],
                        ),
                      ),
                      _Section(
                        title: 'Colors',
                        child: Column(
                          spacing: 12,
                          children: [
                            _ColorEditor(
                              title: 'Text Color',
                              color: state.textColor,
                              onStart: widget.controller.beginInteraction,
                              onEnd: widget.controller.endInteraction,
                              onChanged: widget.controller.updateTextColor,
                            ),
                            _ColorEditor(
                              title: 'Background Color',
                              color: state.backgroundColor,
                              onStart: widget.controller.beginInteraction,
                              onEnd: widget.controller.endInteraction,
                              onChanged: widget.controller.updateBackgroundColor,
                            ),
                          ],
                        ),
                      ),
                      _Section(
                        title: 'Background Image',
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          spacing: 8,
                          children: [
                            Row(
                              spacing: 8,
                              children: [
                                Expanded(
                                  child: Text(
                                    state.backgroundImagePath == null
                                        ? 'No image selected'
                                        : state.backgroundImagePath!,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                  ),
                                ),
                                OutlinedButton.icon(
                                  onPressed: _pickBackgroundImage,
                                  icon: const Icon(Icons.add_photo_alternate_outlined),
                                  label: const Text('Import'),
                                ),
                                OutlinedButton.icon(
                                  onPressed: state.backgroundImagePath == null
                                      ? null
                                      : () => widget.controller.updateBackgroundImagePath(null),
                                  icon: const Icon(Icons.delete_outline),
                                  label: const Text('Clear'),
                                ),
                              ],
                            ),
                            _LabeledSlider(
                              label: 'Image Opacity',
                              value: state.backgroundImageOpacity,
                              min: 0,
                              max: 1,
                              onChanged: widget.controller.updateBackgroundImageOpacity,
                              onChangeStart: (_) => widget.controller.beginInteraction(),
                              onChangeEnd: (_) => widget.controller.endInteraction(),
                            ),
                          ],
                        ),
                      ),
                      _Section(
                        title: 'Shadow / Layout',
                        child: Column(
                          spacing: 8,
                          children: [
                            _LabeledSlider(
                              label: 'Shadow Offset',
                              value: state.shadowOffset,
                              min: 0,
                              max: 24,
                              onChanged: widget.controller.updateShadowOffset,
                              onChangeStart: (_) => widget.controller.beginInteraction(),
                              onChangeEnd: (_) => widget.controller.endInteraction(),
                            ),
                            _LabeledSlider(
                              label: 'Shadow Blur',
                              value: state.shadowBlur,
                              min: 0,
                              max: 20,
                              onChanged: widget.controller.updateShadowBlur,
                              onChangeStart: (_) => widget.controller.beginInteraction(),
                              onChangeEnd: (_) => widget.controller.endInteraction(),
                            ),
                            DropdownButtonFormField<AspectRatioPreset>(
                              initialValue: state.aspectRatio,
                              decoration: const InputDecoration(
                                labelText: 'Aspect Ratio',
                                border: OutlineInputBorder(),
                              ),
                              items: AspectRatioPreset.values
                                  .map((e) => DropdownMenuItem(value: e, child: Text(e.label)))
                                  .toList(),
                              onChanged: (value) {
                                if (value != null) {
                                  widget.controller.updateAspectRatio(value);
                                }
                              },
                            ),
                          ],
                        ),
                      ),
                      _Section(
                        title: 'User Presets',
                        child: Column(
                          spacing: 8,
                          children: [
                            Row(
                              spacing: 8,
                              children: [
                                Expanded(
                                  child: TextField(
                                    controller: _presetNameController,
                                    decoration: const InputDecoration(
                                      border: OutlineInputBorder(),
                                      hintText: 'Preset name',
                                    ),
                                  ),
                                ),
                                FilledButton(onPressed: _savePreset, child: const Text('Save')),
                              ],
                            ),
                            if (_presetMessage != null)
                              Text(
                                _presetMessage!,
                                style: Theme.of(context).textTheme.bodySmall,
                              ),
                            DropdownButtonFormField<String>(
                              initialValue: state.selectedPresetName,
                              decoration: const InputDecoration(
                                labelText: 'Select Preset',
                                border: OutlineInputBorder(),
                              ),
                              items: widget.controller.presets.keys
                                  .map((name) => DropdownMenuItem(value: name, child: Text(name)))
                                  .toList(),
                              onChanged: (value) {
                                if (value != null) {
                                  widget.controller.applyPreset(value);
                                }
                              },
                            ),
                            Align(
                              alignment: Alignment.centerRight,
                              child: OutlinedButton.icon(
                                onPressed: state.selectedPresetName == null
                                    ? null
                                    : () async {
                                        final name = state.selectedPresetName!;
                                        final deleted = await widget.controller.deletePreset(name);
                                        if (!mounted) {
                                          return;
                                        }
                                        setState(() {
                                          _presetMessage = deleted ? 'Preset deleted: $name' : 'Preset not found.';
                                        });
                                      },
                                icon: const Icon(Icons.delete_outline),
                                label: const Text('Delete Selected'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              const VerticalDivider(width: 1),
              Expanded(
                child: Center(
                  child: AspectRatio(
                    aspectRatio: state.aspectRatio.value,
                    child: DecoratedBox(
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(18),
                        boxShadow: const [
                          BoxShadow(blurRadius: 16, color: Color(0x22000000)),
                        ],
                      ),
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(18),
                        child: CustomPaint(
                          painter: PreviewPainter(
                            state: state,
                            backgroundImage: _backgroundImage,
                          ),
                          child: const SizedBox.expand(),
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
          bottomNavigationBar: Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            color: Theme.of(context).colorScheme.surfaceContainerHighest.withValues(alpha: 0.4),
            child: Row(
              children: [
                Text(
                  'Preview quality: ${state.qualityMode.name.toUpperCase()}',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                const Spacer(),
                OutlinedButton.icon(
                  onPressed: () => _exportCurrentWallpaper(ExportImageFormat.png),
                  icon: const Icon(Icons.save_alt),
                  label: const Text('Export PNG'),
                ),
                const SizedBox(width: 8),
                OutlinedButton.icon(
                  onPressed: () => _exportCurrentWallpaper(ExportImageFormat.jpg),
                  icon: const Icon(Icons.image),
                  label: const Text('Export JPG'),
                ),
                const SizedBox(width: 8),
                FilledButton.icon(
                  onPressed: _applyWallpaper,
                  icon: const Icon(Icons.wallpaper),
                  label: const Text('Apply Wallpaper'),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({required this.title, required this.child});
  final String title;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          spacing: 10,
          children: [
            Text(title, style: Theme.of(context).textTheme.titleMedium),
            child,
          ],
        ),
      ),
    );
  }
}

class _LabeledSlider extends StatelessWidget {
  const _LabeledSlider({
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.onChanged,
    this.onChangeStart,
    this.onChangeEnd,
  });

  final String label;
  final double value;
  final double min;
  final double max;
  final ValueChanged<double> onChanged;
  final ValueChanged<double>? onChangeStart;
  final ValueChanged<double>? onChangeEnd;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text('$label: ${value.toStringAsFixed(1)}'),
        Slider(
          value: value.clamp(min, max),
          min: min,
          max: max,
          onChanged: onChanged,
          onChangeStart: onChangeStart,
          onChangeEnd: onChangeEnd,
        ),
      ],
    );
  }
}

class _ColorEditor extends StatelessWidget {
  const _ColorEditor({
    required this.title,
    required this.color,
    required this.onChanged,
    required this.onStart,
    required this.onEnd,
  });

  final String title;
  final Color color;
  final ValueChanged<Color> onChanged;
  final VoidCallback onStart;
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      spacing: 4,
      children: [
        Row(
          children: [
            Text(title),
            const SizedBox(width: 8),
            Container(
              width: 20,
              height: 20,
              decoration: BoxDecoration(
                color: color,
                borderRadius: BorderRadius.circular(4),
                border: Border.all(color: Colors.black26),
              ),
            ),
          ],
        ),
        _ColorChannelSlider(
          name: 'R',
          value: color.r,
          onStart: onStart,
          onEnd: onEnd,
          onChanged: (r) => onChanged(color.withValues(red: r)),
        ),
        _ColorChannelSlider(
          name: 'G',
          value: color.g,
          onStart: onStart,
          onEnd: onEnd,
          onChanged: (g) => onChanged(color.withValues(green: g)),
        ),
        _ColorChannelSlider(
          name: 'B',
          value: color.b,
          onStart: onStart,
          onEnd: onEnd,
          onChanged: (b) => onChanged(color.withValues(blue: b)),
        ),
      ],
    );
  }
}

class _ColorChannelSlider extends StatelessWidget {
  const _ColorChannelSlider({
    required this.name,
    required this.value,
    required this.onChanged,
    required this.onStart,
    required this.onEnd,
  });

  final String name;
  final double value;
  final ValueChanged<double> onChanged;
  final VoidCallback onStart;
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(width: 18, child: Text(name)),
        Expanded(
          child: Slider(
            value: (value * 255).clamp(0, 255),
            min: 0,
            max: 255,
            onChangeStart: (_) => onStart(),
            onChangeEnd: (_) => onEnd(),
            onChanged: (v) => onChanged(v / 255),
          ),
        ),
      ],
    );
  }
}
