import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_app/features/wallpaper/application/wallpaper_controller.dart';
import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/preset_store.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  late File tempFile;
  late WallpaperController controller;

  setUp(() async {
    tempFile = File(
      '${Directory.systemTemp.path}${Platform.pathSeparator}wallpaper_flutter_test_${DateTime.now().microsecondsSinceEpoch}.json',
    );
    controller = WallpaperController(presetStore: PresetStore(filePath: tempFile.path));
    await controller.initialize();
  });

  tearDown(() async {
    controller.dispose();
    if (await tempFile.exists()) {
      await tempFile.delete();
    }
  });

  test('undo and redo restore prior state', () {
    final initialText = controller.state.text;

    controller.updateText('line 1\nline 2');
    expect(controller.state.text, 'line 1\nline 2');

    controller.undo();
    expect(controller.state.text, initialText);

    controller.redo();
    expect(controller.state.text, 'line 1\nline 2');
  });

  test('preset name validation catches duplicates', () async {
    final firstResult = await controller.savePreset('Apple Light');
    expect(firstResult, isNull);

    final secondResult = await controller.savePreset('Apple Light');
    expect(secondResult, isNotNull);
    expect(secondResult, contains('already exists'));
  });

  test('interaction toggles quality mode to fast then high', () async {
    expect(controller.state.qualityMode, RenderQualityMode.high);

    controller.beginInteraction();
    expect(controller.state.qualityMode, RenderQualityMode.fast);

    controller.endInteraction();
    await Future<void>.delayed(const Duration(milliseconds: 160));
    expect(controller.state.qualityMode, RenderQualityMode.high);
  });

  test('apply preset updates text and color fields', () async {
    controller.updateText('MIGRATION');
    controller.updateTextColor(const Color(0xFF112233));
    final result = await controller.savePreset('A');
    expect(result, isNull);

    controller.updateText('CHANGED');
    controller.updateTextColor(const Color(0xFFABCDEF));

    controller.applyPreset('A');
    expect(controller.state.text, 'MIGRATION');
    expect(controller.state.textColor, const Color(0xFF112233));
  });
}
