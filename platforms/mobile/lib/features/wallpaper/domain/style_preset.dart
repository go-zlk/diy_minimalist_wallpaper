import 'dart:ui';

import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';

class StylePreset {
  const StylePreset({
    required this.name,
    required this.textColor,
    required this.backgroundColor,
    required this.lastUsedText,
  });

  final String name;
  final Color textColor;
  final Color backgroundColor;
  final String lastUsedText;

  factory StylePreset.fromState(String name, WallpaperState state) {
    return StylePreset(
      name: name,
      textColor: state.textColor,
      backgroundColor: state.backgroundColor,
      lastUsedText: state.text,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'textColor': textColor.toARGB32(),
      'backgroundColor': backgroundColor.toARGB32(),
      'lastUsedText': lastUsedText,
    };
  }

  factory StylePreset.fromJson(Map<String, dynamic> json) {
    return StylePreset(
      name: json['name'] as String,
      textColor: Color((json['textColor'] as num).toInt()),
      backgroundColor: Color((json['backgroundColor'] as num).toInt()),
      lastUsedText: (json['lastUsedText'] as String?) ?? '',
    );
  }
}
