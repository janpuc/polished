import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// One wheel: its name in Fraunces, the ring of real tips with the count in the hub, and the
/// swatches as a list; at the foot Rename, the tag's moves and Delete (docs/NATIVE.md 5.2). A slot
/// opens the swatch; the builder arrives in run 4.
struct WheelScreen: View {
    let slug: String
    @Environment(AppModel.self) private var app
    @State private var wheel = Resource<WheelDetail>()
    @State private var picked: Tile?
    @State private var sheet: WheelSheet?
    @State private var confirmsNewTag = false

    private enum WheelSheet: String, Identifiable {
        case rename, delete, takeTag
        var id: String { rawValue }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                if wheel.isOffline { OfflineLine().padding(.horizontal, -16) }
                if let value = wheel.value {
                    content(value)
                } else if let error = wheel.error {
                    LoadFailure(error: error) { Task { await wheel.load(.wheel(slug: slug), api: app.api) } }
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 120)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 32)
            .frame(maxWidth: 1100)
            .frame(maxWidth: .infinity)
        }
        .background(Color.board)
        .navigationTitle("")
        .toolbarTitleDisplayMode(.inline)
        .revalidating(wheel, .wheel(slug: slug))
        .sheet(item: $picked) { tile in
            SwatchSheet(tile: tile, wheelName: wheel.value?.name ?? "")
                .presentationDetents([.medium, .large])
                .presentationDragIndicator(.visible)
        }
        .sheet(item: $sheet) { which in
            if let value = wheel.value {
                switch which {
                case .rename:
                    RenameWheelSheet(wheel: value) { archived in
                        if archived { app.router.closeWheel(slug: slug) }
                    }
                case .delete:
                    DeleteWheelSheet(wheel: value) { swatches in
                        app.router.closeWheel(slug: slug)
                        app.writes.show(
                            swatches == 0 ? "Deleted \(value.name)" : "Deleted \(value.name) and \(swatches) swatch\(swatches == 1 ? "" : "es")")
                    }
                case .takeTag:
                    TakeTagSheet(wheel: value) { other, moved in
                        app.router.swapWheelSlugs(slug, other.slug)
                        app.writes.show("\(value.name) took the tag of \(other.name)")
                    }
                }
            }
        }
        .confirmationDialog("Make a new tag URL?", isPresented: $confirmsNewTag, titleVisibility: .visible) {
            Button("New tag URL", role: .destructive) { Task { await newTag() } }
        } message: {
            Text("The old sticker will stop working.")
        }
    }

    private func newTag() async {
        guard let value = wheel.value else { return }
        do {
            let renewed = try await app.writes.perform(.regenerateTag(wheelID: value.id), affecting: .wheelChange)
            app.router.replaceWheelSlug(slug, with: renewed.slug)
            app.writes.show("New tag URL. Write it to the sticker again.")
        } catch let error as APIError {
            app.writes.show("Couldn\u{2019}t make a new tag URL. \(error.message)", kind: .failure)
        } catch {}
    }

    @ViewBuilder
    private func content(_ value: WheelDetail) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            Text(value.name)
                .displayFont(.wheelNamePage)
                .foregroundStyle(Color.ink)
                .lineLimit(2)
                .accessibilityAddTraits(.isHeader)
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 32) {
                    ring(value)
                        .frame(width: 420)
                    swatches(value)
                        .frame(maxWidth: .infinity, alignment: .topLeading)
                }
                .frame(minWidth: 860)
                VStack(alignment: .leading, spacing: 28) {
                    ring(value)
                    swatches(value)
                }
            }
            foot(value)
        }
    }

    /// Rename (with Archive under it), the tag's moves, and the red Delete.
    private func foot(_ value: WheelDetail) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "This wheel")
            VStack(spacing: 0) {
                footRow(value.archived ? "Rename or restore" : "Rename or archive", id: "rename-wheel") { sheet = .rename }
                Divider().padding(.leading, 16)
                footRow("New tag URL", id: "new-tag-url") { confirmsNewTag = true }
                if !value.others.isEmpty {
                    Divider().padding(.leading, 16)
                    footRow("Take the tag of…", id: "take-the-tag") { sheet = .takeTag }
                }
                Divider().padding(.leading, 16)
                footRow("Delete", color: Color.bad, id: "delete-wheel") { sheet = .delete }
            }
            .groupCard()
        }
        .padding(.top, 8)
    }

    private func footRow(_ title: String, color: Color = Color.ink, id: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack {
                Text(title).foregroundStyle(color)
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Color.ink3)
            }
            .padding(.horizontal, 16)
            .frame(minHeight: 50)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier(id)
    }

    private func ring(_ value: WheelDetail) -> some View {
        WheelRing(tiles: value.tiles, slotCount: value.slotCount, filled: value.filledCount) { tile in
            if tile.filled { picked = tile }
        }
        .frame(maxWidth: .infinity)
        .accessibilityIdentifier("wheel-ring")
    }

    private func swatches(_ value: WheelDetail) -> some View {
        let filled = value.tiles.filter(\.filled)
        return VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "Swatches")
            if filled.isEmpty {
                Text("Nothing swatched yet. Tap a slot to start.")
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
            } else {
                VStack(spacing: 0) {
                    ForEach(Array(filled.enumerated()), id: \.element.id) { index, tile in
                        Button {
                            picked = tile
                        } label: {
                            SwatchRow(tile: tile)
                        }
                        .buttonStyle(.plain)
                        if index < filled.count - 1 { Divider().padding(.leading, 76) }
                    }
                }
                .groupCard()
            }
        }
    }
}

