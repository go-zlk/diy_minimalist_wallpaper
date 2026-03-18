import 'package:flutter/foundation.dart';
import 'package:image/image.dart' as img;

enum ExportImageFormat { png, jpg }

class ExportEncodeOptions {
  const ExportEncodeOptions({
    required this.format,
    this.jpgQuality = 92,
    this.useIsolate = true,
  });

  final ExportImageFormat format;
  final int jpgQuality;
  final bool useIsolate;
}

class IsolateRenderPipeline {
  Future<Uint8List> encodeFromPngBytes(
    Uint8List pngBytes, {
    required ExportEncodeOptions options,
  }) async {
    if (!options.useIsolate) {
      return _encodeOutputBytesOnIsolate(
        <String, dynamic>{
          'bytes': pngBytes,
          'format': options.format.name,
          'jpgQuality': options.jpgQuality,
        },
      );
    }
    return compute(
      _encodeOutputBytesOnIsolate,
      <String, dynamic>{
        'bytes': pngBytes,
        'format': options.format.name,
        'jpgQuality': options.jpgQuality,
      },
    );
  }
}

Future<Uint8List> _encodeOutputBytesOnIsolate(Map<String, dynamic> payload) async {
  final bytes = payload['bytes'] as Uint8List;
  final formatName = payload['format'] as String;
  final quality = (payload['jpgQuality'] as num?)?.toInt() ?? 92;
  final format = ExportImageFormat.values.firstWhere((element) => element.name == formatName);

  if (format == ExportImageFormat.png) {
    return bytes;
  }
  final decoded = img.decodePng(bytes);
  if (decoded == null) {
    throw StateError('Failed to decode PNG before JPG encoding.');
  }
  final jpg = img.encodeJpg(decoded, quality: quality.clamp(1, 100).toInt());
  return Uint8List.fromList(jpg);
}
