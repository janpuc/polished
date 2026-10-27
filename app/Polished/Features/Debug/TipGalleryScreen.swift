#if DEBUG
import NailTips
import PolishedModels
import SwiftUI

extension SampleShade {
    /// The shade as the API would send it, for the gallery's hero.
    var row: ShadeRow {
        ShadeRow(
            id: id, title: name, finishes: tip.finishes.sorted(), ownedCount: 1,
            tip: Tip(id: id, hex: tip.hex, hex2: tip.hex2, finishes: tip.finishes.sorted()))
    }
}

/// A case of `spec/tips/cases.json`; the build copies the file into the app as `TipCases.json`
/// (Debug only), so the gallery shows exactly the recipes the parity tests pin.
struct GalleryCase: Identifiable, Decodable {
    var name: String
    var layers: [TipShade]
    var id: String { name }

    var recipe: TipRecipe { TipRecipe(layers) }
}

private struct GalleryFile: Decodable {
    var cases: [GalleryCase]
}

enum GalleryFixtures {
    static func load() -> [GalleryCase] {
        guard let url = Bundle.main.url(forResource: "TipCases", withExtension: "json"),
            let data = try? Data(contentsOf: url),
            let file = try? JSONDecoder().decode(GalleryFile.self, from: data)
        else { return [] }
        return file.cases
    }
}

/// Every fixture recipe at the four list sizes, on a light board and a dark one, and the Home
/// hero on its plate in each. Opened by the Home toolbar and by `-screen gallery`.
struct TipGalleryScreen: View {
    private let cases = GalleryFixtures.load()

    var body: some View {
        ScrollView {
            LazyVStack(spacing: 0) {
                GalleryBoard(scheme: .light, cases: cases)
                GalleryBoard(scheme: .dark, cases: cases)
                Text("End of the gallery")
                    .font(.footnote)
                    .foregroundStyle(Color.ink3)
                    .padding(24)
                    .accessibilityIdentifier("gallery-end")
            }
        }
        .navigationTitle("Tip gallery")
        .navigationBarTitleDisplayMode(.inline)
    }
}

private struct GalleryBoard: View {
    let scheme: ColorScheme
    let cases: [GalleryCase]

    var body: some View {
        VStack(alignment: .leading, spacing: 28) {
            Text(scheme == .light ? "Light, \(cases.count) tips" : "Dark, \(cases.count) tips")
                .font(.title2.weight(.semibold))
                .foregroundStyle(Color.ink)
                .accessibilityIdentifier("gallery-\(scheme == .light ? "light" : "dark")")
            WearTodayHero(wear: Wear(shade: SampleShade.acidDrip.row, bottle: Bottle(id: 1, shadeId: 31, state: .half, printedCode: "P12"), wornToday: false), wore: {}, another: {})
            ForEach([TipSize.xl, .l, .m, .s], id: \.self) { size in
                GallerySection(size: size, cases: cases)
            }
        }
        .padding(16)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color.board)
        .environment(\.colorScheme, scheme)
    }
}

private struct GallerySection: View {
    let size: TipSize
    let cases: [GalleryCase]
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        let dimensions = size.dimensions(regular: horizontalSizeClass == .regular)
        let cell = max(dimensions.width + 18, 56)
        VStack(alignment: .leading, spacing: 12) {
            Text("\(label) \(Int(dimensions.width)) by \(Int(dimensions.height))")
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Color.ink2)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: cell), spacing: 6, alignment: .top)], spacing: 14) {
                ForEach(Array(cases.enumerated()), id: \.element.id) { index, tipCase in
                    VStack(spacing: 8) {
                        TipView(tipCase.recipe, size: size)
                            .padding(.bottom, 6)
                        Text(size == .xl || size == .l ? tipCase.name : String(index + 1))
                            .font(.system(size: 10))
                            .foregroundStyle(Color.ink2)
                            .lineLimit(2)
                            .multilineTextAlignment(.center)
                    }
                    .frame(maxWidth: .infinity)
                }
            }
        }
    }

    private var label: String {
        switch size {
        case .xl: "tip-xl"
        case .l: "tip-l"
        case .m: "tip-m"
        case .s: "tip-s"
        case .ring: "ring"
        }
    }
}

/// Twelve recipes at tip-xl on fixed coordinates, so a browser page with the same coordinates
/// (the web's tips from the same recipes) lines up with the screenshot for the parity montage.
/// Opened by `-screen parity`.
struct ParityScreen: View {
    static let names = [
        "creme_alone", "jelly_alone", "shimmer_alone", "glitter_alone",
        "flakie_alone", "magnetic_alone", "holographic_alone", "thermal_alone",
        "chrome_alone", "duochrome_alone", "matte_alone", "chrome_and_flakie",
    ]
    static let columns = 4
    static let origin = CGPoint(x: 4, y: 90)
    static let cell = CGSize(width: 96, height: 200)
    static let tip = CGSize(width: 96, height: 158)

    private let cases = GalleryFixtures.load()

    var body: some View {
        ZStack(alignment: .topLeading) {
            Color.board
            ForEach(Array(Self.names.enumerated()), id: \.offset) { index, name in
                if let tipCase = cases.first(where: { $0.name == name }) {
                    let x = Self.origin.x + CGFloat(index % Self.columns) * (Self.cell.width + 2)
                    let y = Self.origin.y + CGFloat(index / Self.columns) * Self.cell.height
                    TipView(tipCase.recipe, size: .xl, painting: .direct)
                        .position(x: x + Self.tip.width / 2, y: y + Self.tip.height / 2)
                }
            }
        }
        .ignoresSafeArea()
        .environment(\.horizontalSizeClass, .compact)
    }
}
#endif
