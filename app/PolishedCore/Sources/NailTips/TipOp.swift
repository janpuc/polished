import Foundation

/// A gradient stop: offset 0...1, `#rrggbb`, opacity.
public struct TipStop: Sendable, Equatable {
    public var offset: Double
    public var color: String
    public var opacity: Double

    public init(_ offset: Double, _ color: String, _ opacity: Double) {
        self.offset = offset
        self.color = color
        self.opacity = opacity
    }
}

/// A fill in fractions of the tip (or, for a path, of the path's own bounding box).
public enum TipFill: Sendable, Equatable {
    case solid(String)
    case linear(x1: Double, y1: Double, x2: Double, y2: Double, stops: [TipStop])
    case radial(cx: Double, cy: Double, r: Double, stops: [TipStop])
}

/// One paint operation of `tips.py` `ops()`, in painting order (docs/NATIVE.md 4.1).
public enum TipOp: Sendable, Equatable {
    case rect(fill: TipFill, opacity: Double)
    case dots(color: String, opacity: Double, circles: [[Double]])
    case star(cx: Double, cy: Double, size: Double, color: String, opacity: Double)
    case polygon(
        points: [[Double]], color: String, opacity: Double,
        stroke: String, strokeOpacity: Double, strokeWidth: Double
    )
    case path(d: String, paint: PathPaint, opacity: Double, blur: Double?)
    case ellipse(cx: Double, cy: Double, rx: Double, ry: Double, rotate: Double, color: String, opacity: Double)

    /// A path has a `color` or, for the gloss highlight, a gradient `fill`.
    public enum PathPaint: Sendable, Equatable {
        case color(String)
        case fill(TipFill)
    }

    public var kind: String {
        switch self {
        case .rect: "rect"
        case .dots: "dots"
        case .star: "star"
        case .polygon: "polygon"
        case .path: "path"
        case .ellipse: "ellipse"
        }
    }
}

// MARK: - Codable: the shape of spec/tips/cases.json

extension TipStop: Codable {
    public init(from decoder: any Decoder) throws {
        var c = try decoder.unkeyedContainer()
        offset = try c.decode(Double.self)
        color = try c.decode(String.self)
        opacity = try c.decode(Double.self)
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.unkeyedContainer()
        try c.encode(offset)
        try c.encode(color)
        try c.encode(opacity)
    }
}

extension TipFill: Codable {
    private enum Key: String, CodingKey { case kind, color, x1, y1, x2, y2, cx, cy, r, stops }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: Key.self)
        switch try c.decode(String.self, forKey: .kind) {
        case "solid":
            self = .solid(try c.decode(String.self, forKey: .color))
        case "linear":
            self = .linear(
                x1: try c.decode(Double.self, forKey: .x1), y1: try c.decode(Double.self, forKey: .y1),
                x2: try c.decode(Double.self, forKey: .x2), y2: try c.decode(Double.self, forKey: .y2),
                stops: try c.decode([TipStop].self, forKey: .stops)
            )
        case "radial":
            self = .radial(
                cx: try c.decode(Double.self, forKey: .cx), cy: try c.decode(Double.self, forKey: .cy),
                r: try c.decode(Double.self, forKey: .r), stops: try c.decode([TipStop].self, forKey: .stops)
            )
        case let kind:
            throw DecodingError.dataCorruptedError(
                forKey: .kind, in: c, debugDescription: "unknown fill kind \(kind)")
        }
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: Key.self)
        switch self {
        case .solid(let color):
            try c.encode("solid", forKey: .kind)
            try c.encode(color, forKey: .color)
        case .linear(let x1, let y1, let x2, let y2, let stops):
            try c.encode("linear", forKey: .kind)
            try c.encode(x1, forKey: .x1)
            try c.encode(y1, forKey: .y1)
            try c.encode(x2, forKey: .x2)
            try c.encode(y2, forKey: .y2)
            try c.encode(stops, forKey: .stops)
        case .radial(let cx, let cy, let r, let stops):
            try c.encode("radial", forKey: .kind)
            try c.encode(cx, forKey: .cx)
            try c.encode(cy, forKey: .cy)
            try c.encode(r, forKey: .r)
            try c.encode(stops, forKey: .stops)
        }
    }
}

extension TipOp: Codable {
    private enum Key: String, CodingKey {
        case op, fill, opacity, color, circles, cx, cy, size, points, stroke, d, blur
        case rx, ry, rotate
        case strokeOpacity = "stroke_opacity"
        case strokeWidth = "stroke_width"
    }

