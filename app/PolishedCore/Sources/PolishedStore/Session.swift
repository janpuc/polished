import Foundation
import Observation
import Security
import Synchronization

/// Where the device token lives between launches.
public protocol TokenStore: Sendable {
    func read() -> String?
    func write(_ token: String) throws
    func delete()
}

/// The token in the Keychain: a generic password, readable after the first unlock and never
/// moved to another device or a backup (docs/NATIVE.md 2.4).
public struct KeychainTokenStore: TokenStore {
    public struct Failure: Error, Equatable {
        public var status: OSStatus
    }

    private let service: String
    private let account: String

    public init(service: String = "com.janpuc.polished", account: String = "api-token") {
        self.service = service
        self.account = account
    }

    private var match: [String: Any] {
        [kSecClass as String: kSecClassGenericPassword, kSecAttrService as String: service, kSecAttrAccount as String: account]
    }

    public func read() -> String? {
        var query = match
        query[kSecReturnData as String] = true
        query[kSecMatchLimit as String] = kSecMatchLimitOne
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess, let data = item as? Data else { return nil }
        return String(data: data, encoding: .utf8)
    }

    public func write(_ token: String) throws {
        delete()
        var attributes = match
        attributes[kSecValueData as String] = Data(token.utf8)
        attributes[kSecAttrAccessible as String] = kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly
        let status = SecItemAdd(attributes as CFDictionary, nil)
        guard status == errSecSuccess else { throw Failure(status: status) }
    }

    public func delete() {
        SecItemDelete(match as CFDictionary)
    }
}

/// A token held in memory, for tests and for the debug launch argument `-token`.
public final class MemoryTokenStore: TokenStore {
    private let token: Mutex<String?>

    public init(_ token: String? = nil) {
        self.token = Mutex(token)
    }

    public func read() -> String? { token.withLock { $0 } }
    public func write(_ value: String) throws { token.withLock { $0 = value } }
    public func delete() { token.withLock { $0 = nil } }
}

/// Signed in or not. The token is read from any thread (`LiveAPI` asks for it on every call); the
/// state the screens observe changes on the main actor only. A 401 anywhere ends in `signOut`.
@MainActor
@Observable
public final class Session {
    public private(set) var isSignedIn: Bool
    /// Why the sign-in screen is showing, when it is not the first run: "Signed out", or the
    /// error of the last attempt.
    public var notice: String?

    @ObservationIgnored private let store: any TokenStore
    @ObservationIgnored private let live: Mutex<String?>

    public init(store: any TokenStore) {
        self.store = store
        let token = store.read()
        live = Mutex(token)
        isSignedIn = token != nil
    }

    /// The bearer token, from any thread.
    public nonisolated var token: String? { live.withLock { $0 } }

    public func signIn(token: String) throws {
        try store.write(token)
        live.withLock { $0 = token }
        notice = nil
        isSignedIn = true
    }

    public func signOut(notice: String? = nil) {
        store.delete()
        live.withLock { $0 = nil }
        self.notice = notice
        isSignedIn = false
    }
}
