import PolishedStore
import SwiftUI

private struct RouteDestinations: ViewModifier {
    @Environment(\.tipNamespace) private var tips

    func body(content: Content) -> some View {
        content.navigationDestination(for: Route.self) { route in
            switch route {
            case .shade(let id):
                if let tips {
                    // The tip the person tapped grows into the detail (docs/NATIVE.md 5.7).
                    ShadeDetailScreen(id: id).navigationTransition(.zoom(sourceID: id, in: tips))
                } else {
                    ShadeDetailScreen(id: id)
                }
            case .wheel(let slug):
                WheelScreen(slug: slug)
            }
        }
    }
}

extension View {
    /// The screens a `Route` pushes: shade detail (zooming out of the tapped tip) and the wheel.
    func routeDestinations() -> some View {
        modifier(RouteDestinations())
    }
}
