import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_app/features/wallpaper/domain/style_preset.dart';
import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/preset_store.dart';

class WallpaperController extends ChangeNotifier {
  WallpaperController({required PresetStore presetStore}) : _presetStore = presetStore;

  final PresetStore _presetStore;
  WallpaperState _state = WallpaperState.initial();
  final List<WallpaperState> _history = <WallpaperState>[];
  final List<WallpaperState> _future = <WallpaperState>[];
  Map<String, StylePreset> _presets = <String, StylePreset>{};
  Timer? _interactionTimer;

  WallpaperState get state => _state;
  Map<String, StylePreset> get presets => Map.unmodifiable(_presets);
  bool get canUndo => _history.isNotEmpty;
  bool get canRedo => _future.isNotEmpty;

  Future<void> initialize() async {
    _presets = await _presetStore.load();
    notifyListeners();
  }

  Future<void> savePresets() async {
    await _presetStore.save(_presets);
  }

  void _pushHistory() {
    _history.add(_state);
    if (_history.length > 100) {
      _history.removeAt(0);
    }
    _future.clear();
  }

  void _setState(WallpaperState next, {bool addToHistory = true}) {
    if (addToHistory) {
      _pushHistory();
    }
    _state = next.copyWith(clearSelectedPresetName: addToHistory);
    notifyListeners();
  }

  void beginInteraction() {
    _interactionTimer?.cancel();
    if (_state.qualityMode != RenderQualityMode.fast) {
      _state = _state.copyWith(qualityMode: RenderQualityMode.fast);
      notifyListeners();
    }
  }

  void endInteraction() {
    _interactionTimer?.cancel();
    _interactionTimer = Timer(const Duration(milliseconds: 120), () {
      _state = _state.copyWith(qualityMode: RenderQualityMode.high);
      notifyListeners();
    });
  }

  void updateText(String value) => _setState(_state.copyWith(text: value));

  void updateTextColor(Color value) => _setState(_state.copyWith(textColor: value));

  void updateBackgroundColor(Color value) => _setState(_state.copyWith(backgroundColor: value));

  void updateBackgroundImagePath(String? path) =>
      _setState(path == null ? _state.copyWith(clearBackgroundImagePath: true) : _state.copyWith(backgroundImagePath: path));

  void updateBackgroundImageOpacity(double value) =>
      _setState(_state.copyWith(backgroundImageOpacity: value.clamp(0, 1)));

  void updateFontSize(double value) => _setState(_state.copyWith(fontSize: value));

  void updateLetterSpacing(double value) => _setState(_state.copyWith(letterSpacing: value));

  void updateShadowOffset(double value) => _setState(_state.copyWith(shadowOffset: value));

  void updateShadowBlur(double value) => _setState(_state.copyWith(shadowBlur: value));

  void updateItalic(bool value) => _setState(_state.copyWith(italic: value));

  void updateAspectRatio(AspectRatioPreset preset) => _setState(_state.copyWith(aspectRatio: preset));

  String? validatePresetName(String value) {
    final name = value.trim();
    if (name.isEmpty) {
      return 'Preset name is required.';
    }
    if (_presets.containsKey(name)) {
      return 'Preset name already exists.';
    }
    return null;
  }

  Future<String?> savePreset(String name) async {
    final error = validatePresetName(name);
    if (error != null) {
      return error;
    }
    final trimmed = name.trim();
    _presets = <String, StylePreset>{
      ..._presets,
      trimmed: StylePreset.fromState(trimmed, _state),
    };
    await savePresets();
    _state = _state.copyWith(selectedPresetName: trimmed);
    notifyListeners();
    return null;
  }

  Future<bool> deletePreset(String name) async {
    if (!_presets.containsKey(name)) {
      return false;
    }
    final next = <String, StylePreset>{..._presets}..remove(name);
    _presets = next;
    await savePresets();
    if (_state.selectedPresetName == name) {
      _state = _state.copyWith(clearSelectedPresetName: true);
    }
    notifyListeners();
    return true;
  }

  void applyPreset(String name) {
    final preset = _presets[name];
    if (preset == null) {
      return;
    }
    _setState(
      _state.copyWith(
        textColor: preset.textColor,
        backgroundColor: preset.backgroundColor,
        text: preset.lastUsedText.isEmpty ? _state.text : preset.lastUsedText,
        selectedPresetName: name,
      ),
    );
  }

  void undo() {
    if (_history.isEmpty) {
      return;
    }
    _future.add(_state);
    _state = _history.removeLast();
    notifyListeners();
  }

  void redo() {
    if (_future.isEmpty) {
      return;
    }
    _history.add(_state);
    _state = _future.removeLast();
    notifyListeners();
  }

  @override
  void dispose() {
    _interactionTimer?.cancel();
    super.dispose();
  }
}
