import Foundation
import PolishedStore

/// How the process was started. The release app reads none of this: the server is the production
/// one and the session is the Keychain's. A Debug build also honours launch arguments, which
/// is how UI tests and simulators skip the Pocket ID sign-in against a local server
/// (docs/NATIVE.md 6.2):
///
///     -server http://127.0.0.1:8080 -token dev -uitest 1 -open https://…/w/k3m9xq -signedout 1 -nfc ok -reducemotion 1
struct LaunchOptions {
    var server = URL(string: "https://polished.janpuc.com")!
    /// A development bearer token: skips sign-in, kept in memory.
    var devToken: String?
    /// UI tests: the snapshot cache lives in memory so a run never sees an earlier one.
    var inMemoryCache = false
    /// A link to open once the shell is up, as if it had been tapped.
    var openURL: URL?
    /// Shows the sign-in screen whatever the Keychain holds (screenshots).
    var forceSignedOut = false
    /// The tab to open on (screenshots).
    var tab: AppTab?
    /// Opens the Shades search as if Home's search field had been tapped (screenshots).
    var focusSearch = false

    /// UI tests: the builder behaves as under Reduce Motion (the system setting cannot be set
    /// from a test).
    var reduceMotion = false

    /// UI tests: a sticker in memory instead of Core NFC, "ok" (blank), "other" (holds another
    /// wheel's link) or "readonly" (refuses a write).
    var fakeStickers: String?

    static let current: LaunchOptions = {
        var options = LaunchOptions()
        #if DEBUG
        let defaults = UserDefaults.standard
        if let server = defaults.string(forKey: "server"), let url = URL(string: server) { options.server = url }
        options.devToken = defaults.string(forKey: "token")
        options.inMemoryCache = defaults.bool(forKey: "uitest")
        options.openURL = defaults.string(forKey: "open").flatMap(URL.init(string:))
        options.forceSignedOut = defaults.bool(forKey: "signedout")
        options.focusSearch = defaults.bool(forKey: "focussearch")
        options.fakeStickers = defaults.string(forKey: "nfc")
        options.reduceMotion = defaults.bool(forKey: "reducemotion")
        options.tab = defaults.string(forKey: "tab").flatMap(AppTab.init(rawValue:))
        #endif
        return options
    }()
}
