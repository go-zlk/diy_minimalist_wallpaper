import 'package:flutter/material.dart';
import 'package:flutter_app/app/app_theme.dart';
import 'package:flutter_app/features/wallpaper/application/wallpaper_controller.dart';
import 'package:flutter_app/features/wallpaper/infrastructure/preset_store.dart';
import 'package:flutter_app/features/wallpaper/presentation/wallpaper_page.dart';

class WallpaperApp extends StatefulWidget {
  const WallpaperApp({super.key});

  @override
  State<WallpaperApp> createState() => _WallpaperAppState();
}

class _WallpaperAppState extends State<WallpaperApp> {
  late final WallpaperController controller;
  late final Future<void> initializeFuture;

  @override
  void initState() {
    super.initState();
    controller = WallpaperController(presetStore: PresetStore());
    initializeFuture = controller.initialize();
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'WallpaperDIY Flutter',
      theme: buildWallpaperTheme(),
      home: FutureBuilder<void>(
        future: initializeFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) {
            return const Scaffold(body: Center(child: CircularProgressIndicator()));
          }
          return WallpaperPage(controller: controller);
        },
      ),
    );
  }
}
