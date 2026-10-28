import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// One wheel: its name in Fraunces, the ring of real tips with the count in the hub, and the
/// swatches as a list; at the foot Rename, the tag's moves and Delete (docs/NATIVE.md 5.2). A slot,
/// filled or empty, opens the layer builder: a sheet on a phone, an inspector beside the ring on
/// a regular width.
struct WheelScreen: View {
    let slug: String
    /// The slot to ring in foil, from a shade's "Swatched on".
    var highlight: Int?
    @Environment(AppModel.self) private var app
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var wheel = Resource<WheelDetail>()
    @State private var builder: BuilderTarget?
    /// The builder closed last with Cancel, whose draft may still be on its way out.
    @State private var closing: BuilderModel?
    @State private var sheet: WheelSheet?
    /// The slot that was just saved: its tile gets the sweep once the builder has closed.
    @State private var swept: SweptSlot?
    @State private var saves = 0
    /// The room above the builder's sheet: the screen's height and the bars above the page, to size the ring to it.
    @State private var page = PageMetrics()

    private struct PageMetrics: Equatable {
        var screenHeight: CGFloat = 0
        var barsHeight: CGFloat = 0
    }

    private struct SweptSlot: Equatable {
        var position: Int
        var serial: Int
    }

    private enum WheelSheet: String, Identifiable {
        case rename, delete
        var id: String { rawValue }
    }

    var body: some View {
        ScrollViewReader { page in
            scroll
                .onChange(of: builder?.position) { _, position in
                    guard horizontalSizeClass != .regular else { return }
                    // The sheet opens over the lower half: the ring comes up under the bar, so the slot
                    // being edited stays in sight above it, and goes back when the builder closes.
                    withAnimation(.smooth(duration: 0.35)) {
                        page.scrollTo(position == nil ? "top" : "ring", anchor: .top)
                    }
                }
        }
    }

    private var scroll: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 0) {
                Color.clear.frame(height: 0).id("top")
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
        .onGeometryChange(for: PageMetrics.self) { proxy in
            PageMetrics(
                screenHeight: proxy.size.height + proxy.safeAreaInsets.top + proxy.safeAreaInsets.bottom,
                barsHeight: proxy.safeAreaInsets.top)
        } action: { page = $0 }
        .navigationTitle("")
        .toolbarTitleDisplayMode(.inline)
        .revalidating(wheel, .wheel(slug: slug))
        .builderPresentation($builder, wheelName: wheel.value?.name ?? "") { outcome in finish(outcome) }
        .sensoryFeedback(.success, trigger: saves)
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
                }
            }
        }
        // The builder beside the ring needs the room of the split view's sidebar column.
        .onChange(of: builder?.position != nil) { _, open in app.builderIsOpen = open }
        .onDisappear { app.builderIsOpen = false }
    }

    private func openBuilder(_ tile: Tile, in value: WheelDetail) {
        guard builder?.position != tile.position else { return }
        // The sheet shows the tile's layers at once; the draft opens in the background.
        let model = BuilderModel(
            wheelID: value.id, position: tile.position, api: app.api, writes: app.writes,
            preview: BuilderPreview(wheel: StackWheel(id: value.id, slug: value.slug, name: value.name), tile: tile),
            pickMemory: app.pickMemory, after: closing?.discarding)
        builder = BuilderTarget(position: tile.position, saved: tile.filled, model: model)
        Task { await model.open() }
    }

    /// The builder closed: a saved swatch gets its sweep once the sheet is gone, with the success
    /// haptic as it lands (docs/NATIVE.md 5.7, 5.8).
    private func finish(_ outcome: BuilderOutcome) {
        let removed = builder?.position
        if case .cancelled = outcome { closing = builder?.model }
        builder = nil
        switch outcome {
        case .saved(let result):
            Task {
                try? await Task.sleep(for: .milliseconds(reduceMotion ? 200 : 450))
                saves += 1
                swept = SweptSlot(position: result.position, serial: saves)
            }
        case .removed:
            if let removed { app.writes.show("Removed the swatch from slot \(removed)") }
        case .cancelled, .closed:
            break
        }
    }

    @ViewBuilder
    private func content(_ value: WheelDetail) -> some View {
        VStack(alignment: .leading, spacing: 24) {
            Text(value.name)
                .displayFont(.wheelNamePage)
                .foregroundStyle(Color.ink)
                .lineLimit(2)
                .accessibilityAddTraits(.isHeader)
                // The sheet's head names the wheel while the builder is open; the title would
                // only slide under the bar.
                .opacity(builder == nil || horizontalSizeClass == .regular ? 1 : 0)
                .animation(.smooth(duration: 0.25), value: builder == nil)
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

    /// Tag and QR, Rename (with Archive under it), and the red Delete.
    private func foot(_ value: WheelDetail) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "This wheel")
            VStack(spacing: 0) {
                footRow("Tag and QR", id: "tag-and-qr") { app.router.tagSlug = slug }
                Divider().padding(.leading, 16)
                footRow(value.archived ? "Rename or restore" : "Rename or archive", id: "rename-wheel") { sheet = .rename }
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
        WheelRing(
            tiles: value.tiles, slotCount: value.slotCount, filled: value.filledCount, highlighted: highlight,
            editing: builder?.position, editingRecipe: draftRecipe, editingSummary: builder?.model.sheet?.summary,
            sweeping: swept.map { ($0.position, $0.serial) }
        ) { tile in
            openBuilder(tile, in: value)
        }
        .frame(maxWidth: .infinity)
        .scaleEffect(ringScale, anchor: .top)
        .animation(.smooth(duration: 0.35), value: ringScale)
        .id("ring")
        .accessibilityIdentifier("wheel-ring")
    }

    /// Under the builder's sheet the ring shrinks to fit between the bar and the sheet's top
    /// edge (the middle detent, a little under half the screen), so every slot stays in view.
    private var ringScale: CGFloat {
        guard builder != nil, horizontalSizeClass != .regular, page.screenHeight > 0 else { return 1 }
        let room = page.screenHeight * 0.475 - page.barsHeight - 20
        return min(1, max(0.5, room / 362))
    }

    /// The draft in the open slot, painted as the builder has it.
    private var draftRecipe: TipRecipe? {
        guard let tips = builder?.model.sheet?.tip, !tips.isEmpty else { return nil }
        return TipRecipe(tips: tips)
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
                            openBuilder(tile, in: value)
                        } label: {
                            SwatchRow(tile: tile)
                        }
                        .buttonStyle(.plain)
                        .accessibilityIdentifier("swatch-row-\(tile.position)")
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
