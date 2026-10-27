import Foundation

/// A response kept for a resource key (docs/NATIVE.md 2.3): the body as the server sent it, with
/// its ETag.
public struct CachedResponse: Sendable, Equatable {
    public var key: String
    public var etag: String?
    public var body: Data
    public var fetchedAt: Date

    public init(key: String, etag: String?, body: Data, fetchedAt: Date) {
        self.key = key
        self.etag = etag
        self.body = body
        self.fetchedAt = fetchedAt
    }
}

/// Where `LiveAPI` keeps the last good answer of each GET: its ETag for `If-None-Match`, and the
/// body a 304 resolves to and a screen draws first. `PolishedStore` implements it with SwiftData.
public protocol ResponseCache: Sendable {
    func entry(for key: String) async -> CachedResponse?
    func save(_ entry: CachedResponse) async
    /// Forgets the answers whose key starts with any of `prefixes` (a write changed them).
    func invalidate(prefixes: [String]) async
    /// Forgets everything (sign out).
    func clear() async
}
