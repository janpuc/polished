import Foundation
import Observation
import PolishedAPI
import PolishedModels

public enum AppTab: String, Hashable, CaseIterable, Sendable {
    case home, shades, bottles, wheels, wishlist, settings
}

/// A screen pushed onto a tab's stack.
public enum Route: Hashable, Sendable {
    case shade(Int)
    case wheel(slug: String)
}

/// Which tab is up and what each tab's stack holds. Deep links and the Home shortcuts write
/// here; the screens read it. A link that arrives while signed out waits in `pendingLink`
/// (docs/NATIVE.md 2.3).
@MainActor
@Observable
public final class Router {
    public var tab: AppTab = .home
    public var paths: [AppTab: [Route]] = [:]
    public var pendingLink: DeepLink?
    /// The Shades tab opens with this query (the Home shortcuts), then forgets it.
    public var shadesPreset: ShadeQuery?
    /// The Shades tab puts the cursor in its search field (Home's search field).
    public var focusSearch = false

    public init() {}

    public func path(_ tab: AppTab) -> [Route] { paths[tab] ?? [] }

    public func setPath(_ tab: AppTab, _ path: [Route]) { paths[tab] = path }

    /// Shows the shade or the wheel a link names, on the tab it belongs to.
    public func open(_ link: DeepLink) {
        switch link {
        case .wheel(let slug):
            tab = .wheels
            paths[.wheels] = [.wheel(slug: slug)]
        case .shade(let id):
            tab = .shades
            paths[.shades] = [.shade(id)]
        }
    }

    /// A tapped URL: a link of ours is opened, anything else is dropped. Signed out, it is kept
    /// until sign-in finishes.
    public func handle(_ url: URL, signedIn: Bool) {
        guard let link = DeepLink(url: url) else { return }
        if signedIn { open(link) } else { pendingLink = link }
    }

    /// Opens the link that waited for sign-in.
    public func openPending() {
        guard let link = pendingLink else { return }
        pendingLink = nil
        open(link)
    }

    public func showShades(_ query: ShadeQuery, focusSearch: Bool = false) {
        shadesPreset = query
        self.focusSearch = focusSearch
        paths[.shades] = []
        tab = .shades
    }
}
