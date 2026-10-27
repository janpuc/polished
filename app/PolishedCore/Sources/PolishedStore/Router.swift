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
    /// `highlight` is the slot to ring in foil (a shade's "Swatched on").
    case wheel(slug: String, highlight: Int? = nil)

    public var wheelSlug: String? {
        if case .wheel(let slug, _) = self { slug } else { nil }
    }
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
    /// The wheel whose Tag and QR sheet is up. It lives here, not in the wheel page, so the sheet
    /// stays up when a new tag URL or a swap changes the wheel's address under it.
    public var tagSlug: String?

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

    /// A wheel's tag changed: every stack that shows it follows the new address.
    public func replaceWheelSlug(_ old: String, with new: String) {
        if tagSlug == old { tagSlug = new }
        for tab in paths.keys {
            paths[tab] = paths[tab]?.map { route in
                if case .wheel(old, let highlight) = route { return .wheel(slug: new, highlight: highlight) }
                return route
            }
        }
    }

    /// Two wheels traded tags: each stack that shows one follows its address to the other.
    public func swapWheelSlugs(_ first: String, _ second: String) {
        if tagSlug == first { tagSlug = second } else if tagSlug == second { tagSlug = first }
        for tab in paths.keys {
            paths[tab] = paths[tab]?.map { route in
                if case .wheel(first, let highlight) = route { return .wheel(slug: second, highlight: highlight) }
                if case .wheel(second, let highlight) = route { return .wheel(slug: first, highlight: highlight) }
                return route
            }
        }
    }

    /// A wheel is gone: it leaves every stack.
    public func closeWheel(slug: String) {
        if tagSlug == slug { tagSlug = nil }
        for tab in paths.keys {
            paths[tab]?.removeAll { $0.wheelSlug == slug }
        }
    }

    public func showShades(_ query: ShadeQuery, focusSearch: Bool = false) {
        shadesPreset = query
        self.focusSearch = focusSearch
        paths[.shades] = []
        tab = .shades
    }
}
