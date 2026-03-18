import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/isolate_render_pipeline.dart';
import 'package:flutter_app/features/wallpaper/presentation/preview_painter.dart';

class ExportService {
  ExportService({IsolateRenderPipeline? pipeline}) : _pipeline = pipeline ?? IsolateRenderPipeline();

  final IsolateRenderPipeline _pipeline;

  Future<String> exportImage({
    required WallpaperState state,
    required Size size,
    required String outputPath,
    required ExportEncodeOptions options,
  }) async {
    final pngBytes = await renderPngBytes(state: state, size: size);
    final bytes = await _pipeline.encodeFromPngBytes(pngBytes, options: options);
    final file = File(outputPath);
    await file.parent.create(recursive: true);
    await file.writeAsBytes(bytes, flush: true);
    return file.path;
  }

  Future<Uint8List> renderPngBytes({
    required WallpaperState state,
    required Size size,
  }) async {
    final backgroundImage = await _loadBackgroundImage(state.backgroundImagePath);
    final recorder = ui.PictureRecorder();
    final canvas = Canvas(recorder);
    final painter = PreviewPainter(state: state, backgroundImage: backgroundImage);
    painter.paint(canvas, size);
    final picture = recorder.endRecording();
    final image = await picture.toImage(size.width.toInt(), size.height.toInt());
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    if (data == null) {
      throw StateError('Failed to encode PNG bytes.');
    }
    return data.buffer.asUint8List();
  }

  Future<ui.Image?> _loadBackgroundImage(String? path) async {
    if (path == null || path.isEmpty) {
      return null;
    }
    final file = File(path);
    if (!await file.exists()) {
      return null;
    }
    try {
      final bytes = await file.readAsBytes();
      final codec = await ui.instantiateImageCodec(bytes);
      final frame = await codec.getNextFrame();
      return frame.image;
    } catch (_) {
      return null;
    }
  }
}
