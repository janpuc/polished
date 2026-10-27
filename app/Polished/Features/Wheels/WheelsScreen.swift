import NailTips
import PolishedAPI
import PolishedModels
import PolishedStore
import SwiftUI

/// Wheels: a card per wheel with its ring, the count and the drafts. A phone pushes the wheel; a
/// regular width shows it beside the list.
struct WheelsTab: View {
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass
    @Environment(AppModel.self) private var app
    @Namespace private var tips

    var body: some View {
        Group {
            if horizontalSizeClass == .regular {
                WheelsSplit()
            } else {
                NavigationStack(path: Binding(get: { app.router.path(.wheels) }, set: { app.router.setPath(.wheels, $0) })) {
                    WheelsListScreen(selection: nil)
                        .routeDestinations()
                }
            }
        }
        .environment(\.tipNamespace, tips)
    }
}

private struct WheelsSplit: View {
    @Environment(AppModel.self) private var app
    @State private var detailPath: [Route] = []

    var body: some View {
        let selection = Binding<Route?>(
            get: { app.router.path(.wheels).first },
            set: { app.router.setPath(.wheels, $0.map { [$0] } ?? []) })
        NavigationSplitView {
            WheelsListScreen(selection: selection)
                .navigationSplitViewColumnWidth(min: 320, ideal: 380, max: 420)
        } detail: {
            NavigationStack(path: $detailPath) {
                if case .wheel(let slug, let highlight)? = selection.wrappedValue {
                    WheelScreen(slug: slug, highlight: highlight).id(slug)
                } else {
                    SplitPlaceholder(line: "Pick a wheel")
                }
            }
            .routeDestinations()
            .onChange(of: selection.wrappedValue) { detailPath = [] }
        }
    }
}

struct WheelsListScreen: View {
    let selection: Binding<Route?>?
    @Environment(AppModel.self) private var app
    @State private var wheels = Resource<Wheels>()
    @State private var archived = Resource<Wheels>()
    @State private var showsArchived = false
    @State private var showsNewWheel = false

    var body: some View {
        content
            .scrollContentBackground(.hidden)
            .background(Color.board)
            .navigationTitle("Wheels")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("New wheel", systemImage: "plus") { showsNewWheel = true }
                        .accessibilityIdentifier("new-wheel")
                }
            }
            .sheet(isPresented: $showsNewWheel) {
                NewWheelSheet { wheel in app.router.open(.wheel(slug: wheel.slug)) }
            }
            .revalidating(wheels, .wheels())
            .task(id: showsArchived) {
                if showsArchived { await archived.load(.wheels(archived: true), api: app.api) }
            }
    }

    @ViewBuilder
    private var content: some View {
        if let selection {
            List(selection: selection) { rows }
        } else {
            List { rows }
        }
    }

    @ViewBuilder
    private var rows: some View {
        if let value = wheels.value {
            if wheels.isOffline { OfflineLine().listRowBackground(Color.clear) }
            if value.items.isEmpty {
                EmptyState(line: "No wheels yet. Make a wheel for the nail tips you swatch.", action: "Make one") {
                    showsNewWheel = true
                }
                    .listRowBackground(Color.clear)
                    .listRowSeparator(.hidden)
            } else {
                Section {
                    ForEach(value.items) { wheel in
                        WheelCard(wheel: wheel, selection: selection)
                    }
                }
            }
            Section {
                DisclosureGroup("Archived", isExpanded: $showsArchived) {
                    if let old = archived.value {
                        if old.items.isEmpty {
                            Text("Nothing archived. Their tags keep working.")
                                .font(.subheadline)
                                .foregroundStyle(Color.ink2)
                        }
                        ForEach(old.items) { wheel in WheelCard(wheel: wheel, selection: selection) }
                    } else {
                        ProgressView()
                    }
                }
                .font(.headline)
                .foregroundStyle(Color.ink)
                .listRowBackground(Color.surface)
            }
        } else if let error = wheels.error {
            LoadFailure(error: error) { Task { await wheels.load(.wheels(), api: app.api) } }
                .listRowBackground(Color.clear)
        } else {
            ProgressView().frame(maxWidth: .infinity).padding(.top, 60)
                .listRowBackground(Color.clear)
        }
    }
}

private struct WheelCard: View {
    let wheel: WheelWithTiles
    let selection: Binding<Route?>?

    var body: some View {
        NavigationLink(value: Route.wheel(slug: wheel.slug)) {
            HStack(spacing: 16) {
                MiniRing(tiles: wheel.tiles, slotCount: wheel.slotCount, diameter: 84)
                    .padding(.vertical, 6)
                VStack(alignment: .leading, spacing: 3) {
                    Text(wheel.name)
                        .displayFont(.wheelNameCard)
                        .foregroundStyle(Color.ink)
                        .lineLimit(2)
                    Text(count)
                        .font(.subheadline)
                        .foregroundStyle(Color.ink2)
                }
            }
            .accessibilityElement(children: .ignore)
            .accessibilityLabel("\(wheel.name), \(count)")
        }
        .rowSurface(.wheel(slug: wheel.slug), selection: selection)
        .accessibilityIdentifier("wheel-card-\(wheel.slug)")
    }

    private var count: String {
        "\(wheel.filled) of \(wheel.slotCount)" + (wheel.drafts > 0 ? ", \(wheel.drafts) draft\(wheel.drafts == 1 ? "" : "s")" : "")
    }
}
