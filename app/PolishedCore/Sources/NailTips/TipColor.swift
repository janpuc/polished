import Foundation

/// Colour arithmetic of `tips.py`: colours are lowercase `#rrggbb` strings, channels are rounded
/// half to even like Python's `round`.
enum TipColor {
    static func rgb(_ colour: String) -> (Double, Double, Double) {
        let digits = Array(colour.utf8.dropFirst())
        func channel(_ at: Int) -> Double {
            Double(hexValue(digits[at]) * 16 + hexValue(digits[at + 1]))
        }
        return (channel(0), channel(2), channel(4))
    }

    private static func hexValue(_ byte: UInt8) -> Int {
        switch byte {
        case UInt8(ascii: "0")...UInt8(ascii: "9"): Int(byte) - Int(UInt8(ascii: "0"))
        case UInt8(ascii: "a")...UInt8(ascii: "f"): Int(byte) - Int(UInt8(ascii: "a")) + 10
        case UInt8(ascii: "A")...UInt8(ascii: "F"): Int(byte) - Int(UInt8(ascii: "A")) + 10
        default: 0
        }
    }

    static func hex(_ r: Double, _ g: Double, _ b: Double) -> String {
        func part(_ c: Double) -> String {
            let value = Int(max(0, min(255, c.rounded(.toNearestOrEven))))
            return (value < 16 ? "0" : "") + String(value, radix: 16)
        }
        return "#" + part(r) + part(g) + part(b)
    }

    /// `amount` of b in a.
    static func mix(_ a: String, _ b: String, _ amount: Double) -> String {
        let (ar, ag, ab) = rgb(a)
        let (br, bg, bb) = rgb(b)
        return hex(
            ar + (br - ar) * amount,
            ag + (bg - ag) * amount,
            ab + (bb - ab) * amount
        )
    }

    static func lighten(_ colour: String, _ amount: Double) -> String {
        mix(colour, "#ffffff", amount)
    }

    static func darken(_ colour: String, _ amount: Double) -> String {
        mix(colour, "#000000", amount)
    }

    /// Python's float `%` for a positive modulus.
    private static func mod(_ x: Double, _ w: Double) -> Double {
        let r = fmod(x, w)
        return r != 0 && r < 0 ? r + w : r
    }

    // colorsys.rgb_to_hsv, line for line.
    static func hsv(_ r: Double, _ g: Double, _ b: Double) -> (h: Double, s: Double, v: Double) {
        let maxc = max(r, g, b)
        let minc = min(r, g, b)
        let range = maxc - minc
        let v = maxc
        if minc == maxc { return (0, 0, v) }
        let s = range / maxc
        let rc = (maxc - r) / range
        let gc = (maxc - g) / range
        let bc = (maxc - b) / range
        var h: Double
        if r == maxc {
            h = bc - gc
        } else if g == maxc {
            h = 2.0 + rc - bc
        } else {
            h = 4.0 + gc - rc
        }
        h = mod(h / 6.0, 1.0)
        return (h, s, v)
    }

    // colorsys.hsv_to_rgb, line for line.
    static func rgb(h: Double, s: Double, v: Double) -> (Double, Double, Double) {
        if s == 0.0 { return (v, v, v) }
        var i = Int(h * 6.0)
        let f = h * 6.0 - Double(i)
        let p = v * (1.0 - s)
        let q = v * (1.0 - s * f)
        let t = v * (1.0 - s * (1.0 - f))
        i %= 6
        switch i {
        case 0: return (v, t, p)
        case 1: return (q, v, p)
        case 2: return (p, v, t)
        case 3: return (p, q, v)
        case 4: return (t, p, v)
        default: return (v, p, q)
        }
    }

    static func shiftHue(_ colour: String, _ degrees: Double) -> String {
        let (r, g, b) = rgb(colour)
        let (h, s, v) = hsv(r / 255, g / 255, b / 255)
        let (nr, ng, nb) = rgb(h: mod(h + degrees / 360, 1), s: s, v: v)
        return hex(nr * 255, ng * 255, nb * 255)
    }

    static func luminance(_ colour: String) -> Double {
        let (r, g, b) = rgb(colour)
        return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
    }

    static func saturation(_ colour: String) -> Double {
        let (r, g, b) = rgb(colour)
        return hsv(r / 255, g / 255, b / 255).s
    }
}
