import 'package:flutter/material.dart';

ThemeData buildWallpaperTheme() {
  const surface = Color(0xFFF7F7F8);
  const text = Color(0xFF212122);
  return ThemeData(
    colorScheme: ColorScheme.fromSeed(
      seedColor: text,
      brightness: Brightness.light,
      surface: surface,
    ),
    scaffoldBackgroundColor: surface,
    useMaterial3: true,
  );
}
