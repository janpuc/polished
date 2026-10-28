import NailTips
import PolishedModels
import PolishedStore
import SwiftUI

/// The layers of the swatch in painting order, base first: one compact row each on the 2 pt rail
/// that runs through the tips (docs/NATIVE.md 5.2). A tap opens the row's popover (coats,
/// Remove); a long press, or the Arrange button, makes the rows jiggle and a drag reorders them,
/// the rows it passes making room, until Done or a tap outside. The hand is `ArrangeGestures`
/// (UIKit recognizers over the rows); what it did is `session`, which the builder owns so Save,
/// Cancel and the sheet closing can end it.
struct LayerStack: View {
    let model: BuilderModel
    @Binding var session: ArrangeSession

    static let rowHeight: CGFloat = 52

    @Environment(\.accessibilityReduceMotion) private var systemReduceMotion
    @State private var heldID: Int?
    @State private var popover: Int?
    /// When a popover last went away: the tap that dismissed it must not also open the next.
    @State private var popoverClosedAt = Date.distantPast
    @State private var pickups = 0
    @State private var crossings = 0
    @State private var drops = 0

    private var reduceMotion: Bool { systemReduceMotion || LaunchOptions.current.reduceMotion }
    private var arranging: Bool { session.isArranging }

    var body: some View {
        let layers = model.layers
        VStack(alignment: .leading, spacing: 8) {
            if layers.count > 1 { header }
            TimelineView(.animation(minimumInterval: 1.0 / 60, paused: !(arranging && !reduceMotion))) { context in
                let time = context.date.timeIntervalSinceReferenceDate
                VStack(spacing: 0) {
                    ForEach(Array(layers.enumerated()), id: \.element.id) { index, layer in
                        row(layer, index: index, count: layers.count, time: time)
                    }
                }
            }
            .overlay { hand(count: layers.count) }
            .groupCard()
        }
        .onChange(of: layers.count) { session.layerCountChanged(to: layers.count) }
        .onChange(of: arranging) { if !arranging { heldID = nil } }
        .sensoryFeedback(.selection, trigger: pickups)
        .sensoryFeedback(.selection, trigger: crossings)
        .sensoryFeedback(.impact(weight: .medium), trigger: drops)
    }

    // MARK: Head

    private var header: some View {
        HStack(spacing: 8) {
            Text(arranging ? "Drag to reorder" : "Hold a layer to rearrange")
                .font(.footnote)
                .foregroundStyle(Color.ink2)
                .contentTransition(.opacity)
            Spacer(minLength: 0)
            if arranging {
                Button("Done") { session.done() }
                    .buttonStyle(CompactPrimaryButtonStyle())
                    .accessibilityIdentifier("layers-done")
                    .transition(.opacity.combined(with: .scale(scale: 0.9, anchor: .trailing)))
            } else {
                // The same mode as the long press, for a hand that does not find it.
                Button("Arrange") { begin() }
                    .buttonStyle(CompactButtonStyle())
                    .accessibilityIdentifier("layers-arrange")
                    .transition(.opacity)
            }
        }
        .frame(minHeight: 36)
        .padding(.horizontal, 4)
        .animation(.smooth(duration: 0.2), value: arranging)
    }

    // MARK: Rows

