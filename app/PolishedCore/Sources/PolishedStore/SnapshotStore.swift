import Foundation
import PolishedAPI
import SwiftData

/// One cached response per resource key (docs/NATIVE.md 2.3).
@Model
final class SnapshotRecord {
    @Attribute(.unique) var key: String
    var etag: String?
    var body: Data
    var fetchedAt: Date

    init(key: String, etag: String?, body: Data, fetchedAt: Date) {
        self.key = key
        self.etag = etag
        self.body = body
        self.fetchedAt = fetchedAt
    }
}

/// The snapshot cache: every screen renders what is here first and revalidates after (instant
/// launch, reading offline). A SwiftData store of key, ETag, body and fetch time; the oldest
/// snapshots go when there are more than `limit`, which keeps a long run of searches from
/// growing it.
@ModelActor
public actor SnapshotStore: ResponseCache {
    private static let limit = 300

    /// `inMemory` for UI tests and previews: nothing outlives the process.
    public static func make(inMemory: Bool = false) throws -> SnapshotStore {
        let configuration = ModelConfiguration(isStoredInMemoryOnly: inMemory)
        let container = try ModelContainer(for: SnapshotRecord.self, configurations: configuration)
        return SnapshotStore(modelContainer: container)
    }

    public func entry(for key: String) -> CachedResponse? {
        guard let record = record(for: key) else { return nil }
        return CachedResponse(key: record.key, etag: record.etag, body: record.body, fetchedAt: record.fetchedAt)
    }

    public func save(_ entry: CachedResponse) {
        if let record = record(for: entry.key) {
            record.etag = entry.etag
            record.body = entry.body
            record.fetchedAt = entry.fetchedAt
        } else {
            modelContext.insert(
                SnapshotRecord(key: entry.key, etag: entry.etag, body: entry.body, fetchedAt: entry.fetchedAt))
        }
        prune()
        try? modelContext.save()
    }

    public func invalidate(prefixes: [String]) {
        let records = (try? modelContext.fetch(FetchDescriptor<SnapshotRecord>())) ?? []
        for record in records where prefixes.contains(where: { record.key.hasPrefix($0) }) {
            modelContext.delete(record)
        }
        try? modelContext.save()
    }

    public func clear() {
        try? modelContext.delete(model: SnapshotRecord.self)
        try? modelContext.save()
    }

    public func count() -> Int {
        (try? modelContext.fetchCount(FetchDescriptor<SnapshotRecord>())) ?? 0
    }

    private func record(for key: String) -> SnapshotRecord? {
        var descriptor = FetchDescriptor<SnapshotRecord>(predicate: #Predicate { $0.key == key })
        descriptor.fetchLimit = 1
        return try? modelContext.fetch(descriptor).first
    }

    private func prune() {
        guard let total = try? modelContext.fetchCount(FetchDescriptor<SnapshotRecord>()), total > Self.limit else {
            return
        }
        var oldest = FetchDescriptor<SnapshotRecord>(sortBy: [SortDescriptor(\.fetchedAt)])
        oldest.fetchLimit = total - Self.limit + 30
        for record in (try? modelContext.fetch(oldest)) ?? [] { modelContext.delete(record) }
    }
}
