import Foundation
import PolishedModels

/// One GET of the contract: its path and query, and what it decodes to. `key` is the path with
/// the query, which keys the response cache.
public struct Endpoint<Value: Decodable & Sendable>: Sendable {
    public var path: String
    public var query: [URLQueryItem]

    public init(_ path: String, query: [URLQueryItem] = []) {
        self.path = path
        self.query = query
    }

    public var key: String {
        guard !query.isEmpty else { return path }
        var components = URLComponents()
        components.queryItems = query
        return path + "?" + (components.percentEncodedQuery ?? "")
    }
}

/// The parameters of `GET /shades`. A parameter left at its default is not sent, so the same
/// search always has the same cache key.
public struct ShadeQuery: Sendable, Hashable {
    public var q = ""
    public var finish: [String] = []
    public var color: [String] = []
    public var collection = ""
    public var kind = ""
    public var status = ""
    public var sort = "name"
    public var owned = ""
    public var page = 1

    public init() {}

    /// How many filters are on (the badge on the filter button); the query and the sort are not
    /// filters.
    public var filterCount: Int {
        finish.count + color.count + (collection.isEmpty ? 0 : 1) + (kind.isEmpty ? 0 : 1)
            + (status.isEmpty ? 0 : 1) + (owned.isEmpty || owned == "any" ? 0 : 1)
    }

    public var hasWords: Bool { !q.trimmingCharacters(in: .whitespaces).isEmpty }

    public var queryItems: [URLQueryItem] {
        var items: [URLQueryItem] = []
        let words = q.trimmingCharacters(in: .whitespaces)
        if !words.isEmpty { items.append(URLQueryItem(name: "q", value: words)) }
        items += finish.sorted().map { URLQueryItem(name: "finish", value: $0) }
        items += color.sorted().map { URLQueryItem(name: "color", value: $0) }
        if !collection.isEmpty { items.append(URLQueryItem(name: "collection", value: collection)) }
        if !kind.isEmpty { items.append(URLQueryItem(name: "kind", value: kind)) }
        if !status.isEmpty { items.append(URLQueryItem(name: "status", value: status)) }
        if sort != "name" { items.append(URLQueryItem(name: "sort", value: sort)) }
        if !owned.isEmpty { items.append(URLQueryItem(name: "owned", value: owned)) }
        if page > 1 { items.append(URLQueryItem(name: "page", value: String(page))) }
        return items
    }
}

/// Every GET endpoint, so a screen, the cache and the fixtures name a resource the same way.
extension Endpoint {
    public static func me() -> Endpoint<Me> { Endpoint<Me>("/api/v1/me") }
    public static func devices() -> Endpoint<Devices> { Endpoint<Devices>("/api/v1/auth/devices") }

    public static func home(another: Bool = false) -> Endpoint<Home> {
        Endpoint<Home>("/api/v1/home", query: another ? [URLQueryItem(name: "another", value: "1")] : [])
    }

    public static func shades(_ query: ShadeQuery) -> Endpoint<ShadePage> {
        Endpoint<ShadePage>("/api/v1/shades", query: query.queryItems)
    }

    public static func facets() -> Endpoint<Facets> { Endpoint<Facets>("/api/v1/shades/facets") }
    public static func shade(id: Int) -> Endpoint<ShadeDetail> { Endpoint<ShadeDetail>("/api/v1/shades/\(id)") }

    public static func bottles(state: String? = nil, archived: Bool = false) -> Endpoint<BottleGroups> {
        var items: [URLQueryItem] = []
        if let state { items.append(URLQueryItem(name: "state", value: state)) }
        if archived { items.append(URLQueryItem(name: "archived", value: "true")) }
        return Endpoint<BottleGroups>("/api/v1/bottles", query: items)
    }

    public static func history() -> Endpoint<History> { Endpoint<History>("/api/v1/bottles/history") }

    public static func wishlist(maxPriority: Int? = nil) -> Endpoint<Wishlist> {
        Endpoint<Wishlist>(
            "/api/v1/wishlist",
            query: maxPriority.map { [URLQueryItem(name: "max_priority", value: String($0))] } ?? [])
    }

    public static func wheels(archived: Bool = false) -> Endpoint<Wheels> {
        Endpoint<Wheels>("/api/v1/wheels", query: archived ? [URLQueryItem(name: "archived", value: "true")] : [])
    }

    public static func wheel(id: Int) -> Endpoint<WheelDetail> { Endpoint<WheelDetail>("/api/v1/wheels/\(id)") }
    public static func wheel(slug: String) -> Endpoint<WheelDetail> { Endpoint<WheelDetail>("/api/v1/w/\(slug)") }
    public static func stack(id: Int) -> Endpoint<StackSheet> { Endpoint<StackSheet>("/api/v1/stacks/\(id)") }

    public static func copySources(q: String = "") -> Endpoint<CopySources> {
        Endpoint<CopySources>("/api/v1/stacks/copy-sources", query: q.isEmpty ? [] : [URLQueryItem(name: "q", value: q)])
    }

    public static func pick(q: String = "", scope: String? = nil) -> Endpoint<Pick> {
        var items: [URLQueryItem] = []
        if !q.isEmpty { items.append(URLQueryItem(name: "q", value: q)) }
        if let scope { items.append(URLQueryItem(name: "scope", value: scope)) }
        return Endpoint<Pick>("/api/v1/stacks/pick", query: items)
    }

    public static func lookup(q: String, via: String? = nil) -> Endpoint<Lookup> {
        var items = [URLQueryItem(name: "q", value: q)]
        if let via { items.append(URLQueryItem(name: "via", value: via)) }
        return Endpoint<Lookup>("/api/v1/lookup", query: items)
    }

    public static func identifiers() -> Endpoint<LearnedCodes> { Endpoint<LearnedCodes>("/api/v1/identifiers") }
    public static func sync() -> Endpoint<SyncStatus> { Endpoint<SyncStatus>("/api/v1/sync") }
}
