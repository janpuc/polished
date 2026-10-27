import NailTips
import PolishedModels
import PolishedStore
import SwiftUI

/// One layer of the swatch: its mini tip on the rail that runs through the stack, the name with
/// Base or Top above it, a coats stepper, and move up, move down and remove. Every control is at
/// least 44 pt to tap.
struct LayerRow: View {
    let layer: Layer
    let isFirst: Bool
    let isLast: Bool
    let model: BuilderModel

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            TipView(TipRecipe(layer.tip.shade), size: .s)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 4) {
                VStack(alignment: .leading, spacing: 0) {
                    if !layer.label.isEmpty {
                        Text(layer.label)
                            .font(.caption)
                            .foregroundStyle(Color.ink2)
                    }
                    Text(layer.title)
                        .font(.headline)
                        .foregroundStyle(Color.ink)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .accessibilityElement(children: .combine)
                HStack(spacing: 0) {
                    coats
                    Spacer(minLength: 4)
                    iconButton("chevron.up", "Move \(layer.title) up", enabled: !isFirst) { model.move(layer, up: true) }
                    iconButton("chevron.down", "Move \(layer.title) down", enabled: !isLast) { model.move(layer, up: false) }
                    iconButton("xmark", "Remove \(layer.title)", enabled: true) { model.remove(layer) }
                }
            }
        }
        .padding(.vertical, 12)
        .background(alignment: .leading) { rail }
        .padding(.horizontal, 14)
    }

    /// The 2 pt line through the tips: the first row starts at its tip, the last ends at it. The
    /// tip's middle sits 12 pt of padding, 2 pt and half the 46 pt tip from the top.
    private var rail: some View {
        VStack(spacing: 0) {
            Rectangle().fill(isFirst ? Color.clear : Color.line2).frame(height: 37)
            Rectangle().fill(isLast ? Color.clear : Color.line2)
        }
        .frame(width: 2)
        .padding(.leading, 13)
        .accessibilityHidden(true)
    }

    private var coats: some View {
        HStack(spacing: 0) {
            iconButton("minus", "Remove a coat of \(layer.title)", enabled: layer.coats > BuilderModel.minCoats) {
                model.changeCoats(of: layer, by: -1)
            }
            Text("\(layer.coats)")
                .font(.body.weight(.semibold))
                .monospacedDigit()
                .foregroundStyle(Color.ink)
                .frame(minWidth: 22)
                .contentTransition(.numericText())
                .animation(.snappy(duration: 0.2), value: layer.coats)
                .accessibilityLabel("\(layer.coats) coat\(layer.coats == 1 ? "" : "s") of \(layer.title)")
            iconButton("plus", "Add a coat of \(layer.title)", enabled: layer.coats < BuilderModel.maxCoats) {
                model.changeCoats(of: layer, by: 1)
            }
        }
        .background(Color.fill, in: Capsule())
    }

    private func iconButton(_ symbol: String, _ label: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Color.ink)
                .frame(width: 40, height: 40)
                .contentShape(Rectangle())
        }
        .buttonStyle(IconPressStyle())
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.3)
        .accessibilityLabel(label)
    }
}

private struct IconPressStyle: ButtonStyle {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    func makeBody(configuration: Configuration) -> some View {
        configuration.label.pressScale(configuration.isPressed, reduceMotion: reduceMotion)
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
