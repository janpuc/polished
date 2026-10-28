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

    public init(id: Int, ord: Int, shadeId: Int, title: String, coats: Int, label: String, tip: Tip) {
        self.id = id
        self.ord = ord
        self.shadeId = shadeId
        self.title = title
        self.coats = coats
        self.label = label
        self.tip = tip
    }
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

    public init(
        position: Int, filled: Bool, hasDraft: Bool = false, stackId: Int? = nil, draftStackId: Int? = nil,
        summary: String = "", layers: [Layer] = [], paintedOn: String? = nil, note: String? = nil
    ) {
        self.position = position
        self.filled = filled
        self.hasDraft = hasDraft
        self.stackId = stackId
        self.draftStackId = draftStackId
        self.summary = summary
        self.layers = layers
        self.paintedOn = paintedOn
        self.note = note
    }

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

    public init(id: Int, slug: String, name: String) {
        self.id = id
        self.slug = slug
        self.name = name
    }
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
    /// Only on the answer of opening a slot's draft: the draft was already there.
    public var resumed: Bool?
    /// Only on the answer of a template: `added`, `already`, `unavailable`, `copied` or `nothing_saved`.
    public var result: String?

    public init(
        stackId: Int, wheel: StackWheel, position: Int, name: String? = nil, note: String? = nil,
        paintedOn: String? = nil, layers: [Layer], summary: String, full: Bool, tip: [Tip],
        resumed: Bool? = nil, result: String? = nil
    ) {
        self.stackId = stackId
        self.wheel = wheel
        self.position = position
        self.name = name
        self.note = note
        self.paintedOn = paintedOn
        self.layers = layers
        self.summary = summary
        self.full = full
        self.tip = tip
        self.resumed = resumed
        self.result = result
    }
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
}
