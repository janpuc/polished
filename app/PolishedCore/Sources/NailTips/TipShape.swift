import SwiftUI

/// The tip's outline, CSS `border-radius: 50% 50% 38% 38% / 62% 62% 30% 30%`: the top corners
/// have radii (0.5 w, 0.62 h), the bottom ones (0.38 w, 0.30 h), each a quarter ellipse drawn
/// with four cubic arcs.
public struct TipShape: Shape {
    static let kappa = 0.5523

    public init() {}

    public func path(in rect: CGRect) -> Path {
        let w = rect.width, h = rect.height
        let topX = 0.5 * w, topY = 0.62 * h
        let bottomX = 0.38 * w, bottomY = 0.30 * h
        let k = Self.kappa
        let minX = rect.minX, maxX = rect.maxX, minY = rect.minY, maxY = rect.maxY

        var p = Path()
        p.move(to: CGPoint(x: minX + topX, y: minY))
        // top right
        p.addCurve(
            to: CGPoint(x: maxX, y: minY + topY),
            control1: CGPoint(x: maxX - topX + k * topX, y: minY),
            control2: CGPoint(x: maxX, y: minY + topY - k * topY))
        p.addLine(to: CGPoint(x: maxX, y: maxY - bottomY))
        // bottom right
        p.addCurve(
            to: CGPoint(x: maxX - bottomX, y: maxY),
            control1: CGPoint(x: maxX, y: maxY - bottomY + k * bottomY),
            control2: CGPoint(x: maxX - bottomX + k * bottomX, y: maxY))
        p.addLine(to: CGPoint(x: minX + bottomX, y: maxY))
        // bottom left
        p.addCurve(
            to: CGPoint(x: minX, y: maxY - bottomY),
            control1: CGPoint(x: minX + bottomX - k * bottomX, y: maxY),
            control2: CGPoint(x: minX, y: maxY - bottomY + k * bottomY))
        p.addLine(to: CGPoint(x: minX, y: minY + topY))
        // top left
        p.addCurve(
            to: CGPoint(x: minX + topX, y: minY),
            control1: CGPoint(x: minX, y: minY + topY - k * topY),
            control2: CGPoint(x: minX + topX - k * topX, y: minY))
        p.closeSubpath()
        return p
    }
}
