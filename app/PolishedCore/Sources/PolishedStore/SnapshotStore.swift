import Foundation

/// A cached response (docs/NATIVE.md 2.3): the body of one resource with its ETag. Run 2
/// replaces the storage with SwiftData; the shape stays.
public struct Snapshot: Sendable, Equatable {
    public var key: String
    public var etag: String?
    public var json: Data
    public var fetchedAt: Date

    public init(key: String, etag: String?, json: Data, fetchedAt: Date) {
        self.key = key
        self.etag = etag
        self.json = json
        self.fetchedAt = fetchedAt
    }
}

/// The snapshot cache, in memory for now.
public actor SnapshotStore {
    private var snapshots: [String: Snapshot] = [:]

    public init() {}

    public func snapshot(for key: String) -> Snapshot? {
        snapshots[key]
    }

    public func save(_ snapshot: Snapshot) {
        snapshots[snapshot.key] = snapshot
    }
}