    private func row(_ layer: Layer, index: Int, count: Int, time: TimeInterval) -> some View {
        let lifted = session.held != nil && heldID == layer.id
        let reflow = session.held.map {
            lifted
                ? 0
                : BuilderArrangement.reflow(
                    index: index, from: $0.from, target: $0.target, rowHeight: Self.rowHeight)
        } ?? 0
        return LayerRow(
            layer: layer, isFirst: index == 0, isLast: index == count - 1, arranging: arranging,
            showsHandle: arranging && reduceMotion, model: model,
            isPopoverPresented: Binding(
                get: { popover == layer.id },
                set: {
                    if !$0, popover == layer.id {
                        popover = nil
                        popoverClosedAt = .now
                    }
                }),
            removal: { popover = nil; model.remove(layer) }
        )
        .offset(y: lifted ? session.held?.translation ?? 0 : reflow)
        // The dragged row follows the finger 1:1: no animation reaches its offset while it is held.
        .transaction { if lifted { $0.animation = nil } }
        .rotationEffect(.degrees(jiggles(lifted) ? 1.5 * sin(2 * .pi * 7 * time + 1.3 * Double(index)) : 0))
        .offset(y: jiggles(lifted) ? 0.5 * sin(2 * .pi * 7 * time + 1.9 * Double(index)) : 0)
        .scaleEffect(lifted && !reduceMotion ? 1.04 : 1)
        .background(lifted ? Color.surface : Color.clear, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .shadow(color: Color.shadowInk.opacity(lifted ? 0.2 : 0), radius: 16, y: 8)
        .zIndex(lifted ? 1 : 0)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(spoken(layer))
        .accessibilityValue(arranging ? "Rearranging" : "")
        .accessibilityHint("Opens coats and remove")
        .accessibilityAddTraits(.isButton)
        .accessibilityIdentifier("layer-row-\(layer.id)")
        .accessibilityAction { if session.opensPopover { popover = layer.id } }
        .accessibilityAdjustableAction { direction in
            model.changeCoats(of: layer, by: direction == .increment ? 1 : -1)
        }
        .accessibilityAction(named: "Move up") { withAnimation(.smooth(duration: 0.3)) { model.move(layer, up: true) } }
        .accessibilityAction(named: "Move down") { withAnimation(.smooth(duration: 0.3)) { model.move(layer, up: false) } }
        .accessibilityAction(named: "Remove") { model.remove(layer) }
    }

    private func jiggles(_ lifted: Bool) -> Bool { arranging && !lifted && !reduceMotion }

    /// "Top, Flakie Holo Taco, 2 coats".
    private func spoken(_ layer: Layer) -> String {
        let coats = "\(layer.coats) coat\(layer.coats == 1 ? "" : "s")"
        return [layer.label, layer.title, coats].filter { !$0.isEmpty }.joined(separator: ", ")
    }

    // MARK: Hand

    /// The recognizers over the rows. They are invisible to VoiceOver (the rows speak and act).
    private func hand(count: Int) -> some View {
        ArrangeGestures(
            rowHeight: Self.rowHeight, rowCount: count, arranging: arranging, enabled: popover == nil,
            onTap: { index in
                let layers = model.layers
                guard Date.now.timeIntervalSince(popoverClosedAt) > 0.5 else { return }
                if session.opensPopover, layers.indices.contains(index) { popover = layers[index].id }
            },
            onHold: { index in
                var event = ArrangeSession.Event.none
                withAnimation(.snappy(duration: 0.2)) { event = session.hold(at: index, count: model.layers.count) }
                pickedUp(event, at: index)
            },
            onDragBegan: { index in
                var event = ArrangeSession.Event.none
                withAnimation(.snappy(duration: 0.2)) { event = session.dragBegan(at: index, count: model.layers.count) }
                pickedUp(event, at: index)
            },
            onDragMoved: { follow($0) },
            onDragEnded: { drop() }
        )
        .accessibilityHidden(true)
    }

    /// The Arrange button: the rows jiggle, none is held yet.
    private func begin() {
        if session.begin(count: model.layers.count) == .pickedUp { pickups += 1 }
    }

    private func pickedUp(_ event: ArrangeSession.Event, at index: Int) {
        guard event == .pickedUp else { return }
        pickups += 1
        let layers = model.layers
        heldID = session.held != nil && layers.indices.contains(index) ? layers[index].id : nil
    }

    private func follow(_ translation: CGFloat) {
        guard let held = session.held else { return }
        let count = model.layers.count
        let target = BuilderArrangement.target(
            from: held.from, translation: translation, count: count, rowHeight: Self.rowHeight)
        if target != held.target {
            crossings += 1
            // The rows it passes make room with a critically damped spring; the held row is not
            // animated (`transaction` above).
            withAnimation(.spring(response: 0.3, dampingFraction: 1)) {
                _ = session.dragMoved(translation: translation, count: count, rowHeight: Self.rowHeight)
            }
        } else {
            _ = session.dragMoved(translation: translation, count: count, rowHeight: Self.rowHeight)
        }
    }

    /// Settles the held row: the model gets one move per row crossed, in order, and the row
    /// springs from where the finger left it to its place.
    private func drop() {
        let layers = model.layers
        guard let held = session.held, let id = heldID else { return }
        drops += 1
        withAnimation(.spring(response: 0.35, dampingFraction: 0.85)) {
            if case .dropped(let moves) = session.dragEnded(),
                layers.indices.contains(held.from), layers[held.from].id == id
            {
                let layer = layers[held.from]
                for up in moves { model.move(layer, up: up) }
            }
        }
        heldID = nil
    }
}

/// One layer: its mini tip on the rail, its name, and a ×N badge when it has more than one coat.
/// 52 pt tall. The popover holds the coats stepper and Remove.
struct LayerRow: View {
    let layer: Layer
    let isFirst: Bool
    let isLast: Bool
    let arranging: Bool
    /// Reduce Motion: a handle takes the place of the jiggle.
    let showsHandle: Bool
    let model: BuilderModel
    @Binding var isPopoverPresented: Bool
    let removal: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            TipView(TipRecipe(layer.tip.shade), size: .s)
            Text(layer.title)
                .font(.headline)
                .foregroundStyle(Color.ink)
                .lineLimit(1)
                .truncationMode(.middle)
            Spacer(minLength: 4)
            if layer.coats > 1 {
                Text("\u{00D7}\(layer.coats)")
                    .font(.footnote)
                    .monospacedDigit()
                    .foregroundStyle(Color.ink)
                    .padding(.horizontal, 9)
                    .frame(minHeight: 24)
                    .background(Color.fill, in: Capsule())
                    .transition(.opacity)
            }
            if showsHandle {
                Image(systemName: "line.3.horizontal")
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Color.ink3)
                    .transition(.opacity)
            }
        }
        .padding(.horizontal, 14)
        .frame(height: LayerStack.rowHeight)
        .background(alignment: .leading) { rail }
        .contentShape(Rectangle())
        .animation(.snappy(duration: 0.2), value: layer.coats)
        .popover(isPresented: $isPopoverPresented) {
            LayerPopover(layerID: layer.id, model: model, remove: removal)
                .presentationCompactAdaptation(.popover)
        }
    }

    /// The 2 pt line through the tips: the first row starts at its tip, the last ends at it. The
    /// tip's middle sits half the 52 pt row from the top.
    private var rail: some View {
        VStack(spacing: 0) {
            Rectangle().fill(isFirst ? Color.clear : Color.line2).frame(height: LayerStack.rowHeight / 2)
            Rectangle().fill(isLast ? Color.clear : Color.line2)
        }
        .frame(width: 2)
        .padding(.leading, 27)
        .accessibilityHidden(true)
    }
}

