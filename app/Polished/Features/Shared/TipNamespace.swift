import SwiftUI

private struct TipNamespaceKey: EnvironmentKey {
    static let defaultValue: Namespace.ID? = nil
}

extension EnvironmentValues {
    /// The namespace a tab's tips are matched in, so a tapped tip can zoom into its shade.
    var tipNamespace: Namespace.ID? {
        get { self[TipNamespaceKey.self] }
        set { self[TipNamespaceKey.self] = newValue }
    }
}

private struct TipSource: ViewModifier {
    let shadeID: Int
    @Environment(\.tipNamespace) private var namespace

    func body(content: Content) -> some View {
        if let namespace {
            content.matchedTransitionSource(id: shadeID, in: namespace)
        } else {
            content
        }
    }
}

extension View {
    /// Marks this view as the place a shade's detail zooms out of (docs/NATIVE.md 5.7, moment 2).
    func tipSource(_ shadeID: Int) -> some View {
        modifier(TipSource(shadeID: shadeID))
    }
}
