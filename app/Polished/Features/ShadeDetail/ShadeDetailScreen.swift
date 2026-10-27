import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// One shade: its lit tip on the plate, the shop's photos, the bottles owned, the facts, and the
/// wheels it is swatched on (docs/NATIVE.md 5.2). Add bottle, the heart and the bottles' levels
/// write; the tip colour can be set by hand.
struct ShadeDetailScreen: View {
    let id: Int
    @Environment(AppModel.self) private var app
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var detail = Resource<ShadeDetail>()
    @State private var storePage: URL?
    @State private var bottleSheet: BottleSheetMode?
    /// A heart tap is in flight: the next one waits for the item's id.
    @State private var heartBusy = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 28) {
                if detail.isOffline { OfflineLine().padding(.horizontal, -16) }
                if let value = detail.value {
                    content(value)
                } else if let error = detail.error {
                    LoadFailure(error: error) { Task { await detail.load(.shade(id: id), api: app.api) } }
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 120)
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 32)
            .frame(maxWidth: 900)
            .frame(maxWidth: .infinity)
        }
        .background(Color.board)
        .navigationTitle("")
        .toolbarTitleDisplayMode(.inline)
        .toolbar {
            if horizontalSizeClass == .regular, let shade = detail.value?.shade {
                ToolbarItem(placement: .primaryAction) {
                    Button("Add bottle", systemImage: "plus") { bottleSheet = .add(shade) }
                        .keyboardShortcut("n")
                }
            }
        }
        .revalidating(detail, .shade(id: id))
        .safariSheet($storePage)
        .sheet(item: $bottleSheet) { BottleSheet(mode: $0) }
    }

    @ViewBuilder
    private func content(_ value: ShadeDetail) -> some View {
        let shade = value.shade
        plate(value)
        actions(value)
        if !value.images.isEmpty { photos(value.images, title: shade.title) }
        if !value.bottles.isEmpty { bottles(value.bottles) }
        facts(value)
        if !value.swatchedOn.isEmpty { swatched(value.swatchedOn) }
        TipColourSection(detail: detail, value: value)
        if let store = value.storeUrl, let url = URL(string: store) {
            Button {
                storePage = url
            } label: {
                HStack {
                    Text("View at Holo Taco")
                    Spacer()
                    Image(systemName: "arrow.up.right")
                        .font(.footnote.weight(.semibold))
                }
                .foregroundStyle(Color.ink)
                .padding(.horizontal, 16)
                .frame(minHeight: 50)
                .groupCard()
            }
            .buttonStyle(.plain)
        }
    }

    // MARK: Plate

    private func plate(_ value: ShadeDetail) -> some View {
        let shade = value.shade
        return DetailPlate(shade: shade, onSale: value.onSale)
    }

    // MARK: Actions

    /// Add bottle, and the heart: on the wishlist or not.
    private func actions(_ value: ShadeDetail) -> some View {
        let wished = value.wishlist != nil
        return HStack(spacing: 12) {
            Button("Add bottle") { bottleSheet = .add(value.shade) }
                .buttonStyle(PrimaryButtonStyle())
                .accessibilityIdentifier("add-bottle")
            Button {
                Task { await toggleHeart(value) }
            } label: {
                Image(systemName: wished ? "heart.fill" : "heart")
                    .font(.title3)
                    .foregroundStyle(wished ? Color.heart : Color.ink)
                    .frame(width: 54, height: 50)
                    .background(Color.fill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(wished ? "On the wishlist, tap to remove" : "Add to the wishlist")
            .accessibilityAddTraits(wished ? .isSelected : [])
            .accessibilityIdentifier("wishlist-heart")
            .sensoryFeedback(.selection, trigger: wished)
        }
    }

    /// The heart is optimistic: it flips at once, and flips back with a status line when the
    /// server refuses.
    private func toggleHeart(_ value: ShadeDetail) async {
        guard !heartBusy else { return }
        heartBusy = true
        defer { heartBusy = false }
        let detail = detail
        let shadeID = value.shade.id
        if let entry = value.wishlist {
            await app.writes.toggle(
                lane: "wish-\(shadeID)", .removeWish(id: entry.id), affecting: .wishlistChange,
                failure: "Couldn\u{2019}t save. Still on your wishlist.",
                apply: { detail.update { $0.wishlist = nil; $0.shade.wishlisted = false } },
                revert: { detail.update { $0.wishlist = entry; $0.shade.wishlisted = true } })
        } else {
            await app.writes.toggle(
                lane: "wish-\(shadeID)", .wish(shadeID: shadeID), affecting: .wishlistChange,
                failure: "Couldn\u{2019}t save. Not on your wishlist.",
                apply: { detail.update { $0.wishlist = WishlistEntry(id: 0, priority: 2, note: nil); $0.shade.wishlisted = true } },
                revert: { detail.update { $0.wishlist = nil; $0.shade.wishlisted = false } },
                onSuccess: { item in
                    detail.update { $0.wishlist = WishlistEntry(id: item.id, priority: item.priority, note: item.note) }
                })
        }
    }

    // MARK: Photos

    private func photos(_ urls: [String], title: String) -> some View {
        ScrollView(.horizontal, showsIndicators: false) {
            LazyHStack(spacing: 12) {
                ForEach(urls, id: \.self) { url in
                    ShopPhoto(url: url)
                        .containerRelativeFrame(.horizontal) { width, _ in
                            min(width * (horizontalSizeClass == .regular ? 0.4 : 0.62), 340)
                        }
                        .aspectRatio(3 / 4, contentMode: .fit)
                        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
                        .overlay {
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .strokeBorder(Color.line, lineWidth: 1)
                        }
                        .accessibilityLabel("Photo of \(title)")
                }
            }
            .scrollTargetLayout()
            .padding(.horizontal, 16)
        }
        .scrollTargetBehavior(.viewAligned)
        .padding(.horizontal, -16)
    }

    // MARK: Bottles

    private func bottles(_ bottles: [Bottle]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: bottles.count == 1 ? "Bottle" : "Bottles")
            VStack(spacing: 0) {
                ForEach(Array(bottles.enumerated()), id: \.element.id) { index, bottle in
                    BottleRow(
                        bottle: bottle,
                        onEdit: { if let shade = detail.value?.shade { bottleSheet = .edit(bottle, shade) } },
                        onLevel: { level in Task { await setLevel(bottle, to: level) } })
                    if index < bottles.count - 1 { Divider().padding(.leading, 16) }
                }
            }
            .groupCard()
        }
    }

    private func setLevel(_ bottle: Bottle, to level: BottleState) async {
        let detail = detail
        await app.writes.changeLevel(bottle, to: level) { id, change in
            detail.update { value in
                if let index = value.bottles.firstIndex(where: { $0.id == id }) { change(&value.bottles[index]) }
            }
        }
    }

    // MARK: Facts

    private func facts(_ value: ShadeDetail) -> some View {
        let shade = value.shade
        var rows: [(String, String)] = []
        if !value.tags.finish.isEmpty { rows.append(("Finish", Words.list(value.tags.finish))) }
        if !value.tags.color.isEmpty { rows.append(("Colour", Words.list(value.tags.color))) }
        if let official = shade.officialCollection { rows.append(("Collection", official)) }
        else if !value.tags.collection.isEmpty { rows.append(("Collection", Words.list(value.tags.collection))) }
        if let released = Words.day(shade.releasedOn) { rows.append(("Released", released)) }
        if let sku = value.sku { rows.append(("SKU", sku)) }
        if shade.source == "manual" { rows.append(("Source", "Added by hand")) }
        if value.tipSource == "sampled" { rows.append(("Tip colour", "Sampled from the photo")) }
        else if value.tipSource == "override" { rows.append(("Tip colour", "Set by you")) }
        return VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "Facts")
            VStack(spacing: 0) {
                ForEach(Array(rows.enumerated()), id: \.offset) { index, row in
                    HStack(alignment: .firstTextBaseline) {
                        Text(row.0)
                            .foregroundStyle(Color.ink2)
                        Spacer(minLength: 16)
                        Text(row.1)
                            .foregroundStyle(Color.ink)
                            .multilineTextAlignment(.trailing)
                    }
                    .font(.subheadline)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 13)
                    .accessibilityElement(children: .combine)
                    if index < rows.count - 1 { Divider().padding(.leading, 16) }
                }
            }
            .groupCard()
        }
    }

    // MARK: Swatched on

    private func swatched(_ places: [SwatchedOn]) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "Swatched on")
            VStack(spacing: 0) {
                ForEach(Array(places.enumerated()), id: \.element.id) { index, place in
                    NavigationLink(value: Route.wheel(slug: place.slug, highlight: place.position)) {
                        HStack {
                            Text(place.name).foregroundStyle(Color.ink)
                            Text("slot \(place.position)").foregroundStyle(Color.ink2)
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.footnote.weight(.semibold))
                                .foregroundStyle(Color.ink3)
                        }
                        .font(.body)
                        .padding(.horizontal, 16)
                        .frame(minHeight: 50)
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    if index < places.count - 1 { Divider().padding(.leading, 16) }
                }
            }
            .groupCard()
        }
    }
}

