import Foundation
import PolishedAPI
import PolishedStore
import Security
import Testing

@Suite("SnapshotStore")
struct SnapshotStoreTests {
    @Test func savesReplacesAndClears() async throws {
        let store = try SnapshotStore.make(inMemory: true)
        #expect(await store.entry(for: "/api/v1/home") == nil)
        let stamp = Date(timeIntervalSince1970: 1_800_000_000)
        await store.save(CachedResponse(key: "/api/v1/home", etag: "\"a\"", body: Data("one".utf8), fetchedAt: stamp))
        await store.save(CachedResponse(key: "/api/v1/home", etag: "\"b\"", body: Data("two".utf8), fetchedAt: stamp))
        let entry = try #require(await store.entry(for: "/api/v1/home"))
        #expect(entry.etag == "\"b\"")
        #expect(entry.body == Data("two".utf8))
        #expect(await store.count() == 1)
        await store.clear()
        #expect(await store.count() == 0)
    }

    @Test func keepsTheNewestWhenFull() async throws {
        let store = try SnapshotStore.make(inMemory: true)
        for index in 0..<330 {
            await store.save(
                CachedResponse(
                    key: "/k/\(index)", etag: nil, body: Data(), fetchedAt: Date(timeIntervalSince1970: Double(index))))
        }
        #expect(await store.count() <= 300)
        #expect(await store.entry(for: "/k/329") != nil)
        #expect(await store.entry(for: "/k/0") == nil)
    }
}

@Suite("Session")
struct SessionTests {
    @Test @MainActor func signInAndOutKeepTheTokenInTheStore() throws {
        let store = MemoryTokenStore()
        let session = Session(store: store)
        #expect(!session.isSignedIn)
        try session.signIn(token: "secret")
        #expect(session.isSignedIn)
        #expect(session.token == "secret")
        #expect(store.read() == "secret")
        #expect(Session(store: store).isSignedIn)
        session.signOut(notice: "Signed out")
        #expect(session.token == nil)
        #expect(store.read() == nil)
        #expect(session.notice == "Signed out")
    }

    @Test func keychainRoundTrip() throws {
        let store = KeychainTokenStore(service: "com.janpuc.polished.tests.\(UUID().uuidString)", account: "t")
        defer { store.delete() }
        #expect(store.read() == nil)
        do {
            try store.write("first")
            try store.write("second")
        } catch let failure as KeychainTokenStore.Failure where failure.status == errSecMissingEntitlement {
            // An unsigned test process (`swift test`, and test.sh builds with CODE_SIGNING_ALLOWED=NO)
            // has no keychain entitlement; the round trip below runs wherever the process is signed.
            return
        }
        #expect(store.read() == "second")
        store.delete()
        #expect(store.read() == nil)
    }
}
