public struct WishlistItem: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var shade: ShadeRow
    /// 1 (want most) to 3.
    public var priority: Int
    public var note: String?
    public var addedOn: String
    public var buyable: Bool
}

public struct WishlistSummary: Codable, Sendable, Hashable {
    public var count: Int
    public var totalCents: Int
    public var buyableCount: Int
    public var buyableCents: Int
}

/// The Holo Taco checkout link for what is in stock.
public struct Cart: Codable, Sendable, Hashable {
    public var url: String?
    public var totalCents: Int
    public var count: Int
    public var skipped: Int
    public var names: [String]
}

/// `GET /wishlist`.
public struct Wishlist: Codable, Sendable, Hashable {
    public var items: [WishlistItem]
    public var summary: WishlistSummary
    public var cart: Cart
}
