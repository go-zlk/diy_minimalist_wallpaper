import 'dart:ui';

enum AspectRatioPreset {
  r16x9(16 / 9, '16:9'),
  r9x16(9 / 16, '9:16'),
  r4x3(4 / 3, '4:3'),
  r1x1(1, '1:1');

  const AspectRatioPreset(this.value, this.label);
  final double value;
  final String label;
}

enum RenderQualityMode { fast, high }

class WallpaperState {
  const WallpaperState({
    required this.text,
    required this.textColor,
    required this.backgroundColor,
    required this.backgroundImagePath,
    required this.backgroundImageOpacity,
    required this.fontSize,
    required this.letterSpacing,
    required this.shadowOffset,
    required this.shadowBlur,
    required this.italic,
    required this.aspectRatio,
    required this.qualityMode,
    required this.selectedPresetName,
  });

  factory WallpaperState.initial() {
    return const WallpaperState(
      text: 'FOCUS\nINFINITE PROGRESS',
      textColor: Color(0xFF212122),
      backgroundColor: Color(0xFFF7F7F8),
      backgroundImagePath: null,
      backgroundImageOpacity: 1,
      fontSize: 64,
      letterSpacing: 0,
      shadowOffset: 6,
      shadowBlur: 8,
      italic: false,
      aspectRatio: AspectRatioPreset.r16x9,
      qualityMode: RenderQualityMode.high,
      selectedPresetName: null,
    );
  }

  final String text;
  final Color textColor;
  final Color backgroundColor;
  final String? backgroundImagePath;
  final double backgroundImageOpacity;
  final double fontSize;
  final double letterSpacing;
  final double shadowOffset;
  final double shadowBlur;
  final bool italic;
  final AspectRatioPreset aspectRatio;
  final RenderQualityMode qualityMode;
  final String? selectedPresetName;

  WallpaperState copyWith({
    String? text,
    Color? textColor,
    Color? backgroundColor,
    String? backgroundImagePath,
    double? backgroundImageOpacity,
    double? fontSize,
    double? letterSpacing,
    double? shadowOffset,
    double? shadowBlur,
    bool? italic,
    AspectRatioPreset? aspectRatio,
    RenderQualityMode? qualityMode,
    String? selectedPresetName,
    bool clearSelectedPresetName = false,
    bool clearBackgroundImagePath = false,
  }) {
    return WallpaperState(
      text: text ?? this.text,
      textColor: textColor ?? this.textColor,
      backgroundColor: backgroundColor ?? this.backgroundColor,
      backgroundImagePath:
          clearBackgroundImagePath ? null : (backgroundImagePath ?? this.backgroundImagePath),
      backgroundImageOpacity: backgroundImageOpacity ?? this.backgroundImageOpacity,
      fontSize: fontSize ?? this.fontSize,
      letterSpacing: letterSpacing ?? this.letterSpacing,
      shadowOffset: shadowOffset ?? this.shadowOffset,
      shadowBlur: shadowBlur ?? this.shadowBlur,
      italic: italic ?? this.italic,
      aspectRatio: aspectRatio ?? this.aspectRatio,
      qualityMode: qualityMode ?? this.qualityMode,
      selectedPresetName:
          clearSelectedPresetName ? null : (selectedPresetName ?? this.selectedPresetName),
    );
  }
}
