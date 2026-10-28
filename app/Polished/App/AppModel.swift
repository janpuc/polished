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
    /// Every write goes through here (docs/NATIVE.md 2.3).
    let writes: WriteCoordinator
    let launch: LaunchOptions
    /// For Settings: whether the token is the launch argument's, which has nothing to revoke.
    let usesDevToken: Bool

    /// The household's time zone from `/me`, which decides what "today" is for dates the server
    /// checks; the phone's until it arrives.
    private(set) var day = HouseholdDay()
    /// The builder's picker lists from the last time, shown at once (docs/NATIVE.md 8, run 9).
    let pickMemory = PickMemory()
    /// The wheel's layer builder is up beside the ring; a split view gives its sidebar column back.
    var builderIsOpen = false
    /// The NFC stickers (a fake one in a Debug build launched with `-nfc`).
    let stickers: any StickerService
    /// The last bottle added, so its shade's tip can arrive (docs/NATIVE.md 5.7, moment 3).
    private(set) var arrival = Arrival(shadeID: 0, serial: 0)

    struct Arrival: Equatable {
        var shadeID: Int
        var serial: Int
    }

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
        let live = LiveAPI(
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
        api = live
        writes = WriteCoordinator(api: live, cache: cache)
        #if DEBUG
        if let mode = launch.fakeStickers {
            stickers = FakeStickers(mode: mode, server: launch.server)
        } else {
            stickers = CoreNFCStickers()
        }
        #else
        stickers = CoreNFCStickers()
        #endif
        if launch.forceSignedOut { session.signOut() }
        if let tab = launch.tab { router.tab = tab }
        router.focusSearch = launch.focusSearch
    }

    /// Reads the household's time zone once signed in.
    func loadHouseholdZone() async {
        guard let me = try? await api.me(), let zone = TimeZone(identifier: me.server.timezone) else { return }
        day = HouseholdDay(timeZone: zone)
    }

    /// A bottle of `shadeID` was just added: its tip arrives wherever it is on screen.
    func arrive(shadeID: Int) {
        arrival = Arrival(shadeID: shadeID, serial: arrival.serial + 1)
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

