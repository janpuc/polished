/// A bottle of a shade (docs/NATIVE.md 3, "Shared shapes"). Dates are `YYYY-MM-DD`, timestamps
/// UTC.
public struct Bottle: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var shadeId: Int
    public var state: BottleState
    public var printedCode: String?
    public var boughtOn: String?
    public var pricePaidCents: Int?
    public var openedOn: String?
    public var notes: String?
    public var archived: Bool
    public var createdAt: String
    public var updatedAt: String

    public init(
        id: Int, shadeId: Int, state: BottleState = .full, printedCode: String? = nil, boughtOn: String? = nil,
        pricePaidCents: Int? = nil, openedOn: String? = nil, notes: String? = nil, archived: Bool = false,
        createdAt: String = "", updatedAt: String = ""
    ) {
        self.id = id
        self.shadeId = shadeId
        self.state = state
        self.printedCode = printedCode
        self.boughtOn = boughtOn
        self.pricePaidCents = pricePaidCents
        self.openedOn = openedOn
        self.notes = notes
        self.archived = archived
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }
}

public struct BottleGroup: Codable, Sendable, Hashable, Identifiable {
    public var shade: ShadeRow
    public var bottles: [Bottle]

    public var id: Int { shade.id }
}

/// `GET /bottles`.
public struct BottleGroups: Codable, Sendable, Hashable {
    public var groups: [BottleGroup]
}

public struct HistoryRow: Codable, Sendable, Hashable, Identifiable {
    public var bottle: Bottle
    public var shade: ShadeRow
    /// The date is the one the person entered, not the day the row was created.
    public var datedByEntry: Bool

    public var id: Int { bottle.id }
}

public struct HistoryMonth: Codable, Sendable, Hashable, Identifiable {
    public var month: Int
    public var label: String
    public var count: Int
    public var totalCents: Int
    public var unpriced: Int
    public var rows: [HistoryRow]

    public var id: Int { month }
}

public struct HistoryYear: Codable, Sendable, Hashable, Identifiable {
    public var year: Int
    public var count: Int
    public var totalCents: Int
    public var unpriced: Int
    public var months: [HistoryMonth]

    public var id: Int { year }
}

/// `GET /bottles/history`.
public struct History: Codable, Sendable, Hashable {
    public var years: [HistoryYear]
}
