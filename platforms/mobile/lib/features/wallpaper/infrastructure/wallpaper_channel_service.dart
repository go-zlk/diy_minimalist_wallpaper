import 'package:flutter/services.dart';

class WallpaperApplyResult {
  const WallpaperApplyResult({
    required this.success,
    required this.message,
    this.needsSettings = false,
  });

  final bool success;
  final String message;
  final bool needsSettings;
}

class WallpaperChannelService {
  WallpaperChannelService({MethodChannel? channel})
      : _channel = channel ?? const MethodChannel('wallpaper_diy/channel');

  final MethodChannel _channel;

  Future<bool> applyWallpaper(String imagePath) async {
    try {
      final result = await _channel.invokeMapMethod<String, dynamic>(
        'saveToPhotosAndGuide',
        <String, dynamic>{'imagePath': imagePath},
      );
      return (result?['success'] as bool?) ?? false;
    } on MissingPluginException {
      return false;
    } on PlatformException {
      return false;
    }
  }

  Future<WallpaperApplyResult> saveToPhotosAndGuide(String imagePath) async {
    try {
      final result = await _channel.invokeMapMethod<String, dynamic>(
        'saveToPhotosAndGuide',
        <String, dynamic>{'imagePath': imagePath},
      );
      return WallpaperApplyResult(
        success: (result?['success'] as bool?) ?? false,
        message: (result?['message'] as String?) ?? 'Save to Photos is unavailable on this platform.',
        needsSettings: (result?['needsSettings'] as bool?) ?? false,
      );
    } on MissingPluginException {
      return const WallpaperApplyResult(
        success: false,
        message: 'Save to Photos is unavailable on this platform.',
      );
    } on PlatformException {
      return const WallpaperApplyResult(
        success: false,
        message: 'Save to Photos failed on this platform.',
      );
    }
  }

  Future<bool> openAppSettings() async {
    try {
      final opened = await _channel.invokeMethod<bool>('openAppSettings');
      return opened ?? false;
    } on MissingPluginException {
      return false;
    } on PlatformException {
      return false;
    }
  }

  Future<String?> pickBackgroundImagePath() async {
    try {
      final path = await _channel.invokeMethod<String>('pickBackgroundImage');
      if (path == null || path.isEmpty) {
        return null;
      }
      return path;
    } on MissingPluginException {
      return null;
    } on PlatformException {
      return null;
    }
  }
}
