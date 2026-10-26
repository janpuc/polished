import SwiftUI

/// Path data for the fixed paths of `tips.py`: absolute M, L, Q, C and Z, numbers separated by
/// spaces or a minus sign ("84-8" is 84 and -8).
enum SVGPath {
    static func parse(_ d: String) -> Path {
        var path = Path()
        var scanner = Scanner(d)
        var command: Character = "M"
        while let next = scanner.nextToken() {
            switch next {
            case .command(let c):
                command = c
                if c == "Z" { path.closeSubpath() }
            case .number(let first):
                var numbers = [first]
                let needed =
                    switch command {
                    case "M", "L": 2
                    case "Q": 4
                    case "C": 6
                    default: 0
                    }
                while numbers.count < needed, let more = scanner.nextNumber() { numbers.append(more) }
                guard numbers.count == needed else { return path }
                let p = stride(from: 0, to: needed, by: 2).map { CGPoint(x: numbers[$0], y: numbers[$0 + 1]) }
                switch command {
                case "M": path.move(to: p[0])
                case "L": path.addLine(to: p[0])
                case "Q": path.addQuadCurve(to: p[1], control: p[0])
                case "C": path.addCurve(to: p[2], control1: p[0], control2: p[1])
                default: break
                }
            }
        }
        return path
    }

    /// The tight bounding box of the filled geometry (SVG's `objectBoundingBox`; `Path.boundingRect`
    /// would include the curves' control points), found by sampling the curves.
    static func tightBounds(of path: Path) -> CGRect {
        var minX = Double.infinity, minY = Double.infinity, maxX = -Double.infinity, maxY = -Double.infinity
        func add(_ p: CGPoint) {
            minX = min(minX, p.x)
            maxX = max(maxX, p.x)
            minY = min(minY, p.y)
            maxY = max(maxY, p.y)
        }
        var current = CGPoint.zero
        var start = CGPoint.zero
        path.forEach { element in
            switch element {
            case .move(let to):
                current = to
                start = to
                add(to)
            case .line(let to):
                current = to
                add(to)
            case .quadCurve(let to, let control):
                for i in 1...64 {
                    let t = Double(i) / 64
                    let u = 1 - t
                    add(
                        CGPoint(
                            x: u * u * current.x + 2 * u * t * control.x + t * t * to.x,
                            y: u * u * current.y + 2 * u * t * control.y + t * t * to.y))
                }
                current = to
            case .curve(let to, let c1, let c2):
                for i in 1...64 {
                    let t = Double(i) / 64
                    let u = 1 - t
                    add(
                        CGPoint(
                            x: u * u * u * current.x + 3 * u * u * t * c1.x + 3 * u * t * t * c2.x + t * t * t * to.x,
                            y: u * u * u * current.y + 3 * u * u * t * c1.y + 3 * u * t * t * c2.y + t * t * t * to.y))
                }
                current = to
            case .closeSubpath:
                current = start
            }
        }
        guard minX.isFinite else { return .zero }
        return CGRect(x: minX, y: minY, width: maxX - minX, height: maxY - minY)
    }

    private enum Token {
        case command(Character)
        case number(Double)
    }

    private struct Scanner {
        private let chars: [Character]
        private var index = 0

        init(_ text: String) { chars = Array(text) }

        mutating func nextToken() -> Token? {
            skipSeparators()
            guard index < chars.count else { return nil }
            let c = chars[index]
            if c.isLetter {
                index += 1
                return .command(c)
            }
            return nextNumber().map(Token.number)
        }

        mutating func nextNumber() -> Double? {
            skipSeparators()
            guard index < chars.count else { return nil }
            var text = ""
            if chars[index] == "-" || chars[index] == "+" {
                text.append(chars[index])
                index += 1
            }
            var seenDot = false
            while index < chars.count {
                let c = chars[index]
                if c.isNumber {
                    text.append(c)
                } else if c == ".", !seenDot {
                    seenDot = true
                    text.append(c)
                } else {
                    break
                }
                index += 1
            }
            return Double(text)
        }

        private mutating func skipSeparators() {
            while index < chars.count, chars[index] == " " || chars[index] == "," { index += 1 }
        }
    }
}
