import PolishedStore
import SwiftUI

/// Where the builder opens (docs/NATIVE.md 5.1): a sheet on a compact width, with detents
/// `.medium` and `.large`, opening at `.medium` so the ring stays in view (the search field or a
/// scroll of the list asks for `.large`), and the ring behind it still tappable down to `.medium`; an inspector beside the ring on a regular width (the iPad, the iPhone Duo unfolded).
private struct BuilderPresentation: ViewModifier {
    @Binding var target: BuilderTarget?
    let wheelName: String
    let onFinish: (BuilderOutcome) -> Void
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var detent = PresentationDetent.medium

    private var isCompact: Bool { horizontalSizeClass != .regular }

    func body(content: Content) -> some View {
        // One presentation at a time: a sheet and an inspector on the same view fight over it.
        if isCompact {
            content
                .sheet(
                    item: Binding(
                        get: { target },
                        set: { if $0 == nil { target = nil } })
                ) { target in
                    BuilderView(target: target, wheelName: wheelName, detent: $detent, onFinish: onFinish)
                        .presentationBackgroundInteraction(.enabled(upThrough: .medium))
                        .presentationDragIndicator(.visible)
                        .sensoryFeedback(.selection, trigger: detent)
                        .onAppear { detent = .medium }
                }
        } else {
            content
                .inspector(
                    isPresented: Binding(
                        get: { target != nil },
                        set: { if !$0 { target = nil } })
                ) {
                    if let target {
                        BuilderView(target: target, wheelName: wheelName, onFinish: onFinish)
                            .id(target.position)
                            .inspectorColumnWidth(min: 360, ideal: 380, max: 400)
                    }
                }
        }
    }
}

extension View {
    /// The builder for `target`, in the shell the width calls for.
    func builderPresentation(
        _ target: Binding<BuilderTarget?>, wheelName: String, onFinish: @escaping (BuilderOutcome) -> Void
    ) -> some View {
        modifier(BuilderPresentation(target: target, wheelName: wheelName, onFinish: onFinish))
    }
}

/// The sheet's detents (`.medium` and `.large`, the selection shared with the builder), or just the
/// current one while the layers are being arranged: a finger dragging a row must not also drag the
/// sheet. Nothing in an inspector, which has no detent.
struct SheetDetents: ViewModifier {
    let detent: Binding<PresentationDetent>?
    let pinned: Bool

    func body(content: Content) -> some View {
        if let detent {
            content.presentationDetents(pinned ? [detent.wrappedValue] : [.medium, .large], selection: detent)
        } else {
            content
        }
    }
}