    public init(from decoder: any Decoder) throws {
        let c = try decoder.container(keyedBy: Key.self)
        let opacity = try c.decode(Double.self, forKey: .opacity)
        switch try c.decode(String.self, forKey: .op) {
        case "rect":
            self = .rect(fill: try c.decode(TipFill.self, forKey: .fill), opacity: opacity)
        case "dots":
            self = .dots(
                color: try c.decode(String.self, forKey: .color), opacity: opacity,
                circles: try c.decode([[Double]].self, forKey: .circles))
        case "star":
            self = .star(
                cx: try c.decode(Double.self, forKey: .cx), cy: try c.decode(Double.self, forKey: .cy),
                size: try c.decode(Double.self, forKey: .size), color: try c.decode(String.self, forKey: .color),
                opacity: opacity)
        case "polygon":
            self = .polygon(
                points: try c.decode([[Double]].self, forKey: .points), color: try c.decode(String.self, forKey: .color),
                opacity: opacity, stroke: try c.decode(String.self, forKey: .stroke),
                strokeOpacity: try c.decode(Double.self, forKey: .strokeOpacity),
                strokeWidth: try c.decode(Double.self, forKey: .strokeWidth))
        case "path":
            let paint: PathPaint =
                if let fill = try c.decodeIfPresent(TipFill.self, forKey: .fill) {
                    .fill(fill)
                } else {
                    .color(try c.decode(String.self, forKey: .color))
                }
            self = .path(
                d: try c.decode(String.self, forKey: .d), paint: paint, opacity: opacity,
                blur: try c.decodeIfPresent(Double.self, forKey: .blur))
        case "ellipse":
            self = .ellipse(
                cx: try c.decode(Double.self, forKey: .cx), cy: try c.decode(Double.self, forKey: .cy),
                rx: try c.decode(Double.self, forKey: .rx), ry: try c.decode(Double.self, forKey: .ry),
                rotate: try c.decode(Double.self, forKey: .rotate), color: try c.decode(String.self, forKey: .color),
                opacity: opacity)
        case let kind:
            throw DecodingError.dataCorruptedError(
                forKey: .op, in: c, debugDescription: "unknown op \(kind)")
        }
    }

    public func encode(to encoder: any Encoder) throws {
        var c = encoder.container(keyedBy: Key.self)
        try c.encode(kind, forKey: .op)
        switch self {
        case .rect(let fill, let opacity):
            try c.encode(fill, forKey: .fill)
            try c.encode(opacity, forKey: .opacity)
        case .dots(let color, let opacity, let circles):
            try c.encode(color, forKey: .color)
            try c.encode(opacity, forKey: .opacity)
            try c.encode(circles, forKey: .circles)
        case .star(let cx, let cy, let size, let color, let opacity):
            try c.encode(cx, forKey: .cx)
            try c.encode(cy, forKey: .cy)
            try c.encode(size, forKey: .size)
            try c.encode(color, forKey: .color)
            try c.encode(opacity, forKey: .opacity)
        case .polygon(let points, let color, let opacity, let stroke, let strokeOpacity, let strokeWidth):
            try c.encode(points, forKey: .points)
            try c.encode(color, forKey: .color)
            try c.encode(opacity, forKey: .opacity)
            try c.encode(stroke, forKey: .stroke)
            try c.encode(strokeOpacity, forKey: .strokeOpacity)
            try c.encode(strokeWidth, forKey: .strokeWidth)
        case .path(let d, let paint, let opacity, let blur):
            try c.encode(d, forKey: .d)
            switch paint {
            case .color(let color): try c.encode(color, forKey: .color)
            case .fill(let fill): try c.encode(fill, forKey: .fill)
            }
            try c.encode(opacity, forKey: .opacity)
            try c.encodeIfPresent(blur, forKey: .blur)
        case .ellipse(let cx, let cy, let rx, let ry, let rotate, let color, let opacity):
            try c.encode(cx, forKey: .cx)
            try c.encode(cy, forKey: .cy)
            try c.encode(rx, forKey: .rx)
            try c.encode(ry, forKey: .ry)
            try c.encode(rotate, forKey: .rotate)
            try c.encode(color, forKey: .color)
            try c.encode(opacity, forKey: .opacity)
        }
    }
}
