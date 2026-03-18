import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';
import 'package:flutter_app/features/wallpaper/presentation/preview_painter.dart';

void main() {
  testWidgets('preview painter smoke test', (WidgetTester tester) async {
    final state = WallpaperState.initial();
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SizedBox.expand(
            child: CustomPaint(
              painter: PreviewPainter(state: state),
            ),
          ),
        ),
      ),
    );

    expect(find.byType(CustomPaint), findsWidgets);
  });
}
