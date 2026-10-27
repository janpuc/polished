/// A shade's availability in the shop; `nil` on a `ShadeRow` for manual shades.
public struct Status: Codable, Sendable, Hashable {
    public var key: String
    public var label: String
    public var buyable: Bool
}

/// The row of a shade list and the shade a bottle, a wishlist item or a lookup carries
/// (docs/NATIVE.md 3). `marks` are Unicode-scalar offsets into `title` (see `Marks`).
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
    public var heroImageUrl: String?
    public var releasedOn: String?
    public var officialCollection: String?
    public var marks: [[Int]]
    public var tip: Tip

    public init(
        id: Int, title: String, kind: String = "polish", source: String = "holotaco", isTopper: Bool = false,
        priceCents: Int? = nil, compareAtCents: Int? = nil, status: Status? = nil, finishes: [String] = [],
        ownedCount: Int = 0, wishlisted: Bool = false, heroImageUrl: String? = nil, releasedOn: String? = nil,
        officialCollection: String? = nil, marks: [[Int]] = [], tip: Tip
    ) {
        self.id = id
        self.title = title
        self.kind = kind
        self.source = source
        self.isTopper = isTopper
        self.priceCents = priceCents
        self.compareAtCents = compareAtCents
        self.status = status
        self.finishes = finishes
        self.ownedCount = ownedCount
        self.wishlisted = wishlisted
        self.heroImageUrl = heroImageUrl
        self.releasedOn = releasedOn
        self.officialCollection = officialCollection
        self.marks = marks
        self.tip = tip
    }
}

/// `GET /shades`: one page of 40.
public struct ShadePage: Codable, Sendable, Hashable {
    public var items: [ShadeRow]
    public var total: Int
    public var page: Int
    public var hasMore: Bool
    /// The words matched loosely (typos, word order): the count line says "closest first".
    public var fuzzy: Bool
}

/// `GET /shades/facets`: the values the filter sheet offers.
public struct Facets: Codable, Sendable, Hashable {
    public var finish: [String]
    public var color: [String]
    public var collection: [String]
    public var official: [String]
}

public struct ShadeTags: Codable, Sendable, Hashable {
    public var finish: [String]
    public var color: [String]
    public var collection: [String]
}

public struct SwatchedOn: Codable, Sendable, Hashable, Identifiable {
    public var wheelId: Int
    public var slug: String
    public var name: String
    public var position: Int
    public var stackId: Int

    public var id: Int { stackId }
}

public struct WishlistEntry: Codable, Sendable, Hashable {
    public var id: Int
    public var priority: Int
    public var note: String?

    public init(id: Int, priority: Int, note: String?) {
        self.id = id
        self.priority = priority
        self.note = note
    }
}

/// `GET /shades/{id}`.
public struct ShadeDetail: Codable, Sendable, Hashable {
    public var shade: ShadeRow
    public var images: [String]
    public var tags: ShadeTags
    public var sku: String?
    public var handle: String?
    public var storeUrl: String?
    public var onSale: Bool
    public var bottles: [Bottle]
    public var wishlist: WishlistEntry?
    public var swatchedOn: [SwatchedOn]
    /// "override", "sampled" or "none": where the tip's colour came from.
    public var tipSource: String
}
