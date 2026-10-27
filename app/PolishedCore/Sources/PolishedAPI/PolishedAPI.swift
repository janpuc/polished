import Foundation
import PolishedModels

/// The server contract as the app sees it (`spec/api/openapi.yaml`): one async method per GET and
/// the auth calls. The requirements `get` and `cached` carry every GET; the named methods in the
/// extension are the contract's endpoints spelled out, so a screen reads `api.home()` and a test
/// double implements only `get`.
public protocol PolishedAPI: Sendable {
    /// The endpoint's answer, revalidated with the server (a 304 resolves to the cached body).
    func get<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async throws -> Value
    /// The last answer kept for the endpoint, if any; never touches the network.
    func cached<Value: Decodable & Sendable>(_ endpoint: Endpoint<Value>) async -> Value?

    /// `POST /auth/exchange`: public; the code and the verifier are the credential.
    func exchange(_ request: ExchangeRequest) async throws -> ExchangeResponse
    /// `POST /auth/revoke`: signs this device out on the server.
    func revoke() async throws
}

extension PolishedAPI {
    public func me() async throws -> Me { try await get(.me()) }
    public func devices() async throws -> Devices { try await get(.devices()) }
    public func home(another: Bool = false) async throws -> Home { try await get(.home(another: another)) }
    public func shades(_ query: ShadeQuery) async throws -> ShadePage { try await get(.shades(query)) }
    public func facets() async throws -> Facets { try await get(.facets()) }
    public func shade(id: Int) async throws -> ShadeDetail { try await get(.shade(id: id)) }

    public func bottles(state: String? = nil, archived: Bool = false) async throws -> BottleGroups {
        try await get(.bottles(state: state, archived: archived))
    }

    public func history() async throws -> History { try await get(.history()) }

    public func wishlist(maxPriority: Int? = nil) async throws -> Wishlist {
        try await get(.wishlist(maxPriority: maxPriority))
    }

    public func wheels(archived: Bool = false) async throws -> Wheels { try await get(.wheels(archived: archived)) }
    public func wheel(id: Int) async throws -> WheelDetail { try await get(.wheel(id: id)) }
    public func wheel(slug: String) async throws -> WheelDetail { try await get(.wheel(slug: slug)) }
    public func stack(id: Int) async throws -> StackSheet { try await get(.stack(id: id)) }
    public func copySources(q: String = "") async throws -> CopySources { try await get(.copySources(q: q)) }
    public func pick(q: String = "", scope: String? = nil) async throws -> Pick { try await get(.pick(q: q, scope: scope)) }
    public func lookup(q: String, via: String? = nil) async throws -> Lookup { try await get(.lookup(q: q, via: via)) }
    public func identifiers() async throws -> LearnedCodes { try await get(.identifiers()) }
    public func sync() async throws -> SyncStatus { try await get(.sync()) }
}