/// The head of a shade: its lit tip-xl on the plate (Surface in light, Velvet in dark, so holo and
/// glitter have contrast) with a pool of its own colour behind it, the name in Fraunces, the price
/// and the status.
struct DetailPlate: View {
    let shade: ShadeRow
    var onSale = false
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        HStack(alignment: .center, spacing: 22) {
            TipView(shade.recipe, size: .xl, painting: .direct)
                .arrival(of: shade.id)
                .padding(.vertical, 10)
            VStack(alignment: .leading, spacing: 8) {
                Text(shade.title)
                    .displayFont(.shadeTitle)
                    .foregroundStyle(Color.ink)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                if !shade.finishLine.isEmpty {
                    Text(shade.finishLine)
                        .font(.subheadline)
                        .foregroundStyle(Color.ink)
                }
                meta
            }
            Spacer(minLength: 0)
        }
        .padding(20)
        .background {
            ZStack {
                RoundedRectangle(cornerRadius: 24, style: .continuous).fill(Color.velvet)
                RadialGradient(
                    colors: [Color(hex: shade.tip.hex).opacity(colorScheme == .dark ? 0.26 : 0.14), .clear],
                    center: UnitPoint(x: 0.22, y: 0.45), startRadius: 0, endRadius: 240
                )
                .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
            }
        }
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .strokeBorder(Color.line, lineWidth: 1)
        }
        .accessibilityElement(children: .combine)
    }

    private var meta: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(alignment: .firstTextBaseline, spacing: 10) {
                if let cents = shade.priceCents {
                    Text(Words.money(cents))
                        .font(.title3.weight(.semibold))
                        .monospacedDigit()
                        .foregroundStyle(Color.ink)
                    if onSale, let compare = shade.compareAtCents, compare > cents {
                        Text(Words.money(compare))
                            .font(.subheadline)
                            .monospacedDigit()
                            .strikethrough()
                            .foregroundStyle(Color.ink3)
                    }
                }
                if shade.ownedCount > 0 {
                    Text("Owned ×\(shade.ownedCount)")
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(Color.ink)
                }
            }
            if let word = shade.statusWord {
                Text(word)
                    .font(.subheadline)
                    .foregroundStyle(shade.status == nil ? Color.ink3 : shade.statusColor)
            }
            if shade.wishlisted {
                Label("On your wishlist", systemImage: "heart.fill")
                    .font(.subheadline)
                    .foregroundStyle(Color.heart)
            }
        }
    }
}

