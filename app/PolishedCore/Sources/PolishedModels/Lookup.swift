/// A shade found by a scan or a typed code: the row plus its photos.
public struct LookupShade: Codable, Sendable, Hashable, Identifiable {
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
    public var heroImageUrl: String?
    public var releasedOn: String?
    public var officialCollection: String?
    public var marks: [[Int]]
    public var tip: Tip
    public var images: [String]
}

public struct LookupResults: Codable, Sendable, Hashable {
    public var items: [ShadeRow]
    public var total: Int
}

/// `GET /lookup`. `outcome` is one of match, suggestion, unknown_code, unknown_printed,
/// invalid_code, results.
public struct Lookup: Codable, Sendable, Hashable {
    public var outcome: String
    public var code: String?
    /// "gtin", "printed" or "sku".
    public var kind: String?
    public var shade: LookupShade?
    public var identifierId: Int?
    public var results: LookupResults?
}

public struct Identifier: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var kind: String
    public var value: String
    public var shade: ShadeRow
    public var useCount: Int
    public var createdAt: String
    public var lastUsedAt: String?
}

/// `GET /identifiers`: the learned codes.
public struct LearnedCodes: Codable, Sendable, Hashable {
    public var items: [Identifier]
}

extension LookupShade {
    /// The same shade as a list row (the learn answer carries a row, not the photos).
    public var row: ShadeRow {
        ShadeRow(
            id: id, title: title, kind: kind, source: source, isTopper: isTopper, priceCents: priceCents,
            compareAtCents: compareAtCents, status: status, finishes: finishes, ownedCount: ownedCount,
            wishlisted: wishlisted, heroImageUrl: heroImageUrl, releasedOn: releasedOn,
            officialCollection: officialCollection, marks: marks, tip: tip)
    }
}
