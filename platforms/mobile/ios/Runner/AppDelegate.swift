import Flutter
import Photos
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    if let controller = window?.rootViewController as? FlutterViewController {
      let channel = FlutterMethodChannel(
        name: "wallpaper_diy/channel",
        binaryMessenger: controller.binaryMessenger
      )
      channel.setMethodCallHandler { [weak self] call, result in
        guard let self else {
          result(
            FlutterError(
              code: "DEALLOCATED",
              message: "AppDelegate is unavailable.",
              details: nil
            )
          )
          return
        }
        switch call.method {
        case "saveToPhotosAndGuide":
          guard
            let args = call.arguments as? [String: Any],
            let imagePath = args["imagePath"] as? String
          else {
            result(
              FlutterError(
                code: "INVALID_ARGS",
                message: "imagePath is required.",
                details: nil
              )
            )
            return
          }
          self.saveImageToPhotos(imagePath: imagePath, result: result)
        case "openAppSettings":
          self.openAppSettings(result: result)
        default:
          result(FlutterMethodNotImplemented)
        }
      }
    }

    GeneratedPluginRegistrant.register(with: self)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  private func saveImageToPhotos(imagePath: String, result: @escaping FlutterResult) {
    let status = PHPhotoLibrary.authorizationStatus(for: .addOnly)
    switch status {
    case .authorized, .limited:
      performSaveToPhotos(imagePath: imagePath, result: result)
    case .notDetermined:
      PHPhotoLibrary.requestAuthorization(for: .addOnly) { [weak self] newStatus in
        DispatchQueue.main.async {
          guard let self else {
            result(["success": false, "message": "Internal error.", "needsSettings": false])
            return
          }
          if newStatus == .authorized || newStatus == .limited {
            self.performSaveToPhotos(imagePath: imagePath, result: result)
          } else {
            result([
              "success": false,
              "message": "Photo permission denied. Enable Photos access in Settings.",
              "needsSettings": true
            ])
          }
        }
      }
    default:
      result([
        "success": false,
        "message": "Photo permission denied. Enable Photos access in Settings.",
        "needsSettings": true
      ])
    }
  }

  private func performSaveToPhotos(imagePath: String, result: @escaping FlutterResult) {
    let url = URL(fileURLWithPath: imagePath)
    guard FileManager.default.fileExists(atPath: imagePath) else {
      result(["success": false, "message": "Image file not found.", "needsSettings": false])
      return
    }
    PHPhotoLibrary.shared().performChanges({
      PHAssetChangeRequest.creationRequestForAssetFromImage(atFileURL: url)
    }) { success, error in
      DispatchQueue.main.async {
        if success {
          result([
            "success": true,
            "message": "Saved to Photos. Open Photos -> Share -> Use as Wallpaper.",
            "needsSettings": false
          ])
        } else {
          result([
            "success": false,
            "message": "Failed to save image: \(error?.localizedDescription ?? "unknown error").",
            "needsSettings": false
          ])
        }
      }
    }
  }

  private func openAppSettings(result: @escaping FlutterResult) {
    guard let url = URL(string: UIApplication.openSettingsURLString) else {
      result(false)
      return
    }
    if UIApplication.shared.canOpenURL(url) {
      UIApplication.shared.open(url, options: [:]) { opened in
        result(opened)
      }
    } else {
      result(false)
    }
  }
}