/// A filled slot as a row: its number, the painted tip of the stack, what is in it and when it
/// was painted.
struct SwatchRow: View {
    let tile: Tile

    var body: some View {
        HStack(spacing: 12) {
            Text("\(tile.position)")
                .font(.subheadline.weight(.semibold))
                .monospacedDigit()
                .foregroundStyle(Color.ink2)
                .frame(width: 24, alignment: .trailing)
            TipView(TipRecipe(tips: tile.layerTips), size: .m)
                .padding(.vertical, 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(tile.summary)
                    .font(.headline)
                    .foregroundStyle(Color.ink)
                    .multilineTextAlignment(.leading)
                if let painted = Words.day(tile.paintedOn) {
                    Text(painted)
                        .font(.footnote)
                        .foregroundStyle(Color.ink2)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 14)
        .frame(minHeight: 60)
        .contentShape(Rectangle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(
            "Slot \(tile.position), \(tile.summary)" + (Words.day(tile.paintedOn).map { ", painted \($0)" } ?? ""))
        .accessibilityAddTraits(.isButton)
    }
}

/// What a slot holds: the stack's tip, its layers with their coats, the note and the day. The
/// builder that edits it arrives in run 4.
struct SwatchSheet: View {
    let tile: Tile
    let wheelName: String
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    HStack(alignment: .center, spacing: 20) {
                        TipView(TipRecipe(tips: tile.layerTips), size: .xl, painting: .direct)
                            .padding(.vertical, 8)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("Slot \(tile.position)")
                                .font(.title2.weight(.semibold))
                                .foregroundStyle(Color.ink)
                            Text(wheelName)
                                .font(.subheadline)
                                .foregroundStyle(Color.ink2)
                            if let painted = Words.day(tile.paintedOn) {
                                Text("Painted \(painted)")
                                    .font(.subheadline)
                                    .foregroundStyle(Color.ink2)
                            }
                        }
                        Spacer(minLength: 0)
                    }
                    if let note = tile.note {
                        Text(note)
                            .font(.body)
                            .foregroundStyle(Color.ink)
                    }
                    VStack(spacing: 0) {
                        ForEach(Array(tile.layers.enumerated()), id: \.element.id) { index, layer in
                            NavigationLink(value: Route.shade(layer.shadeId)) {
                                HStack(spacing: 12) {
                                    TipView(TipRecipe(layer.tip.shade), size: .s)
                                        .padding(.vertical, 8)
                                    VStack(alignment: .leading, spacing: 1) {
                                        Text(layer.title)
                                            .font(.body)
                                            .foregroundStyle(Color.ink)
                                        Text(layerLine(layer))
                                            .font(.footnote)
                                            .foregroundStyle(Color.ink2)
                                    }
                                    Spacer()
                                }
                                .padding(.horizontal, 16)
                                .frame(minHeight: 56)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            if index < tile.layers.count - 1 { Divider().padding(.leading, 60) }
                        }
                    }
                    .groupCard()
                }
                .padding(16)
            }
            .background(Color.board)
            .navigationBarTitleDisplayMode(.inline)
            .navigationDestination(for: Route.self) { route in
                if case .shade(let id) = route { ShadeDetailScreen(id: id) }
            }
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button("Done") { dismiss() } }
            }
        }
    }

    private func layerLine(_ layer: Layer) -> String {
        let coats = "\(layer.coats) coat\(layer.coats == 1 ? "" : "s")"
        return layer.label.isEmpty ? coats : "\(layer.label), \(coats)"
    }
}
