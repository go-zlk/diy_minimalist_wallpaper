import 'package:flutter/material.dart';
import 'package:flutter_app/features/wallpaper/domain/wallpaper_state.dart';
import 'dart:ui' as ui;

class PreviewPainter extends CustomPainter {
  const PreviewPainter({
    required this.state,
    this.backgroundImage,
  });

  final WallpaperState state;
  final ui.Image? backgroundImage;

  @override
  void paint(Canvas canvas, Size size) {
    final bgPaint = Paint()..color = state.backgroundColor;
    canvas.drawRect(Offset.zero & size, bgPaint);

    if (backgroundImage != null && state.backgroundImageOpacity > 0) {
      final image = backgroundImage!;
      final srcSize = Size(image.width.toDouble(), image.height.toDouble());
      final srcAspect = srcSize.width / srcSize.height;
      final dstAspect = size.width / size.height;

      Rect srcRect;
      if (srcAspect > dstAspect) {
        final srcW = srcSize.height * dstAspect;
        final left = (srcSize.width - srcW) / 2;
        srcRect = Rect.fromLTWH(left, 0, srcW, srcSize.height);
      } else {
        final srcH = srcSize.width / dstAspect;
        final top = (srcSize.height - srcH) / 2;
        srcRect = Rect.fromLTWH(0, top, srcSize.width, srcH);
      }
      final dstRect = Offset.zero & size;
      final imagePaint = Paint()
        ..filterQuality = FilterQuality.high
        ..color = Colors.white.withValues(alpha: state.backgroundImageOpacity);
      canvas.drawImageRect(image, srcRect, dstRect, imagePaint);
    }

    final textStyle = TextStyle(
      color: state.textColor,
      fontSize: state.fontSize,
      letterSpacing: state.letterSpacing,
      fontStyle: state.italic ? FontStyle.italic : FontStyle.normal,
      fontWeight: FontWeight.w700,
      height: 1.1,
    );

    final textPainter = TextPainter(
      text: TextSpan(text: state.text, style: textStyle),
      textDirection: TextDirection.ltr,
      textAlign: TextAlign.center,
    )..layout(maxWidth: size.width * 0.86);

    final centerX = (size.width - textPainter.width) / 2;
    final centerY = (size.height - textPainter.height) / 2;

    final shadowPaint = Paint()
      ..color = Colors.black.withValues(alpha: state.qualityMode == RenderQualityMode.fast ? 0.10 : 0.14)
      ..maskFilter = MaskFilter.blur(
        BlurStyle.normal,
        state.qualityMode == RenderQualityMode.fast ? 0 : state.shadowBlur,
      );

    canvas.saveLayer(Offset.zero & size, shadowPaint);
    textPainter.paint(
      canvas,
      Offset(centerX + state.shadowOffset, centerY + state.shadowOffset),
    );
    canvas.restore();

    textPainter.paint(canvas, Offset(centerX, centerY));
  }

  @override
  bool shouldRepaint(covariant PreviewPainter oldDelegate) {
    return oldDelegate.state != state || oldDelegate.backgroundImage != backgroundImage;
  }
}
