import Foundation

/// The paint plan of a stack: a port of `ops()` in `tips.py`, same call order and same numbers
/// (docs/NATIVE.md 4.1). A single shade is a stack of one.
public enum TipPainter {
    public static let width = 102.0
    public static let height = 168.0

    static let neutralHex = "#c9bfc0"
    static let nudeHex = "#e9d2c6"
    static let rainbow = ["#ff5fa2", "#ffb347", "#f4ec6a", "#5fe3a1", "#5fb8ff", "#a07bff"]

    /// An opaque polish covers what is below it; a see-through one tints it; a topper adds only
    /// its finish. Over nothing opaque, the layers go on a sheer nude so a lone topper shows.
    public static func ops(for layers: [TipShade]) -> [TipOp] {
        var plan = Plan()
        var start = 0
        for (index, shade) in layers.enumerated() where shade.opaque {
            start = index
        }
        if !layers.contains(where: \.opaque) {
            plan.rect(
                linear([
                    TipStop(0, TipColor.lighten(nudeHex, 0.25), 1),
                    TipStop(1, TipColor.darken(nudeHex, 0.08), 1),
                ]))
        }
        for shade in layers[start...] {
            paint(&plan, shade)
        }
        finish(&plan, matte: layers.last?.finishes.contains("matte") ?? false)
        return plan.ops
    }

    // MARK: plan helpers

    private struct Plan {
        var ops: [TipOp] = []

        mutating func rect(_ fill: TipFill, _ opacity: Double = 1) {
            ops.append(.rect(fill: fill, opacity: opacity))
        }
    }

    private static func solid(_ colour: String) -> TipFill { .solid(colour) }

    private static func linear(
        _ stops: [TipStop], _ x1: Double = 0, _ y1: Double = 0, _ x2: Double = 0, _ y2: Double = 1
    ) -> TipFill {
        .linear(x1: x1, y1: y1, x2: x2, y2: y2, stops: stops)
    }

    private static func radial(_ stops: [TipStop], _ cx: Double = 0.5, _ cy: Double = 0.5, _ r: Double = 0.5)
        -> TipFill
    {
        .radial(cx: cx, cy: cy, r: r, stops: stops)
    }

    /// Round dots in groups by colour (in order of first use), so the plan stays short.
    private static func dots(
        _ plan: inout Plan, _ rng: inout TipRandom, _ count: Int,
        _ radius: ClosedRange<Double>, _ colours: [String], _ opacity: Double
    ) {
        var order: [String] = []
        var groups: [String: [[Double]]] = [:]
        for _ in 0..<count {
            let colour = rng.choice(colours)
            let r = rng.uniform(radius.lowerBound, radius.upperBound)
            let cx = rng.uniform(0, width)
            let cy = rng.uniform(0, height)
            if groups[colour] == nil { order.append(colour) }
            groups[colour, default: []].append([cx, cy, r])
        }
        for colour in order {
            plan.ops.append(.dots(color: colour, opacity: opacity, circles: groups[colour] ?? []))
        }
    }

    private static func sparklePalette(_ shade: TipShade) -> [String] {
        let base = shade.hex
        var palette = [
            base, TipColor.lighten(base, 0.5), TipColor.lighten(base, 0.25), TipColor.darken(base, 0.3), "#ffffff",
        ]
        if let hex2 = shade.hex2 {
            palette += [hex2, TipColor.lighten(hex2, 0.5)]
        }
        if !shade.finishes.isDisjoint(with: ["holographic", "iridescent"]) {
            palette += rainbow
        }
        return palette
    }

    /// The spectrum spread over the tip in two soft diagonal sweeps, starting at a colour that
    /// differs from shade to shade.
    private static func rainbowSheen(_ plan: inout Plan, _ rng: inout TipRandom, _ opacity: Double) {
        let start = rng.randrange(rainbow.count)
        let colours = (0..<(2 * rainbow.count)).map { rainbow[(start + $0) % rainbow.count] }
        let last = colours.count - 1
        let stops = colours.enumerated().map { index, colour in
            TipStop(
                Double(index) / Double(last), colour,
                opacity * (index == 0 || index == last ? 0.55 : 1))
        }
        plan.rect(linear(stops, 0, 0.15, 1, 0.85))
    }

    private static func flakes(_ plan: inout Plan, _ rng: inout TipRandom, _ shade: TipShade) {
        let palette =
            rainbow + [
                shade.hex, shade.hex, TipColor.lighten(shade.hex, 0.4),
                shade.hex2 ?? TipColor.lighten(shade.hex, 0.2),
            ]
        for _ in 0..<18 {
            let cx = rng.uniform(4, width - 4)
            let cy = rng.uniform(4, height - 4)
            let size = rng.uniform(3.5, 9)
            var points: [[Double]] = []
            for index in 0..<rng.randint(4, 6) {
                let angle = Double(index) / 5 * 6.283 + rng.uniform(-0.5, 0.5)
                let radius = size * rng.uniform(0.55, 1.1)
                points.append([cx + radius * cos(angle), cy + radius * sin(angle)])
            }
            let colour = rng.choice(palette)
            plan.ops.append(
                .polygon(
                    points: points, color: colour, opacity: rng.uniform(0.5, 0.8),
                    stroke: "#ffffff", strokeOpacity: 0.35, strokeWidth: 0.4))
        }
    }

