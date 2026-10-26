import Foundation

/// One layer of a recipe: a shade as `tips.py` sees it (`TipShade`). Decodes the fixture and the
/// API's tip shape; `finishes` and `colours` are sets, `colours` is nil when the row carried no
/// colour tags.
public struct TipShade: Sendable, Hashable, Codable {
    public var id: Int
    public var hex: String
    public var hex2: String?
    public var finishes: Set<String>
    public var topper: Bool
    public var clear: Bool
    public var coats: Int
    public var colours: Set<String>?

    public init(
        id: Int,
        hex: String,
        hex2: String? = nil,
        finishes: Set<String> = [],
        topper: Bool = false,
        clear: Bool = false,
        coats: Int = 1,
        colours: Set<String>? = nil
    ) {
        self.id = id
        self.hex = hex
        self.hex2 = hex2
        self.finishes = finishes
        self.topper = topper
        self.clear = clear
        self.coats = coats
        self.colours = colours
    }

    /// Colour tags that mean a topper carries no tint of its own.
    static let untintedColours: Set<String> = ["clear", "silver", "neutral", "black", "white", "grey", "gray"]

    /// Whether a topper leaves a hint of its own colour: by the shop's colour tags when the row
    /// has them, else by the saturation of its sampled colour.
    var tinted: Bool {
        if let colours {
            return !colours.subtracting(Self.untintedColours).isEmpty
        }
        return TipColor.saturation(hex) > 0.25
    }

    var seeThrough: Bool { !topper && !finishes.isDisjoint(with: ["jelly"]) }

    var opaque: Bool { !(topper || clear || seeThrough) }
}
