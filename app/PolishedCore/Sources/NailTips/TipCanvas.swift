import SwiftUI

extension Color {
    /// `#rrggbb` as sRGB with an opacity.
    init(tipHex hex: String, opacity: Double = 1) {
        let (r, g, b) = TipColor.rgb(hex)
        self.init(.sRGB, red: r / 255, green: g / 255, blue: b / 255, opacity: opacity)
    }
}

/// Draws a paint plan on a `Canvas`: the SVG of `tips.py` in 102 by 168 units, scaled to fill
/// (SVG `slice`). Gradients are measured in the tip's (or the path's) bounding box like SVG's
/// `objectBoundingBox`, so a radial one is an ellipse and a diagonal one is sheared the same way.
public struct TipCanvas: View {
    private let ops: [TipOp]

    public init(ops: [TipOp]) {
        self.ops = ops
    }

    public var body: some View {
        Canvas { context, size in
            var context = context
            Self.draw(ops, in: &context, size: size)
        }
    }

    public static func draw(_ ops: [TipOp], in context: inout GraphicsContext, size: CGSize) {
        let width = TipPainter.width, height = TipPainter.height
        let scale = max(size.width / width, size.height / height)
        context.translateBy(x: (size.width - width * scale) / 2, y: (size.height - height * scale) / 2)
        context.scaleBy(x: scale, y: scale)
        let tip = Path(CGRect(x: 0, y: 0, width: width, height: height))
        for op in ops {
            draw(op, in: context, tip: tip, scale: scale)
        }
    }

    // MARK: ops

    private static func draw(_ op: TipOp, in base: GraphicsContext, tip: Path, scale: Double) {
        var context = base
        switch op {
        case .rect(let fill, let opacity):
            context.opacity = opacity
            paint(fill, path: tip, in: context, box: tip.boundingRect)

        case .dots(let color, let opacity, let circles):
            var path = Path()
            for circle in circles {
                path.addEllipse(in: CGRect(x: circle[0] - circle[2], y: circle[1] - circle[2], width: circle[2] * 2, height: circle[2] * 2))
            }
            context.opacity = opacity
            context.fill(path, with: .color(Color(tipHex: color)))

        case .star(let cx, let cy, let size, let color, let opacity):
            let pinch = size * 0.16
            var path = Path()
            path.move(to: CGPoint(x: cx, y: cy - size))
            path.addLine(to: CGPoint(x: cx + pinch, y: cy - pinch))
            path.addLine(to: CGPoint(x: cx + size, y: cy))
            path.addLine(to: CGPoint(x: cx + pinch, y: cy + pinch))
            path.addLine(to: CGPoint(x: cx, y: cy + size))
            path.addLine(to: CGPoint(x: cx - pinch, y: cy + pinch))
            path.addLine(to: CGPoint(x: cx - size, y: cy))
            path.addLine(to: CGPoint(x: cx - pinch, y: cy - pinch))
            path.closeSubpath()
            context.opacity = opacity
            context.fill(path, with: .color(Color(tipHex: color)))

        case .polygon(let points, let color, let opacity, let stroke, let strokeOpacity, let strokeWidth):
            var path = Path()
            for (index, point) in points.enumerated() {
                let p = CGPoint(x: point[0], y: point[1])
                index == 0 ? path.move(to: p) : path.addLine(to: p)
            }
            path.closeSubpath()
            context.fill(path, with: .color(Color(tipHex: color, opacity: opacity)))
            context.stroke(
                path, with: .color(Color(tipHex: stroke, opacity: strokeOpacity)),
                style: StrokeStyle(lineWidth: strokeWidth, lineJoin: .miter, miterLimit: 4))

        case .path(let d, let paintSource, let opacity, let blur):
            let path = SVGPath.parse(d)
            context.opacity = opacity
            func fillPath(_ context: GraphicsContext) {
                switch paintSource {
                case .color(let color):
                    context.fill(path, with: .color(Color(tipHex: color)))
                case .fill(let fill):
                    paint(fill, path: path, in: context, box: SVGPath.tightBounds(of: path))
                }
            }
            if let blur {
                context.drawLayer { layer in
                    layer.addFilter(.blur(radius: blur))
                    fillPath(layer)
                }
            } else {
                fillPath(context)
            }

        case .ellipse(let cx, let cy, let rx, let ry, let rotate, let color, let opacity):
            context.opacity = opacity
            context.translateBy(x: cx, y: cy)
            context.rotate(by: .degrees(rotate))
            context.fill(
                Path(ellipseIn: CGRect(x: -rx, y: -ry, width: rx * 2, height: ry * 2)),
                with: .color(Color(tipHex: color)))
        }
    }

    /// Fills `path` with `fill` whose coordinates are fractions of `box`.
    private static func paint(_ fill: TipFill, path: Path, in context: GraphicsContext, box: CGRect) {
        switch fill {
        case .solid(let color):
            context.fill(path, with: .color(Color(tipHex: color)))
        case .linear(let x1, let y1, let x2, let y2, let stops):
            let shading = GraphicsContext.Shading.linearGradient(
                gradient(stops), startPoint: CGPoint(x: x1, y: y1), endPoint: CGPoint(x: x2, y: y2))
            fillInUnitBox(path, shading: shading, in: context, box: box)
        case .radial(let cx, let cy, let r, let stops):
            let shading = GraphicsContext.Shading.radialGradient(
                gradient(stops), center: CGPoint(x: cx, y: cy), startRadius: 0, endRadius: r)
            fillInUnitBox(path, shading: shading, in: context, box: box)
        }
    }

    /// Maps `box` to the unit square, so the gradient's fractions apply and stretch with the box.
    private static func fillInUnitBox(_ path: Path, shading: GraphicsContext.Shading, in context: GraphicsContext, box: CGRect) {
        var unit = context
        unit.translateBy(x: box.minX, y: box.minY)
        unit.scaleBy(x: box.width, y: box.height)
        let inverse = CGAffineTransform(translationX: -box.minX, y: -box.minY)
            .concatenating(CGAffineTransform(scaleX: 1 / box.width, y: 1 / box.height))
        unit.fill(path.applying(inverse), with: shading)
    }

    /// SVG interpolates a gradient's colour and opacity separately (straight alpha); SwiftUI
    /// interpolates premultiplied colours, which turns a fade from one colour to a darker one into
    /// the darker colour early. Stops whose colour and opacity both change get intermediate stops
    /// worked out in straight alpha, so the two agree.
    static func gradient(_ stops: [TipStop]) -> Gradient {
        let steps = 8
        var expanded: [Gradient.Stop] = []
        for (index, stop) in stops.enumerated() {
            if index > 0 {
                let previous = stops[index - 1]
                if previous.color != stop.color, previous.opacity != stop.opacity {
                    let (pr, pg, pb) = TipColor.rgb(previous.color)
                    let (r, g, b) = TipColor.rgb(stop.color)
                    for step in 1..<steps {
                        let t = Double(step) / Double(steps)
                        expanded.append(
                            .init(
                                color: Color(
                                    .sRGB, red: (pr + (r - pr) * t) / 255, green: (pg + (g - pg) * t) / 255,
                                    blue: (pb + (b - pb) * t) / 255,
                                    opacity: previous.opacity + (stop.opacity - previous.opacity) * t),
                                location: previous.offset + (stop.offset - previous.offset) * t))
                    }
                }
            }
            expanded.append(.init(color: Color(tipHex: stop.color, opacity: stop.opacity), location: stop.offset))
        }
        return Gradient(stops: expanded)
    }
}