/// What a row's tap opens: the number of coats, 1 to 5, and Remove.
struct LayerPopover: View {
    let layerID: Int
    let model: BuilderModel
    let remove: () -> Void

    var body: some View {
        let coats = model.layers.first { $0.id == layerID }?.coats ?? 1
        VStack(spacing: 0) {
            Stepper(
                value: Binding(
                    get: { coats },
                    set: { value in
                        if let layer = model.layers.first(where: { $0.id == layerID }) {
                            model.changeCoats(of: layer, by: value - layer.coats)
                        }
                    }),
                in: BuilderModel.minCoats...BuilderModel.maxCoats
            ) {
                HStack {
                    Text("Coats")
                    Text("\(coats)")
                        .monospacedDigit()
                        .foregroundStyle(Color.ink2)
                        .contentTransition(.numericText())
                        .animation(.snappy(duration: 0.2), value: coats)
                }
            }
            .accessibilityIdentifier("layer-coats")
            .padding(.horizontal, 16)
            .frame(minHeight: 52)
            Divider()
            Button(role: .destructive, action: remove) {
                Text("Remove")
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
            }
            .padding(.horizontal, 16)
            .frame(minHeight: 48)
            .accessibilityIdentifier("layer-remove")
        }
        .frame(width: 260)
    }
}

/// A shade in the picker: tapping it paints it as the next layer.
struct PickRow: View {
    let shade: ShadeRow
    let model: BuilderModel
    /// The matched letters of a search washed in.
    var marks = true

