import Foundation

/// A field of a PATCH body: left out (the server keeps the value), cleared (`null`) or set. The
/// contract's PATCH routes change only the keys they are sent (docs/NATIVE.md 3, "Writes").
public enum Patch<Value: Sendable & Hashable>: Sendable, Hashable {
    case keep
    case clear
    case set(Value)

    /// `value` set, or cleared when it is nil.
    public init(_ value: Value?) {
        self = value.map { .set($0) } ?? .clear
    }
}

extension KeyedEncodingContainer {
    fileprivate mutating func encode<Value: Encodable & Sendable & Hashable>(
        _ patch: Patch<Value>, forKey key: Key
    ) throws {
        switch patch {
        case .keep: break
        case .clear: try encodeNil(forKey: key)
        case .set(let value): try encode(value, forKey: key)
        }
    }
}

// MARK: Bottles

/// `POST /shades/{id}/bottles`. Every field is optional; the level defaults to full on the server.
public struct BottleRequest: Encodable, Sendable, Hashable {
    public var state: BottleState
    public var boughtOn: String?
    public var pricePaidCents: Int?
    public var openedOn: String?
    public var notes: String?

    public init(
        state: BottleState = .full, boughtOn: String? = nil,
        pricePaidCents: Int? = nil, openedOn: String? = nil, notes: String? = nil
    ) {
        self.state = state
        self.boughtOn = boughtOn
        self.pricePaidCents = pricePaidCents
        self.openedOn = openedOn
        self.notes = notes
    }
}

/// `PATCH /bottles/{id}`: any subset of the bottle's fields, `archived` included.
public struct BottlePatch: Encodable, Sendable, Hashable {
    public var state: Patch<BottleState> = .keep
    public var boughtOn: Patch<String> = .keep
    public var pricePaidCents: Patch<Int> = .keep
    public var openedOn: Patch<String> = .keep
    public var notes: Patch<String> = .keep
    public var archived: Patch<Bool> = .keep

    public init() {}

    private enum CodingKeys: String, CodingKey {
        case state, boughtOn, pricePaidCents, openedOn, notes, archived
    }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(state, forKey: .state)
        try container.encode(boughtOn, forKey: .boughtOn)
        try container.encode(pricePaidCents, forKey: .pricePaidCents)
        try container.encode(openedOn, forKey: .openedOn)
        try container.encode(notes, forKey: .notes)
        try container.encode(archived, forKey: .archived)
    }
}

/// `POST /shades/{id}/bottles` (201).
public struct BottleCreated: Codable, Sendable, Hashable {
    public var bottle: Bottle
}

// MARK: Wishlist

/// `PUT /shades/{id}/wishlist`: the priority of a new item (an existing item is kept as it is).
public struct WishlistAdd: Encodable, Sendable, Hashable {
    public var priority: Int

    public init(priority: Int = 2) {
        self.priority = priority
    }
}

/// `PATCH /wishlist/{item_id}`.
public struct WishlistPatch: Encodable, Sendable, Hashable {
    public var priority: Patch<Int> = .keep
    public var note: Patch<String> = .keep

    public init(priority: Patch<Int> = .keep, note: Patch<String> = .keep) {
        self.priority = priority
        self.note = note
    }

    private enum CodingKeys: String, CodingKey { case priority, note }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(priority, forKey: .priority)
        try container.encode(note, forKey: .note)
    }
}

public struct BoughtItem: Encodable, Sendable, Hashable {
    public var id: Int
    /// Always sent, `null` when no price was paid.
    public var priceCents: Int?

    public init(id: Int, priceCents: Int?) {
        self.id = id
        self.priceCents = priceCents
    }

    private enum CodingKeys: String, CodingKey { case id, priceCents }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(id, forKey: .id)
        try container.encode(priceCents, forKey: .priceCents)
    }
}

/// `POST /wishlist/bought`: one full bottle per item, on one date.
public struct BoughtRequest: Encodable, Sendable, Hashable {
    public var items: [BoughtItem]
    public var boughtOn: String?

    public init(items: [BoughtItem], boughtOn: String? = nil) {
        self.items = items
        self.boughtOn = boughtOn
    }
}

/// `POST /wishlist/bought`: the new bottles and what is left of the wishlist.
public struct Bought: Codable, Sendable, Hashable {
    public var bottles: [Bottle]
    public var wishlist: Wishlist
}

// MARK: Shades

/// `POST /shades`: a shade entered by hand ("polish", "topper" or "base").
public struct ManualShadeRequest: Encodable, Sendable, Hashable {
    public var title: String
    public var kind: String

    public init(title: String, kind: String) {
        self.title = title
        self.kind = kind
    }
}

