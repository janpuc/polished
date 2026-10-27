import AVFoundation
import SwiftUI
import Vision
import VisionKit

/// Why the live camera is not there: the simulator and devices without a camera, or access that
/// was refused. The screen then offers the typed field alone.
enum CameraAvailability {
    case ready
    case unsupported
    case denied

    @MainActor
    static var current: CameraAvailability {
        guard DataScannerViewController.isSupported else { return .unsupported }
        return DataScannerViewController.isAvailable ? .ready : .denied
    }
}

/// VisionKit's live scanner for the barcodes on a bottle: EAN-13 (a UPC-A reads as one), EAN-8 and
/// UPC-E; Code 128 is off (it is on shipping labels, not on polish). It highlights what it sees
/// and tells the person how to hold the phone; each barcode it reports goes to `onBarcode`.
struct DataScannerView: UIViewControllerRepresentable {
    @Binding var torchIsOn: Bool
    let onBarcode: (String) -> Void

    static var hasTorch: Bool { AVCaptureDevice.default(for: .video)?.hasTorch == true }

    func makeCoordinator() -> Coordinator {
        Coordinator(onBarcode: onBarcode)
    }

    func makeUIViewController(context: Context) -> DataScannerViewController {
        let scanner = DataScannerViewController(
            recognizedDataTypes: [.barcode(symbologies: [.ean13, .ean8, .upce])],
            qualityLevel: .balanced,
            recognizesMultipleItems: false,
            isHighFrameRateTrackingEnabled: false,
            isPinchToZoomEnabled: true,
            isGuidanceEnabled: true,
            isHighlightingEnabled: true)
        scanner.delegate = context.coordinator
        return scanner
    }

    func updateUIViewController(_ scanner: DataScannerViewController, context: Context) {
        context.coordinator.onBarcode = onBarcode
        if !scanner.isScanning { try? scanner.startScanning() }
        Self.setTorch(torchIsOn)
    }

    static func dismantleUIViewController(_ scanner: DataScannerViewController, coordinator: Coordinator) {
        scanner.stopScanning()
        setTorch(false)
    }

    @MainActor
    private static func setTorch(_ on: Bool) {
        guard let device = AVCaptureDevice.default(for: .video), device.hasTorch,
            (device.torchMode == .on) != on, (try? device.lockForConfiguration()) != nil
        else { return }
        device.torchMode = on ? .on : .off
        device.unlockForConfiguration()
    }

    @MainActor
    final class Coordinator: NSObject, DataScannerViewControllerDelegate {
        var onBarcode: (String) -> Void

        init(onBarcode: @escaping (String) -> Void) {
            self.onBarcode = onBarcode
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didAdd addedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            report(addedItems)
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didUpdate updatedItems: [RecognizedItem], allItems: [RecognizedItem]) {
            report(updatedItems)
        }

        func dataScanner(_ dataScanner: DataScannerViewController, didTapOn item: RecognizedItem) {
            report([item])
        }

        private func report(_ items: [RecognizedItem]) {
            for case .barcode(let barcode) in items {
                if let payload = barcode.payloadStringValue {
                    onBarcode(payload)
                    return
                }
            }
        }
    }
}