/// One bottle in a group: when it was bought and for how much, when it was opened, the notes; the
/// level at the trailing edge as a menu that changes it, the P code as the lightest fact. The
/// body opens the edit sheet.
struct BottleRow: View {
    let bottle: Bottle
    var onEdit: (() -> Void)?
    var onLevel: ((BottleState) -> Void)?

    var body: some View {
        HStack(alignment: .center, spacing: 12) {
            Button {
                onEdit?()
            } label: {
                info
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(onEdit == nil)
            .accessibilityElement(children: .ignore)
            .accessibilityLabel(bottle.spokenLabel)
            .accessibilityHint(onEdit == nil ? "" : "Edit this bottle")
            .accessibilityAddTraits(onEdit == nil ? [] : .isButton)
            .accessibilityIdentifier("bottle-\(bottle.id)")
            if let onLevel {
                LevelMenu(bottle: bottle, choose: onLevel)
            } else {
                LevelLabel(state: bottle.state)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 6)
        .frame(minHeight: 50)
    }

    private var info: some View {
        VStack(alignment: .leading, spacing: 3) {
            HStack(alignment: .firstTextBaseline, spacing: 8) {
                Text(bottle.factsLine)
                    .font(.subheadline)
                    .foregroundStyle(Color.ink)
                if let code = bottle.printedCode {
                    Text(code)
                        .font(.footnote)
                        .monospacedDigit()
                        .foregroundStyle(Color.ink3)
                }
            }
            if let opened = Words.day(bottle.openedOn) {
                Text("Opened \(opened)")
                    .font(.footnote)
                    .foregroundStyle(Color.ink2)
            }
            if let notes = bottle.notes {
                Text(notes)
                    .font(.footnote)
                    .foregroundStyle(Color.ink2)
                    .lineLimit(2)
            }
        }
        .padding(.vertical, 6)
    }
}

/// The level, tappable: its arc and word, and a menu of the four levels. The change is optimistic.
struct LevelMenu: View {
    let bottle: Bottle
    let choose: (BottleState) -> Void

    var body: some View {
        Menu {
            Picker("Level", selection: Binding(get: { bottle.state }, set: choose)) {
                ForEach(BottleState.allCases, id: \.self) { level in
                    Text(level.label).tag(level)
                }
            }
        } label: {
            HStack(spacing: 6) {
                LevelLabel(state: bottle.state)
                Image(systemName: "chevron.up.chevron.down")
                    .font(.caption2.weight(.semibold))
                    .foregroundStyle(Color.ink3)
                    .accessibilityHidden(true)
            }
            .frame(minHeight: 44)
            .contentShape(Rectangle())
        }
        .accessibilityLabel("Level, \(bottle.state.label)")
        .accessibilityHint("Change how much is left")
        .accessibilityIdentifier("bottle-level-\(bottle.id)")
        .sensoryFeedback(.selection, trigger: bottle.state)
    }
}
