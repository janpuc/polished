/// One layer of a swatch: a shade at a number of coats (`label` is "Base" or "Top" when the stack
/// has more than one layer).
public struct Layer: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var ord: Int
    public var shadeId: Int
    public var title: String
    public var coats: Int
    public var label: String
    public var tip: Tip
}

/// One slot of a wheel.
public struct Tile: Codable, Sendable, Hashable, Identifiable {
    public var position: Int
    public var filled: Bool
    public var hasDraft: Bool
    public var stackId: Int?
    public var draftStackId: Int?
    public var summary: String
    public var layers: [Layer]
    public var paintedOn: String?
    public var note: String?

    public var id: Int { position }

    /// What the slot shows: the layers' tips in order; nil for an empty or draft-only slot.
    public var layerTips: [Tip] { layers.map(\.tip) }
}

public struct Wheel: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var slug: String
    public var name: String
    public var slotCount: Int
    public var archived: Bool
    public var filled: Int
    public var drafts: Int
    public var tagUrl: String
    public var createdAt: String
}

/// A wheel in a list or on Home: the wheel and its tiles (the list draws mini rings).
public struct WheelWithTiles: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var slug: String
    public var name: String
    public var slotCount: Int
    public var archived: Bool
    public var filled: Int
    public var drafts: Int
    public var tagUrl: String
    public var createdAt: String
    public var tiles: [Tile]
}

/// `GET /wheels`.
public struct Wheels: Codable, Sendable, Hashable {
    public var items: [WheelWithTiles]
}

public struct WheelRef: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var name: String
    public var slug: String
}

/// `GET /wheels/{id}` and `GET /w/{slug}`.
public struct WheelDetail: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var slug: String
    public var name: String
    public var slotCount: Int
    public var archived: Bool
    public var filled: Int
    public var drafts: Int
    public var tagUrl: String
    public var createdAt: String
    public var tiles: [Tile]
    public var filledCount: Int
    public var others: [WheelRef]
}

public struct StackWheel: Codable, Sendable, Hashable {
    public var id: Int
    public var slug: String
    public var name: String
}

/// `GET /stacks/{id}`: the swatch being built, or a saved one's layers.
public struct StackSheet: Codable, Sendable, Hashable {
    public var stackId: Int
    public var wheel: StackWheel
    public var position: Int
    public var name: String?
    public var note: String?
    public var paintedOn: String?
    public var layers: [Layer]
    public var summary: String
    public var full: Bool
    public var tip: [Tip]
}

public struct CopySource: Codable, Sendable, Hashable, Identifiable {
    public var stackId: Int
    public var wheelName: String
    public var wheelSlug: String
    public var position: Int
    public var name: String?
    public var paintedOn: String?
    public var summary: String
    public var layers: [Layer]

    public var id: Int { stackId }
}

/// `GET /stacks/copy-sources`.
public struct CopySources: Codable, Sendable, Hashable {
    public var items: [CopySource]
}

/// `GET /stacks/pick`.
public struct Pick: Codable, Sendable, Hashable {
    public var items: [ShadeRow]
    public var total: Int
    public var suggestion: ShadeRow?
}
