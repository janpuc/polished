import NailTips
import SwiftUI

/// The five tip sizes (docs/NATIVE.md 4.3); the regular width classes use the larger set.
enum TipSize: CaseIterable {
    case s, m, l, xl, ring

    func dimensions(regular: Bool) -> CGSize {
        switch self {
        case .s: CGSize(width: 28, height: 46)
        case .m: regular ? CGSize(width: 44, height: 72) : CGSize(width: 40, height: 66)
        case .l: regular ? CGSize(width: 88, height: 144) : CGSize(width: 72, height: 118)
        case .xl: regular ? CGSize(width: 120, height: 197) : CGSize(width: 96, height: 158)
        case .ring: regular ? CGSize(width: 44, height: 72) : CGSize(width: 38, height: 62)
        }
    }
}

/// How the painted tip gets onto the screen: from the image cache (rows, which scroll), or
/// drawn live (heroes, the rack, the ring).
enum TipPainting {
    case cached
    case direct
}

/// A tip under one light: the painted nail of `TipCanvas` inside the v3 treatment of
/// `app.css` `.tip` (docs/advice/fable-v3-web-2026-10-26.md 2.4): a contact shadow, a die-cut
/// edge, and on the face the mat, the rim, the occlusion, a specular pool and the 115 degree
/// band in soft light. A nil recipe is the unpainted tip. Tips are decorative: the row that
/// holds one carries the label.
struct TipView: View {
    let recipe: TipRecipe?
    let size: TipSize
    /// A slot of a ring has its own size (the ring's geometry decides it); the edge and the
    /// shadow thin out with the height.
    var dimensions: CGSize?
    var light: TipLight = .static
    var painting: TipPainting = .cached

    @Environment(\.colorScheme) private var colorScheme
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    init(
        _ recipe: TipRecipe?, size: TipSize, dimensions: CGSize? = nil, light: TipLight = .static,
        painting: TipPainting = .cached
    ) {
        self.recipe = recipe
        self.size = size
        self.dimensions = dimensions
        self.light = light
        self.painting = painting
    }

    var body: some View {
        let dimensions = dimensions ?? size.dimensions(regular: horizontalSizeClass == .regular)
        let dark = colorScheme == .dark
        let small = size == .s || dimensions.height < 40
        face(dimensions)
            .frame(width: dimensions.width, height: dimensions.height)
            .background {
                // Outside the clip and larger than the face, so they must not take part in layout.
                ZStack {
                    TipShadow(dimensions: dimensions, dark: dark, lifted: !small)
                    TipEdge(dimensions: dimensions, dark: dark, thin: small)
                }
            }
            .accessibilityHidden(true)
    }

    // CSS draws the pool (white 50%) and the band (white 35%) in `soft-light`. Core Graphics' soft
    // light lifts red and blue more and green less than the W3C formula, which tints the pool
    // pink. So each is drawn as a smaller soft-light part plus a small plain white lift, tuned
    // against the web's tips on the parity montage (docs/NATIVE.md 4.3).
    private static let softPool = 0.25
    private static let softBand = 0.12
    private static let liftPool = 0.08
    private static let liftBand = 0.09

    private func face(_ dimensions: CGSize) -> some View {
        ZStack {
            Color.fill
            if let recipe {
                painted(recipe, dimensions)
            }
            TipSurfaceLight(light: light, poolAlpha: Self.softPool, bandAlpha: Self.softBand, chrome: true)
                .blendMode(.softLight)
            TipSurfaceLight(light: light, poolAlpha: Self.liftPool, bandAlpha: Self.liftBand, chrome: false)
        }
        .compositingGroup()
        .clipShape(TipShape())
    }

    @ViewBuilder
    private func painted(_ recipe: TipRecipe, _ dimensions: CGSize) -> some View {
        switch painting {
        case .cached:
            if let image = TipImageCache.shared.image(for: recipe, size: dimensions) {
                image.resizable()
            }
        case .direct:
            TipCanvas(ops: recipe.ops)
        }
    }

    /// The unpainted tip, for a state with no shade to show.
    static func unpainted(size: TipSize, light: TipLight = .static) -> TipView {
        TipView(nil, size: size, light: light)
    }
}

/// The contact shadow under the foot and the soft drop under the face. The shadows sit outside
/// the clip, so a parent must leave room for them.
private struct TipShadow: View {
    let dimensions: CGSize
    let dark: Bool
    let lifted: Bool

