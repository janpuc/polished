import NailTips

/// The tip recipe the API carries inline on every shade and layer (docs/NATIVE.md 3, "Shared
/// shapes"); `id` is the shade id, which seeds the tip's random generator.
public struct Tip: Codable, Sendable, Hashable {
    public var id: Int
    public var hex: String
    public var hex2: String?
    public var finishes: [String]
    public var topper: Bool
    public var clear: Bool
    public var coats: Int
    public var colours: [String]?
    public var revision: String

    public init(
        id: Int, hex: String, hex2: String? = nil, finishes: [String] = [], topper: Bool = false,
        clear: Bool = false, coats: Int = 1, colours: [String]? = nil, revision: String = ""
    ) {
        self.id = id
        self.hex = hex
        self.hex2 = hex2
        self.finishes = finishes
        self.topper = topper
        self.clear = clear
        self.coats = coats
        self.colours = colours
        self.revision = revision
    }

    public var shade: TipShade {
        TipShade(
            id: id, hex: hex, hex2: hex2, finishes: Set(finishes), topper: topper, clear: clear,
            coats: coats, colours: colours.map(Set.init))
    }
}

extension TipRecipe {
    /// The recipe of a stack: the layers' tips in order.
    public init(tips: [Tip]) {
        self.init(tips.map(\.shade))
    }
}
