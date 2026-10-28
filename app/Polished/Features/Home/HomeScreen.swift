import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// The shelf: greeting, Wear today, what was added lately on its ledge, the wheel, the numbers
/// (docs/NATIVE.md 5.2, 5.3).
struct HomeScreen: View {
    @Environment(AppModel.self) private var app
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @State private var home = Resource<Home>()
    @State private var me = Resource<Me>()
    /// "Another": the shade the server picked instead of today's.
    @State private var another = Resource<Wear>()
    @State private var asking = false
    @State private var anotherCount = 0
    @State private var woreCount = 0
    @State private var showsSettings = false
    @State private var showsScan = false
    @Namespace private var tips

    var body: some View {
        @Bindable var router = app.router
        NavigationStack(path: Binding(get: { app.router.path(.home) }, set: { app.router.setPath(.home, $0) })) {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if home.isOffline { OfflineLine().padding(.horizontal, -16) }
                    if let value = home.value {
                        content(value)
                    } else if let error = home.error {
                        LoadFailure(error: error) { Task { await home.load(.home(), api: app.api) } }
                    } else {
                        ProgressView().frame(maxWidth: .infinity).padding(.top, 120)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .frame(maxWidth: 1120)
                .frame(maxWidth: .infinity)
            }
            .background(Color.board)
            .scrollEdgeEffectStyle(.soft, for: .top)
            .navigationTitle("")
            .toolbarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        showsSettings = true
                    } label: {
                        Image("Mark")
                            .resizable()
                            .frame(width: 30, height: 30)
                            .clipShape(RoundedRectangle(cornerRadius: 7, style: .continuous))
                    }
                    .accessibilityLabel("Settings")
                    .accessibilityIdentifier("settings-button")
                }
            }
            .routeDestinations()
            .revalidating(home, .home())
            .task { await me.load(.me(), api: app.api) }
            // Once the server's own pick is the one she wore, "Another" has done its job.
            .onChange(of: home.value?.wear) { _, wear in
                if let wear, wear.wornToday, wear.shade.id == another.value?.shade.id { another.clear() }
            }
            .sensoryFeedback(.success, trigger: woreCount)
        }
        .environment(\.tipNamespace, tips)
        .scanCover(isPresented: $showsScan)
        .sheet(isPresented: $showsSettings) {
            NavigationStack { SettingsScreen() }
                .presentationSizing(.form)
        }
    }

    // MARK: Layout

    @ViewBuilder
    private func content(_ home: Home) -> some View {
        VStack(alignment: .leading, spacing: 28) {
            header(home)
            HStack(spacing: 10) {
                searchField(home)
                ScanButton { showsScan = true }
            }
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .top, spacing: 28) {
                    VStack(alignment: .leading, spacing: 28) {
                        wearSection(home)
                        recentSection(home)
                    }
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                    VStack(alignment: .leading, spacing: 28) {
                        wheelSection(home)
                        collectionSection(home)
                        linksSection
                    }
                    .frame(maxWidth: .infinity, alignment: .topLeading)
                }
                .frame(minWidth: 700)
                VStack(alignment: .leading, spacing: 28) {
                    wearSection(home)
                    recentSection(home)
                    wheelSection(home)
                    collectionSection(home)
                    linksSection
                }
            }
        }
        .padding(.bottom, 24)
    }

    private func header(_ home: Home) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text("\(greeting), \(home.greetingName)")
                .displayFont(.greeting)
                .foregroundStyle(Color.ink)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .accessibilityAddTraits(.isHeader)
            if let day = Words.longDay(home.date) {
                Text(day)
                    .font(.subheadline)
                    .foregroundStyle(Color.ink2)
            }
        }
    }

    /// By the hour in the household's time zone (`/me`), the phone's until that arrives.
    private var greeting: String {
        let zone = me.value.flatMap { TimeZone(identifier: $0.server.timezone) } ?? .current
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = zone
        switch calendar.component(.hour, from: Date()) {
        case 5..<12: return "Good morning"
        case 12..<18: return "Good afternoon"
        default: return "Good evening"
        }
    }

    private func searchField(_ home: Home) -> some View {
        Button {
            app.router.showShades(ShadeQuery(), focusSearch: true)
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "magnifyingglass")
                    .foregroundStyle(Color.ink2)
                Text("Search \(me.value?.server.shadeCount ?? home.counts.shades) shades")
                    .foregroundStyle(Color.ink2)
                Spacer()
            }
            .font(.body)
            .padding(.horizontal, 14)
            .frame(minHeight: 48)
            .background(Color.fill, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityIdentifier("home-search")
    }

    // MARK: Sections

    @ViewBuilder
    private func wearSection(_ home: Home) -> some View {
        let wear = another.value ?? home.wear
        VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "Wear today")
            if let wear {
                WearTodayHero(
                    wear: wear, isAsking: asking, sweepTrigger: anotherCount,
                    wore: { Task { await wore(wear) } },
                    another: { Task { await askForAnother() } })
            } else {
                EmptyState(line: "Nothing to wear yet. Add a bottle and it shows up here.")
                    .groupCard()
            }
        }
    }

    private func askForAnother() async {
        asking = true
        defer { asking = false }
        if let fresh = try? await app.api.home(another: true).wear {
            another.set(fresh)
            anotherCount += 1
        }
    }

    /// "I wore this" is optimistic: it reads "Worn today" at once, and goes back with a status
    /// line when the server refuses.
    private func wore(_ wear: Wear) async {
        let home = home
        let another = another
        let shadeID = wear.shade.id
        func mark(_ worn: Bool) {
            home.update { if $0.wear?.shade.id == shadeID { $0.wear?.wornToday = worn } }
            another.update { if $0.shade.id == shadeID { $0.wornToday = worn } }
        }
        let response = await app.writes.toggle(
            lane: "wear-\(shadeID)", .wear(shadeID: shadeID), affecting: .wear,
            failure: "Couldn\u{2019}t save. Not marked as worn.",
            apply: { mark(true) }, revert: { mark(false) })
        if response != nil { woreCount += 1 }
    }

    @ViewBuilder
    private func recentSection(_ home: Home) -> some View {
        if !home.recent.isEmpty {
            VStack(alignment: .leading, spacing: 12) {
                Button {
                    app.router.tab = .bottles
                } label: {
                    SectionHeading(title: "Recently added", trailing: "All \(home.counts.bottles) bottles")
                }
                .buttonStyle(.plain)
                Rack(items: home.recent.map { Rack.Item(id: $0.shade.id, name: $0.shade.title, recipe: $0.shade.recipe) })
                    .frame(height: Rack.height(regular: horizontalSizeClass == .regular))
                    // On a phone the ledge runs edge to edge; on a regular width it stays in its column.
                    .padding(.horizontal, horizontalSizeClass == .regular ? -4 : -16)
            }
        }
    }

    @ViewBuilder
    private func wheelSection(_ home: Home) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Button {
                app.router.tab = .wheels
            } label: {
                SectionHeading(title: "Wheels", trailing: "All")
            }
            .buttonStyle(.plain)
            if let wheel = home.wheel {
                NavigationLink(value: Route.wheel(slug: wheel.slug)) {
                    HStack(spacing: 20) {
                        MiniRing(tiles: wheel.tiles, slotCount: wheel.slotCount, diameter: 132)
                        VStack(alignment: .leading, spacing: 4) {
                            Text(wheel.name)
                                .displayFont(.wheelNameCard)
                                .foregroundStyle(Color.ink)
                                .lineLimit(2)
                            Text(wheelCount(wheel))
                                .font(.subheadline)
                                .foregroundStyle(Color.ink2)
                        }
                        Spacer(minLength: 0)
                        Image(systemName: "chevron.right")
                            .font(.footnote.weight(.semibold))
                            .foregroundStyle(Color.ink3)
                    }
                    .padding(16)
                    .groupCard()
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("\(wheel.name), \(wheelCount(wheel))")
            } else {
                EmptyState(line: "No wheel yet. Make one on the Wheels tab.")
                    .groupCard()
            }
        }
    }

    private func collectionSection(_ home: Home) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            SectionHeading(title: "Collection")
            CollectionNumbers(
                bottles: home.counts.bottles, shades: home.counts.shades, wished: home.counts.wished,
                wishedLabel: Words.money(home.counts.wishedCents))
        }
    }

    private var linksSection: some View {
        VStack(spacing: 0) {
            link("Browse all shades", ShadeQuery(), first: true)
            link("Toppers", { var query = ShadeQuery(); query.kind = "topper"; return query }())
            link("New and in stock", { var query = ShadeQuery(); query.status = "buyable"; query.sort = "newest"; return query }(), last: true)
        }
        .groupCard()
    }

    private func link(_ title: String, _ query: ShadeQuery, first: Bool = false, last: Bool = false) -> some View {
        VStack(spacing: 0) {
            Button {
                app.router.showShades(query)
            } label: {
                HStack {
                    Text(title).foregroundStyle(Color.ink)
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
            if !last { Divider().padding(.leading, 16) }
        }
    }

    private func wheelCount(_ wheel: WheelWithTiles) -> String {
        "\(wheel.filled) of \(wheel.slotCount)" + (wheel.drafts > 0 ? ", \(wheel.drafts) draft\(wheel.drafts == 1 ? "" : "s")" : "")
    }
}

/// The Wear today hero: the shade's tip-xl on its plate (Surface in light, Velvet in dark) with a
/// pool of its own colour behind it, and the one filled action.
struct WearTodayHero: View {
    let wear: Wear
    var isAsking = false
    /// Changes when "Another" brought a new shade: one band of light crosses its tip.
    var sweepTrigger = 0
    let wore: () -> Void
    let another: () -> Void
    @Environment(\.colorScheme) private var colorScheme

    var body: some View {
        HStack(alignment: .center, spacing: 20) {
            NavigationLink(value: Route.shade(wear.shade.id)) {
                TipView(wear.shade.recipe, size: .xl, painting: .direct)
                    .sweep(trigger: sweepTrigger)
                    .tipSource(wear.shade.id)
                    .padding(.vertical, 14)
                    .padding(.leading, 4)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 10) {
                NavigationLink(value: Route.shade(wear.shade.id)) {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(wear.shade.title)
                            .displayFont(.shadeTitle)
                            .foregroundStyle(Color.ink)
                            .fixedSize(horizontal: false, vertical: true)
                            .multilineTextAlignment(.leading)
                        if !wear.shade.finishLine.isEmpty {
                            Text(wear.shade.finishLine)
                                .font(.subheadline)
                                .foregroundStyle(Color.ink)
                                .multilineTextAlignment(.leading)
                        }
                        Text(detail)
                            .font(.footnote)
                            .foregroundStyle(Color.ink2)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Wear today: \(wear.shade.title), \(wear.shade.finishLine), \(detail)")
                HStack(spacing: 10) {
                    if wear.wornToday {
                        Label("Worn today", systemImage: "checkmark")
                            .font(.subheadline.weight(.semibold))
                            .foregroundStyle(Color.ok)
                            .accessibilityIdentifier("worn-today")
                    } else {
                        Button("I wore this", action: wore)
                            .buttonStyle(CompactPrimaryButtonStyle())
                            .accessibilityIdentifier("wore-button")
                    }
                    Button(action: another) {
                        Label("Another", systemImage: "arrow.triangle.2.circlepath")
                    }
                    .buttonStyle(CompactButtonStyle())
                    .opacity(isAsking ? 0.5 : 1)
                    .disabled(isAsking)
                    .accessibilityIdentifier("another-button")
                }
                .padding(.top, 4)
            }
        }
        .padding(16)
        .background {
            ZStack {
                RoundedRectangle(cornerRadius: 22, style: .continuous).fill(Color.velvet)
                // A pool of the tip's own colour behind it: the plate is lit, not flat.
                RadialGradient(
                    colors: [Color(hex: wear.shade.tip.hex).opacity(colorScheme == .dark ? 0.24 : 0.13), .clear],
                    center: UnitPoint(x: 0.18, y: 0.5), startRadius: 0, endRadius: 230
                )
                .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
            }
        }
        .overlay {
            RoundedRectangle(cornerRadius: 22, style: .continuous)
                .strokeBorder(Color.line, lineWidth: 1)
        }
    }

    private var detail: String {
        wear.bottle.state.leftLabel
    }
}

struct CollectionNumbers: View {
    let bottles: Int
    let shades: Int
    let wished: Int
    let wishedLabel: String

    var body: some View {
        HStack(alignment: .top, spacing: 0) {
            figure(bottles, bottles == 1 ? "bottle" : "bottles")
            figure(shades, shades == 1 ? "shade" : "shades")
            figure(wished, "wished, \(wishedLabel)")
        }
        .padding(.vertical, 16)
        .groupCard()
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(bottles) bottles, \(shades) shades, \(wished) wished, \(wishedLabel)")
    }

    private func figure(_ value: Int, _ label: String) -> some View {
        VStack(spacing: 2) {
            DisplayNumber(value: value, role: .collectionNumber)
                .foregroundStyle(Color.ink)
            Text(label)
                .font(.footnote)
                .foregroundStyle(Color.ink2)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
    }
}