    var body: some View {
        let w = dimensions.width, h = dimensions.height
        let ink = dark ? Color.black : Color.shadowInk
        ZStack {
            // ellipse 76% wide and 16% tall, its bottom 5% below the tip
            Ellipse()
                .fill(ink.opacity(dark ? 0.55 : 0.26))
                .frame(width: w * 0.76, height: h * 0.16)
                .blur(radius: 4)
                .offset(y: h * 0.47)
            // 0 1px 2px
            TipShape()
                .fill(ink.opacity(dark ? 0.5 : 0.18))
                .blur(radius: 1)
                .offset(y: 1)
            if lifted {
                // 0 8px 18px -6px (dark: 0 10px 22px -6px)
                TipShape()
                    .fill(ink.opacity(dark ? 0.7 : 0.35))
                    .frame(width: w - 12, height: h - 12)
                    .blur(radius: dark ? 11 : 9)
                    .offset(y: dark ? 10 : 8)
            }
        }
    }
}

/// The die-cut edge: a 1.5 pt ring of Surface in light, a 1 pt white 14% ring in dark.
private struct TipEdge: View {
    let dimensions: CGSize
    let dark: Bool
    let thin: Bool

    var body: some View {
        let spread: CGFloat = dark || thin ? 1 : 1.5
        TipShape()
            .fill(dark ? Color.white.opacity(0.14) : Color.surface)
            .frame(width: dimensions.width + spread * 2, height: dimensions.height + spread * 2)
    }
}

/// The light on the surface: drawn once, in soft light over the painted tip.
private struct TipSurfaceLight: View {
    let light: TipLight
    let poolAlpha: Double
    let bandAlpha: Double
    /// The mat, the rim and the occlusion, which belong to the soft-light part only.
    let chrome: Bool

    var body: some View {
        Canvas { context, size in
            let bounds = CGRect(origin: .zero, size: size)
            let shape = TipShape().path(in: bounds)
            let w = size.width, h = size.height

            // The specular pool: an ellipse 60% by 40% of the tip around the light's place.
            do {
                var pool = context
                pool.clip(to: shape)
                pool.translateBy(x: w * (0.5 + light.lx * 0.4), y: h * (0.5 + light.ly * 0.4))
                pool.scaleBy(x: w * 0.6, y: h * 0.4)
                pool.fill(
                    Path(CGRect(x: -2, y: -2, width: 4, height: 4)),
                    with: .radialGradient(
                        Gradient(stops: [
                            .init(color: .white.opacity(poolAlpha), location: 0),
                            .init(color: .white.opacity(0), location: 0.7),
                        ]),
                        center: .zero, startRadius: 0, endRadius: 1))
            }

            // The 115 degree band, transparent / white 35% / transparent at 38 / 48 / 58%.
            do {
                var band = context
                band.clip(to: shape)
                let angle = 115.0 * .pi / 180
                let direction = CGPoint(x: sin(angle), y: -cos(angle))
                let length = abs(w * direction.x) + abs(h * direction.y)
                let centre = CGPoint(x: w / 2, y: h / 2)
                band.fill(
                    Path(bounds),
                    with: .linearGradient(
                        Gradient(stops: [
                            .init(color: .white.opacity(0), location: 0.38),
                            .init(color: .white.opacity(bandAlpha), location: 0.48),
                            .init(color: .white.opacity(0), location: 0.58),
                        ]),
                        startPoint: CGPoint(x: centre.x - direction.x * length / 2, y: centre.y - direction.y * length / 2),
                        endPoint: CGPoint(x: centre.x + direction.x * length / 2, y: centre.y + direction.y * length / 2)))
            }

            guard chrome else { return }
            // inset 0 0 0 1px mat
            do {
                var mat = context
                mat.clip(to: shape)
                mat.stroke(shape, with: .color(.mat), lineWidth: 2)
            }
            // inset 1px 1px 0 rim: the lit edge, top left
            insetShadow(context, shape: shape, bounds: bounds, offset: CGSize(width: 1, height: 1), blur: 0, color: .rim)
            // inset -1px -2px 2px shadow-ink 25%: the occlusion, bottom right
            insetShadow(context, shape: shape, bounds: bounds, offset: CGSize(width: -1, height: -2), blur: 1, color: Color.shadowInk.opacity(0.25))
        }
    }

    /// CSS `inset` box-shadow: the part of the shape not covered by the shape moved by `offset`.
    private func insetShadow(
        _ context: GraphicsContext, shape: Path, bounds: CGRect, offset: CGSize, blur: CGFloat, color: Color
    ) {
        var layerContext = context
        layerContext.clip(to: shape)
        var ring = Path(bounds.insetBy(dx: -20, dy: -20))
        ring.addPath(shape.offsetBy(dx: offset.width, dy: offset.height))
        layerContext.drawLayer { layer in
            if blur > 0 { layer.addFilter(.blur(radius: blur)) }
            layer.fill(ring, with: .color(color), style: FillStyle(eoFill: true))
        }
    }
}