    /// One layer: its base, then its finish.
    private static func paint(_ plan: inout Plan, _ shade: TipShade) {
        if shade.clear { return }
        var rng = TipRandom(seed: UInt64(bitPattern: Int64(shade.id)))
        let finishes = shade.finishes
        let base = shade.hex

        if finishes.contains("thermal") {
            let other = shade.hex2 ?? TipColor.shiftHue(TipColor.lighten(base, 0.2), 70)
            let fill = linear([TipStop(0, base, 1), TipStop(0.45, base, 1), TipStop(1, other, 1)])
            plan.rect(fill, shade.topper ? 0.9 : 1)
        } else if shade.seeThrough {
            plan.rect(solid(base), min(0.95, 0.68 + 0.1 * Double(shade.coats)))
            // depth: deeper toward the free edge
            plan.rect(linear([TipStop(0, base, 0), TipStop(1, TipColor.darken(base, 0.45), 0.55)]), 1)
        } else if !shade.topper {
            plan.rect(solid(base))
        } else if shade.tinted {
            plan.rect(solid(base), 0.3)  // a coloured topper leaves a hint of its colour
        }

        if let hex2 = shade.hex2, !shade.topper, !shade.seeThrough,
            finishes.isDisjoint(with: ["thermal", "metallic", "chrome", "magnetic"]),
            TipColor.luminance(hex2) > 0.12
        {
            // duochrome and multichrome shift: the second colour sweeps in across the tip
            plan.rect(
                linear(
                    [TipStop(0, hex2, 0), TipStop(0.45, hex2, 0.0), TipStop(1, hex2, 0.7)], 0, 0.1, 1, 0.9))
        }

        if !finishes.isDisjoint(with: ["metallic", "chrome", "reflective"]) {
            let strong = finishes.contains("chrome")
            let top = TipColor.lighten(base, strong ? 0.6 : 0.4)
            let low = TipColor.darken(base, strong ? 0.5 : 0.35)
            let stops = [
                TipStop(0, top, 1), TipStop(0.28, base, 1), TipStop(0.55, low, 1),
                TipStop(0.8, base, 1), TipStop(1, TipColor.lighten(base, 0.3), 1),
            ]
            plan.rect(linear(stops, 0, 0, 0.9, 1), (strong ? 0.9 : 0.6) * (shade.topper ? 0.5 : 1))
        }

        if finishes.contains("magnetic") {
            plan.ops.append(
                .path(
                    d: "M-8 150Q51 52 112 96L112 128Q51 84-8 176Z",
                    paint: .color(TipColor.lighten(base, 0.6)), opacity: 0.75, blur: 3.5))
            plan.ops.append(
                .path(
                    d: "M-8 128Q51 36 112 74L112 84Q51 52-8 146Z",
                    paint: .color(TipColor.darken(base, 0.45)), opacity: 0.35, blur: 3.5))
        }

        if !finishes.isDisjoint(with: ["holographic", "iridescent"]) {
            let strength = finishes.contains("holographic") ? 0.2 : 0.12
            rainbowSheen(&plan, &rng, strength * (shade.topper ? 0.6 : 1))
        }
        if !finishes.isDisjoint(with: ["shimmer", "holographic", "iridescent", "reflective"]) {
            let count = finishes.contains("shimmer") ? 190 : 90
            dots(
                &plan, &rng, count, 0.35...0.8,
                [TipColor.lighten(base, 0.45), TipColor.lighten(base, 0.25), TipColor.darken(base, 0.3)], 0.5)
        }
        if finishes.contains("glitter") {
            dots(&plan, &rng, 55, 0.7...1.9, sparklePalette(shade), 0.9)
            for _ in 0..<7 {
                let cx = rng.uniform(8, width - 8)
                let cy = rng.uniform(8, height - 8)
                let size = rng.uniform(2.6, 5.2)
                plan.ops.append(.star(cx: cx, cy: cy, size: size, color: "#ffffff", opacity: 0.9))
            }
        }
        if finishes.contains("flakie") {
            flakes(&plan, &rng, shade)
        }
    }

    /// Over everything: the curve of the nail, then the gloss unless the top coat is matte. The
    /// lit tip's overlay adds the occlusion and the specular pool on top of this.
    private static func finish(_ plan: inout Plan, matte: Bool) {
        plan.rect(radial([TipStop(0.55, "#000000", 0), TipStop(1, "#000000", 0.18)], 0.5, 0.42, 0.78), 1)
        if matte { return }
        plan.ops.append(
            .path(
                d: "M25 30C26 20 37 20 39 30L36 98C35 106 29 105 28 97Z",
                paint: .fill(linear([TipStop(0, "#ffffff", 0.5), TipStop(1, "#ffffff", 0.03)])),
                opacity: 1, blur: nil))
        plan.ops.append(.ellipse(cx: 66, cy: 30, rx: 6, ry: 15, rotate: 14, color: "#ffffff", opacity: 0.1))
    }
}
