import Foundation
import Observation
import PolishedAPI
import PolishedModels
import PolishedStore
import UIKit

/// The app's one model: the session, the API with its snapshot cache, and the router. Screens
/// get it from the environment.
@MainActor
@Observable
final class AppModel {
    let session: Session
    let serverURL: URL
    let api: any PolishedAPI
    let router = Router()
    let launch: LaunchOptions
    /// For Settings: whether the token is the launch argument's, which has nothing to revoke.
    let usesDevToken: Bool

    @ObservationIgnored private let cache: SnapshotStore?

    static var version: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "0"
    }

    static var build: String {
        Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "0"
    }

    init(launch: LaunchOptions = .current) {
        self.launch = launch
        serverURL = launch.server
        usesDevToken = launch.devToken != nil
        let tokenStore: any TokenStore = launch.devToken.map { MemoryTokenStore($0) } ?? KeychainTokenStore()
        let session = Session(store: tokenStore)
        self.session = session
        let cache = (try? SnapshotStore.make(inMemory: launch.inMemoryCache)) ?? (try? SnapshotStore.make(inMemory: true))
        self.cache = cache
        api = LiveAPI(
            baseURL: launch.server,
            appVersion: Self.version,
            token: { session.token },
            cache: cache,
            onUnauthorized: { [weak session] in
                Task { @MainActor in
                    guard let session, session.isSignedIn else { return }
                    session.signOut(notice: "You were signed out. Sign in again.")
                    await cache?.clear()
                }
            })
        if launch.forceSignedOut { session.signOut() }
        if let tab = launch.tab { router.tab = tab }
        router.focusSearch = launch.focusSearch
    }

    /// The device name the server lists under Devices.
    static var deviceName: String {
        UIDevice.current.name
    }

    func finishSignIn(_ response: ExchangeResponse) async throws {
        await cache?.clear()
        try session.signIn(token: response.token)
        router.openPending()
    }

    /// Sign out: the server forgets this device's token, then this device its copy and its
    /// snapshots. An offline revoke still signs out here; the web's Devices list can finish it.
    func signOut() async {
        if !usesDevToken { try? await api.revoke() }
        await cache?.clear()
        session.signOut()
    }
}