/// `PUT /shades/{id}/tip-colour`: `#rrggbb`, or nil (sent as `null`) to go back to the sampled colour.
public struct TipColourRequest: Encodable, Sendable, Hashable {
    public var hex: String?

    public init(hex: String?) {
        self.hex = hex
    }

    private enum CodingKeys: String, CodingKey { case hex }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(hex, forKey: .hex)
    }
}

/// `POST /wear/{shade_id}`.
public struct WearRecorded: Codable, Sendable, Hashable {
    public var wornOn: String

    public init(wornOn: String) {
        self.wornOn = wornOn
    }
}

// MARK: Wheels

/// `POST /wheels`: a name (cut to 60 characters) and 1 to 40 slots.
public struct WheelRequest: Encodable, Sendable, Hashable {
    public var name: String
    public var slotCount: Int

    public init(name: String, slotCount: Int = 20) {
        self.name = name
        self.slotCount = slotCount
    }
}

/// `PATCH /wheels/{id}`: `name` and/or `archived`.
public struct WheelPatch: Encodable, Sendable, Hashable {
    public var name: Patch<String> = .keep
    public var archived: Patch<Bool> = .keep

    public init(name: Patch<String> = .keep, archived: Patch<Bool> = .keep) {
        self.name = name
        self.archived = archived
    }

    private enum CodingKeys: String, CodingKey { case name, archived }

    public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(name, forKey: .name)
        try container.encode(archived, forKey: .archived)
    }
}

/// `POST /wheels/{id}/slug/take`.
public struct TakeTagRequest: Encodable, Sendable, Hashable {
    public var fromWheelId: Int

    public init(fromWheelId: Int) {
        self.fromWheelId = fromWheelId
    }
}

/// `DELETE /wheels/{id}`.
public struct WheelDeleted: Codable, Sendable, Hashable {
    public var deletedSwatches: Int
}

// MARK: Sync

/// `POST /sync/run` (202): the run goes on in the background; `GET /sync` says when it ends.
public struct SyncStarted: Codable, Sendable, Hashable {
    public var runId: Int
}

/// The body of a 204.
public struct NoContent: Codable, Sendable, Hashable {
    public init() {}
}

// MARK: Stacks (the builder)

/// `POST /stacks/{id}/layers`.
public struct LayerRequest: Encodable, Sendable, Hashable {
    public var shadeId: Int

    public init(shadeId: Int) {
        self.shadeId = shadeId
    }
}

/// `PATCH /stacks/{id}/layers/{layer_id}`: exactly one of a coat more or less, or a move.
public struct LayerPatch: Encodable, Sendable, Hashable {
    public var coatsDelta: Int?
    /// "up" is towards the base.
    public var move: String?

    public init(coatsDelta: Int? = nil, move: String? = nil) {
        self.coatsDelta = coatsDelta
        self.move = move
    }
}

/// `POST /stacks/{id}/template`.
public struct TemplateRequest: Encodable, Sendable, Hashable {
    /// "over_black", "copy" or "last".
    public var kind: String
    public var sourceStackId: Int?

    public init(kind: String, sourceStackId: Int? = nil) {
        self.kind = kind
        self.sourceStackId = sourceStackId
    }
}

/// `POST /stacks/{id}/save`: an empty name or note is sent as an empty string; the date is the
/// day the swatch was painted (the server defaults to today).
public struct SaveStackRequest: Encodable, Sendable, Hashable {
    public var name: String
    public var note: String
    public var paintedOn: String?

    public init(name: String, note: String, paintedOn: String?) {
        self.name = name
        self.note = note
        self.paintedOn = paintedOn
    }
}

/// `POST /stacks/{id}/save` and `/cancel`: the slot as it is now.
public struct SlotResult: Codable, Sendable, Hashable {
    public var wheelId: Int
    public var position: Int
    public var tile: Tile
}

// MARK: Identifiers

/// `POST /identifiers`: teach the server that a barcode is a shade. `kind` is "gtin" (the 13-digit
/// form).
public struct LearnRequest: Encodable, Sendable, Hashable {
    public var kind: String
    public var value: String
    public var shadeId: Int

    public init(kind: String, value: String, shadeId: Int) {
        self.kind = kind
        self.value = value
        self.shadeId = shadeId
    }
}

public struct LearnedIdentifier: Codable, Sendable, Hashable, Identifiable {
    public var id: Int
    public var kind: String
    public var value: String
    public var shadeId: Int
}

/// The answer to `POST /identifiers`: 201 and `created` when the code was new, 200 when it was
/// known (it keeps its shade, `shade` is that one).
public struct IdentifierSaved: Codable, Sendable, Hashable {
    public var identifier: LearnedIdentifier
    public var created: Bool
    public var shade: ShadeRow
}
