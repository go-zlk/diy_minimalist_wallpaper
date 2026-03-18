import 'dart:convert';
import 'dart:io';

import 'package:flutter_app/features/wallpaper/domain/style_preset.dart';

class PresetStore {
  PresetStore({String? filePath})
      : _filePath = filePath ?? '${Directory.current.path}${Platform.pathSeparator}user_color_presets_flutter.json';

  final String _filePath;

  Future<Map<String, StylePreset>> load() async {
    final file = File(_filePath);
    if (!await file.exists()) {
      return {};
    }
    final content = await file.readAsString();
    if (content.trim().isEmpty) {
      return {};
    }
    final dynamic raw = jsonDecode(content);
    if (raw is! Map<String, dynamic>) {
      return {};
    }
    final result = <String, StylePreset>{};
    for (final MapEntry<String, dynamic> entry in raw.entries) {
      final value = entry.value;
      if (value is Map<String, dynamic>) {
        result[entry.key] = StylePreset.fromJson(value);
      }
    }
    return result;
  }

  Future<void> save(Map<String, StylePreset> presets) async {
    final payload = <String, dynamic>{};
    presets.forEach((key, value) {
      payload[key] = value.toJson();
    });
    final file = File(_filePath);
    await file.parent.create(recursive: true);
    await file.writeAsString(const JsonEncoder.withIndent('  ').convert(payload));
  }
}
