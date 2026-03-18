import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/export_service.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/isolate_render_pipeline.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/wallpaper_channel_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('export service renders non-empty PNG bytes', () async {
    final service = ExportService();
    final bytes = await service.renderPngBytes(
      state: WallpaperState.initial(),
      size: const Size(480, 270),
    );
    expect(bytes, isA<Uint8List>());
    expect(bytes.length, greaterThan(100));
  });

  test('isolate pipeline passes through PNG bytes', () async {
    final service = ExportService();
    final source = await service.renderPngBytes(
      state: WallpaperState.initial(),
      size: const Size(320, 180),
    );
    final pipeline = IsolateRenderPipeline();
    final encoded = await pipeline.encodeFromPngBytes(
      source,
      options: const ExportEncodeOptions(
        format: ExportImageFormat.png,
        useIsolate: true,
      ),
    );
    expect(encoded.length, equals(source.length));
    expect(encoded.take(8).toList(), equals(source.take(8).toList()));
  });

  test('isolate pipeline encodes JPG cross-platform', () async {
    final service = ExportService();
    final source = await service.renderPngBytes(
      state: WallpaperState.initial(),
      size: const Size(320, 180),
    );
    final pipeline = IsolateRenderPipeline();
    final jpg = await pipeline.encodeFromPngBytes(
      source,
      options: const ExportEncodeOptions(
        format: ExportImageFormat.jpg,
        jpgQuality: 90,
        useIsolate: true,
      ),
    );
    expect(jpg.length, greaterThan(100));
    expect(jpg[0], equals(0xFF));
    expect(jpg[1], equals(0xD8));
  });

  test('export service writes JPG file', () async {
    final service = ExportService();
    final outDir = await Directory.systemTemp.createTemp('wallpaper_diy_export_test_');
    final outPath = '${outDir.path}${Platform.pathSeparator}wallpaper.jpg';
    final path = await service.exportImage(
      state: WallpaperState.initial(),
      size: const Size(320, 180),
      outputPath: outPath,
      options: const ExportEncodeOptions(
        format: ExportImageFormat.jpg,
        jpgQuality: 88,
        useIsolate: true,
      ),
    );
    final bytes = await File(path).readAsBytes();
    expect(bytes[0], equals(0xFF));
    expect(bytes[1], equals(0xD8));
    await outDir.delete(recursive: true);
  });

  test('wallpaper channel service returns fallback on missing plugin', () async {
    final service = WallpaperChannelService();
    final result = await service.saveToPhotosAndGuide('dummy.png');
    expect(result.success, isFalse);
    expect(result.message, isNotEmpty);
  });

  test('wallpaper channel service maps saveToPhotosAndGuide response', () async {
    const channel = MethodChannel('wallpaper_diy/channel');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
      channel,
      (call) async {
        if (call.method == 'saveToPhotosAndGuide') {
          return <String, dynamic>{
            'success': true,
            'message': 'Saved to Photos',
            'needsSettings': false,
          };
        }
        return false;
      },
    );

    final service = WallpaperChannelService(channel: channel);
    final result = await service.saveToPhotosAndGuide('mock.png');
    expect(result.success, isTrue);
    expect(result.message, contains('Saved'));

    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
      channel,
      null,
    );
  });

  test('wallpaper channel service picks background image path', () async {
    const channel = MethodChannel('wallpaper_diy/channel');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
      channel,
      (call) async {
        if (call.method == 'pickBackgroundImage') {
          return r'C:\test\bg.png';
        }
        return null;
      },
    );

    final service = WallpaperChannelService(channel: channel);
    final path = await service.pickBackgroundImagePath();
    expect(path, equals(r'C:\test\bg.png'));

    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(
      channel,
      null,
    );
  });
}
