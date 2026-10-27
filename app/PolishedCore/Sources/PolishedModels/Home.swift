public struct Wear: Codable, Sendable, Hashable {
    public var shade: ShadeRow
    public var bottle: Bottle
    public var wornToday: Bool

    public init(shade: ShadeRow, bottle: Bottle, wornToday: Bool) {
        self.shade = shade
        self.bottle = bottle
        self.wornToday = wornToday
    }
}

public struct RecentBottle: Codable, Sendable, Hashable, Identifiable {
    public var bottle: Bottle
    public var shade: ShadeRow

    public var id: Int { bottle.id }
}

public struct HomeCounts: Codable, Sendable, Hashable {
    public var bottles: Int
    public var shades: Int
    public var wished: Int
    public var wishedCents: Int
}

/// `GET /home`: the shelf.
public struct Home: Codable, Sendable, Hashable {
    public var greetingName: String
    /// `YYYY-MM-DD` in the household's time zone.
    public var date: String
    public var wear: Wear?
    public var recent: [RecentBottle]
    public var wheel: WheelWithTiles?
    public var counts: HomeCounts
}
