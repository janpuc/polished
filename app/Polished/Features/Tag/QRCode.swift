import CoreImage.CIFilterBuiltins
import SwiftUI

/// A QR code of `text` on a white plate, drawn from the generator's modules at a whole number of
/// pixels each so the edges stay hard at any size. The plate is white in dark mode too: a camera
/// reads dark modules on a light ground.
struct QRCodeView: View {
    let text: String
    var side: CGFloat = 216
    @Environment(\.displayScale) private var displayScale

    var body: some View {
        Group {
            if let image = Self.image(text, pixels: Int(side * displayScale)) {
                Image(decorative: image, scale: displayScale)
                    .interpolation(.none)
                    .resizable()
                    .frame(width: side, height: side)
            } else {
                Color.clear.frame(width: side, height: side)
            }
        }
        .padding(16)
        .background(Color.white, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay { RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(Color.line, lineWidth: 1) }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("QR code for \(text)")
        .accessibilityIdentifier("tag-qr")
    }

    /// Correction level M; each module is `pixels / modules` rounded down to whole pixels, and the
    /// image is centred in `pixels` square.
    static func image(_ text: String, pixels: Int) -> CGImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(text.utf8)
        filter.correctionLevel = "M"
        guard let output = filter.outputImage else { return nil }
        let modules = Int(output.extent.width)
        let scale = max(1, pixels / max(1, modules))
        let scaled = output.transformed(by: CGAffineTransform(scaleX: CGFloat(scale), y: CGFloat(scale)))
        let side = modules * scale
        let canvas = CGRect(x: 0, y: 0, width: max(pixels, side), height: max(pixels, side))
        let offset = CGAffineTransform(translationX: (canvas.width - CGFloat(side)) / 2, y: (canvas.height - CGFloat(side)) / 2)
        let white = CIImage(color: .white).cropped(to: canvas)
        let composed = scaled.transformed(by: offset).composited(over: white)
        return CIContext().createCGImage(composed, from: canvas)
    }
}