    var body: some View {
        Button {
            model.add(shade)
        } label: {
            HStack(spacing: 12) {
                TipView(shade.recipe, size: .s)
                    .padding(.vertical, 8)
                VStack(alignment: .leading, spacing: 2) {
                    Group {
                        if marks { Text(shade.markedTitle) } else { Text(shade.title) }
                    }
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                    HStack(spacing: 8) {
                        if shade.isTopper && !shade.finishLine.localizedCaseInsensitiveContains("topper") {
                            Text("Topper")
                        }
                        if !shade.finishLine.isEmpty { Text(shade.finishLine) }
                        if shade.ownedCount > 0 { Text("×\(shade.ownedCount)").monospacedDigit() }
                    }
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
                    .lineLimit(1)
                }
                Spacer(minLength: 8)
                ZStack {
                    if model.adding == shade.id {
                        ProgressView()
                    } else {
                        Image(systemName: "plus")
                            .font(.body.weight(.semibold))
                            .foregroundStyle(Color.ink)
                    }
                }
                .frame(width: 36, height: 36)
                .background(Color.fill, in: Circle())
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 60)
            .contentShape(Rectangle())
        }
        .buttonStyle(RowPressStyle())
        .accessibilityLabel("Add \(shade.title)")
        .accessibilityIdentifier("pick-\(shade.id)")
    }
}

/// A row that washes Fill while it is pressed.
private struct RowPressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.background(configuration.isPressed ? Color.fill : Color.clear)
    }
}

/// Copy from…: the swatches saved on any wheel, most recent first, searchable by shade name.
/// Choosing one replaces the draft's layers with a copy of its layers.
struct CopySourcesSheet: View {
    let model: BuilderModel
    /// The draft has layers that the copy replaces.
    let replaces: Bool
    let onPick: (CopySource) -> Void
    @Environment(\.dismiss) private var dismiss
    @State private var sources: [CopySource]?
    @State private var text = ""
    @State private var chosen: CopySource?

    var body: some View {
        NavigationStack {
            Group {
                if let sources {
                    if sources.isEmpty {
                        Text(text.isEmpty ? "Nothing is saved on a wheel yet." : "No saved swatch has \u{201C}\(text)\u{201D}.")
                            .font(.subheadline)
                            .foregroundStyle(Color.ink2)
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                    } else {
                        List(sources) { source in
                            Button {
                                if replaces { chosen = source } else { pick(source) }
                            } label: {
                                row(source)
                            }
                            .listRowBackground(Color.surface)
                            .accessibilityIdentifier("copy-source-\(source.stackId)")
                        }
                        .scrollContentBackground(.hidden)
                    }
                } else {
                    ProgressView().frame(maxWidth: .infinity, maxHeight: .infinity)
                }
            }
            .background(Color.board)
            .navigationTitle("Copy from…")
            .navigationBarTitleDisplayMode(.inline)
            .searchable(text: $text, prompt: "Search by shade name")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
            }
            .task(id: text) {
                if !text.isEmpty { try? await Task.sleep(for: .milliseconds(200)) }
                guard !Task.isCancelled else { return }
                if let loaded = await model.copySources(matching: text) { sources = loaded.items }
            }
            .confirmationDialog(
                "Replace the layers?", isPresented: Binding(get: { chosen != nil }, set: { if !$0 { chosen = nil } }),
                titleVisibility: .visible, presenting: chosen
            ) { source in
                Button("Replace with a copy") { pick(source) }
            } message: { _ in
                Text("The layers you have now are swapped for a copy of these.")
            }
        }
        .presentationDetents([.medium, .large])
        .presentationDragIndicator(.visible)
        .presentationSizing(.form)
    }

    private func pick(_ source: CopySource) {
        dismiss()
        onPick(source)
    }

    private func row(_ source: CopySource) -> some View {
        HStack(spacing: 12) {
            TipView(TipRecipe(tips: source.layers.map(\.tip)), size: .m)
                .padding(.vertical, 6)
            VStack(alignment: .leading, spacing: 2) {
                Text(source.name.flatMap { $0.isEmpty ? nil : $0 } ?? source.summary)
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .multilineTextAlignment(.leading)
                if source.name?.isEmpty == false {
                    Text(source.summary)
                        .font(.subheadline)
                        .foregroundStyle(Color.ink2)
                        .multilineTextAlignment(.leading)
                }
                Text("\(source.wheelName), slot \(source.position)" + (Words.day(source.paintedOn).map { ", \($0)" } ?? ""))
                    .font(.footnote)
                    .foregroundStyle(Color.ink2)
            }
            Spacer(minLength: 0)
        }
        .frame(minHeight: 56)
        .contentShape(Rectangle())
    }
}
