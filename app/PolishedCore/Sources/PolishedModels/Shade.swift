/// A shade's availability in the shop; `nil` on a `ShadeRow` for manual shades.
public struct Status: Codable, Sendable, Hashable {
    public var key: String
    public var label: String
    public var buyable: Bool
}

/// The row of a shade list (docs/NATIVE.md 3). A skeleton: run 2 decodes every fixture into it.
public struct ShadeRow: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var title: String
    public var kind: String
    public var source: String
    public var isTopper: Bool
    public var priceCents: Int?
    public var compareAtCents: Int?
    public var status: Status?
    public var finishes: [String]
    public var ownedCount: Int
    public var wishlisted: Bool
    public var heroImageURL: String?
    public var releasedOn: String?
    public var officialCollection: String?
    public var marks: [[Int]]
    public var tip: Tip

    private enum CodingKeys: String, CodingKey {
        case id, title, kind, source, status, finishes, wishlisted, marks, tip
        case isTopper = "is_topper"
        case priceCents = "price_cents"
        case compareAtCents = "compare_at_cents"
        case ownedCount = "owned_count"
        case heroImageURL = "hero_image_url"
        case releasedOn = "released_on"
        case officialCollection = "official_collection"
    }
}
